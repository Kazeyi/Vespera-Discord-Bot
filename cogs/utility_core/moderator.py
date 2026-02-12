import sqlite3
import sys
import os
import time
import json
import re

# Add bot root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import DB_FILE, get_mod_settings
from ai_manager import ask_ai
from .personality import VesperaPersonality as VP

DEFAULT_MODEL = 'models/gemma-3-27b-it'

INTERNED_STRINGS = {}

def intern_string(s: str) -> str:
    if s not in INTERNED_STRINGS:
        INTERNED_STRINGS[s] = sys.intern(str(s))
    return INTERNED_STRINGS[s]

def enable_wal_mode():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=-32000;")
    conn.commit()
    conn.close()
    print("✅ SQLite WAL mode enabled for Moderator")

def ensure_mod_tables():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS mod_settings (
        guild_id TEXT PRIMARY KEY,
        log_channel_id TEXT,
        mod_role_id TEXT
    )''')
    
    columns = ["politics_channel_id", "nsfw_channel_id", "gaming_channel_id", 
               "vip_role_id", "server_context", "ai_model"]
    for col in columns:
        try:
            c.execute(f"ALTER TABLE mod_settings ADD COLUMN {col} TEXT")
        except:
            pass
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_reputation (
        user_id TEXT,
        guild_id TEXT,
        toxicity_score INTEGER DEFAULT 0,
        last_offense_time REAL,
        PRIMARY KEY (user_id, guild_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS message_context_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_name TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp REAL DEFAULT (unixepoch()),
        INDEX idx_guild_channel (guild_id, channel_id),
        INDEX idx_timestamp (timestamp)
    )''')
    
    conn.commit()
    conn.close()

def get_lightweight_context(guild_id: str, channel_id: str, limit: int = 5) -> str:
    guild_id = intern_string(str(guild_id))
    channel_id = intern_string(str(channel_id))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT author_name, content FROM message_context_log
        WHERE guild_id = ? AND channel_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (guild_id, channel_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    context_lines = [f"{row[0]}: {row[1]}" for row in reversed(rows)]
    return " | ".join(context_lines) if context_lines else ""

def log_message_to_context(guild_id: str, channel_id: str, 
                           author_id: str, author_name: str, content: str):
    guild_id = intern_string(str(guild_id))
    channel_id = intern_string(str(channel_id))
    author_id = intern_string(str(author_id))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO message_context_log (guild_id, channel_id, author_id, author_name, content)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, channel_id, author_id, author_name, content[:500]))
    
    conn.commit()
    conn.close()

async def analyze_content(text, context_history="", server_context="General Gaming",
                          guild_id=None, current_channel_type="General"):
    try:
        clean = text.replace("||", "")
        ch_instr = ""
        if current_channel_type == "POLITICS":
            ch_instr = "IN POLITICS CHANNEL: Allow gov/pol anger."
        elif current_channel_type == "GAMING":
            ch_instr = "IN GAMING CHANNEL: Allow deep strategy."
        
        prompt = (f"{VP.SYSTEM_PROMPT}\n"
                  f"PROTOCOL: Threat Analysis & Response Calculation.\n"
                  f"CONTEXT: {server_context} | CHANNEL: {current_channel_type}\n{ch_instr}\n\n"
                  
                  f"THREAT DEFINITIONS:\n"
                  f"- **TOXIC:** Personal attacks, severe harassment. (Slurs = Severity 10).\n"
                  f"- **POLITICS:** Government/Election talk keywords. (Severity 4+).\n"
                  f"- **GAMING:** Technical jargon/Stats. (Severity 5+).\n\n"
                  
                  f"RESPONSE PROTOCOL:\n"
                  f"- Severity 1-3: 'Monitor subject.'\n"
                  f"- Severity 4-6: 'Issue verbal warning or Redirect.'\n"
                  f"- Severity 7-8: 'Recommended: Timeout/Mute.'\n"
                  f"- Severity 9-10: 'CRITICAL: Immediate Ban recommended.'\n\n"

                  f"INPUT: {clean}\nHISTORY: {context_history}\n"
                  f"JSON SCHEMA: {{ \"category\": \"Str\", \"severity\": Int(0-10), "
                  f"\"reason\": \"Str\", \"action_recommendation\": \"Str\" }}")
        
        target_model = DEFAULT_MODEL
        if guild_id:
            s = get_mod_settings(guild_id)
            if s and len(s) > 7 and s[7]:
                target_model = s[7]

        raw, used = await ask_ai(prompt, target_model)
        if "```" in raw:
            raw = re.sub(r"```json|```", "", raw).strip()
        d = json.loads(raw)
        return (
            d.get("category", "SAFE").upper(),
            d.get("severity", 0),
            d.get("reason", "No reason"),
            d.get("action_recommendation", "Monitor subject")
        )
    except:
        return "SAFE", 0, "Error", "None"

def update_rep(user_id, guild_id, points):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT toxicity_score, last_offense_time FROM user_reputation WHERE user_id=? AND guild_id=?",
              (str(user_id), str(guild_id)))
    res = c.fetchone()
    now = time.time()
    
    if res:
        score, last = res
        decay = int((now - last) / 3600) * 2
        new_score = max(0, score - decay) + points
    else:
        new_score = points
    
    c.execute("REPLACE INTO user_reputation VALUES (?, ?, ?, ?)",
              (str(user_id), str(guild_id), new_score, now))
    conn.commit()
    conn.close()
    return new_score

def save_settings(guild_id, **kwargs):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO mod_settings (guild_id) VALUES (?)", (str(guild_id),))
    
    mapping = {
        'log_channel': 'log_channel_id',
        'mod_role': 'mod_role_id',
        'politics_channel': 'politics_channel_id',
        'nsfw_channel': 'nsfw_channel_id',
        'gaming_channel': 'gaming_channel_id',
        'vip_role': 'vip_role_id',
        'context': 'server_context',
        'model': 'ai_model'
    }
    
    for k, v in kwargs.items():
        col = mapping.get(k, k)
        if col and kwargs[k]:
            val = kwargs[k]
            val_str = str(val.id) if hasattr(val, 'id') else str(val)
            if val is None:
                val_str = "None"
            c.execute(f"UPDATE mod_settings SET {col}=? WHERE guild_id=?", (val_str, str(guild_id)))
    
    conn.commit()
    conn.close()
