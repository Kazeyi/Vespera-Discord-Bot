"""
==============================================================================
GENRE MAPPER — cogs/utility_core/genre_mapper.py
==============================================================================
Provides:
  normalise_lang(raw)           → canonical ISO-639-1 short code
  load_genre_map()              → loads data/song_genre_map.json (cached)
  reload_genre_map()            → clears cache + LRU, for hot-reload
  get_genre(title, artist, lang) → resolves genre key via exact / fuzzy / default
"""

import json
import logging
from pathlib import Path
from difflib import get_close_matches
from functools import lru_cache

logger = logging.getLogger(__name__)

# ==============================================================================
# PATHS
# ==============================================================================
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_GENRE_MAP_PATH = _DATA_DIR / "song_genre_map.json"
_SUGGESTIONS_PATH = _DATA_DIR / "genre_suggestions.log"

# ==============================================================================
# LANGUAGE NORMALISATION
# ==============================================================================
_LANG_TABLE = {
    # Full names from /subtitle dropdown
    "japanese":  "ja", "chinese":    "zh", "korean":    "ko",
    "english":   "en", "indonesian": "id", "arabic":    "ar",
    "russian":   "ru", "thai":       "th", "french":    "fr",
    "german":    "de", "spanish":    "es", "hindi":     "hi",
    # langdetect variants
    "zh-cn": "zh", "zh-tw": "zh",
    # "auto" maps to "ja" as a warm placeholder only;
    # actual detection is done separately in get_gemini_translation
    "auto": "ja",
}

def normalise_lang(raw: str) -> str:
    """Return a canonical 2-letter ISO-639-1 code for any language representation.

    Handles: dropdown full names ("Japanese"), langdetect codes ("zh-cn"),
    short codes ("ja"), and "auto".  Falls back to the first 2 chars of raw.
    """
    if not raw:
        return "ja"
    return _LANG_TABLE.get(raw.lower().strip(), raw.lower()[:2])


# ==============================================================================
# GENRE MAP — lazy load + cache
# ==============================================================================
_GENRE_MAP: dict | None = None

def load_genre_map() -> dict:
    """Load song_genre_map.json once; create data/ directory if absent."""
    global _GENRE_MAP
    if _GENRE_MAP is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not _GENRE_MAP_PATH.exists():
            logger.warning("song_genre_map.json not found — genre lookup will use language defaults only")
            _GENRE_MAP = {"_default_": {"_any_": "balanced"}}
        else:
            with open(_GENRE_MAP_PATH, "r", encoding="utf-8") as f:
                _GENRE_MAP = json.load(f)
            logger.info(f"Genre map loaded: {len(_GENRE_MAP) - 1} artists")
    return _GENRE_MAP


def reload_genre_map() -> None:
    """Clear the in-memory cache and LRU cache so the next call reloads from disk."""
    global _GENRE_MAP
    _GENRE_MAP = None
    get_genre.cache_clear()
    logger.info("Genre map cache cleared — will reload on next lookup")


# ==============================================================================
# LANGUAGE-BASED DEFAULTS
# ==============================================================================
_LANG_DEFAULTS: dict[str, str] = {
    "zh": "emotional_ballad",   # Mandarin pop is ballad-heavy
    "ja": "balanced",           # Wide variety — let LLM self-classify
    "ko": "balanced",           # K-pop spans all genres equally
    "en": "balanced",
}


# ==============================================================================
# GENRE LOOKUP
# ==============================================================================
@lru_cache(maxsize=256)
def get_genre(title: str | None, artist: str | None, lang: str = "ja") -> str:
    """Resolve a genre key for a given song.

    Priority:
      1. Exact match (artist → title in map)
      2. Fuzzy match on combined "artist title" string (cutoff 0.6, min 4 chars)
      3. Language-based default
      4. Global "balanced" fallback

    Returns one of: upbeat_rap, mid_tempo_rock, uplifting_anthem,
                    emotional_ballad, balanced
    """
    genre_map = load_genre_map()
    title_norm  = (title  or "").strip().lower()
    artist_norm = (artist or "").strip().lower()

    # 1. Exact match
    if artist_norm in genre_map:
        if title_norm in genre_map[artist_norm]:
            return genre_map[artist_norm][title_norm]

    # 2. Fuzzy match — skip if combined string is too short (avoids false positives)
    combined = f"{artist_norm} {title_norm}".strip()
    if len(combined) >= 4:
        candidates = [
            (f"{art} {t}", g)
            for art, songs in genre_map.items()
            if art != "_default_"
            for t, g in songs.items()
        ]
        candidate_strings = [c[0] for c in candidates]
        matches = get_close_matches(combined, candidate_strings, n=1, cutoff=0.6)
        if matches:
            matched_genre = next(g for c, g in candidates if c == matches[0])
            logger.info(f"Fuzzy match: {combined!r} → {matches[0]!r} (genre={matched_genre})")
            return matched_genre

    # 3. Language-based default
    default = _LANG_DEFAULTS.get(lang, "balanced")
    if title or artist:
        logger.info(
            f"Unknown song: {artist!r} – {title!r} (lang={lang}) → fallback '{default}'"
        )
    return default


# ==============================================================================
# SUGGESTION LOGGER
# ==============================================================================
def log_genre_suggestion(title: str, artist: str, genre: str, user_id: int) -> None:
    """Append a user genre suggestion to the suggestions log (not the live map)."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = f"[user={user_id}] {artist!r} – {title!r} → {genre}\n"
    with open(_SUGGESTIONS_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
    logger.info(f"Genre suggestion logged: {entry.strip()}")
