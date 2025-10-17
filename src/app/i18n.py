from __future__ import annotations

import json
from collections.abc import Callable
from importlib import resources as importlib_resources

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

SUPPORTED_LANGS = ("en", "ja")
DEFAULT_LANG = "ja"

_catalogs: dict[str, dict] = {}


def load_translations() -> None:
    """Load locale JSON catalogs packaged in app.locales."""
    global _catalogs
    _catalogs = {}
    package = "app.locales"
    for lang in SUPPORTED_LANGS:
        try:
            with (
                importlib_resources.files(package)
                .joinpath(f"{lang}.json")
                .open("rb") as f
            ):
                _catalogs[lang] = json.load(f)
        except Exception:
            _catalogs[lang] = {}


def _resolve_key(data: dict, dotted_key: str) -> str | None:
    cur: object = data
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, (str, int, float, bool)):
        return str(cur)
    return None


def translate(lang: str, key: str, **kwargs) -> str:
    """Resolve translation for key in lang, fallback to en, then key.
    Supports str.format(**kwargs).
    """
    # prefer requested -> default(ja) -> en -> key
    text = (
        _resolve_key(_catalogs.get(lang, {}), key)
        or _resolve_key(_catalogs.get(DEFAULT_LANG, {}), key)
        or _resolve_key(_catalogs.get("en", {}), key)
        or key
    )
    try:
        return text.format(**kwargs) if kwargs else text
    except Exception:
        return text


def _normalize_lang(raw: str | None) -> str:
    if not raw:
        return DEFAULT_LANG
    raw = raw.lower()
    for code in SUPPORTED_LANGS:
        if raw.startswith(code):
            return code
    return DEFAULT_LANG


class LocaleMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default: str = DEFAULT_LANG):
        super().__init__(app)
        self.default = default

    async def dispatch(self, request: Request, call_next):
        # Priority: query `lang`, then Accept-Language header, else default
        lang_param = request.query_params.get("lang")
        header = request.headers.get("accept-language", "")
        header_lang = header.split(",")[0].split(";")[0].strip() if header else None
        lang = _normalize_lang(lang_param or header_lang or self.default)
        request.state.lang = lang
        response = await call_next(request)
        response.headers["Content-Language"] = lang
        return response


Translator = Callable[[str], str]


def get_translator(request: Request) -> Translator:
    lang = getattr(request.state, "lang", DEFAULT_LANG)

    def t(key: str, **kwargs) -> str:
        return translate(lang, key, **kwargs)

    return t
