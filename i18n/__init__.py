import os
from .en import TRANSLATIONS as EN_TRANS
from .pt import TRANSLATIONS as PT_TRANS
from .es import TRANSLATIONS as ES_TRANS
from .fr import TRANSLATIONS as FR_TRANS
from .de import TRANSLATIONS as DE_TRANS
from .it import TRANSLATIONS as IT_TRANS
from .ru import TRANSLATIONS as RU_TRANS
from .uk import TRANSLATIONS as UK_TRANS

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'pt': 'Português',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'ru': 'Русский',
    'uk': 'Українська',
}

_LANG_DICTS = {
    'en': EN_TRANS,
    'pt': PT_TRANS,
    'es': ES_TRANS,
    'fr': FR_TRANS,
    'de': DE_TRANS,
    'it': IT_TRANS,
    'ru': RU_TRANS,
    'uk': UK_TRANS,
}

_CURRENT_LANG = 'en'

def set_language(code: str) -> bool:
    global _CURRENT_LANG
    code = code.lower().strip()
    if code in SUPPORTED_LANGUAGES:
        _CURRENT_LANG = code
        return True
    return False

def get_language() -> str:
    return _CURRENT_LANG

def get_language_name(code: str = None) -> str:
    if code is None:
        code = _CURRENT_LANG
    return SUPPORTED_LANGUAGES.get(code, 'English')

def t(key: str, **kwargs) -> str:
    lang_dict = _LANG_DICTS.get(_CURRENT_LANG, EN_TRANS)
    val = lang_dict.get(key)
    if val is None:
        val = EN_TRANS.get(key, key)
    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val
