import sqlite3
import time
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import discord

from database import DB_FILE, get_dnd_config, get_dnd_history, get_session_protagonist
from .ai import generate_text
from .constants import FAST_MODEL, PHASE_TIME_SKIPS

# --- HISTORY MANAGER ---
class HistoryManager:
    """Efficient history management with summarization"""
    
    @staticmethod
    async def summarize_history(guild_id: int, thread_id: int, force: bool = False) -> Optional[str]:
        """Summarize old history entries to save tokens"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        try:
            c.execute("SELECT COUNT(*) FROM dnd_history WHERE thread_id=?", (str(thread_id),))
            result = c.fetchone()
            count = result[0] if result else 0
            
            if count < 20 and not force:
                conn.close()
                return None
            
            c.execute('''SELECT role, content FROM dnd_history 
                        WHERE thread_id=? 
                        ORDER BY timestamp ASC LIMIT 15''', 
                    (str(thread_id),))
            old_entries = c.fetchall()
            
            if not old_entries:
                conn.close()
                return None
            
            history_text = "\n".join([f"{role}: {content[:100]}" for role, content in old_entries])
            
            prompt = f"""Summarize these D&D session events into 2-3 sentences:
            
            {history_text}
            
            Summary:"""
            
            summary = await generate_text(prompt, FAST_MODEL, max_tokens=150, temperature=0.3)
            
            if not summary:
                conn.close()
                return None
                
            c.execute('''DELETE FROM dnd_history 
                        WHERE thread_id=? AND timestamp IN (
                            SELECT timestamp FROM dnd_history 
                            WHERE thread_id=? 
                            ORDER BY timestamp ASC LIMIT 15
                        )''', (str(thread_id), str(thread_id)))
            
            c.execute('''INSERT INTO dnd_history (thread_id, role, content, timestamp)
                        VALUES (?, ?, ?, ?)''',
                    (str(thread_id), "SUMMARY", summary, time.time()))
            
            conn.commit()
            return summary
            
        except Exception as e:
            print(f"[History] Summarization failed: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def get_optimized_history(thread_id: int, limit: int = 8) -> List[Tuple[str, str]]:
        """Get history with efficient windowing"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''SELECT role, content FROM dnd_history 
                    WHERE thread_id=? 
                    ORDER BY timestamp DESC LIMIT ?''',
                 (str(thread_id), limit))
        
        results = c.fetchall()
        conn.close()
        
        return results[::-1]

# --- SESSION SCRIBE ---
class SessionScribe:
    """Generate session summaries"""
    
    @staticmethod
    def generate_session_embed(guild_id: int, thread_id: int, session_title: str = "Session Report") -> Optional[discord.Embed]:
        """Generate a session summary embed"""
        config = get_dnd_config(guild_id)
        if not config:
            return None
        
        history = get_dnd_history(thread_id, limit=15)
        
        player_actions = []
        dm_narration = []
        
        for role, content in history:
            if role == "DM":
                dm_narration.append(content[:100])
            elif role != "SUMMARY":
                player_actions.append(f"{role}: {content[:50]}")
        
        embed = discord.Embed(
            title=f"📝 {session_title}",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        
        quest_name = "Adventure"
        # Config index 8 is often quest_data in this codebase, but code says config[10]
        # Checking dnd.py code: "if config[10]: try: quest_data = json.loads(config[10])"
        if len(config) > 10 and config[10]:
            try:
                quest_data = json.loads(config[10])
                quest_name = quest_data.get('name', quest_name)
            except:
                pass
        
        embed.add_field(name="Quest", value=quest_name, inline=True)
        embed.add_field(name="Location", value=config[1] or "Unknown", inline=True)
        
        if player_actions:
            actions_text = "\n".join(player_actions[:5])
            if len(player_actions) > 5:
                actions_text += f"\n...and {len(player_actions) - 5} more actions"
            embed.add_field(name="Recent Actions", value=actions_text, inline=False)
        
        if dm_narration:
            narration_text = "... ".join(dm_narration[-3:])[:300]
            embed.add_field(name="Story Progress", value=narration_text + "...", inline=False)
        
        protagonist, score = get_session_protagonist(guild_id)
        if protagonist:
            embed.add_field(name="Protagonist", value=f"{protagonist} (Destiny: {score})", inline=True)
        
        embed.set_footer(text="Vespera Chronicles • Session recorded")
        
        return embed

# --- CHRONICLES SCROLL ---
class ChroniclesScroll:
    """
    Generates the final campaign end-screen showing the complete legacy journey.
    """
    
    @staticmethod
    def create_chronicle_entry(phase: int, character_name: str, character_class: str,
                              player_name: str, key_achievement: str) -> dict:
        """Record a hero in the chronicles"""
        return {
            "phase": phase,
            "name": character_name,
            "class": character_class,
            "player": player_name,
            "achievement": key_achievement,
            "recorded_at": datetime.now().timestamp()
        }
    
    @staticmethod
    def generate_final_scroll(campaign_data: dict) -> str:
        """
        Generate the final chronicles scroll as a formatted string.
        """
        founder = campaign_data.get("founder", {})
        legend = campaign_data.get("legend", {})
        savior = campaign_data.get("savior", {})
        total_years = campaign_data.get("total_years", 0)
        unique_point = campaign_data.get("unique_point", "Unknown")
        
        scroll = f"""
╔════════════════════════════════════════════════════════════╗
║          THE CHRONICLES SCROLL OF THE VOID CYCLE           ║
╚════════════════════════════════════════════════════════════╝

**PHASE 1: THE FOUNDER ERA**
{founder.get('name', 'Unknown')} the {founder.get('class', 'Hero')}
Player: {founder.get('player', 'Unknown')}
Achievement: {founder.get('achievement', 'Established a legacy')}

**PHASE 2: THE LEGEND ERA** (20-50 years later)
{legend.get('name', 'Unknown')} the {legend.get('class', 'Legend')}
Player: {legend.get('player', 'Unknown')}
Achievement: {legend.get('achievement', 'Inherited their legacy')}

**PHASE 3: THE INTEGRATED ERA** (500-{500 + total_years} years later)
{savior.get('name', 'Unknown')} the Ascended {savior.get('class', 'Savior')}
Player: {savior.get('player', 'Unknown')}
Achievement: {savior.get('achievement', 'Completed the cycle')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**TOTAL YEARS ELAPSED:** {total_years} years
**WORLD'S UNIQUE POINT:** {unique_point}
**GENERATIONS BRIDGED:** 3 eras, 1 world, 1 unbroken legacy

May their names echo through eternity.

╔════════════════════════════════════════════════════════════╗
║            ~ END OF THE VOID CYCLE ~                       ║
╚════════════════════════════════════════════════════════════╝
        """
        return scroll

# --- DYNAMIC CHRONOS ENGINE (Randomized Time Skips) ---
class TimeSkipManager:
    """Manages randomized time skips between phases"""
    
    @staticmethod
    def generate_time_skip(target_phase: int) -> Tuple[int, str]:
        """Generate a random time skip for the target phase"""
        if target_phase not in PHASE_TIME_SKIPS:
            return 0, ""
        
        min_years, max_years = PHASE_TIME_SKIPS[target_phase]
        years = random.randint(min_years, max_years)
        
        if target_phase == 2:
            descriptors = [
                f"The world turns, and {years} years slip by like water.",
                f"Generations are born and age during {years} years of absence.",
                f"Civilizations shift and adapt across {years} long years.",
                f"Tales are written and forgotten in {years} years' time."
            ]
        else:  # Phase 3
            decades = years // 10
            centuries = years // 100
            descriptors = [
                f"Civilizations rise and fall across {years} years—{centuries} centuries of history.",
                f"The world forgets and remembers itself {centuries} times in {years} years.",
                f"Epochs pass in silence. {years} years have shattered the old world."
            ]
        
        flavor = random.choice(descriptors)
        return years, flavor
    
    @staticmethod
    def calculate_generations(years: int) -> Dict[str, int]:
        """Calculate generational impact of time skip"""
        generations = max(1, years // 25)
        dynasties = max(1, years // 100)
        
        return {
            "generations": generations,
            "dynasties": dynasties,
            "cultural_shifts": random.randint(2, 5) if years >= 500 else 1
        }
