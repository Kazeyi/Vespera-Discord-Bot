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

async def get_gemini_translation(text, target_language, style="Slang/Chat", guild_id=None):
    clean_text = sanitize_input(text, max_length=4000)
    model_name = get_server_model_name(guild_id) if guild_id else 'models/gemma-3-27b-it'
    
    tone = "INTERNET SLANG"
    if style == "Formal":
        tone = "STRICT FORMAL"
    elif style == "Informal":
        tone = "NATURAL"
    elif style == "Lyrical":
        tone = "POETIC"

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
        if "```" in raw_text:
            raw_text = re.sub(r"```json|```", "", raw_text).strip()
        
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                data = data[0]
        except:
            return "NA", raw_text, "NA"

        return (
            data.get("input_romanization", "NA"),
            data.get("translation", "Error"),
            data.get("target_romanization", "NA")
        )
    except Exception as e:
        return "NA", f"Error: {str(e)}", "NA"
