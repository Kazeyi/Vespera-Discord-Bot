import asyncio
import re
import os
import json
import sys
import time
import html
import gc

# Add bot root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import save_user_language, get_target_language, save_user_style, get_user_global_style, get_server_model_name
from ai_manager import ask_ai, sanitize_input
from .personality import VesperaPersonality as VP

import logging
import subprocess
from pathlib import Path
from langdetect import detect
from .genre_mapper import normalise_lang, get_genre, load_genre_map

logger = logging.getLogger(__name__)

# ==============================================================================
# ROMANIZATION ENGINE — Lazy-Loading Multi-Backend
# ==============================================================================
# Each backend is imported on first use only to keep startup lean.
# Routing:  jpn → pykakasi  |  cmn → pypinyin  |  kor → korean_romanizer  |  * → uroman

_romaji_engine = None      # pykakasi instance (Japanese)
_pinyin_module = None      # pypinyin lazy module handle
_romaja_module = None      # korean_romanizer lazy module handle

def _get_romaji_engine():
    """Lazy-load pykakasi (Japanese)."""
    global _romaji_engine
    if _romaji_engine is None:
        try:
            import pykakasi as _pk
            _romaji_engine = _pk.kakasi()
            logger.info("pykakasi loaded for Japanese romanization")
        except ImportError:
            logger.warning("pykakasi not installed; Japanese romanization will use uroman")
    return _romaji_engine

def _get_pinyin_module():
    """Lazy-load pypinyin (Chinese)."""
    global _pinyin_module
    if _pinyin_module is None:
        try:
            import pypinyin as _pp
            _pinyin_module = _pp
            logger.info("pypinyin loaded for Chinese romanization")
        except ImportError:
            logger.warning("pypinyin not installed; Chinese romanization will use uroman")
    return _pinyin_module

def _get_romaja_module():
    """Lazy-load korean_romanizer (Korean)."""
    global _romaja_module
    if _romaja_module is None:
        try:
            from korean_romanizer.romanizer import Romanizer as _KR
            _romaja_module = _KR
            logger.info("korean_romanizer loaded for Korean romanization")
        except ImportError:
            logger.warning("korean_romanizer not installed; Korean romanization will use uroman")
    return _romaja_module

# ==============================================================================
# LYRICAL COT INITIALIZATION
# ==============================================================================
BASE_DIR = Path(__file__).parent.parent.parent
KB_PATH = BASE_DIR / "knowledge_base" / "lyrical_philosophy.md"

try:
    with open(KB_PATH, "r", encoding="utf-8") as f:
        LYRICAL_TRUTH_BLOCK = f.read()
except FileNotFoundError:
    logger.warning("lyrical_philosophy.md missing – lyrical translations will use fallback prompt")
    LYRICAL_TRUTH_BLOCK = "Translate prioritizing poetic rhythm and equivalence."

def extract_short_philosophy(full_text: str) -> str:
    parts = full_text.split("\n## 4.")
    return parts[0] if len(parts) > 1 else full_text

LYRICAL_PHILOSOPHY_SHORT = extract_short_philosophy(LYRICAL_TRUTH_BLOCK)
COT_ENABLED = os.getenv("LYRICAL_COT_ENABLED", "true").lower() == "true"

LANG_TO_ISO = {
    "japanese": "jpn", "chinese": "cmn", "arabic": "ara", "korean": "kor",
    "spanish": "spa", "french": "fra", "german": "deu", "russian": "rus",
    "hindi": "hin", "indonesian": "ind", "english": "eng", "thai": "tha"
}

# langdetect returns ISO 639-1 codes (e.g. "ja", "zh-cn") — map these to ISO 639-3 for uroman
DETECT_TO_ISO = {
    "ja": "jpn", "zh-cn": "cmn", "zh-tw": "cmn", "zh": "cmn",
    "ko": "kor", "ar": "ara", "ru": "rus", "hi": "hin",
    "th": "tha", "es": "spa", "fr": "fra", "de": "deu",
    "id": "ind", "en": "eng",
}

def romanize_text(text: str, lang_code: str) -> str:
    """Route text to the best available romanization engine.
    
    jpn → pykakasi | cmn → pypinyin | kor → korean_romanizer | * → uroman
    Returns "NA" if the text is already Latin-script or romanization fails.
    """
    if not text or not lang_code:
        return "NA"

    # ── Japanese ─────────────────────────────────────────────────────────────
    if lang_code == "jpn":
        engine = _get_romaji_engine()
        if engine:
            try:
                items = engine.convert(text)
                romaji = " ".join(i["hepburn"] for i in items if i["hepburn"]).strip()
                return romaji or "NA"
            except Exception as e:
                logger.warning(f"pykakasi error: {e} — falling through to uroman")

    # ── Chinese (Mandarin) ────────────────────────────────────────────────────
    elif lang_code in ("cmn", "zho"):
        pp = _get_pinyin_module()
        if pp:
            try:
                from pypinyin import Style as _PStyle
                syllables = pp.lazy_pinyin(text, style=_PStyle.TONE3)
                # Filter out punctuation tokens (pure non-alpha)
                syllables = [s for s in syllables if any(c.isalpha() for c in s)]
                return " ".join(syllables) or "NA"
            except Exception as e:
                logger.warning(f"pypinyin error: {e} — falling through to uroman")

    # ── Korean ───────────────────────────────────────────────────────────────
    elif lang_code == "kor":
        KR = _get_romaja_module()
        if KR:
            try:
                return KR(text).romanize() or "NA"
            except Exception as e:
                logger.warning(f"korean_romanizer error: {e} — falling through to uroman")

    # ── All other scripts: Arabic, Russian, Thai, Hindi, etc. ────────────────
    try:
        uroman_path = "/home/kazeyami/venv/bin/uroman"
        if not os.path.exists(uroman_path):
            uroman_path = "uroman"

        result = subprocess.run(
            [uroman_path, "-l", lang_code],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.warning(f"uroman failed for {lang_code}: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"uroman exception: {e}")

    return "NA"

# Keep old name as an alias so nothing else breaks
romanize_with_uroman = romanize_text

# ==============================================================================
# GENRE-AWARE LYRICAL PROMPT CONSTANTS
# ==============================================================================
GENRE_STYLE_PROMPTS: dict[str, str] = {
    "upbeat_rap": (
        "Style: Upbeat / Rap (e.g., YOASOBI 'Idol', Vivid Bad Squad 'Fire Dance', K-pop rap).\n"
        "- Short punchy lines (4–8 syllables).\n"
        "- Exclamation marks and rhetorical questions for energy.\n"
        "- Preserve concrete actions and rapid-fire questioning.\n"
        "- Keep code-switched English/caps and wordplay.\n"
        "- Do NOT add slow, romantic, or melancholic imagery.\n"
    ),
    "mid_tempo_rock": (
        "Style: Mid-tempo rock / J-pop (e.g., Leo/Need 'SToRY').\n"
        "- Moderate pace, gentle rhymes, narrative clarity.\n"
        "- Vocabulary: grasp, burden, tears, forgive, ache.\n"
        "- Emotional but not melodramatic — understated weight.\n"
    ),
    "uplifting_anthem": (
        "Style: Uplifting anthem / anime opening (e.g., Alexandros 'Koeru').\n"
        "- Second person ('you'), metaphors of crossing and surpassing.\n"
        "- Use contractions natural to the target language for pace.\n"
        "- Build towards a climactic, triumphant resolve.\n"
    ),
    "emotional_ballad": (
        "Style: Slow emotional ballad (e.g., PSO2 Nadereh, Chinese/Korean ballads).\n"
        "- Long flowing lines (8–12 syllables preferred).\n"
        "- Lore-specific or environmental imagery (desert, wind, stars, ocean).\n"
        "- Hopeful first-person resolve; avoid rushed phrasing.\n"
    ),
    "balanced": (
        "No genre hint is available. Classify the genre yourself using the Genre Table "
        "in Section 2 of the Truth Block, then apply the appropriate style.\n"
        "- Natural rhythm, faithful meaning, no forced style.\n"
    ),
}

SOURCE_LANG_HINTS: dict[str, str] = {
    "ja": "Mora-timed language. Keep syllable count within ±10% of original.",
    "zh": "Monosyllabic/tonal language. Adapt natural flow; do NOT write tone marks.",
    "ko": "Syllable-timed language. Preserve natural Korean rhythmic energy.",
    "en": "Stress-timed language. Prioritise natural English lyric stress patterns.",
    "id": "Agglutinative language. Use contractions (s'lalu, 'kan, 'tuk) for upbeat genres.",
}


def build_lyrical_prompt(
    source_text: str,
    target_lang: str,
    genre_key: str = "balanced",
    source_lang: str = "ja",
) -> str:
    """Build the full Silent Architect prompt with 5-layer injection order:
    1. Mandatory target language override
    2. Source language hint
    3. Genre style prefix
    4. Full Truth Block
    5. Source text
    """
    # Layer 1: mandatory target language override
    prompt = (
        f"⚠️ MANDATORY OVERRIDE — TARGET LANGUAGE: **{target_lang}**\n"
        f"You MUST translate ONLY into {target_lang}. "
        f"Any language mentioned in the rules below is for style reference only. "
        f"The final output must be in {target_lang} exclusively.\n\n"
    )

    # Layer 2: source language hint
    lang_hint = SOURCE_LANG_HINTS.get(source_lang, "")
    if lang_hint:
        prompt += f"Source language ({source_lang.upper()}): {lang_hint}\n\n"

    # Layer 3: genre style prefix
    genre_snippet = GENRE_STYLE_PROMPTS.get(genre_key, GENRE_STYLE_PROMPTS["balanced"])
    prompt += f"GENRE STYLE GUIDE:\n{genre_snippet}\n"

    # Layer 4: full Truth Block
    if COT_ENABLED:
        prompt += (
            f"You are the Silent Architect, translating lyrics into {target_lang}.\n"
            f"=== TRUTH BLOCK ===\n{LYRICAL_TRUTH_BLOCK}\n===================\n\n"
            "INSTRUCTIONS:\n"
            "Execute the pipeline defined in Section 6 of the Truth Block.\n"
            "You MUST follow this exact output XML-like template structure:\n\n"
            "<scratchpad>\n"
            "1. Genre Identification:\n"
            "[Identify the genre of the source text]\n\n"
            "2. Literal Meaning:\n"
            "[Provide the literal meaning/translation of the lines]\n\n"
            "3. Rhyme Scheme & Syllable Target:\n"
            "[Plan the rhyme scheme and singability syllable counts]\n\n"
            "4. Candidate Drafts:\n"
            "[List candidate drafts and lyric options]\n\n"
            "5. Constraint Check:\n"
            "[Audit drafts against formatting, rhythmic constraints, and guidelines]\n"
            "</scratchpad>\n\n"
            "[WRITE FINAL POETIC LYRICS HERE - STRICTLY EXCLUDE ANY EXPLANATORY COMMENTARY, LABELS, OR METADATA OUTSIDE OF THE SCRATCHPAD]\n\n"
            "NEGATIVE CONSTRAINT: Absolutely do NOT output any conversational text, notes, headers, or explanations outside of the <scratchpad> tags. "
            "Output only the final translated lyrics directly after the closing </scratchpad> tag.\n"
        )
    else:
        prompt += (
            f"You are a lyrical translator.\n"
            f"=== RULES ===\n{LYRICAL_PHILOSOPHY_SHORT}\n=============\n\n"
            f"Translate the following lyrics to {target_lang} poetically, following the rules above.\n"
            f"Output ONLY the final translated lyrics in {target_lang} (plain text).\n"
        )

    # Layer 5: source text + sentinel output marker
    prompt += (
        f"\nSource Text:\n{source_text}\n"
        "\n"
        "=== TRANSLATED LYRICS ===\n"
        "(Write ONLY the translated lyrics below this line. "
        "No analysis, no labels, no line numbers, no commentary.)\n"
    )
    return prompt

# Sentinel used in build_lyrical_prompt — must match exactly
_SENTINEL = "=== TRANSLATED LYRICS ==="

# Single-line patterns that indicate analysis/metadata (not lyrics)
_ANALYSIS_LINE_PAT = re.compile(
    r'^[*\-\s]*('
    r'Source\s*:|'
    r'Language\s*:|'
    r'Target\s*(Language)?\s*:|'
    r'Key\s+constraint|'
    r'Genre\s*(Identification)?\s*:|'
    r'Style\s*:|'
    r'Priority\s*:|'
    r'Line\s+\d+\s*:|'
    r'Syllable\s*:|'
    r'Literal\s*:|'
    r'Constraint\s*:|'
    r'Step\s+\d+\s*:|'
    r'Note\s*:|'
    r'Notes\s*:|'
    r'Reasoning\s*:|'
    r'Thinking\s*:|'
    r'Analysis\s*:|'
    r'Translation\s+Analysis|'
    r'Translate\s*\([A-Za-z]+\)\s*[^:]*:|'
    r'Persona\s*:|'
    r'Task\s*:|'
    r'Target\s+Tone\s*:|'
    r'Specific\s+Directive\s*:|'
    r'Output\s+Format\s*:|'
    r'Input\s*:|'
    r'Extreme\s+Fidelity\s+Rules\s*:|'
    r'Golden\s+Standard\s*:'
    r')',
    re.IGNORECASE,
)

# Markers for known alternate scratchpad formats
_SCRATCHPAD_VARIANTS = [
    (r'<scratchpad>.*?</scratchpad>', re.DOTALL),
    (r'\[SCRATCHPAD\].*?\[/SCRATCHPAD\]', re.DOTALL | re.IGNORECASE),
    (r'---\s*Reason(?:ing)?:.*?---', re.DOTALL | re.IGNORECASE),
    (r'```.*?```', re.DOTALL),
    (r'~~~.*?~~~', re.DOTALL),
]


def strip_leading_metadata(text: str) -> str:
    """Removes leading headers, analysis, and rule blocks before the actual lyrics."""
    lines = text.splitlines()
    i = 0
    n = len(lines)
    
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        is_metadata = False
        if _ANALYSIS_LINE_PAT.match(line):
            is_metadata = True
        elif re.match(r'^\d+[\s\.\)]', line) and any(kw in line.lower() for kw in ["meaning", "genre", "literal", "rhyme", "syllable", "draft", "check", "constraint", "theme", "structure", "comparison"]):
            is_metadata = True
        elif line.startswith("*") and any(kw in line.lower() for kw in ["source", "target", "constraint", "genre", "extreme", "golden", "standard", "lyrics", "mid-section", "overall", "structure", "comparison"]):
            is_metadata = True
        elif any(line.lower().startswith(p) for p in ["lyrics start with", "mid-section has", "overall theme", "structure:", "comparison:", "very similar to"]):
            is_metadata = True
            
        if is_metadata:
            i += 1
        else:
            break
            
    return "\n".join(lines[i:]).strip()


def _strip_analysis_block(lines: list[str]) -> str:
    """Remove a leading contiguous block of numbered-list analysis lines.

    Only strips lines if they form a block at the top of the text AND are
    clearly analysis (e.g. '1. Literal Meaning: ...'). Stops at the first
    non-numbered, non-blank line — which is treated as the start of lyrics.

    Lyric lines that happen to start with a number (e.g. '1 AM, the rain falls')
    are protected because they won't match '\\d+\\. [A-Z][a-z]+ [A-Z]'.
    """
    # Only trigger if the first non-blank line looks like '1. Genre Identification:'
    for ln in lines:
        if not ln.strip():
            continue
        if re.match(r'^\s*1\.\s+[A-Z][a-zA-Z\s]+:', ln):
            break   # confirmed analysis block at top
        return "\n".join(lines).strip()   # no analysis block — return as-is

    filtered, in_block = [], True
    for ln in lines:
        if in_block:
            if re.match(r'^\s*\d+\.\s+', ln) or (not ln.strip()):
                continue   # skip numbered analysis lines and blank lines inside block
            else:
                in_block = False  # first real content line = start of lyrics
        filtered.append(ln)
    return "\n".join(filtered).strip()


def _clean_lyrical_output_inner(raw_text: str) -> str:
    if not COT_ENABLED:
        return raw_text.strip()

    # ── Strategy 0: Split by scratchpad closing tag (case-insensitive) ──
    for tag in ["</scratchpad>", "[/scratchpad]", "[/SCRATCHPAD]"]:
        tag_idx = raw_text.lower().find(tag.lower())
        if tag_idx != -1:
            remainder = raw_text[tag_idx + len(tag):].strip()
            if remainder:
                clean_remainder = strip_leading_metadata(remainder)
                if clean_remainder:
                    logger.info("clean_lyrical_output: ✅ scratchpad closing tag split & metadata stripped")
                    return clean_remainder

    # ── Strategy 1: sentinel marker ──────────────────────────────────────────
    if _SENTINEL in raw_text:
        after = raw_text.split(_SENTINEL, 1)[1]
        lines = after.strip().splitlines()
        # Drop instruction echo line if model repeated it
        lines = [ln for ln in lines if not ln.strip().startswith("(Write ONLY")]
        result = "\n".join(lines).strip()
        if result:
            logger.info("clean_lyrical_output: ✅ sentinel")
            return strip_leading_metadata(result)

    # ── Strategies 2–4: tag/block variants ───────────────────────────────────
    working = raw_text
    changed = False
    for pattern, flags in _SCRATCHPAD_VARIANTS:
        new = re.sub(pattern, '', working, flags=flags).strip()
        if new and new != working.strip():
            working = new
            changed = True
    if changed:
        result = re.sub(r'\n{3,}', '\n\n', working).strip()
        if result:
            logger.info("clean_lyrical_output: ✅ tag/block removal")
            return strip_leading_metadata(result)

    # ── Strategy 5: double-blank-line separator ───────────────────────────────
    # LLMs often write analysis, then TWO blank lines, then the lyrics.
    paragraphs = re.split(r'\n\s*\n', raw_text.strip())
    if len(paragraphs) >= 2:
        # Check if the remaining contiguous paragraphs from some point are clean lyrics
        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if para and not _ANALYSIS_LINE_PAT.match(para.splitlines()[0]):
                # Take all paragraphs from this one onwards
                joined = "\n\n".join(p.strip() for p in paragraphs[idx:] if p.strip())
                logger.info("clean_lyrical_output: ✅ double-blank-line split")
                return strip_leading_metadata(joined)

    # ── Strategy 6: drop known analysis-header lines ─────────────────────────
    lines = raw_text.splitlines()
    kept = [ln for ln in lines if not _ANALYSIS_LINE_PAT.match(ln.strip())]
    result = "\n".join(kept).strip()
    if result and result != raw_text.strip():
        logger.info("clean_lyrical_output: ✅ line-by-line analysis filter")
        return strip_leading_metadata(result)

    # ── Strategy 7: numbered-list analysis block at top ──────────────────────
    result = _strip_analysis_block(raw_text.splitlines())
    if result and result != raw_text.strip():
        logger.info("clean_lyrical_output: ✅ numbered-block strip")
        return strip_leading_metadata(result)

    # ── Strategy 8: raw fallback ──────────────────────────────────────────────
    logger.warning(
        f"clean_lyrical_output: ⚠️ all strategies failed – raw preview: {repr(raw_text[:300])}"
    )
    return strip_leading_metadata(raw_text)


def clean_lyrical_output(raw_text: str) -> str:
    """Extract only the final translated lyrics from the LLM response."""
    result = _clean_lyrical_output_inner(raw_text)
    # Final cleanup: strip enclosing markdown code blocks
    result = re.sub(r'^```[a-zA-Z]*\s*\n|```\s*$', '', result, flags=re.MULTILINE).strip()
    return result

# ==============================================================================
# STRING INTERNING
# ==============================================================================
INTERNED_STRINGS = {}

def intern_string(s: str) -> str:
    if s not in INTERNED_STRINGS:
        INTERNED_STRINGS[s] = sys.intern(str(s))
    return INTERNED_STRINGS[s]

# ==============================================================================
# STYLE THEMES
# ==============================================================================
STYLE_THEMES = {
    "Formal": {"icon": "👔", "color": 0x2E86C1},
    "Informal": {"icon": "🧢", "color": 0x1ABC9C},
    "Slang/Chat": {"icon": "⚡", "color": 0xE74C3C},
    "Lyrical": {"icon": "🎻", "color": 0x9B59B6}
}

# ==============================================================================
# GLOSSARIES
# ==============================================================================
GLOSSARY_DND = {
    "Fireball": "Bola Api",
    "Wizard": "Penyihir",
    "Dragon": "Naga",
    "Dungeon Master": "Pengatur Dungeon",
    "Initiative": "Inisiatif",
    "Saving Throw": "Lemparan Penyelamatan",
    "Hit Points": "Poin Kesehatan",
    "Armor Class": "Kelas Armor",
    "Critical Hit": "Pukulan Kritis",
    "Spell Slot": "Slot Mantra",
    "Cantrip": "Mantra Dasar",
    "Concentration": "Konsentrasi",
    "Advantage": "Keuntungan",
    "Disadvantage": "Kerugian",
}

GLOSSARY_CLOUD = {
    "Terraform": "Infraestructura como Código",
    "Kubernetes": "Sistema de Orquestación",
    "Docker": "Contenedor",
    "AWS": "Amazon Web Services",
    "GCP": "Google Cloud Platform",
    "Azure": "Microsoft Azure",
    "Load Balancer": "Balanceador de Carga",
    "Auto Scaling": "Escalado Automático",
    "Virtual Machine": "Máquina Virtual",
    "Cloud Function": "Función en la Nube",
    "Container": "Contenedor",
    "Serverless": "Sin Servidor",
}

MASTER_GLOSSARY = {intern_string(k): v for k, v in {**GLOSSARY_DND, **GLOSSARY_CLOUD}.items()}
GLOSSARY_KEYWORDS = set(k.lower() for k in MASTER_GLOSSARY.keys())

# ==============================================================================
# LOGIC
# ==============================================================================

def get_needed_terms(text: str) -> dict:
    text_lower = text.lower()
    needed = {}
    for keyword in GLOSSARY_KEYWORDS:
        if keyword in text_lower:
            for original_key, translation in MASTER_GLOSSARY.items():
                if original_key.lower() == keyword:
                    needed[original_key] = translation
                    break
    return needed

def smart_split(text, limit=1900):
    if len(text) <= limit:
        return [text]
    
    chunks = []
    current_chunk = ""
    paragraphs = text.split('\n')
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 <= limit:
            current_chunk += para + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(para) > limit:
                words = para.split(' ')
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 <= limit:
                        temp_chunk += word + " "
                    else:
                        chunks.append(temp_chunk.strip())
                        temp_chunk = word + " "
                current_chunk = temp_chunk
            else:
                current_chunk = para + "\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def extract_json_block(text: str) -> str:
    """Finds all potential JSON block candidates using brace balancing and tries to parse them."""
    candidates = []
    n = len(text)
    for i in range(n):
        if text[i] == '{':
            brace_count = 0
            for j in range(i, n):
                if text[j] == '{':
                    brace_count += 1
                elif text[j] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        candidate = text[i:j+1]
                        candidates.append(candidate)
                        break
    
    # Sort candidates by length descending
    candidates.sort(key=len, reverse=True)
    
    # First pass: look for candidates that successfully parse and have the "translation" key
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "translation" in parsed:
                return candidate
        except Exception:
            continue
            
    # Second pass: look for any candidate that successfully parses
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return candidate
        except Exception:
            continue
            
    # Fallback to regex search
    json_match = re.search(r'\{.*?\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
        
    return None


async def get_gemini_translation(
    text,
    target_language,
    style="Slang/Chat",
    guild_id=None,
    source_lang="auto",
    title=None,
    artist=None,
    genre_override=None,
):
    clean_text = sanitize_input(text, max_length=4000)
    model_name = await asyncio.to_thread(get_server_model_name, guild_id) if guild_id else 'models/gemma-3-27b-it'

    tone = "INTERNET SLANG"
    if style == "Formal":
        tone = "STRICT FORMAL"
    elif style == "Informal":
        tone = "NATURAL"
    elif style == "Lyrical":
        tone = "POETIC"

    if style.lower() == "lyrical":
        # ── Resolve source language ──────────────────────────────────────────
        actual_lang = normalise_lang(source_lang)

        # FIXED: check ORIGINAL source_lang value so explicit "Japanese"
        # is never overridden by langdetect
        if source_lang.lower() == "auto":
            try:
                detected = detect(clean_text)
                actual_lang = normalise_lang(detected)
                logger.info(
                    f"auto source_lang: langdetect returned '{detected}' → '{actual_lang}'"
                )
            except Exception as e:
                logger.warning(
                    f"Language detection failed: {e}. Falling back to 'ja'."
                )
                actual_lang = "ja"

        # ── Resolve genre ────────────────────────────────────────────────────
        genre_key = genre_override or get_genre(title, artist, lang=actual_lang)

        # ── Build & send prompt ──────────────────────────────────────────────
        # Romanization intentionally omitted for Lyrical mode
        prompt = build_lyrical_prompt(clean_text, target_language, genre_key, actual_lang)
        try:
            raw_response, used_model = await ask_ai(prompt, model_name)
            logger.info(
                f"[Lyrical] model={used_model} | "
                f"raw_len={len(raw_response)} | "
                f"sentinel_present={'=== TRANSLATED LYRICS ===' in raw_response} | "
                f"scratchpad_tag={'<scratchpad>' in raw_response} | "
                f"raw_preview={repr(raw_response[:200])}"
            )
            translated_text = clean_lyrical_output(raw_response)
            logger.info(
                f"[Lyrical] clean_len={len(translated_text)} | "
                f"clean_preview={repr(translated_text[:200])}"
            )
            return "NA", translated_text, "NA"
        except Exception as e:
            logger.error(f"[Lyrical] ask_ai/clean exception: {e}", exc_info=True)
            return "NA", f"Error: {str(e)}", "NA"

    try:
        needed_terms = get_needed_terms(clean_text)
        glossary_note = ""
        if needed_terms:
            terms_list = [f"'{k}' = '{v}'" for k, v in list(needed_terms.items())[:10]]
            glossary_note = f"\nGLOSSARY (preserve these): {', '.join(terms_list)}\n"
        
        prompt = (f"{VP.SYSTEM_PROMPT}\n"
                  f"TASK: Translate input to {target_language} with absolute precision.\n"
                  f"TONE: {style} ({tone}).\n"
                  f"DIRECTIVE: Map 'wkwk'='lol'. Handle cultural nuance perfectly.\n"
                  f"{glossary_note}"
                  f"JSON OUTPUT ONLY:\n"
                  f"{{\n"
                  f'  "input_romanization": "String (NA if Latin input. REQUIRED for CJK/Arabic)",\n'
                  f'  "translation": "String (The translated text)",\n'
                  f'  "target_romanization": "String (NA if target is English/Indo/Latin. REQUIRED if target is Japanese/Chinese/Arabic/Russian)"\n'
                  f"}}\n"
                  f"INPUT: {clean_text}")
        
        raw_text, used_model = await ask_ai(prompt, model_name)
        
        # Defensive JSON block extraction using robust brace-balancing and fallback regex
        balanced_json = extract_json_block(raw_text)
        if balanced_json:
            raw_text = balanced_json
        elif "```" in raw_text:
            raw_text = re.sub(r"```json|```", "", raw_text).strip()
        
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                data = data[0]
        except Exception as json_err:
            logger.error(f"JSON extraction/parsing failed: {json_err} | Raw: {raw_text}")
            return "NA", raw_text, "NA"

        return (
            data.get("input_romanization", "NA"),
            data.get("translation", "Error"),
            data.get("target_romanization", "NA")
        )
    except Exception as e:
        return "NA", f"Error: {str(e)}", "NA"
