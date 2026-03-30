# -*- coding: utf-8 -*-
"""
simtradelab i18n — 线程安全的翻译模块

使用方式:
    from simtradelab.i18n import set_locale, t
    set_locale("en")
    log.info(t("bt.start", strategy="my_strategy"))
"""

import json
import locale
import os
import sys
import threading
from pathlib import Path

_locales: dict[str, dict[str, str]] = {}
_thread_local = threading.local()
_SUPPORTED_LOCALES = {"zh", "en", "de"}


def _detect_locale() -> str:
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env, "")
        if val:
            lang = val.split("_")[0].split(".")[0]
            if lang in _SUPPORTED_LOCALES:
                return lang
            break
    try:
        lang = (locale.getlocale()[0] or "").split("_")[0]
        if lang in _SUPPORTED_LOCALES:
            return lang
    except Exception:
        pass
    return "en"


_DEFAULT_LOCALE = _detect_locale()


def _load_locales() -> None:
    base = getattr(sys, "_MEIPASS", None)
    locales_dir = Path(base) / "simtradelab" / "locales" if base else Path(__file__).parent / "locales"
    for path in locales_dir.glob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            _locales[path.stem] = json.load(f)


def set_locale(locale: str) -> None:
    _thread_local.locale = locale


def get_locale() -> str:
    return getattr(_thread_local, "locale", _DEFAULT_LOCALE)


def t(key: str, **params: object) -> str:
    locale = get_locale()
    translations = _locales.get(locale) or _locales.get(_DEFAULT_LOCALE, {})
    template = translations.get(key)
    if template is None:
        template = _locales.get(_DEFAULT_LOCALE, {}).get(key, key)
    return template.format(**params) if params else template


_load_locales()
