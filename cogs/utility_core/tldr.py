import re
import os
import json
import sys
import time
import gc
from datetime import datetime

# Add bot root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import get_server_model_name
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
# LOGIC
# ==============================================================================

def smart_truncate_history(full_text, max_chars=20000):
    if len(full_text) <= max_chars:
        return full_text
    head = full_text[:6000]
    tail = full_text[-6000:]
    return f"{head}\n\n... [Middle removed] ...\n\n{tail}"

def extract_json(text: str) -> dict:
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        else:
            return {
                "topic": "General Discussion",
                "summary": text,
                "actions": [],
                "sentiment": "neutral",
                "key_participants": []
            }
    except Exception:
        return {
            "topic": "General Discussion",
            "summary": text,
            "actions": [],
            "sentiment": "neutral",
            "key_participants": []
        }

async def generate_summary(text, lang, guild_id):
    lang = sanitize_input(lang, max_length=50)
    model = get_server_model_name(guild_id)
    
    now_str = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = (f"{VP.SYSTEM_PROMPT}\n"
              f"PROTOCOL: Generate a Tactical Summary (TL;DR) for {now_str}.\n"
              f"TARGET LANGUAGE: {lang}.\n\n"
              
              f"DIRECTIVE: Return ONLY valid JSON:\n"
              f"{{\n"
              f'  "topic": "string (main discussion topic)",\n'
              f'  "summary": "string (2-3 sentences, concise summary)",\n'
              f'  "actions": ["list", "of", "important", "tasks", "or", "mentions"],\n'
              f'  "sentiment": "neutral/tense/happy/sad",\n'
              f'  "key_participants": ["user1", "user2"] (VIP users marked with 🌟)\n'
              f"}}\n\n"
              
              f"RULES:\n"
              f"1. VIP users (marked 🌟) are high-priority.\n"
              f"2. Group by topic. Eliminate noise.\n"
              f"3. Tone: Clinical, precise, helpful.\n\n"
              
              f"INPUT LOG:\n{text[:12000]}\n\n"
              f"OUTPUT JSON ONLY:")
    
    response, used_model = await ask_ai(prompt, model)
    data = extract_json(response)
    
    return data, used_model
