import pytest
import re
import sys
import os

# Add bot root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.utility_core.translation import clean_lyrical_output, LANG_TO_ISO
from cogs.utility_core.genre_mapper import get_genre, normalise_lang, reload_genre_map

# ==============================================================================
# LYRICAL OUTPUT CLEANING
# ==============================================================================
def test_scratchpad_removal():
    raw = "<scratchpad>\n1. Genre: Ballad\n2. Literal: ...\n</scratchpad>\nFinal lyrics here."
    cleaned = clean_lyrical_output(raw)
    assert "<scratchpad>" not in cleaned
    assert "Final lyrics here" in cleaned

def test_malformed_fallback():
    raw = "No scratchpad, just plain text"
    cleaned = clean_lyrical_output(raw)
    assert cleaned == raw

def test_code_fence_removal():
    raw = "```plaintext\nSome lyrics\n```"
    cleaned = clean_lyrical_output(raw)
    assert "```" not in cleaned
    assert "Some lyrics" in cleaned

def test_language_mapping():
    assert LANG_TO_ISO.get("japanese") == "jpn"
    assert LANG_TO_ISO.get("korean") == "kor"

# ==============================================================================
# GENRE MAPPER — normalise_lang
# ==============================================================================
def test_normalise_full_name():
    assert normalise_lang("Japanese") == "ja"
    assert normalise_lang("Chinese") == "zh"
    assert normalise_lang("Korean") == "ko"

def test_normalise_langdetect_variant():
    assert normalise_lang("zh-cn") == "zh"
    assert normalise_lang("zh-tw") == "zh"

def test_normalise_auto():
    assert normalise_lang("auto") == "ja"

def test_normalise_empty():
    assert normalise_lang("") == "ja"

# ==============================================================================
# GENRE MAPPER — get_genre
# ==============================================================================
def setup_function():
    """Clear LRU cache before each test to ensure clean state."""
    reload_genre_map()

def test_genre_exact_match():
    assert get_genre("Idol", "YOASOBI") == "upbeat_rap"

def test_genre_exact_case_insensitive():
    assert get_genre("idol", "yoasobi") == "upbeat_rap"
    assert get_genre("IDOL", "YOASOBI") == "upbeat_rap"

def test_genre_fuzzy_match_typo():
    # "idel" is close enough to "idol" with "yoasobi" as artist
    result = get_genre("idel", "yoasobi")
    assert result == "upbeat_rap"

def test_genre_short_input_no_false_positive():
    # combined string "ok" < 4 chars: fuzzy is skipped, falls to lang default
    result = get_genre("ok", None, lang="ja")
    assert result == "balanced"

def test_genre_unknown_chinese_default():
    assert get_genre(None, None, lang="zh") == "emotional_ballad"

def test_genre_unknown_korean_default():
    assert get_genre(None, None, lang="ko") == "balanced"

def test_genre_unknown_japanese_default():
    assert get_genre(None, None, lang="ja") == "balanced"

def test_genre_no_args():
    assert get_genre(None, None) == "balanced"
