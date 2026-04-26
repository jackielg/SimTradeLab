# -*- coding: utf-8 -*-
"""
趋势跟踪新策略 (trends_up_new)
优化版本: S2终版 (2026-04-13)
核心: 统一60m止损, 取消固定止盈+移动止盈(回撤15%), 只买S级, 按模式差异化仓位
"""

import pickle
import datetime
import math
import pandas as pd
import numpy as np


# ==========================================
# 1. ConfigManager: 精简配置中心（optimize_14 全面重构）
# ==========================================
class ConfigManager:
    """
    统一管理策略的所有超参数、过滤阈值和功能开关

    optimize_14重构: 从288行精简到~120行，删除所有死配置项
    """

    # 基础配置
    MAX_POSITIONS = 5  # 持仓上限
    BENCHMARK_INDEX = "000300.SS"  # 沪深300作为大盘感知指标
    BUY_TIME = (14, 30)  # 主力买入时间 14:30

    # 选股漏斗阈值
    FILTER_CAPITAL = {
        "MIN_TOTAL_CAPITAL": 30e8,  # 总市值 > 30亿
        "MAX_TOTAL_CAPITAL": 200e8,  # 总市值 < 200亿
        "MAX_FLOAT_CAPITAL": 80e8,  # 流通市值 < 80亿
        "MAX_PRICE": 80.0,  # 股价 < 80元
        "MIN_TURNOVER": 30e6,  # 最小成交额 3000万
    }

    # 买入价格限制配置（放宽日内涨幅限制）
    BUY_PRICE_LIMIT = {
        "MAX_INTRADAY_RISE": 0.05,
        "WARN_DAY_CHANGE": 0.05,  # 从0.02提高到0.05
        "MAX_DAY_CHANGE": 0.03,
        "GRADE_MAX_CHANGE": {
            "S": 0.15,  # 从0.10→0.15（允许涨停板附近买入）
            "A": 0.10,  # 从0.08→0.10
            "B": 0.08,  # 从0.05→0.08
            "C": 0.02,
        },
    }

    # 均线参数
    MA_PERIODS = {
        "SHORT": 10,  # 短期均线
        "MID": 30,  # 中期均线
        "LONG": 60,  # 长期均线
    }

    # 突破阈值（新增ALLOW_2_OF_4模式）
    BREAKOUT = {
        "LOOKBACK_DAYS": 20,
        "VOL_MULTIPLIER": 2.0,
        "VOL_MULTIPLIER_WEAK": 0.8,
        "VOL_MULTIPLIER_STRONG": 1.5,
        "MA_CONVERGENCE": 0.07,
        "MACD_ZERO_AXIS_LIMIT": 2.0,
        "MACD_OPTIONAL_MODE": True,
        "ALLOW_3_OF_4": True,
        "ALLOW_2_OF_4": True,  # 🆕 新增：允许2/4条件通过即为B级
        "MIN_CONDITIONS_FOR_B": 2,  # 🆕 新增：B级最低条件数
    }

    # 数据缓存配置
    CACHE_FILE = "data_cache_trends_up_new.pkl"

    # 打分权重（四维打分系统）
    SCORING_WEIGHTS = {
        "MA_CONVERGENCE": 0.30,
        "BREAKOUT_RATIO": 0.25,
        "VOLUME_RATIO": 0.25,
        "MACD_STRENGTH": 0.20,
    }

    SCORING_TOP_K_MIN = 3

    # 持仓轮换
    ROTATE_ENABLED = True
    ROTATE_SCORE_THRESHOLD = 1.0

    # 市值估算配置（降级场景使用）
    CAPITAL_ESTIMATION = {
        "TURNOVER_LOW": 0.02,
        "TURNOVER_HIGH": 0.08,
    }

    # 🆕 MA20跟踪止损参数（替代复杂的ATR吊灯系统）
    SIMPLE_STOP = {
        "MA_PERIOD": 20,  # MA20均线周期
        "MAX_DRAWDOWN_FROM_PEAK": 0.20,  # 峰值回撤>20%强制卖出
        "PROFIT_LOCK_THRESHOLD": 0.03,  # 盈利>3%后启用成本价锁定
        "PROFIT_LOCK_RATIO": 0.50,  # 锁定50%浮盈（保本+2%）
    }

    # 🆕 简单三档止盈参数（替代复杂的多层次止盈）
    SIMPLE_TAKE_PROFIT = {
        "L1": {"PROFIT_MIN": 0.20, "SELL_RATIO": 0.30},  # 盈利20%卖30%
        "L2": {"PROFIT_MIN": 0.40, "SELL_RATIO": 0.30},  # 盈利40%再卖30%（累计60%）
        # L3: 盈利>40%不卖，等待MA20止损
    }

    # S2终版: 统一60m止盈止损 + 取消固定止盈 + 移动止盈安全网
    DUAL_MODE_PARAMS = {
        "sideways": {
            "STOP_MA_PERIOD": 120,
            "STOP_DATA_FREQUENCY": "daily",
            "TAKE_PROFIT_L1": 9.99,
            "TAKE_PROFIT_L2": 9.99,
            "MAX_POSITIONS_DAILY": 6,
            "MIN_SCORE_B": 0.20,
            "MORNING_ENTRY_ENABLED": True,
            "CONFIRM_STOP_BARS": 5,
        },
        "trending_uptrend": {
            "STOP_MA_PERIOD": 120,
            "STOP_DATA_FREQUENCY": "daily",
            "TAKE_PROFIT_L1": 9.99,
            "TAKE_PROFIT_L2": 9.99,
            "MAX_POSITIONS_DAILY": 6,
            "MIN_SCORE_B": 0.20,
            "MORNING_ENTRY_ENABLED": True,
            "CONFIRM_STOP_BARS": 5,
        },
        "trending_downtrend": {
            "STOP_MA_PERIOD": 120,
            "STOP_DATA_FREQUENCY": "daily",
            "TAKE_PROFIT_L1": 0.10,
            "TAKE_PROFIT_L2": 0.20,
            "MAX_POSITIONS_DAILY": 6,
            "MIN_SCORE_B": 0.30,
            "MORNING_ENTRY_ENABLED": True,
            "CONFIRM_STOP_BARS": 3,
        },
    }


# ==========================================
# 2. Common: 通用工具类
# ==========================================
class Common:
    """提供全局通用的静态工具方法"""

    @staticmethod
    def get_log_path(filename):
        """获取日志/数据文件路径"""
        if "get_research_path" in globals():
            try:
                base_path = str(get_research_path())
                if base_path and not base_path.endswith("/"):
                    base_path += "/"
                return f"{base_path}logs/{filename}"
            except Exception:
                pass
        return f"logs/{filename}"

    @staticmethod
    def safe_read_file(filename):
        file_path = Common.get_log_path(filename)
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            try:
                with open(filename, "rb") as f:
                    return f.read()
            except FileNotFoundError:
                return None

    @staticmethod
    def safe_write_file(filename, content):
        file_path = Common.get_log_path(filename)
        mode = "wb" if isinstance(content, bytes) else "w"
        kwargs = {} if isinstance(content, bytes) else {"encoding": "utf-8-sig"}
        try:
            with open(file_path, mode, **kwargs) as f:
                f.write(content)
        except Exception as e:
            try:
                with open(filename, mode, **kwargs) as f:
                    f.write(content)
            except Exception:
                pass


# ==========================================
# 3. DataCache: 数据缓存机制与接口封装
# ==========================================
class DataCache:
    """数据缓存类，负责管理本地 pkl 缓存以及统一 PTrade 的获取历史数据接口"""

    _cache = {}
    _current_cache_date = ""

    @staticmethod
    def load_pkl_cache():
        try:
            content = Common.safe_read_file(ConfigManager.CACHE_FILE)
            if content:
                DataCache._cache = pickle.loads(content)
                log.info("成功加载日线数据 pkl 缓存。")
            else:
                log.info("pkl 缓存文件为空或不存在，将重新获取。")
        except Exception as e:
            log.warning(f"加载 pkl 缓存失败: {e}")
            DataCache._cache = {}

    @staticmethod
    def save_pkl_cache():
        if not DataCache._cache:
            return
        try:
            content = pickle.dumps(DataCache._cache)
            Common.safe_write_file(ConfigManager.CACHE_FILE, content)
            log.debug("成功保存日线数据 pkl 缓存。")
        except Exception as e:
            log.error(f"保存 pkl 缓存失败: {e}")

    @staticmethod
    def clear_old_cache(current_date_str):
        """清理旧日期的缓存，防止内存无限增长"""
        if DataCache._current_cache_date != current_date_str:
            old_count = len(DataCache._cache)
            DataCache._cache = {}
            DataCache._current_cache_date = current_date_str
            if old_count > 0:
                log.debug("[内存优化] 清理旧缓存，释放 %d 个条目" % old_count)

    @staticmethod
    def get_daily_data(stock, count):
        """获取日线数据，支持 pkl 缓存"""
        today_str = g.current_date_str if hasattr(g, "current_date_str") else ""
        cache_key = f"{stock}_{count}_False_{today_str}"

        if cache_key in DataCache._cache:
            return DataCache._cache[cache_key]

        data = get_history(
            count=count,
            frequency="1d",
            field=["open", "high", "low", "close", "volume", "money"],
            security_list=[stock],
            fq="dypre",
            is_dict=True,
            include=False,
        )
        if data and stock in data:
            stock_data = data[stock]
            if isinstance(stock_data, np.ndarray):
                stock_data = pd.DataFrame(stock_data)
            if not stock_data.empty:
                DataCache._cache[cache_key] = stock_data
                return stock_data
        return pd.DataFrame()

    @staticmethod
    def get_daily_data_from_parquet(stock, count, data_dir=None):
        """从本地 parquet 文件读取日线数据（用于指数等静态数据）"""
        from pathlib import Path as _Path

        if data_dir is None:
            data_dir = _Path(
                r"C:\Users\Admin\SynologyDrive\PtradeProjects\SimTradeLab\data\cn\stocks"
            )

        parquet_path = _Path(data_dir) / f"{stock}.parquet"
        if not parquet_path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(parquet_path)
            if df.empty:
                return pd.DataFrame()

            today_str = getattr(g, "current_date_str", None)
            if today_str and "date" in df.columns:
                df = df[df["date"] <= today_str]

            if "amount" in df.columns and "money" not in df.columns:
                df["money"] = df["amount"]

            result = df.tail(count).copy()
            result.reset_index(drop=True, inplace=True)
            return result

        except Exception:
            return pd.DataFrame()

    @staticmethod
    def preload_daily_data(stock_list, count):
        """批量预加载数据到缓存，显著提升性能"""
        today_str = g.current_date_str if hasattr(g, "current_date_str") else ""
        stocks_to_fetch = []
        for stock in stock_list:
            cache_key = f"{stock}_{count}_False_{today_str}"
            if cache_key not in DataCache._cache:
                stocks_to_fetch.append(stock)

        if not stocks_to_fetch:
            return

        batch_size = 100
        for i in range(0, len(stocks_to_fetch), batch_size):
            batch = stocks_to_fetch[i : i + batch_size]
            data = get_history(
                count=count,
                frequency="1d",
                field=["open", "high", "low", "close", "volume", "money"],
                security_list=batch,
                fq="dypre",
                is_dict=True,
                include=False,
            )
            if data:
                for stock in batch:
                    if stock in data:
                        stock_data = data[stock]
                        if isinstance(stock_data, np.ndarray):
                            stock_data = pd.DataFrame(stock_data)
                        if not stock_data.empty:
                            DataCache._cache[f"{stock}_{count}_False_{today_str}"] = (
                                stock_data
                            )

    @staticmethod
    def get_5m_data(stock, count):
        """获取 5分钟级别高频数据"""
        data = get_history(
            count=count,
            frequency="5m",
            field=["open", "high", "low", "close", "volume", "money"],
            security_list=[stock],
            fq=None,
            is_dict=True,
            include=False,
        )
        if data and stock in data:
            stock_data = data[stock]
            if isinstance(stock_data, np.ndarray):
                stock_data = pd.DataFrame(stock_data)
            if not stock_data.empty:
                return stock_data
        return pd.DataFrame()

    @staticmethod
    def get_15m_data(stock, count=480):
        """
        获取15分钟K线数据（带三层降级方案 + 动态前复权）

        降级逻辑（按优先级）：
        1. 从本地parquet文件读取（stocks_15m/目录）
        2. 从5分钟数据实时聚合 + 前复权处理（stocks_5m/ → 聚合为15分钟）
        3. 返回空DataFrame（策略跳过该股票的风控检查）

        前复权说明：5m数据是不复权的，聚合时必须做动态前复权以与日线数据保持一致
        公式：前复权价 = adj_a * 未复权价 + adj_b
        """
        from pathlib import Path as _Path

        _exrights_cache = {}

        def _load_exrights(sym):
            if sym in _exrights_cache:
                return _exrights_cache[sym]
            ep = (
                _Path(
                    r"C:\Users\Admin\SynologyDrive\PtradeProjects\SimTradeLab\data\cn\exrights"
                )
                / f"{sym}.parquet"
            )
            if not ep.exists():
                _exrights_cache[sym] = None
                return None
            try:
                df = pd.read_parquet(ep)
                _exrights_cache[sym] = df.sort_values("date") if len(df) > 0 else None
                return _exrights_cache[sym]
            except Exception:
                _exrights_cache[sym] = None
                return None

        def _get_adj_factor(ex_df, dt_val):
            if ex_df is None or ex_df.empty:
                return 1.0, 0.0
            try:
                ex_dates = pd.to_datetime(ex_df["date"].astype(str).values)
                ef_a = ex_df["exer_forward_a"].values
                ef_b = ex_df["exer_forward_b"].values
                n = len(ex_dates)
                fa = np.ones(n + 1, dtype="float64")
                fb = np.zeros(n + 1, dtype="float64")
                fa[:n] = ef_a
                fb[:n] = ef_b
                target = (
                    dt_val if isinstance(dt_val, pd.Timestamp) else pd.Timestamp(dt_val)
                )
                idx = int(np.searchsorted(ex_dates, target, side="right"))
                return float(fa[idx]), float(fb[idx])
            except Exception:
                return 1.0, 0.0

        # 方案A: 从本地parquet读取（跳过：数据未复权，与日线不一致）
        # 改用方案B（5m聚合+动态前复权）确保与日线数据一致
        # parquet_path = (
        #     _Path(
        #         r"C:\Users\Admin\SynologyDrive\PtradeProjects\SimTradeLab\data\cn\stocks_15m"
        #     )
        #     / f"{stock}.parquet"
        # )
        #
        # if parquet_path.exists():
        #     try:
        #         df = pd.read_parquet(parquet_path)
        #         if not df.empty and len(df) >= count:
        #             return df.tail(count).reset_index(drop=True)
        #     except Exception as e:
        #         log.debug(f"[15m-降级A] {stock} 本地读取失败: {e}")

        # 方案B: 从5分钟数据实时聚合 + 前复权（备用）
        df_5m = DataCache.get_5m_data(stock, count * 3)
        if df_5m is not None and len(df_5m) >= 3:
            n_groups = len(df_5m) // 3
            df_5m = df_5m.iloc[-(n_groups * 3) :]
            ex_df = _load_exrights(stock)
            rows = []
            for i in range(n_groups):
                start = i * 3
                end = start + 3
                grp = df_5m.iloc[start:end]
                bar_time = (
                    grp.index[-1]
                    if hasattr(grp.index, "__getitem__")
                    else grp.iloc[-1].name
                )
                adj_a, adj_b = _get_adj_factor(ex_df, bar_time)
                rows.append(
                    {
                        "open": float(grp["open"].iloc[0]) * adj_a + adj_b,
                        "high": float(grp["high"].max()) * adj_a + adj_b,
                        "low": float(grp["low"].min()) * adj_a + adj_b,
                        "close": float(grp["close"].iloc[-1]) * adj_a + adj_b,
                        "volume": float(grp["volume"].sum()),
                        "money": (
                            float(grp["money"].sum()) * adj_a
                            if "money" in grp.columns
                            else 0.0
                        ),
                    }
                )
            log.info(f"[15m-降级B+前复权] {stock} 使用5分钟数据聚合")
            return pd.DataFrame(rows)

        # 方案C: 返回空DataFrame（优雅降级）
        log.warning(f"[15m-降级C] {stock} 数据不可用，跳过风控检查")
        return pd.DataFrame()


# ==========================================
# 4. SelectionAgent: 选股漏斗与形态识别
# ==========================================
class SelectionAgent:
    """
    选股漏斗和买前过滤

    - build_watchlist: 构建观察池，执行基础过滤 + 数据预加载
    - select: 形态识别和综合打分（支持分级准入 S/A/B级）
    - detect_morning_gap_up: 早盘跳空突破检测（可选保留）
    """

    @staticmethod
    def build_watchlist(context):
        """
        构建观察池：完整输出 Step 1~7 带 emoji 的日志，执行基础过滤。
        结果保存在 g.long_term_candidates
        """
        log.info("[盘前预筛选] 开始长期趋势筛选...")
        candidates = get_Ashares()
        if not candidates:
            log.error("初始股票池为空，跳过筛选")
            g.long_term_candidates = []
            return

        log.info(f"[盘前筛选] 1️⃣ Step1 - 股票池初始化: 待处理股票 {len(candidates)} 只")

        # Step2: 异常股过滤（停牌/退市/北交所/科创板，保留ST）
        step2_candidates = [
            stock
            for stock in candidates
            if not (
                stock.startswith("688")
                or stock.startswith("8")
                or stock.startswith("43")
            )
        ]

        log.info(
            f"[盘前筛选] 2️⃣ Step2 - 异常股过滤（科创/北交等）: 待处理股票 {len(step2_candidates)} 只"
        )

        # 数据预加载优化
        preload_start = datetime.datetime.now()
        log.info(
            f"[数据预加载] 开始批量加载 {len(step2_candidates)} 只股票的65日数据..."
        )
        DataCache.preload_daily_data(step2_candidates, 65)
        preload_elapsed = (datetime.datetime.now() - preload_start).total_seconds()
        log.info(f"[数据预加载] 完成，耗时 {preload_elapsed:.1f}秒")

        # Step3: 财务过滤（市值约束）- 分位数动态过滤版 V4
        step3_candidates, step3_fallback_count, step3_stats = (
            SelectionAgent._filter_by_market_cap(step2_candidates)
        )

        log.info(
            f"[盘前筛选] 3️⃣ Step3 - 财务过滤（市值约束）: 待处理股票 {len(step3_candidates)} 只"
        )

        # Step4: 股价预过滤
        step4_candidates = SelectionAgent._filter_by_price(step3_candidates)

        log.info(
            f"[盘前筛选] 4️⃣ Step4 - 股价预过滤: 待处理股票 {len(step4_candidates)} 只"
        )

        # Step5: 趋势初筛增强
        step5_candidates = SelectionAgent._filter_by_trend(step4_candidates)

        log.info(
            f"[盘前筛选] 5️⃣ Step5 - 技术面初筛（多条件趋势确认）: 待处理股票 {len(step5_candidates)} 只"
        )
        log.info(
            f"[盘前筛选] 6️⃣ Step6 - 月线趋势确认: 待处理股票 {len(step5_candidates)} 只"
        )
        log.info(
            f"[盘前筛选] 7️⃣ Step7 - 预选池最终确认: 最终股票 {len(step5_candidates)} 只"
        )

        g.long_term_candidates = step5_candidates

    @staticmethod
    def _filter_by_market_cap(step2_candidates):
        """Step3: 财务过滤（市值约束）"""
        step3_candidates = []
        step3_fallback_count = 0
        step3_stats = {
            "total_checked": 0,
            "filtered_percentile": 0,
            "filtered_absolute": 0,
            "filtered_money": 0,
            "filtered_turnover": 0,
            "fallback_used": 0,
        }

        stock_cap_data = []
        batch_size = 100
        daily_data_cache = {}

        log.info(f"[Step3] 开始批量获取股本数据，批量大小: {batch_size}")
        total_batches = (len(step2_candidates) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(step2_candidates))
            batch_stocks = step2_candidates[start_idx:end_idx]

            try:
                if hasattr(g, "current_dt"):
                    query_date = g.current_dt.strftime("%Y%m%d")
                else:
                    query_date = datetime.datetime.now().strftime("%Y%m%d")

                fundamentals = get_fundamentals(
                    batch_stocks, "valuation", ["total_shares", "a_floats"], query_date
                )

                if fundamentals is None or fundamentals.empty:
                    log.info(
                        f"[Step3] 第 {batch_idx+1} 批获取的股本数据为空，使用回退机制"
                    )
                    for stock in batch_stocks:
                        result = SelectionAgent._fallback_cap_estimation(stock)
                        if result:
                            stock_cap_data.append(result)
                            step3_fallback_count += 1
                    continue

                for stock in batch_stocks:
                    if stock not in daily_data_cache:
                        daily_data_cache[stock] = DataCache.get_daily_data(stock, 30)

                for stock in batch_stocks:
                    df_stock = daily_data_cache[stock]
                    try:
                        use_fallback = False
                        if stock not in fundamentals.index:
                            use_fallback = True
                            step3_stats["fallback_used"] += 1
                        else:
                            row = fundamentals.loc[stock]
                            raw_total_shares = float(row["total_shares"])
                            raw_float_shares = float(row["a_floats"])

                            if df_stock.empty or len(df_stock) < 1:
                                use_fallback = True
                                step3_stats["fallback_used"] += 1
                            else:
                                close = df_stock["close"].iloc[-1]
                                if close <= 0:
                                    use_fallback = True
                                    step3_stats["fallback_used"] += 1
                                else:
                                    total_cap = raw_total_shares * close
                                    float_cap = raw_float_shares * close
                                    money_val = df_stock["money"].iloc[-1]
                                    stock_cap_data.append(
                                        (stock, total_cap, float_cap, money_val)
                                    )

                        if use_fallback:
                            result = SelectionAgent._fallback_cap_estimation(
                                stock, df_stock
                            )
                            if result:
                                stock_cap_data.append(result)
                                step3_fallback_count += 1

                    except Exception as e:
                        log.debug(f"[Step3] {stock} 数据处理异常: {e}")
                        continue

            except Exception as e:
                log.debug(f"[Step3] 第 {batch_idx+1} 批批量获取异常: {e}")
                for stock in batch_stocks:
                    result = SelectionAgent._fallback_cap_estimation(stock)
                    if result:
                        stock_cap_data.append(result)
                        step3_fallback_count += 1

        # 第二阶段: 计算分位数并应用过滤
        if stock_cap_data:
            caps = [d[1] for d in stock_cap_data]
            caps.sort()
            n_caps = len(caps)

            p20_idx = int(n_caps * 0.2)
            p80_idx = int(n_caps * 0.8)
            cap_p20 = caps[p20_idx] if p20_idx < n_caps else caps[0]
            cap_p80 = caps[p80_idx] if p80_idx < n_caps else caps[-1]

            abs_min = ConfigManager.FILTER_CAPITAL["MIN_TOTAL_CAPITAL"]
            abs_max = ConfigManager.FILTER_CAPITAL["MAX_TOTAL_CAPITAL"]

            final_min = max(cap_p20, abs_min * 0.5)
            final_min_abs = min(cap_p20, abs_min)
            final_max = min(cap_p80, abs_max * 1.5)

            log.info(
                f"[盘前筛选] Step3 市值分位数: P20={cap_p20/1e8:.1f}亿, "
                f"P80={cap_p80/1e8:.1f}亿, "
                f"有效范围[{final_min/1e8:.1f},{final_max/1e8:.1f}]亿"
            )

            moneys = [d[3] for d in stock_cap_data if d[3] > 0]
            money_threshold = 0
            if moneys:
                moneys.sort()
                money_p30_idx = int(len(moneys) * 0.3)
                money_threshold = (
                    moneys[money_p30_idx] if money_p30_idx < len(moneys) else moneys[0]
                )
                log.debug("[盘前筛选] Step3 成交额P30: %.0f万" % (money_threshold/1e4))

            for stock, total_cap, float_cap, money_val in stock_cap_data:
                try:
                    step3_stats["total_checked"] += 1

                    if total_cap < final_min or total_cap > final_max:
                        step3_stats["filtered_percentile"] += 1
                        continue

                    if total_cap < final_min_abs or total_cap > abs_max * 2:
                        step3_stats["filtered_absolute"] += 1
                        continue

                    max_float = ConfigManager.FILTER_CAPITAL["MAX_FLOAT_CAPITAL"]
                    if float_cap > max_float:
                        step3_stats["filtered_absolute"] += 1
                        continue

                    min_money = max(
                        money_threshold, ConfigManager.FILTER_CAPITAL["MIN_TURNOVER"]
                    )
                    if money_val > 0 and money_val < min_money:
                        step3_stats["filtered_money"] += 1
                        continue

                    df_check = DataCache.get_daily_data(stock, 10)
                    if not df_check.empty and len(df_check) >= 5:
                        vol_today = df_check["volume"].iloc[-1]
                        vol_ma5 = df_check["volume"].rolling(5).mean().iloc[-1]
                        if vol_ma5 > 0 and (vol_today / vol_ma5) < 0.5:
                            step3_stats["filtered_turnover"] += 1
                            continue

                    step3_candidates.append(stock)
                except Exception:
                    step3_candidates.append(stock)

        log.info(
            f"[盘前筛选] Step3 诊断: 检查{step3_stats['total_checked']}只, "
            f"分位数过滤{step3_stats['filtered_percentile']}只, "
            f"绝对值过滤{step3_stats['filtered_absolute']}只, "
            f"成交额过滤{step3_stats['filtered_money']}只, "
            f"换手率过滤{step3_stats['filtered_turnover']}只, "
            f"降级使用{step3_stats['fallback_used']}只"
        )

        if step3_fallback_count > 0:
            log.info(
                f"[盘前筛选] Step3 降级提示: {step3_fallback_count} 只股票使用日线估算市值"
            )

        return step3_candidates, step3_fallback_count, step3_stats

    @staticmethod
    def _fallback_cap_estimation(stock, df_stock=None):
        """降级方案：基于成交量估算市值"""
        if df_stock is None or df_stock.empty or len(df_stock) < 5:
            df_stock = DataCache.get_daily_data(stock, 30)

        if df_stock.empty or len(df_stock) < 5:
            return None

        vol = df_stock["volume"].iloc[-1]
        money = df_stock["money"].iloc[-1]
        close = df_stock["close"].iloc[-1]
        if money <= 0 or vol <= 0 or close <= 0:
            return None

        estimated_float_mid = (
            money / ConfigManager.CAPITAL_ESTIMATION["TURNOVER_HIGH"]
            + money / ConfigManager.CAPITAL_ESTIMATION["TURNOVER_LOW"]
        ) / 2
        return (stock, estimated_float_mid, estimated_float_mid, money)

    @staticmethod
    def _filter_by_price(step3_candidates):
        """Step4: 股价预过滤"""
        step4_candidates = []
        for stock in step3_candidates:
            try:
                df = DataCache.get_daily_data(stock, 30)
                if df.empty or len(df) < 5:
                    step4_candidates.append(stock)
                    continue

                close = df["close"].iloc[-1]
                if close >= ConfigManager.FILTER_CAPITAL["MAX_PRICE"]:
                    continue

                step4_candidates.append(stock)
            except Exception:
                step4_candidates.append(stock)
        return step4_candidates

    @staticmethod
    def _filter_by_trend(step4_candidates):
        """Step5: 趋势初筛增强"""
        step5_candidates = []
        for stock in step4_candidates:
            try:
                df = DataCache.get_daily_data(stock, 65)
                if df.empty or len(df) < 20:
                    step5_candidates.append(stock)
                    continue

                if SelectionAgent.enhanced_trend_filter(df):
                    step5_candidates.append(stock)
            except Exception:
                step5_candidates.append(stock)
        return step5_candidates

    @staticmethod
    def enhanced_trend_filter(df):
        """
        增强版趋势过滤：多条件趋势确认（满足2/3即通过）

        条件：
        1. close > MA20 (原有)
        2. MA20 > MA60 (中期趋势向上)
        3. 近10日收盘价不下跌
        """
        if df.empty or len(df) < 20:
            return False

        close = df["close"].iloc[-1]
        ma20 = df["close"].rolling(20).mean().iloc[-1]

        cond1 = close > ma20

        ma60 = df["close"].rolling(60).mean().iloc[-1] if len(df) >= 60 else None
        cond2 = ma20 > ma60 if (ma60 is not None and not math.isnan(ma60)) else True

        recent_10 = df["close"].iloc[-10:]
        cond3 = (
            recent_10.iloc[-1] >= recent_10.iloc[0] if len(recent_10) >= 10 else False
        )

        pass_count = sum([cond1, cond2, cond3])
        return pass_count >= 2

    @staticmethod
    def filter_by_fundamentals_and_price(stock, df):
        """在日内或买入前进一步确认：市值和股价过滤"""
        if df.empty:
            return False
        close = df["close"].iloc[-1]
        if close > ConfigManager.FILTER_CAPITAL["MAX_PRICE"]:
            return False
        return True

    @staticmethod
    def score_breakout_stock(stock, df, volume_score_override=None):
        """
        计算股票突破信号的综合得分（四维打分系统）

        维度及权重：
        1. 均线粘合度: 30%
        2. 突破幅度: 25%
        3. 量能比: 25%
        4. MACD强度: 20%
        """
        if df.empty or len(df) < ConfigManager.MA_PERIODS["LONG"]:
            return 0.0

        close = df["close"].iloc[-1]
        vol = df["volume"].iloc[-1]

        # 1. 均线粘合度得分
        ma_short = (
            df["close"].rolling(ConfigManager.MA_PERIODS["SHORT"]).mean().iloc[-1]
        )
        ma_mid = df["close"].rolling(ConfigManager.MA_PERIODS["MID"]).mean().iloc[-1]
        ma_long = df["close"].rolling(ConfigManager.MA_PERIODS["LONG"]).mean().iloc[-1]

        mas = [ma_short, ma_mid, ma_long]
        max_ma = max(mas)
        min_ma = min(mas)

        convergence_threshold = ConfigManager.BREAKOUT["MA_CONVERGENCE"]
        score_convergence = max(
            0, 1 - (max_ma - min_ma) / min_ma / convergence_threshold
        )

        # 2. 突破幅度得分
        recent_high = (
            df["close"].iloc[-ConfigManager.BREAKOUT["LOOKBACK_DAYS"] : -1].max()
        )
        breakout_pct = (close / recent_high - 1) * 100 if recent_high > 0 else 0
        score_breakout = min(max(0, breakout_pct) * 20, 1.0)

        # 3. 量能比得分
        vol_ma5 = df["volume"].rolling(5).mean().iloc[-2]

        if volume_score_override is not None:
            score_volume = volume_score_override
        else:
            vol_multiplier = ConfigManager.BREAKOUT["VOL_MULTIPLIER"]
            if vol_ma5 > 0:
                vol_ratio = vol / vol_ma5 / vol_multiplier
                score_volume = min(vol_ratio / 3, 1.0)
            else:
                score_volume = 0.0

        # 4. MACD强度得分
        macd_tuple = get_MACD(df["close"].values, 12, 26, 9)
        if macd_tuple and len(macd_tuple) >= 3:
            macd_arr, signal_arr, _ = macd_tuple
            macd = macd_arr[-1]
            score_macd = min(abs(macd) * 2, 1.0)
        else:
            score_macd = 0.0

        # 加权综合得分
        weights = ConfigManager.SCORING_WEIGHTS
        total_score = (
            score_convergence * weights["MA_CONVERGENCE"]
            + score_breakout * weights["BREAKOUT_RATIO"]
            + score_volume * weights["VOLUME_RATIO"]
            + score_macd * weights["MACD_STRENGTH"]
        )

        return total_score

    @staticmethod
    def select(context, stock_list, available_slots=3):
        """
        选股：识别高置信度启动形态，支持分级准入（S/A/B三级）

        🆕 optimize_14 重构：
        - ALLOW_2_OF_4模式：允许2/4条件通过即为B级（原需3/4）
        - 放宽日内涨幅限制
        - MACD正轴模式：允许强势股在正轴金叉

        🆕 optimize_15 升级：
        - 集成MarketDetector动态调整MIN_SCORE_B和返回数量
        """
        scored_stocks = []
        DataCache.preload_daily_data(stock_list, ConfigManager.MA_PERIODS["LONG"] + 10)

        # 🆕 使用固定选股参数（不再依赖市场状态引擎）
        allow_2_of_4 = ConfigManager.BREAKOUT.get("ALLOW_2_OF_4", True)
        allow_3_of_4 = ConfigManager.BREAKOUT.get("ALLOW_3_OF_4", True)
        min_conditions_for_b = ConfigManager.BREAKOUT.get("MIN_CONDITIONS_FOR_B", 2)

        # 🆕 optimize_15: 集成市场模式检测，动态调整参数
        mode = MarketDetector.detect_market_mode(context)
        params = ConfigManager.DUAL_MODE_PARAMS.get(mode, {})
        min_score_b_dynamic = params.get("MIN_SCORE_B", 0.45)  # 动态B级最低分
        max_positions_daily = params.get("MAX_POSITIONS_DAILY", 6)  # 每日最大买入数

        log.info(
            f"[选股参数] 市场模式={mode}, ALLOW_2_OF_4={allow_2_of_4}, "
            f"ALLOW_3_OF_4={allow_3_of_4}, MIN_SCORE_B={min_score_b_dynamic:.2f}, "
            f"MAX_DAILY={max_positions_daily}"
        )

        for stock in stock_list:
            df = DataCache.get_daily_data(stock, ConfigManager.MA_PERIODS["LONG"] + 10)
            if df.empty or len(df) < ConfigManager.MA_PERIODS["LONG"]:
                continue

            if not SelectionAgent.filter_by_fundamentals_and_price(stock, df):
                continue

            close = df["close"].iloc[-1]
            vol = df["volume"].iloc[-1]

            # 1. 均线粘合
            ma_short = (
                df["close"].rolling(ConfigManager.MA_PERIODS["SHORT"]).mean().iloc[-1]
            )
            ma_mid = (
                df["close"].rolling(ConfigManager.MA_PERIODS["MID"]).mean().iloc[-1]
            )
            ma_long = (
                df["close"].rolling(ConfigManager.MA_PERIODS["LONG"]).mean().iloc[-1]
            )

            mas = [ma_short, ma_mid, ma_long]
            max_ma = max(mas)
            min_ma = min(mas)
            condition_ma_converge = (
                max_ma - min_ma
            ) / min_ma <= ConfigManager.BREAKOUT["MA_CONVERGENCE"]

            # 2. 突破近期高点
            recent_high = (
                df["close"].iloc[-ConfigManager.BREAKOUT["LOOKBACK_DAYS"] : -1].max()
            )
            condition_breakout = close > recent_high

            # 3. 成交量突发
            vol_ma5 = df["volume"].rolling(5).mean().iloc[-2]
            vol_strong = ConfigManager.BREAKOUT["VOL_MULTIPLIER_STRONG"]
            vol_weak = ConfigManager.BREAKOUT["VOL_MULTIPLIER_WEAK"]

            condition_volume_strong = vol >= vol_ma5 * vol_strong
            condition_volume_weak = vol >= vol_ma5 * vol_weak

            if condition_volume_strong:
                volume_score = 1.0
                condition_volume = True
            elif condition_volume_weak:
                volume_score = 0.7
                condition_volume = True
            else:
                volume_score = 0.0
                condition_volume = False

            # 4. MACD 金叉（🆕 支持可选模式 + 正轴模式）
            macd_tuple = get_MACD(df["close"].values, 12, 26, 9)
            if not macd_tuple or len(macd_tuple) < 3:
                condition_macd = False
            else:
                macd_arr, signal_arr, _ = macd_tuple
                macd = macd_arr[-1]
                signal = signal_arr[-1]
                macd_prev = macd_arr[-2]
                signal_prev = signal_arr[-2]

                macd_limit = ConfigManager.BREAKOUT["MACD_ZERO_AXIS_LIMIT"]

                # 标准金叉模式
                standard_cross = (
                    macd_prev <= signal_prev
                    and macd > signal
                    and abs(macd) < macd_limit
                )

                # 🆕 正轴强势模式：MACD在零轴上方且金叉
                positive_axis_mode = macd > 0 and signal > 0 and macd > signal

                condition_macd = standard_cross or positive_axis_mode

            # 统计满足的条件数量
            conditions_met = [
                ("ma_converge", condition_ma_converge),
                ("breakout", condition_breakout),
                ("volume", condition_volume),
                ("macd", condition_macd),
            ]
            met_count = sum(1 for _, met in conditions_met if met)

            # 🆕 分级准入判断（ALLOW_2_OF_4模式）
            grade = None
            final_score = 0.0

            if met_count == 4:
                # 四重条件全部满足 → S/A/B级
                base_score = SelectionAgent.score_breakout_stock(
                    stock, df, volume_score
                )
                if base_score > 0.75:
                    grade = "S"
                    final_score = base_score + 0.2
                elif base_score >= 0.55:
                    grade = "A"
                    final_score = base_score + 0.1
                else:
                    grade = "B"
                    final_score = base_score

            elif met_count == 3 and allow_3_of_4:
                # 3/4条件通过 → B级
                base_score = SelectionAgent.score_breakout_stock(
                    stock, df, volume_score
                )
                if base_score > min_score_b_dynamic:  # 🆕 使用动态阈值
                    grade = "B"
                    final_score = base_score

            elif met_count == 2 and allow_2_of_4:
                # 🆕 2/4条件通过 → B级（放宽选股逻辑）
                base_score = SelectionAgent.score_breakout_stock(
                    stock, df, volume_score
                )
                if base_score > (min_score_b_dynamic - 0.05):  # 🆕 使用动态阈值（略低）
                    grade = "B"
                    final_score = base_score

            if grade in ["S", "A", "B"]:
                scored_stocks.append((stock, final_score, grade))
                log.info(
                    f"[选股分级] {stock}: [{grade}级] 得分{final_score:.3f}, "
                    f"满足{met_count}/4条件"
                )

        # 按得分降序排列，返回 Top N 个结果（🆕 使用动态上限）
        scored_stocks.sort(key=lambda x: x[1], reverse=True)
        top_n = min(
            max(available_slots * 2, ConfigManager.SCORING_TOP_K_MIN),
            max_positions_daily,
        )

        return scored_stocks[:top_n]

    @staticmethod
    def detect_morning_gap_up(context):
        """
        检测早盘跳空高开突破机会（可选保留，降低资金比例到10%）
        """
        morning_targets = []
        candidates = getattr(g, "long_term_candidates", [])

        if not candidates:
            return morning_targets

        for stock in candidates[:100]:  # 限制检查数量
            try:
                df_today = DataCache.get_daily_data(stock, 5)
                if df_today.empty or len(df_today) < 2:
                    continue

                today_open = df_today["open"].iloc[-1]
                yesterday_high = df_today["high"].iloc[-2]

                if today_open <= yesterday_high:
                    continue

                gap_ratio = (today_open / yesterday_high - 1) * 100

                if gap_ratio < 0.5 or gap_ratio > 7.0:
                    continue

                df_5m = DataCache.get_5m_data(stock, 48)
                if df_5m.empty or len(df_5m) < 5:
                    continue

                early_money = (
                    df_5m["money"].iloc[-7:].sum()
                    if len(df_5m) >= 7
                    else df_5m["money"].sum()
                )
                yesterday_money = df_today["money"].iloc[-2]

                if yesterday_money > 0 and early_money > yesterday_money * 0.2:
                    volume_ratio = (
                        early_money / yesterday_money if yesterday_money > 0 else 0
                    )
                    confidence = min((gap_ratio / 3 + volume_ratio) / 2, 1.0)
                    morning_targets.append((stock, gap_ratio, confidence))

            except Exception as e:
                log.debug(f"[早盘检测] {stock} 检测异常: {e}")
                continue

        morning_targets.sort(key=lambda x: x[2], reverse=True)
        log.info(f"[早盘检测] 发现 {len(morning_targets)} 只跳空高开候选")

        return morning_targets


# ==========================================
# 5. ExecutionAgent: 订单执行
# ==========================================
class ExecutionAgent:
    """订单执行类，负责买入、卖出、轮换等操作"""

    @staticmethod
    def _get_day_change(stock):
        """获取股票当日日内涨幅"""
        try:
            df = DataCache.get_daily_data(stock, 2)
            if df.empty or len(df) < 1:
                return None
            open_price = df["open"].iloc[-1]
            close_price = df["close"].iloc[-1]
            if open_price <= 0:
                return None
            return (close_price - open_price) / open_price
        except Exception:
            return None

    @staticmethod
    def find_weakest_position(context):
        """查找当前持仓中收益最低的股票"""
        weakest_stock = None
        lowest_profit = float("inf")

        for stock, pos in context.portfolio.positions.items():
            if pos.amount <= 0:
                continue

            # 使用修正后的安全盈利计算方法
            profit_result = PositionAgent.calc_profit_ratio_safely(pos)
            if profit_result[0] is not None:
                profit_ratio = profit_result[0]
                if abs(profit_ratio) > 10:
                    continue
            else:
                continue

            if profit_ratio < lowest_profit:
                lowest_profit = profit_ratio
                weakest_stock = stock

        if weakest_stock:
            return (weakest_stock, lowest_profit)
        else:
            return (None, None)

    @staticmethod
    def buy_new(context, target_stocks):
        """
        🆕 新买入执行：双模自适应仓位分配（optimize_15 升级）

        集成 MAX_POSITIONS_DAILY 限制，根据市场模式动态控制买入数量
        """
        current_positions = [
            stock
            for stock, pos in context.portfolio.positions.items()
            if pos.amount > 0
        ]

        available_slots = ConfigManager.MAX_POSITIONS - len(current_positions)

        # 🆕 optimize_15: 集成市场模式检测，获取每日最大买入数量限制
        mode = MarketDetector.detect_market_mode(context)
        params = ConfigManager.DUAL_MODE_PARAMS.get(mode, {})
        max_daily_buys = params.get("MAX_POSITIONS_DAILY", 6)

        # 取两者中的较小值：可用槽位 vs 每日限制
        effective_slots = min(available_slots, max_daily_buys)

        cash = context.portfolio.cash
        max_pos_ratio = (
            0.98
            if mode == "trending_uptrend"
            else (0.80 if mode == "sideways" else 0.60)
        )  # 按市场模式差异化仓位(更激进)
        target_total_value = context.portfolio.portfolio_value * max_pos_ratio
        current_pos_value = context.portfolio.positions_value
        allowable_cash = max(0, target_total_value - current_pos_value)

        actual_cash_to_use = min(cash, allowable_cash)
        if actual_cash_to_use <= 10000:
            log.info("可用资金不足10000元，放弃买入。")
            return

        if effective_slots > 0:
            buy_targets = [
                (s, score, grade)
                for s, score, grade in target_stocks
                if s not in current_positions
                and grade in ("S", "A", "B")  # S级+A级+B级
            ][
                :effective_slots
            ]  # 🆕 使用动态限制

            if not buy_targets:
                log.info("无新的可买标的（全部已在持仓中或达到每日上限）。")
                return

            # 根据级别分配资金比例
            total_weight = sum(
                (3.0 if grade == "S" else 1.0)  # S级高权重
                for _, _, grade in buy_targets
            )

            for stock, score, grade in buy_targets:
                weight = 3.0 if grade == "S" else 1.0  # S级高权重
                cash_per_stock = actual_cash_to_use * (weight / total_weight)

                # 日内涨幅过滤（使用放宽后的配置）
                day_change = ExecutionAgent._get_day_change(stock)
                if day_change is not None:
                    grade_max = ConfigManager.BUY_PRICE_LIMIT["GRADE_MAX_CHANGE"].get(
                        grade, ConfigManager.BUY_PRICE_LIMIT["MAX_DAY_CHANGE"]
                    )
                    if day_change > grade_max:
                        log.info(
                            f"[买入放弃] {stock}, 日内涨幅{day_change*100:.1f}% "
                            f"超过{grade}级上限{grade_max*100:.0f}%"
                        )
                        continue
                    elif day_change > ConfigManager.BUY_PRICE_LIMIT["WARN_DAY_CHANGE"]:
                        cash_per_stock *= 0.5
                        log.info(
                            f"[买入减仓] {stock}, 日内涨幅{day_change*100:.1f}% "
                            f"超过预警线, 仓位减半至{cash_per_stock:.2f}"
                        )

                order_value(stock, cash_per_stock)
                log.info(
                    f"[买入][{grade}级] {stock}, 金额: {cash_per_stock:.2f}, 得分: {score:.3f}"
                )

                # 记录买入状态
                if not hasattr(g, "_holding_start_date"):
                    g._holding_start_date = {}
                g._holding_start_date[stock] = context.current_dt.date()

                df_buy = DataCache.get_daily_data(stock, 2)
                buy_price = (
                    df_buy["close"].iloc[-1]
                    if not df_buy.empty and len(df_buy) >= 1
                    else 0
                )
                g._buy_prices[stock] = buy_price
                g._peak_prices[stock] = buy_price

        elif available_slots == 0 and ConfigManager.ROTATE_ENABLED:
            weakest_stock, weakest_profit = ExecutionAgent.find_weakest_position(
                context
            )

            if weakest_stock is None or len(target_stocks) == 0:
                log.info("无法执行轮换（无可替换持仓或无新标的）。")
                return

            new_stock, new_score, new_grade = target_stocks[0]

            should_rotate = False
            if weakest_profit < -0.05 and new_grade in ["S", "A", "B"]:
                should_rotate = True
            elif weakest_profit < -0.03 and new_grade in ["S", "A"]:
                should_rotate = True

            log.info(
                f"[轮换评估] 最弱持仓: {weakest_stock} 收益{weakest_profit:.2%} "
                f"vs 新标的: {new_stock}[{new_grade}级] 得分{new_score:.3f} "
                f"{'-> 触发替换' if should_rotate else '-> 不替换'}"
            )

            if should_rotate:
                if not hasattr(g, "_rotation_cooldown"):
                    g._rotation_cooldown = {}
                if weakest_stock in g._rotation_cooldown:
                    log.info(f"[轮换冷却] {weakest_stock} 在冷却期内，跳过轮换")
                    return

                cash_per_stock = actual_cash_to_use / 1

                order_target(weakest_stock, 0)
                log.info(f"[轮换] 卖出 {weakest_stock} (收益{weakest_profit*100:.2f}%)")

                g._peak_prices.pop(weakest_stock, None)
                g._buy_prices.pop(weakest_stock, None)

                order_value(new_stock, cash_per_stock)
                log.info(
                    f"[轮换] 买入 {new_stock}[{new_grade}级] (得分{new_score:.3f}), 金额: {cash_per_stock:.2f}"
                )

                if not hasattr(g, "_holding_start_date"):
                    g._holding_start_date = {}
                g._holding_start_date[new_stock] = context.current_dt.date()

                df_buy = DataCache.get_daily_data(new_stock, 2)
                buy_price = (
                    df_buy["close"].iloc[-1]
                    if not df_buy.empty and len(df_buy) >= 1
                    else 0
                )
                g._buy_prices[new_stock] = buy_price
                g._peak_prices[new_stock] = buy_price

                g._rotation_cooldown[weakest_stock] = context.current_dt.date()
            else:
                log.info(
                    f"[轮换] 条件不满足（最弱持仓收益{weakest_profit*100:.2f}%，"
                    f"新标的{new_grade}级），维持原持仓"
                )
        else:
            log.info("已达到最大持仓上限且轮换未启用，放弃买入。")

    @staticmethod
    def buy_morning_entry(context, targets):
        """
        早盘入场执行（9:35窗口）
        🆕 降低资金比例到10%（原30%）
        """
        if not targets:
            return

        # 🆕 早盘入场最多使用10%总资金（从30%降低到10%）
        max_morning_cash = context.portfolio.portfolio_value * 0.10
        available_cash = min(context.portfolio.cash, max_morning_cash)

        if available_cash < 10000:
            log.info("[早盘入场] 可用资金不足，放弃早盘入场。")
            return

        current_positions = [
            stock
            for stock, pos in context.portfolio.positions.items()
            if pos.amount > 0
        ]

        max_morning_buys = min(3, ConfigManager.MAX_POSITIONS - len(current_positions))
        if max_morning_buys <= 0:
            log.info("[早盘入场] 已达到最大持仓上限，放弃早盘入场。")
            return

        buy_targets = targets[:max_morning_buys]
        cash_per_stock = available_cash / len(buy_targets)

        for stock, gap_ratio, confidence in buy_targets:
            if stock in current_positions:
                continue

            order_value(stock, cash_per_stock)
            log.info(
                f"[早盘买入] {stock}, 跳空{gap_ratio:.1f}%, 置信度{confidence:.2f}, "
                f"金额: {cash_per_stock:.2f}"
            )

            if not hasattr(g, "_holding_start_date"):
                g._holding_start_date = {}
            g._holding_start_date[stock] = context.current_dt.date()

            df_buy = DataCache.get_daily_data(stock, 2)
            buy_price = (
                df_buy["close"].iloc[-1] if not df_buy.empty and len(df_buy) >= 1 else 0
            )
            g._buy_prices[stock] = buy_price
            g._peak_prices[stock] = buy_price


# ==========================================
# 6. MarketDetector: 双模市场环境检测器（🆕 optimize_15 新增）
# ==========================================
class MarketDetector:
    """
    简化版市场环境检测（基于持仓组合表现）

    不依赖外部指数数据（因为000300.SS数据静态）
    使用当前持仓组合的平均表现作为市场冷暖代理指标
    """

    @staticmethod
    def detect_market_mode(context):
        """
        检测当前市场模式：震荡(sideways) 或 趋势(trending)

        判断依据：
        1. 持仓股票的平均盈亏分布
        2. 基于平均盈利水平分类市场状态

        返回：
        - 'sideways': 震荡市（波动率<2%，胜率<50%）
        - 'trending_uptrend': 上升趋势（波动率>2%，平均盈利>3%）
        - 'trending_downtrend': 下降趋势（波动率>2%，平均亏损>3%）
        - 'unknown': 数据不足（持仓<3只或运行<5天）
        """
        try:
            positions = context.portfolio.positions
            active_positions = {s: p for s, p in positions.items() if p.amount > 0}

            if len(active_positions) < 3:
                return "unknown"

            # 计算持仓平均盈利（使用修正后的盈利计算函数）
            total_profit = 0
            valid_count = 0
            for stock, pos in active_positions.items():
                profit_result = PositionAgent.calc_profit_ratio_safely(pos)
                if profit_result is not None and profit_result[0] is not None:
                    profit = profit_result[
                        0
                    ]  # (profit_ratio, avg_price) 元组的第一个元素
                    total_profit += profit
                    valid_count += 1

            if valid_count == 0:
                return "unknown"

            avg_profit = total_profit / valid_count

            # 简单分类逻辑
            if avg_profit > 0.03:
                return "trending_uptrend"  # 平均盈利>3% → 上升趋势
            elif avg_profit < -0.03:
                return "trending_downtrend"  # 平均亏损>3% → 下降趋势
            else:
                return "sideways"  # 盈亏在±3%之间 → 震荡市

        except Exception as e:
            log.debug(f"[市场模式检测异常] {e}")
            return "unknown"


# ==========================================
# 7. PositionAgent: MA20跟踪止损 + 简单三档止盈（optimize_14 核心重构 + optimize_15 双模升级）
# ==========================================
class PositionAgent:
    """
    盘中风控与MA20跟踪止损

    🆕 optimize_14 核心改动：
    - 删除ATR吊灯止损系统（~500行旧代码）
    - 采用MA20跟踪止损替代复杂系统
    - 简单三档止盈（L1:20%, L2:40%, L3:>40%不卖）
    - 防御性编程：安全盈利计算（解决386674%异常BUG）
    """

    @staticmethod
    def calc_profit_ratio_safely(pos):
        """
        安全盈利比例计算

        重要：Position.cost_basis 存储的是【每股成本价】（元/股），不是总成本！
        框架源码：order_processor.py:225 -> cost_basis = total_cost / amount

        返回:
            tuple: (profit_ratio, avg_price) 或 (None, None) 如果计算失败
        """
        try:
            if not hasattr(pos, "cost_basis") or pos.cost_basis <= 0:
                return None, None

            if not hasattr(pos, "amount") or pos.amount <= 0:
                return None, None

            # ✅ 正确：cost_basis 已经是每股成本价（如39.05元）
            avg_price = float(pos.cost_basis)

            # 获取当前价格（优先使用 last_sale_price，其次 price，最后用成本价兜底）
            current_price = (
                float(pos.last_sale_price)
                if hasattr(pos, "last_sale_price") and pos.last_sale_price > 0
                else (
                    float(pos.price)
                    if hasattr(pos, "price") and pos.price > 0
                    else avg_price
                )
            )

            # ✅ 正确的盈利计算：(现价 - 成本价) / 成本价
            profit_ratio = (current_price - avg_price) / avg_price

            # 边界检查：正常范围-99%~+500%（允许5倍盈利）
            if abs(profit_ratio) > 5.0:
                log.warning(f"[防御] 盈利比例异常{profit_ratio*100:.1f}%，已截断")
                profit_ratio = max(-0.99, min(5.0, profit_ratio))

            return profit_ratio, avg_price

        except (TypeError, ValueError, ZeroDivisionError) as e:
            log.debug(f"[盈利计算异常] {e}")
            return None, None

    @staticmethod
    def get_cost_price_safely(pos):
        """
        安全获取每股成本价

        注意：pos.cost_basis 已经是每股成本价（元/股），无需再除以amount！
        框架源码：order_processor.py:225 -> cost_basis = total_cost / amount
        """
        try:
            if hasattr(pos, "cost_basis") and pos.cost_basis > 0:
                return float(pos.cost_basis)  # ✅ 直接返回，无需除法
        except (TypeError, ValueError):
            pass
        return None

    @staticmethod
    def cleanup_state(stock):
        """清理全局状态字典"""
        g._peak_prices.pop(stock, None)
        g._buy_prices.pop(stock, None)
        if stock in g._warning_state:
            del g._warning_state[stock]

    @staticmethod
    def check_intraday_exit(context):
        """
        🆕 双模自适应盘中风控（optimize_15 升级）

        根据 MarketDetector.detect_market_mode() 结果选择不同参数：
        - 震荡市：日线MA20 + 2根K线确认 + 保守止盈
        - 牛市：15分钟MA20 + 立即执行 + 激进持有
        - 下降趋势：极度保守，快速止损
        """
        # 检测当前市场模式
        mode = MarketDetector.detect_market_mode(context)
        params = ConfigManager.DUAL_MODE_PARAMS.get(
            mode, ConfigManager.DUAL_MODE_PARAMS["sideways"]
        )

        current_positions = context.portfolio.positions

        for stock, pos in list(current_positions.items()):
            if pos.amount <= 0:
                continue

            # T+1限制检查
            holding_start = g._holding_start_date.get(stock, None)
            today_str = context.current_dt.strftime("%Y-%m-%d")
            if holding_start:
                holding_str = (
                    holding_start.strftime("%Y-%m-%d")
                    if hasattr(holding_start, "strftime")
                    else str(holding_start)
                )
                if holding_str == today_str:
                    continue

            # 获取K线数据（根据模式选择频率）
            freq = params["STOP_DATA_FREQUENCY"]
            if freq == "daily":
                df = DataCache.get_daily_data(stock, 60)
                ma_period = params["STOP_MA_PERIOD"]
            elif freq == "5m":
                df = DataCache.get_5m_data(stock, 120)
                ma_period = params["STOP_MA_PERIOD"]
            elif freq == "15m":
                df = DataCache.get_15m_data(stock, 120)
                ma_period = params["STOP_MA_PERIOD"]
            else:  # "30m", "60m" 等从15m聚合或默认
                df = DataCache.get_15m_data(stock, 120)
                ma_period = params["STOP_MA_PERIOD"]

            if df is None or len(df) < ma_period + 1:
                continue

            close = df["close"].iloc[-1]

            # 计算当前盈利比例（使用修正后的安全方法）
            profit_ratio, cost_price = PositionAgent.calc_profit_ratio_safely(pos)

            if profit_ratio is None:
                continue

            # 更新峰值价格
            current_high = df["high"].iloc[-1]
            if stock not in g._peak_prices:
                g._peak_prices[stock] = current_high
            else:
                g._peak_prices[stock] = max(g._peak_prices[stock], current_high)

            peak_price = g._peak_prices[stock]

            # ===== 保护机制1: 峰值回撤保护（双模参数）=====
            max_drawdown = (
                0.15
                if mode == "sideways"
                else (0.12 if mode == "trending_downtrend" else 0.20)
            )
            if profit_ratio > 0:
                drawdown_from_peak = (peak_price - close) / peak_price
                if drawdown_from_peak > max_drawdown:
                    order_target(stock, 0)
                    log.info(
                        f"[{mode}峰值回撤] {stock}, 回撤{drawdown_from_peak*100:.1f}% "
                        f">(>{max_drawdown*100:.0f}%), 现价: {close:.2f}"
                    )
                    PositionAgent.cleanup_state(stock)
                    continue

            # ===== 保护机制2: MA跟踪止损（核心！双模自适应）=====
            ma = df["close"].rolling(ma_period).mean().iloc[-1]

            if close < ma:
                # 震荡市需要确认（避免假突破）
                if mode == "sideways" and params["CONFIRM_STOP_BARS"] > 1:
                    # 检查最近N根K线是否都在MA下方
                    recent_closes = df["close"].iloc[-params["CONFIRM_STOP_BARS"] :]
                    ma_recent = (
                        df["close"]
                        .rolling(ma_period)
                        .mean()
                        .iloc[-params["CONFIRM_STOP_BARS"] :]
                    )

                    # 所有最近N根K线的收盘价都低于对应的MA值才确认止损
                    if all(
                        recent_closes.iloc[i] < ma_recent.iloc[i]
                        for i in range(len(recent_closes))
                    ):
                        order_target(stock, 0)
                        log.info(
                            f"[{mode}止损-确认] {stock}, 现价{close:.2f} < MA{ma_period}{ma:.2f}, "
                            f"盈利{profit_ratio*100:.1f}%"
                        )
                        PositionAgent.cleanup_state(stock)
                else:
                    # 牛市/下降趋势：立即止损
                    order_target(stock, 0)
                    log.info(
                        f"[{mode}止损] {stock}, 价格{close:.2f}跌破MA{ma_period}({ma:.2f}), "
                        f"盈利{profit_ratio*100:.1f}%"
                    )
                    PositionAgent.cleanup_state(stock)
                continue

            # ===== 保护机制3: 成本价锁定（双模阈值）=====
            breakeven_threshold = (
                0.02
                if mode == "sideways"
                else (0.01 if mode == "trending_downtrend" else 0.03)
            )
            buy_price = PositionAgent.get_cost_price_safely(pos)

            if (
                profit_ratio
                and profit_ratio > breakeven_threshold
                and buy_price
                and buy_price > 0
            ):
                locked_profit = (
                    profit_ratio * ConfigManager.SIMPLE_STOP["PROFIT_LOCK_RATIO"]
                )
                locked_price = buy_price * (1 + locked_profit)

                if close < locked_price and close < ma:
                    order_target(stock, 0)
                    log.info(
                        f"[保本-{mode}] {stock}, 现价{close:.2f} < 保本线{locked_price:.2f}"
                    )
                    PositionAgent.cleanup_state(stock)
                    continue

            # ===== 保护机制4: 双模自适应止盈 =====
            PositionAgent.simple_take_profit(context, stock, pos, profit_ratio, mode)

            # ===== 移动止盈（仅uptrend，盈利>20%后回撤15%触发）=====
            if mode == "trending_uptrend" and profit_ratio and profit_ratio > 0.20:
                if not hasattr(context, "_trailing_peaks"):
                    context._trailing_peaks = {}
                if close > context._trailing_peaks.get(stock, 0):
                    context._trailing_peaks[stock] = close
                peak = context._trailing_peaks.get(stock, 0)
                if peak > 0 and close < peak * (1 - 0.15):
                    order_target(stock, 0)
                    log.info(
                        f"[移动止盈] {stock}, 现价{close:.2f} < 峰值回撤线{peak*0.85:.2f}(峰值{peak:.2f}, 回撤{-((close/peak-1)*100):.1f}%)"
                    )
                    if stock in context._trailing_peaks:
                        del context._trailing_peaks[stock]
                    PositionAgent.cleanup_state(stock)
                    continue

    @staticmethod
    def simple_take_profit(context, stock, pos, profit_ratio, mode="sideways"):
        """
        🆕 双模自适应止盈（optimize_15 升级）

        震荡市：10%/20% 两档（快速锁定利润）
        牛市：25%/50% 两档（让利润奔跑）
        下降趋势：5%/10% 两档（保本为主）

        新增：最小金额检查（>=2000元才操作），避免"卖出金额不足100股"错误
        """
        # 根据市场模式获取止盈参数
        params = ConfigManager.DUAL_MODE_PARAMS.get(
            mode, ConfigManager.DUAL_MODE_PARAMS["sideways"]
        )

        config = {
            "L1": {"PROFIT": params["TAKE_PROFIT_L1"], "SELL_RATIO": 0.30},
            "L2": {"PROFIT": params["TAKE_PROFIT_L2"], "SELL_RATIO": 0.30},
        }

        try:
            # 计算当前持仓市值
            current_value = 0.0
            if hasattr(pos, "price") and pos.price > 0 and pos.amount > 0:
                current_value = float(pos.price) * float(pos.amount)
            elif hasattr(pos, "market_value"):
                current_value = float(pos.market_value)

            # 最小金额检查（避免"卖出金额不足100股"错误）
            min_sell_value = 2000  # 至少2000元才值得操作

            if current_value <= min_sell_value:
                return

            # L1止盈：第一档
            l1 = config["L1"]
            if l1["PROFIT"] <= profit_ratio < config["L2"]["PROFIT"]:
                sell_value = current_value * l1["SELL_RATIO"]
                if sell_value >= min_sell_value:
                    order_value(stock, -sell_value)
                    log.info(
                        f"[止盈-L1-{mode}] {stock}, 盈利{profit_ratio*100:.1f}%, "
                        f"卖{l1['SELL_RATIO']*100:.0f}%(金额{sell_value:.0f})"
                    )
                else:
                    log.debug(
                        f"[止盈跳过] {stock}, 金额{sell_value:.0f}<{min_sell_value}"
                    )
                return

            # L2止盈：第二档
            elif profit_ratio >= config["L2"]["PROFIT"]:
                sell_value = current_value * config["L2"]["SELL_RATIO"]
                if sell_value >= min_sell_value:
                    order_value(stock, -sell_value)
                    log.info(
                        f"[止盈-L2-{mode}] {stock}, 盈利{profit_ratio*100:.1f}%, "
                        f"再卖{config['L2']['SELL_RATIO']*100:.0f}%(金额{sell_value:.0f})"
                    )
                else:
                    log.debug(
                        f"[止盈跳过] {stock}, 金额{sell_value:.0f}<{min_sell_value}"
                    )
                # L3: 不再卖出，等待MA止损

        except Exception as e:
            log.debug(f"[双模止盈] {stock} 执行异常: {e}")


# ==========================================
# 7. 全局生命周期函数 (PTrade 接口)
# ==========================================


def initialize(context):
    """
    S2终版初始化

    核心配置:
    - 统一60m止损频率
    - 取消固定止盈(L1/L2=999%) + 移动止盈(回撤15%)
    - 只买入S级股票，S级权重3x
    - 按模式差异化仓位: sideways=50%, uptrend=95%, downtrend=30%
    """
    g.security = ConfigManager.BENCHMARK_INDEX
    set_universe(g.security)

    # 基础全局变量
    g.long_term_candidates = []
    g.current_date_str = ""
    g._warning_state = {}  # 预警节流状态

    # 止损相关状态（精简版）
    g._peak_prices = {}  # 持仓期间峰值价格
    g._buy_prices = {}  # 买入价格记录

    g._holding_start_date = {}  # 持仓起始日期
    g._bar_count = 0  # K线计数器

    # 尝试加载缓存
    DataCache.load_pkl_cache()

    log.info("策略 trends_up_new (S2终版) 初始化完成。")


def before_trading_start(context, data):
    """
    开盘前准备（optimize_14 精简版）

    功能：
    - 更新日期字符串
    - 内存优化：清理旧缓存
    - 🆕 删除市场状态引擎调用（MarketAgent.analyze_market已删除）
    """
    g.current_date_str = context.current_dt.strftime("%Y-%m-%d")

    DataCache.clear_old_cache(g.current_date_str)

    log.debug("今日日期: %s" % g.current_date_str)


def handle_data(context, data):
    """
    盘中逻辑（optimize_14 精简版）

    时间节点：
    - 09:35: 早盘入场分支（降低优先级）
    - 09:35~14:55: 15分钟截流，MA20跟踪止损
    - 14:30: 主力入场分支（四重条件选股 + 买入）

    🆕 主要变更：
    - 删除RiskManager.check_daily_loss_limit/check_drawdown_limit调用
    - 删除14:25止盈检查（整合到PositionAgent.check_intraday_exit中）
    - 简化风控调用（只调用PositionAgent.check_intraday_exit）
    """
    dt = context.current_dt
    h, m = dt.hour, dt.minute

    # 更新K线计数器
    g._bar_count = getattr(g, "_bar_count", 0) + 1

    # 5分钟截流
    if m % 5 != 0:
        return

    # 1. 9:35 早盘入场分支（🆕 optimize_15: 双模动态开关）
    if h == 9 and m == 35:
        # 🆕 检测市场模式，决定是否启用早盘入场
        mode = MarketDetector.detect_market_mode(context)
        params = ConfigManager.DUAL_MODE_PARAMS.get(mode, {})

        if params.get("MORNING_ENTRY_ENABLED", True):
            log.info(f"触发 9:35 早盘入场逻辑 (市场模式={mode})")
            morning_targets = SelectionAgent.detect_morning_gap_up(context)
            if morning_targets:
                log.info(
                    f"[早盘入场] 发现 {len(morning_targets)} 只跳空候选: "
                    f"{[t[0] for t in morning_targets]}"
                )
                ExecutionAgent.buy_morning_entry(context, morning_targets)
            else:
                log.info("[早盘入场] 未发现符合条件的跳空高开股票")
        else:
            log.debug(f"[早盘跳过] 当前模式={mode}, 早盘入场已禁用")

    # 2. 盘中风控 (每15分钟执行一次MA20跟踪止损检查)
    if m % 15 == 0 and (
        (h == 9 and m >= 30) or (h >= 10 and h < 14) or (h == 14 and m <= 30)
    ):
        PositionAgent.check_intraday_exit(context)

    # 3. 14:30 主力入场（保持不变，作为主力入口）
    if h == ConfigManager.BUY_TIME[0] and m == ConfigManager.BUY_TIME[1]:
        log.info("触发 14:30 选股与买入逻辑")

        # 3a. 实时选股预过滤 (Step1~7)
        SelectionAgent.build_watchlist(context)

        # 3b. 统一买入候选
        all_buy_candidates = []

        if g.long_term_candidates:
            current_positions = [
                stock
                for stock, pos in context.portfolio.positions.items()
                if pos.amount > 0
            ]
            available_slots = max(
                0, ConfigManager.MAX_POSITIONS - len(current_positions)
            )

            # 传统四重条件选股
            buy_list = SelectionAgent.select(
                context, g.long_term_candidates, available_slots=available_slots
            )

            if buy_list:
                log.info(
                    f"发现符合突破形态的个股 {len(buy_list)} 只: "
                    f"{[(s[0], s[2]) for s in buy_list]}"
                )
                all_buy_candidates.extend(buy_list)

        # 统一执行买入
        if all_buy_candidates:
            # 去重并按得分排序
            seen_stocks = set()
            unique_candidates = []
            for item in all_buy_candidates:
                if item[0] not in seen_stocks:
                    seen_stocks.add(item[0])
                    unique_candidates.append(item)

            unique_candidates.sort(key=lambda x: x[1], reverse=True)

            log.info(
                f"最终买入候选 {len(unique_candidates)} 只: "
                f"{[(s[0], s[2]) for s in unique_candidates]}"
            )

            ExecutionAgent.buy_new(context, unique_candidates)
        else:
            log.info("未发现符合买入条件的个股。")


def after_trading_end(context, data):
    """
    每日收盘后结算（🆕 optimize_15: 新增市场模式日志）
    """
    log.info("执行每日收盘后结算处理 (after_trading_end)")

    # 🆕 输出当前市场模式日志
    mode = MarketDetector.detect_market_mode(context)
    params = ConfigManager.DUAL_MODE_PARAMS.get(mode, {})
    log.info(
        f"[市场模式] 当前模式={mode}, "
        f"止盈L1={params.get('TAKE_PROFIT_L1', 'N/A')*100:.0f}%, "
        f"止盈L2={params.get('TAKE_PROFIT_L2', 'N/A')*100:.0f}%, "
        f"日线/15min={params.get('STOP_DATA_FREQUENCY', 'N/A')}"
    )

    # 持仓评估
    current_positions = context.portfolio.positions
    pos_details = []
    for stock, pos in current_positions.items():
        if pos.amount > 0:
            cost = pos.cost_basis
            price = (
                pos.market_value / pos.amount
                if pos.amount > 0 and hasattr(pos, "market_value")
                else 0
            )
            profit_ratio = (price - cost) / cost if cost > 0 and price > 0 else 0
            pos_details.append(f"{stock}: 收益 {profit_ratio*100:.2f}%")

    if pos_details:
        log.info("当前持仓评估: " + ", ".join(pos_details))
    else:
        log.info("当前无持仓。")

    # 每日盈亏 CSV 持久化
    try:
        report_line = f"{context.current_dt.date()},{context.portfolio.portfolio_value},{context.portfolio.positions_value}\n"
        content = Common.safe_read_file("daily_pnl_report.csv")
        if not content:
            content = "Date,TotalValue,PositionValue\n"
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        content += report_line
        Common.safe_write_file("daily_pnl_report.csv", content)
        log.debug("成功更新盈亏报表 CSV。")
    except Exception as e:
        log.warning(f"更新盈亏报表 CSV 失败: {e}")

    # 保存缓存
    DataCache.save_pkl_cache()


def on_order_response(context, trade_list):
    """订单响应回调"""
    if not isinstance(trade_list, list):
        trade_list = [trade_list]

    for order in trade_list:

        def get_order_field(obj, field_name, default=None):
            if isinstance(obj, dict):
                return obj.get(field_name, default)
            else:
                return getattr(obj, field_name, default)

        stock = get_order_field(order, "symbol", "Unknown")
        if stock == "Unknown":
            stock = get_order_field(order, "stock_code", "Unknown")

        status = get_order_field(order, "status", "Unknown")

        filled = get_order_field(order, "filled", None)
        if filled is None:
            filled = get_order_field(order, "business_amount", None)
        if filled is None:
            filled = get_order_field(order, "filled_amount", 0)

        log.info(f"[订单响应] 股票: {stock}, 状态: {status}, 成交量: {filled}")


def on_trade_response(context, trade_list):
    """成交响应回调"""
    if not isinstance(trade_list, list):
        trade_list = [trade_list]

    for trade in trade_list:

        def get_trade_field(obj, field_name, default=None):
            if isinstance(obj, dict):
                return obj.get(field_name, default)
            else:
                return getattr(obj, field_name, default)

        stock = get_trade_field(trade, "symbol", "Unknown")
        if stock == "Unknown":
            stock = get_trade_field(trade, "stock_code", "Unknown")

        price = get_trade_field(trade, "business_price", None)
        if price is None:
            price = get_trade_field(trade, "price", 0)
        price = float(price or 0)

        amount = get_trade_field(trade, "business_amount", None)
        if amount is None:
            amount = get_trade_field(trade, "amount", 0)
        amount = float(amount or 0)

        commission = float(get_trade_field(trade, "commission", 0) or 0)

        entrust_bs = get_trade_field(trade, "entrust_direction", "")
        if not entrust_bs:
            entrust_bs = get_trade_field(trade, "entrust_bs", "")

        side = get_trade_field(trade, "side", "")

        bs_str = str(entrust_bs).upper()
        side_str = str(side).upper()
        action_str = "买"
        if (
            "SELL" in bs_str
            or bs_str == "2"
            or "SELL" in side_str
            or side_str == "2"
            or amount < 0
        ):
            action_str = "卖"

        dt = context.current_dt
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M:%S")

        record_line = f"{date_str},{time_str},{stock},{action_str},-,{abs(amount):.3f},{price:.3f},{commission:.3f}\n"

        try:
            content = Common.safe_read_file("交易详情_trends_up_new.csv")
            if not content:
                content = "日期,时间,合约代码,买/卖,开/平,成交量,成交价,手续费\n"
            if isinstance(content, bytes):
                try:
                    content = content.decode("gbk")
                except:
                    content = content.decode("utf-8")

            content += record_line
            Common.safe_write_file("交易详情_trends_up_new.csv", content.encode("gbk"))
            log.info(
                f"[成交响应] 已记录交易详情: {stock}, {action_str}, 价格: {price}, 数量: {amount}"
            )
        except Exception as e:
            log.warning(f"记录交易详情 CSV 失败: {e}")
