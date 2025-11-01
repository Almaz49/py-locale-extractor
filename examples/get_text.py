# LEXICON/__init__.py

import logging
import os
from typing import Any

from .RU.LEXICON_RU import LEXICON_RU
# from .EN.LEXICON_EN import LEXICON_EN

# Используем тот же паттерн, что и в хэндлерах
logger = logging.getLogger(__name__)  # → имя логгера будет "LEXICON"

# Включать ли детальное логирование отсутствующих ключей
# Можно управлять через переменную окружения
LEXICON_DEBUG = os.getenv("LEXICON_DEBUG", "0").lower() in ("1", "true", "yes")

LEXICON_MAP: dict[str, Any] = {
    'ru': LEXICON_RU,
    # 'en': LEXICON_EN,
}

def get_text(key: str, lang: str) -> str:
    """
    Возвращает текст по ключу для указанного языка.
    Гарантированно возвращает строку.

    Fallback: запрошенный язык → русский → [MISSING: key]
    При LEXICON_DEBUG=1 логирует пропущенные ключи и fallback'и.
    """
    def _get_value(lexicon: Any, key_parts: list[str]) -> str | None:
        value = lexicon
        try:
            for k in key_parts:
                value = value[k]
            return value if isinstance(value, str) else str(value)
        except (KeyError, TypeError, AttributeError):
            return None

    keys = key.split('.')

    # 1. Запрошенный язык
    if lang in LEXICON_MAP:
        result = _get_value(LEXICON_MAP[lang], keys)
        if result is not None:
            return result

    # 2. Fallback на русский
    if lang != 'ru' and 'ru' in LEXICON_MAP:
        result = _get_value(LEXICON_MAP['ru'], keys)
        if result is not None:
            if LEXICON_DEBUG:
                logger.warning(
                    "Lexicon fallback to Russian for key '%s' (requested lang: %s)",
                    key, lang
                )
            return result

    # 3. Ключ не найден нигде
    missing = f"[MISSING: {key}]"
    if LEXICON_DEBUG:
        logger.error(
            "Lexicon key not found in any language: '%s' (requested lang: %s)",
            key, lang
        )
    return missing