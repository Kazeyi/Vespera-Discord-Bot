# --- START OF FILE dnd_cog.py ---
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
import asyncio
import random
import re
import sys
import time
import sqlite3
import gc
from typing import Tuple, List, Optional, Dict
from datetime import datetime
from enum import Enum
from groq import Groq
from dotenv import load_dotenv

# Import optimizations
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from global_optimization import intern_string, enable_wal_mode
from database import DB_FILE

from .utility_core.personality import VesperaPersonality as VP

load_dotenv()
GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
FAST_MODEL = "llama-3.3-70b-versatile"
try:
    from cogs.dnd_core.constants import ZONE_TAGS
    from cogs.dnd_core.models import (
        VoidCyclePhase, SpecializationPath, PhaseManager, BloodlineManager, 
        SessionModeManager, UniquePointSystem, AuraAccelerationSystem, SystematicSorcerySystem
    )
    from cogs.dnd_core.legacy import (
        LegacyVaultSystem, SoulRemnantManager, DestinyManager,
        LevelProgression, CharacterLockingSystem
    )
    from cogs.dnd_core.history import HistoryManager, SessionScribe, ChroniclesScroll, TimeSkipManager
    from cogs.dnd_core.combat import CombatTracker, ReactionSuggestionEngine, KillCamNarrator, PrecomputationEngine
    from cogs.dnd_core.rules import ActionEconomyValidator, RulebookRAG, RulebookIngestor, SRDLibrary
    from cogs.dnd_core.ai import DMOversight
    from cogs.dnd_core.helper import validate_dnd_access, is_dnd_player, get_hp_emoji, generate_truth_block
except ImportError:
    try:
        # Fallback for when running as a module where relative imports work (standard bot execution)
        from .dnd_core.constants import ZONE_TAGS
        from .dnd_core.models import (
            VoidCyclePhase, SpecializationPath, PhaseManager, BloodlineManager, 
            SessionModeManager, UniquePointSystem, AuraAccelerationSystem, SystematicSorcerySystem
        )
        from .dnd_core.legacy import (
            LegacyVaultSystem, SoulRemnantManager, DestinyManager,
            LevelProgression, CharacterLockingSystem
        )
        from .dnd_core.history import HistoryManager, SessionScribe, ChroniclesScroll, TimeSkipManager
        from .dnd_core.combat import CombatTracker, ReactionSuggestionEngine, KillCamNarrator, PrecomputationEngine
        from .dnd_core.rules import ActionEconomyValidator, RulebookRAG, RulebookIngestor, SRDLibrary
        from .dnd_core.ai import DMOversight
        from .dnd_core.helper import validate_dnd_access, is_dnd_player, get_hp_emoji, generate_truth_block
    except ImportError as e:
        print(f"Failed to import dnd_core modules: {e}")
        raise e
    # Fallback to local definitions will happen if deletions fail, but better to fail hard if we are refactoring.
    
class DNDCog(commands.Cog):
    """Unified D&D Cog with 2024 rules only"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.cooldowns = {}
        self.rate_limit = 3
        
        # Initialize DB with WAL mode (Optimization)
        try:
            enable_wal_mode(DB_FILE)
        except:
            pass
            
        RulebookRAG.init_rulebook_table()
        LegacyVaultSystem.create_legacy_vault_table()
        self._init_generational_tables()
        
        if not discord.opus.is_loaded():
            try:
                discord.opus.load_opus('libopus.so.0')
            except:
                pass
        
        # Start background optimization tasks
        self.cleanup_task.start()
        self.garbage_collection_task.start()

    def cog_unload(self):
        """Clean shutdown of background tasks"""
        self.cleanup_task.cancel()
        self.garbage_collection_task.cancel()

    @tasks.loop(hours=1)
    async def cleanup_task(self):
        """
        Clean up D&D cache and history.
        - Prunes old voice clients
        - Clears internal caches
        """
        # Clear local caches
        RulebookRAG.RULE_CACHE.clear()
        
        # Cleanup voice clients
        to_remove = []
        for guild_id, vc in self.voice_clients.items():
            if not vc.is_connected():
                to_remove.append(guild_id)
        for guild_id in to_remove:
            self.voice_clients.pop(guild_id, None)
            
        print("🧹 D&D Cog: Cache cleared")

    @tasks.loop(minutes=30)
    async def garbage_collection_task(self):
        """Force garbage collection to prevent memory leaks in D&D module"""
        collected = gc.collect()
        if collected > 0:
            print(f"🗑️ D&D GC: {collected} objects freed")
    
    def _init_generational_tables(self):
        """Initialize generational void cycle database tables"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Create dnd_session_mode table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_session_mode (
                guild_id TEXT PRIMARY KEY,
                session_mode TEXT DEFAULT 'Architect',
                custom_tone TEXT DEFAULT 'Standard',
                selected_biome TEXT DEFAULT 'forest',
                total_years_elapsed INTEGER DEFAULT 0,
                chronos_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create dnd_legacy_data table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_legacy_data (
                legacy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                character_name TEXT,
                character_class TEXT,
                character_level INTEGER,
                phase_number INTEGER,
                years_lived INTEGER,
                notable_deeds TEXT,
                bloodline_traits TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, character_name, phase_number)
            )''')
            
            # Create dnd_soul_remnants table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_soul_remnants (
                remnant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                character_name TEXT,
                class_name TEXT,
                level INTEGER,
                special_abilities TEXT,
                defeated BOOLEAN DEFAULT 0,
                phase_encountered INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create dnd_chronicles table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_chronicles (
                chronicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT UNIQUE,
                phase_1_hero TEXT,
                phase_2_hero TEXT,
                phase_3_hero TEXT,
                victory_scroll TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            conn.commit()
            conn.close()
            print("✅ Generational system tables initialized")
        except Exception as e:
            print(f"⚠️ Warning initializing generational tables: {e}")
    
    def is_rate_limited(self, user_id) -> bool:
        """Simple rate limiting - handles both int and string IDs"""
        now = time.time()
        
        # Convert to string for consistent key usage
        if isinstance(user_id, int):
            user_key = str(user_id)
        else:
            user_key = str(user_id)  # Already string like "npc_guardian_0"
        
        if user_key in self.cooldowns:
            if now - self.cooldowns[user_key] < self.rate_limit:
                return True
        
        self.cooldowns[user_key] = now
        return False
    
    def validate_dnd_thread(self, interaction_or_channel):
        """Validate thread and return config data"""
        try:
            if hasattr(interaction_or_channel, 'channel'):
                channel = interaction_or_channel.channel
                guild_id = interaction_or_channel.guild.id
            else:
                channel = interaction_or_channel
                guild_id = channel.guild.id
            
            if not isinstance(channel, discord.Thread):
                return False, "❌ Not a D&D thread", None
            
            config = get_dnd_config(guild_id)
            if not config:
                return False, "❌ D&D not configured", None
            
            if int(config[0]) != channel.parent_id:
                return False, "❌ Invalid thread channel", None
            
            return True, config[1], config[2], config[3], config[4], "5e 2024", config[6], config[9] or "Narrative"
        
        except Exception as e:
            print(f"[DND] Validation error: {e}")
            return False, "❌ Configuration error", None
    
    async def get_dm_response(self, action: str, thread_id: int, location: str, summary: str, 
                            stats: str, guild_id: int, rulebook: str, mode: str, has_heroic_inspiration: bool, 
                            user_id: int = None) -> dict:
        """Optimized AI response generation with RAG, Architect Mode tone shifting, and Chain of Thought prompting"""
        
        # ===== TYPE SAFETY: Ensure action is a string =====
        # Handle edge cases where action might not be a string
        if not isinstance(action, str):
            action = str(action) if action else "Player takes action"
        
        # Get session mode to determine if automatic tone shifting is enabled
        try:
            session_mode_data = get_session_mode(guild_id)
            session_mode = session_mode_data[0] if session_mode_data else SessionModeManager.ARCHITECT
            current_tone = session_mode_data[1] if session_mode_data and len(session_mode_data) > 1 else "Standard"
        except:
            # Table might not exist yet during migration, use defaults
            session_mode = SessionModeManager.ARCHITECT
            current_tone = "Standard"
        
        # Auto-detect scene context for Architect Mode
        scene_context = "action"
        if "attack" in action.lower() or "fight" in action.lower():
            scene_context = "combat_start"
        elif "boss" in summary.lower() and ("defeated" in action.lower() or "kill" in action.lower()):
            scene_context = "boss_defeat"
        elif "time" in action.lower() and "skip" in action.lower():
            scene_context = "time_skip"
        
        # Apply automatic tone in Architect Mode (will persist once columns migrate)
        if session_mode == SessionModeManager.ARCHITECT:
            current_tone = AutomaticToneShifter.get_automatic_tone(scene_context)
            # Note: update_session_tone will be called after database migration
            # For now, tone is calculated but not persisted
        
        # Get character data for pre-computation
        char = None
        attack_result_data = None  # Store for dice reveal embed
        if user_id:
            char = get_character(user_id, guild_id)
        
        # Get campaign phase for truth block generation
        phase, _ = get_dnd_campaign_data(guild_id)
        
        # Generate truth block with pre-computation (includes phase 3 legacy haunting and zone tags)
        truth_block = generate_truth_block(action, char, phase=phase, guild_id=guild_id, location=location)
        
        # Extract attack result from truth block if it exists (for dice reveal)
        if "[ATTACK RESULT]" in truth_block:
            # Parse the attack result from truth block
            import re
            natural_match = re.search(r"Natural Roll: (\d+)", truth_block)
            total_match = re.search(r"Total \(with \+(\d+)\): (\d+)", truth_block)
            ac_match = re.search(r"Target AC: (\d+)", truth_block)
            outcome_match = re.search(r"Outcome: (\w+)", truth_block)
            roll_type_match = re.search(r"Roll Type: ([A-Z ]+)", truth_block)
            
            if natural_match and total_match and ac_match and outcome_match:
                attack_result_data = {
                    "natural_roll": int(natural_match.group(1)),
                    "attack_bonus": int(total_match.group(1)),
                    "total_roll": int(total_match.group(2)),
                    "target_ac": int(ac_match.group(1)),
                    "outcome": outcome_match.group(1),
                    "roll_type": roll_type_match.group(1) if roll_type_match else "NORMAL"
                }
        
        # Get relevant rules using RAG (enhanced with precision)
        rule_keywords = []
        words = action.lower().split()
        dnd_terms = ["cast", "attack", "save", "check", "spell", "ability", "skill", "rest", 
                     "damage", "hit", "critical", "advantage", "disadvantage", "concentration"]
        
        # Enhanced keyword extraction with specificity
        for word in words:
            if word in dnd_terms or any(term in word for term in ["fireball", "stealth", "concentration", "inspiration", "dice", "roll"]):
                # Add "mechanics" suffix for precision
                rule_keywords.append(f"{word} mechanics 5e")
        
        rule_context = ""
        for keyword in set(rule_keywords[:3]):
            # Use enhanced RAG lookup
            rules = RulebookRAG.lookup_rule(keyword, limit=2)
            if not rules:
                # Try without "mechanics" suffix
                fallback_keyword = keyword.replace(" mechanics 5e", "")
                rules = RulebookRAG.lookup_rule(fallback_keyword, limit=2)
            
            for rule_name, rule_text in rules:
                rule_context += f"[Rule: {rule_name}] {rule_text[:200]}\n\n"
        
        history = HistoryManager.get_optimized_history(thread_id, limit=6)
        context = "\n".join([f"{role}: {content[:100]}" for role, content in history])
        
        combatants = get_combat_order(thread_id)
        combat_text = "\n".join([
            f"{get_hp_emoji(hp, max_hp)} {name} ({hp}/{max_hp})" 
            for _, name, _, hp, max_hp, _, _ in combatants[:5]
        ]) if combatants else "No active combat."
        
        protagonist, destiny_score = get_session_protagonist(guild_id)
        
        # Get tone context for prompt
        tone_context = AutomaticToneShifter.get_tone_context(current_tone)
        
        # Include explicit quest name and theme to reduce hallucinations about location
        quest_name = "Unknown"
        quest_theme = location
        try:
            cfg = get_dnd_config(guild_id)
            if cfg and cfg[10]:
                qd = json.loads(cfg[10]) if isinstance(cfg[10], str) else cfg[10]
                if isinstance(qd, dict):
                    quest_name = qd.get('name', quest_name)
                    quest_theme = qd.get('theme', quest_theme)
        except Exception:
            pass

        # ===== ENHANCED PROMPT WITH CHAIN OF THOUGHT =====
        prompt = f"""D&D DM Response Generator (2024 Rules) - CHAIN OF THOUGHT REQUIRED

{truth_block}

CURRENT GAME STATE:
- Quest: {quest_name}
- Quest Theme: {quest_theme}
- Current Location: {location}
- Game Mode: {mode}
- Campaign Phase: {phase}
- Narrative Tone: {current_tone} - {tone_context}
- Active Combatants: {combat_text}
- Party Status: {stats}
- Session Context: {summary[:200]}
- Protagonist: {protagonist or "None"} (Destiny Score: {destiny_score})

RELEVANT RULES (FROM RAG):
{rule_context}

RECENT HISTORY:
{context}

PLAYER ACTION: {action}

IMPORTANT: The current quest is set in a {quest_theme} environment. All descriptions should match this theme.

=== REQUIREMENTS FOR YOUR RESPONSE ===

STEP 1: MECHANICS CHECK (REQUIRED)
First, analyze the action against the TRUTH BLOCK values and RAG rules:
1. Confirm which specific rule from the RAG applies (or state "No specific rule found")
2. Explain how the TRUTH BLOCK values determine success/failure
3. Note any conditions, concentrations, or special effects that trigger

STEP 2: NARRATION (REQUIRED)
Second, write the narrative consequence (2-3 sentences) in the "{current_tone}" tone.

STEP 3: RESPONSE FORMAT (STRICT JSON)
Return exactly this JSON structure:
{{
  "mechanics_check": "Your step-by-step mechanical analysis here",
  "story": "Your narrative description here",
  "music": "{location}",
  "damage_events": [],
  "suggestions": ["action1", "action2", "action3"],
  "grant_heroic_inspiration": false
}}

CRITICAL INSTRUCTIONS:
- NEVER change the TRUTH BLOCK values
- CRITICAL HITS: Dice are doubled, modifiers are NOT doubled (e.g., 1d8+3 crit = 2d8+3, NOT 2d8+6)
- If RAG context doesn't contain the rule, say in mechanics_check: "I am unsure of the specific rule, how would you like to handle this?"
- Use Species terminology, not Race
- On natural 20, grant Heroic Inspiration
- For phase {phase}, advance story appropriately
- Heroic Inspiration allows rerolls after seeing result
"""
        
        try:
            # Enhanced error handling with retry logic
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: GROQ_CLIENT.chat.completions.create(
                                model=FAST_MODEL,
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.7,
                                max_tokens=500,
                                response_format={"type": "json_object"}
                            )
                        ),
                        timeout=25.0
                    )
                    break  # Success, exit retry loop
                except asyncio.TimeoutError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Brief delay before retry
                        continue
                    else:
                        raise  # Final attempt failed
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1 and "rate_limit" not in str(e).lower():
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise
            
            # Robust JSON parsing with fallback
            try:
                result = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as je:
                # AI returned malformed JSON, create fallback response
                print(f"[get_dm_response] JSON decode error: {je}")
                result = {
                    "mechanics_check": "Unable to parse AI response.",
                    "story": response.choices[0].message.content[:200] if response.choices[0].message.content else "The action unfolds.",
                    "music": location,
                    "damage_events": [],
                    "suggestions": ["Continue", "Investigate", "Rest"],
                    "grant_heroic_inspiration": False
                }
            
            # ===== ENHANCE SUGGESTIONS WITH SMART ACTION ENGINE =====
            # Analyze the action for tactical threats and suggest reactions
            try:
                threat_analysis = ReactionSuggestionEngine.analyze_threat(
                    action=action,
                    character_data=char,
                    combat_context=f"In {location}, {summary[:100]}"
                )
            except Exception as e:
                print(f"[get_dm_response] Threat analysis error: {e}")
                threat_analysis = None
            
            # Merge smart suggestions with AI suggestions
            ai_suggestions = result.get("suggestions", ["Continue", "Investigate", "Rest"])
            if threat_analysis.get("threat_level") in ["MEDIUM", "HIGH"]:
                # Prioritize reaction-based suggestions for incoming threats
                smart_suggestions = threat_analysis.get("suggested_reactions", [])[:2]
                combined_suggestions = smart_suggestions + ai_suggestions
                result["suggestions"] = list(dict.fromkeys(combined_suggestions))[:4]  # Remove duplicates, max 4
            
            # Add attack result data for dice reveal embed
            if attack_result_data:
                result['attack_result'] = attack_result_data
            
            # Extract mechanics check for logging/debugging
            if "mechanics_check" in result:
                # Log truth block usage for accuracy tracking
                TruthBlockLogger.log_truth_block_usage(
                    guild_id=guild_id,
                    user_id=user_id if user_id else 0,
                    action=action,
                    truth_block=truth_block,
                    ai_response=result,
                    timestamp=time.time()
                )
            
            # Ensure story field exists
            if "story" not in result:
                result["story"] = "The story continues..."
            
            return result
            
        except asyncio.TimeoutError:
            return {
                "mechanics_check": "Timeout analyzing mechanics",
                "story": "The Dungeon Master ponders your action...",
                "music": location,
                "suggestions": ["Wait", "Investigate", "Attack"],
                "grant_heroic_inspiration": False
            }
        except Exception as e:
            print(f"[DND] AI Error: {e}")
            return {
                "mechanics_check": f"Error in analysis: {str(e)[:50]}",
                "story": "The threads of fate tremble with your decision...",
                "music": location,
                "suggestions": ["Proceed cautiously", "Regroup"],
                "grant_heroic_inspiration": False
            }
    
    async def launch_game_logic(self, interaction: discord.Interaction, phase: int, rulebook: str, is_continue: bool = False):
        """
        Launch or continue a game session.
        
        Args:
            interaction: Discord interaction
            phase: Campaign phase (1, 2, or 3)
            rulebook: D&D rulebook version (e.g., "5e 2024")
            is_continue: If True, resumes existing session without prologue
        """
        update_game_mode(interaction.guild.id, "Narrative")
        
        config = get_dnd_config(interaction.guild.id)
        quest_data = None
        
        # ===== LOAD QUEST DATA SAFELY =====
        if config and config[10]:
            try:
                # Parse quest data from config
                if isinstance(config[10], str):
                    quest_data = json.loads(config[10])
                elif isinstance(config[10], dict):
                    quest_data = config[10]
                else:
                    quest_data = None
            except Exception as e:
                print(f"[launch_game_logic] Error parsing quest_data: {e}")
                quest_data = None
        
        # ===== CREATE DEFAULT QUEST IF NEEDED =====
        if not quest_data or not isinstance(quest_data, dict):
            # Prefer using the saved current location from config so we don't randomize
            current_location = (config[1].lower() if config and config[1] else "").strip() if config else ""

            # Map common location synonyms to our conquest keys
            if current_location in ["ocean", "sea", "water"]:
                theme = "ocean"
            elif current_location in ["desert", "sands", "dune"]:
                theme = "desert"
            elif current_location in ["volcano", "lava", "fire"]:
                theme = "volcano"
            elif current_location in ["forest", "woods"]:
                theme = "forest"
            elif current_location in ["tavern", "city"]:
                theme = current_location or "tavern"
            else:
                # Fallback to ocean if unknown
                theme = "ocean"

            if theme in CONQUEST_PATHS:
                quest_data = CONQUEST_PATHS[theme]["p1"].copy()
            else:
                # final fallback
                theme = "ocean"
                quest_data = CONQUEST_PATHS[theme]["p1"].copy()

            quest_data["path_key"] = theme
            # Persist a safe JSON representation
            try:
                update_quest_data(interaction.guild.id, json.dumps(quest_data))
            except Exception:
                # best-effort; not fatal
                pass

        # ===== ENSURE QUEST_DATA IS ALWAYS A DICT =====
        if not isinstance(quest_data, dict):
            theme = "ocean"
            quest_data = CONQUEST_PATHS[theme]["p1"].copy()
            quest_data["path_key"] = theme

        # Ensure the stored config location matches the quest theme; set if missing
        try:
            conf_loc = (config[1].lower() if config and config[1] else "").strip()
        except Exception:
            conf_loc = ""

        quest_theme = quest_data.get("theme", quest_data.get("path_key", "ocean")).lower() if isinstance(quest_data, dict) else "ocean"

        # If the config location is empty, set it to the quest theme
        if not conf_loc:
            try:
                update_dnd_location(interaction.guild.id, quest_theme)
            except Exception:
                pass
        else:
            # If they disagree (e.g., config says 'ocean' but quest_data theme is 'desert'), prefer quest theme
            if quest_theme and quest_theme not in conf_loc and not any(x in conf_loc for x in [quest_theme, "tavern"]):
                try:
                    update_dnd_location(interaction.guild.id, quest_theme)
                except Exception:
                    pass
        
        # ===== DETERMINE IF RESUMING EXISTING SESSION =====
        # Check both is_continue parameter and existing campaign summary
        is_resume = is_continue or (config and config[2] and config[2] != "New Campaign Started.")
        
        # ===== SAFELY GET QUEST NAME =====
        quest_name = quest_data.get('name', 'Adventure') if isinstance(quest_data, dict) else 'Adventure'
        quest_theme = quest_data.get('theme', quest_data.get('path_key', 'forest')) if isinstance(quest_data, dict) else 'forest'
        
        if is_resume:
            # RESUME EXISTING SESSION - Use existing summary (no prologue)
            story = config[2] if config and config[2] else "Your adventure continues..."
            title = f"↩️ {quest_name} (Resumed)"
        else:
            # NEW SESSION - Show prologue with narrative setup
            story = f"**{quest_name}**\n\nYour adventure begins in a {quest_theme} setting. The prophecy of 12 heroes must be fulfilled. What will you do first?"
            title = f"📖 {quest_name}"
            update_dnd_summary(interaction.guild.id, story)
        
        embed = discord.Embed(
            title=title,
            description=story,
            color=LOCATION_THEMES.get(quest_theme, 0x3498DB)
        )
        embed.add_field(name="Rules", value="2024 Edition", inline=True)
        embed.add_field(name="Location", value=quest_theme.title(), inline=True)
        embed.set_footer(text="Vespera // Where legends are written")
        
        # Use different action suggestions based on resume vs new
        if is_resume:
            suggestions = ["Continue exploring", "Check inventory", "Regroup with allies", "Assess situation"]
        else:
            suggestions = ["Explore the area", "Talk to locals", "Check equipment", "Form a plan"]
        
        view = DNDGameView(
            self, 
            interaction,
            suggestions=suggestions
        )
        
        await interaction.followup.send(embed=embed, view=view)
        
        # Log the session event
        if is_resume:
            add_dnd_history(interaction.channel.id, "DM", f"Session resumed: {quest_name}")
        else:
            add_dnd_history(interaction.channel.id, "DM", f"Session started: {quest_name}")
    
    async def run_dnd_turn(self, interaction: discord.Interaction, action: str, already_deferred: bool = True):
        """
        Process a player's action/turn in the D&D game.
        
        This method:
        1. Validates the player is in a D&D thread
        2. Gets the DM's AI response to the player's action
        3. Updates game state (location, HP, conditions, etc.)
        4. Displays results with ASCII map, combatants, and available actions
        5. Shows destiny roll (if available) and previous roll caching
        
        Args:
            interaction: Discord interaction from the player
            action: What the player wants to do (text description or action selection)
            already_deferred: Whether response already deferred (skip defer if True)
        """
        # ===== RATE LIMITING =====
        # Prevent spam by rate limiting turns
        if self.is_rate_limited(interaction.user.id):
            if not already_deferred:
                await interaction.response.defer()
            await interaction.followup.send("⏳ Please wait a moment before your next action.", ephemeral=True)
            return
        
        # ===== DEFER RESPONSE =====
        # Discord requires us to acknowledge interaction within 3 seconds
        if not already_deferred:
            await interaction.response.defer()
        
        # ===== VALIDATE D&D CONTEXT =====
        # Make sure this is a valid D&D thread with proper config
        valid, *config_data = self.validate_dnd_thread(interaction)
        if not valid:
            await interaction.followup.send(config_data[0], ephemeral=True)
            return
        
        # Extract config: location, summary, (unused), (unused), rulebook, (unused), mode
        location, summary, _, _, rulebook, _, mode = config_data
        
        # ===== GET PLAYER CHARACTER =====
        # Fetch the player's character sheet
        char = get_character(interaction.user.id, interaction.guild.id)
        stats = f"{char.get('name', 'Unknown')}: {char.get('hp', 0)}/{char.get('max_hp', 1)} HP" if char else "Unknown character"
        
        # ===== LOG ACTION TO HISTORY =====
        # Record this action in the session history for context in future turns
        add_dnd_history(interaction.channel.id, interaction.user.display_name, action[:200])
        
        # ===== GET AI DM RESPONSE =====
        # Call Groq API to get DM's narrative response to the player's action
        dm_response = await self.get_dm_response(
            action, interaction.channel.id, location, summary, stats,
            interaction.guild.id, rulebook, mode, char.get('heroic_inspiration', False) if char else False,
            user_id=interaction.user.id
        )
        
        # Extract key data from DM response
        story = dm_response.get("story", "The story continues...")
        mechanics_check = dm_response.get("mechanics_check", "")
        new_location = dm_response.get("music", location)  # "music" is location in response format
        
        # ===== UPDATE GAME STATE =====
        # Persist changes to the database
        if new_location != location:
            update_dnd_location(interaction.guild.id, new_location)
        
        update_dnd_summary(interaction.guild.id, story[:500])  # Update session summary
        add_dnd_history(interaction.channel.id, "DM", story[:300])  # Log DM response
        
        # ===== GRANT HEROIC INSPIRATION (D&D 2024) =====
        # Natural 20s or critical successes grant inspiration for future rerolls
        if dm_response.get("grant_heroic_inspiration") and char:
            char['heroic_inspiration'] = True
            update_character(interaction.user.id, interaction.guild.id, char)
        
        # ===== PROCESS DAMAGE EVENTS =====
        # Handle any damage dealt to combatants
        updates = []
        damage_events = dm_response.get("damage_events", [])
        
        for event in damage_events:
            target = event.get("target", "")
            amount = event.get("amount", 0)
            
            # Find matching combatant and apply damage
            combatants = get_combat_order(interaction.channel.id)
            for combatant in combatants:
                cid, cname, _, _, _, is_monster, _ = combatant
                if target.lower() in cname.lower():
                    # Update combatant HP
                    new_hp = update_combatant_hp(interaction.channel.id, cid, -amount)
                    
                    # Check for concentration saves (if they're concentrating on a spell)
                    conditions = get_combatant_conditions(interaction.channel.id, cid)
                    if "concentrating" in conditions.lower() and amount > 0:
                        dc = max(10, amount // 2)  # DC = damage / 2, minimum 10
                        updates.append(f"⚠️ **{cname} needs CON Save (DC {dc}) to maintain concentration!**")
                    
                    # Log HP change
                    updates.append(f"{cname}: {new_hp} HP ({-amount} damage)")
                    
                    # Remove dead monsters from combat and trigger kill cam
                    if new_hp <= 0 and is_monster == 1:
                        remove_combatant(interaction.channel.id, cid)
                        updates.append(f"☠️ {cname} defeated!")
                        
                        # === KILL CAM NARRATION ===
                        # Generate cinematic "Final Blow" narration
                        try:
                            kill_cam_narration = await KillCamNarrator.generate_kill_cam(
                                character_name=char.get('name', interaction.user.display_name) if char else interaction.user.display_name,
                                monster_name=cname,
                                player_action=action,
                                final_damage=amount,
                                attack_type=dm_response.get('attack_type', 'unknown')
                            )
                            
                            # Create kill cam embed
                            kill_cam_embed = KillCamNarrator.create_kill_cam_embed(
                                character_name=char.get('name', interaction.user.display_name) if char else interaction.user.display_name,
                                monster_name=cname,
                                narration=kill_cam_narration
                            )
                            
                            # Send kill cam as separate message
                            await interaction.followup.send(embed=kill_cam_embed)
                        except Exception as e:
                            print(f"[KillCam] Error sending kill cam: {e}")
                    
                    # Update player character HP if they took damage
                    if cid == str(interaction.user.id) and char:
                        char['hp'] = new_hp
                        update_character(interaction.user.id, interaction.guild.id, char)
        
        # ===== BUILD RESPONSE EMBED =====
        # Create the Discord embed to show the DM's narrative response
        # Use dynamic color based on party health
        dynamic_color = get_dynamic_embed_color(interaction.channel.id, new_location)
        
        embed = discord.Embed(
            description=story,  # DM's narrative
            color=dynamic_color  # Dynamic color based on party health & encounter type
        )
        
        # ===== DICE REVEAL: ENHANCED COMBAT HEADER =====
        # Show the actual dice rolls for transparency and trust
        if dm_response.get('attack_result'):
            atk = dm_response['attack_result']
            
            # Build detailed dice reveal string
            if atk['roll_type'] == "ADVANTAGE":
                dice_reveal = f"🎲 [{atk['all_rolls'][0]}, {atk['all_rolls'][1]}] → **{atk['natural_roll']}** (ADV) + {atk['attack_bonus']} = **{atk['total_roll']}**"
            elif atk['roll_type'] == "DISADVANTAGE":
                dice_reveal = f"🎲 [{atk['all_rolls'][0]}, {atk['all_rolls'][1]}] → **{atk['natural_roll']}** (DIS) + {atk['attack_bonus']} = **{atk['total_roll']}**"
            else:
                dice_reveal = f"🎲 **[{atk['natural_roll']}]** + {atk['attack_bonus']} = **{atk['total_roll']}**"
            
            # Determine outcome emoji and text
            if atk['outcome'] == "CRITICAL_HIT":
                outcome_emoji = "💥"
                outcome_text = "CRITICAL HIT!"
                outcome_color = "🔴"
            elif atk['outcome'] == "HIT":
                outcome_emoji = "✅"
                outcome_text = "HIT"
                outcome_color = "🟢"
            elif atk['outcome'] == "CRITICAL_MISS":
                outcome_emoji = "💀"
                outcome_text = "CRITICAL MISS!"
                outcome_color = "⚫"
            else:
                outcome_emoji = "❌"
                outcome_text = "MISS"
                outcome_color = "🔵"
            
            dice_reveal += f" vs AC **{atk['target_ac']}** {outcome_color} {outcome_emoji} **{outcome_text}**"
            
            embed.add_field(
                name="⚔️ Attack Roll",
                value=dice_reveal,
                inline=False
            )
        
        # Set author as the player who took the action
        embed.set_author(
            name=f"🎲 {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        
        # ===== ADD ASCII MAP (if available) =====
        # Try to add an ASCII representation of the current location/combat
        try:
            # Get current location theme
            location_theme = LOCATION_THEMES.get(new_location, "dungeon")
            
            # Generate ASCII map based on location
            # Format: Simple ASCII grid representing the area
            ascii_map = f"```\n┌─────────────────────┐\n│  {new_location.upper():^17}  │\n└─────────────────────┘\n```"
            
            # Get active combatants to show on map
            combatants = get_combat_order(interaction.channel.id)
            if combatants:
                # Build combatant list with HP bars
                combat_ascii = "```\nActive Combatants:\n"
                for cid, cname, init, hp, max_hp, is_monster, _ in combatants[:5]:
                    # Calculate HP bar (20 characters)
                    bar_filled = int((hp / max_hp) * 20) if max_hp > 0 else 0
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)
                    combat_ascii += f"{cname}: [{bar}] {hp}/{max_hp}\n"
                combat_ascii += "```"
                
                # Only add if not too long
                if len(combat_ascii) < 1024:
                    embed.add_field(name="⚔️ Battle Map", value=combat_ascii, inline=False)
        except:
            pass  # Gracefully skip ASCII map if error
        
        # ===== ADD MECHANICS CHECK (if available) =====
        # Show the AI's mechanical analysis of the action
        if mechanics_check and len(mechanics_check) > 10:
            embed.add_field(
                name="⚙️ Mechanics Analysis",
                value=mechanics_check[:200] + ("..." if len(mechanics_check) > 200 else ""),
                inline=False
            )
        
        # Get user's preferred language for footer
        user_lang = get_target_language(interaction.user.id)
        embed.set_footer(text=f"Language: {user_lang}" if user_lang and user_lang != "English" else "Language: English")
        
        # ===== ADD GAME UPDATES (damage, status, etc.) =====
        # Show any mechanical changes that occurred this turn
        if updates:
            embed.add_field(
                name="⚡ Updates",
                value="\n".join(updates[:5]),  # Max 5 updates per turn
                inline=False
            )
        
        # ===== ADD PLAYER STATUS =====
        # Show the acting player's current HP and status
        if char:
            embed.add_field(
                name="💚 Your Status",
                value=f"{char.get('hp', 0)}/{char.get('max_hp', 1)} HP",
                inline=True
            )
            
            # ===== SHOW HEROIC INSPIRATION AVAILABILITY =====
            # D&D 2024: Show if player has inspiration to spend on reroll
            if char.get('heroic_inspiration', False):
                embed.add_field(
                    name="✨ Heroic Inspiration",
                    value="Available (use to reroll)",
                    inline=True
                )
        
        # ===== GET DESTINY ROLL (if available) =====
        # Show player's destiny score and if they've already rolled
        try:
            # Get this player's destiny roll from the launch
            protagonist, destiny_score = get_session_protagonist(interaction.guild.id)
            if protagonist == interaction.user.id or protagonist is None:
                # Show destiny roll as a persistent stat
                embed.add_field(
                    name="🔮 Destiny Roll",
                    value=f"**{destiny_score}**",
                    inline=True
                )
        except:
            pass  # Skip if destiny system not available
        
        # ===== CREATE ACTION VIEW =====
        # Build buttons/dropdowns for next action
        view = DNDGameView(
            self,
            interaction,
            suggestions=dm_response.get("suggestions", ["Continue", "Investigate", "Rest"]),
            rulebook=rulebook,
            has_heroic_inspiration=char.get('heroic_inspiration', False) if char else False
        )
        
        # Add mechanics view button if mechanics check exists
        if mechanics_check and len(mechanics_check) > 10:
            mechanics_btn = discord.ui.Button(
                label="🔍 View Full Mechanics",
                style=discord.ButtonStyle.secondary,
                row=3
            )
            
            async def show_mechanics(btn_interaction: discord.Interaction):
                mechanics_view = MechanicsView(mechanics_check, truth_block, action)
                await btn_interaction.response.send_message(
                    "⚙️ **Detailed Mechanics Analysis**",
                    view=mechanics_view,
                    ephemeral=True
                )
            
            mechanics_btn.callback = show_mechanics
            view.add_item(mechanics_btn)
        
        # Add target selection button for combat scenarios
        combatants = get_combat_order(interaction.channel.id)
        if combatants and len(combatants) > 1:
            target_btn = discord.ui.Button(
                label="🎯 Select Target",
                style=discord.ButtonStyle.primary,
                row=3
            )
            
            async def show_target_selector(btn_interaction: discord.Interaction):
                target_view = TargetSelectionView(self, interaction, combatants)
                embed = discord.Embed(
                    title="🎯 Target Selection",
                    description="Choose your target and describe your action:",
                    color=0xE74C3C
                )
                await btn_interaction.response.send_message(embed=embed, view=target_view, ephemeral=True)
            
            target_btn.callback = show_target_selector
            view.add_item(target_btn)
        
        # ===== SEND RESPONSE =====
        # Post the embed with action buttons
        await interaction.followup.send(embed=embed, view=view)
    
    # --- BASIC COMMANDS ---
    
    @app_commands.command(name="setup_dnd", description="Configure D&D for this server")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_dnd(self, interaction: discord.Interaction, 
                       channel: discord.TextChannel,
                       role: discord.Role = None):
        """Set up D&D with parent channel and optional role restriction - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can configure D&D!",
                ephemeral=True
            )
            return
        
        role_id = role.id if role else None
        save_dnd_config(interaction.guild.id, channel.id, role_id)
        
        embed = discord.Embed(
            title="🎲 D&D Configured (2024 Rules)",
            description=f"Dungeons & Dragons has been configured for {channel.mention}",
            color=0x3498DB
        )
        if role:
            embed.add_field(name="Role Restriction", value=role.mention)
        embed.add_field(name="Configured by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Use /start_session to begin")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="start_session", description="Start or continue a D&D session")
    @is_dnd_player()
    async def start_session(self, interaction: discord.Interaction):
        """Start a new session or continue existing one"""
        # ===== IMMEDIATE DEFER (Required within 3 seconds) =====
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction expired, can't respond
            print("[start_session] Interaction expired before defer")
            return
        except Exception as e:
            print(f"[start_session] Defer error: {e}")
            return
        
        try:
            if not await validate_dnd_access(interaction):
                embed = discord.Embed(
                    title="⛔ Access Denied",
                    description="You don't have permission to start D&D sessions.",
                    color=0xE74C3C
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            valid, *_ = self.validate_dnd_thread(interaction)
            if not valid:
                await interaction.followup.send("❌ This is not a valid D&D thread.", ephemeral=True)
                return
            
            # Get config with timeout protection
            try:
                phase, legends = get_dnd_campaign_data(interaction.guild.id)
                config = get_dnd_config(interaction.guild.id)
            except Exception as e:
                print(f"[start_session] Config error: {e}")
                phase, legends = 1, []
                config = None
            
            has_save = config and config[2] and config[2] != "New Campaign Started."
            
            quest_title = "Adventure Awaits"
            if config and config[10]:
                try:
                    quest_data = json.loads(config[10])
                    quest_title = quest_data.get('name', quest_title)
                except:
                    pass
            
            view = SessionLobbyView(
                self,
                interaction,
                phase,
                has_save,
                quest_title=quest_title,
                legends=legends
            )
            
            embed = view.update_embed()
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"[start_session] Error: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Error starting session: {str(e)[:100]}",
                    ephemeral=True
                )
            except:
                pass
    
    
    @app_commands.command(name="do", description="Perform an action in the D&D session")
    @is_dnd_player()
    async def do_action(self, interaction: discord.Interaction, action: str):
        """Perform an action (rate limited)"""
        if len(action) > 300:
            await interaction.response.send_message("❌ Action too long (max 300 characters)", ephemeral=True)
            return
        
        await self.run_dnd_turn(interaction, action)
    
    @app_commands.command(name="import_character", description="Import character from D&D Beyond or text")
    @is_dnd_player()
    async def import_character(self, interaction: discord.Interaction, character_text: str):
        """Import character sheet"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            lines = character_text.split('\n')
            char_data = {
                "name": "Adventurer",
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "heroic_inspiration": False,
                "weapon_masteries": []
            }
            
            for line in lines[:20]:
                line_lower = line.lower()
                if "name:" in line_lower:
                    char_data["name"] = line.split(":", 1)[1].strip()
                elif "hp:" in line_lower or "hit points:" in line_lower:
                    try:
                        hp_part = line.split(":", 1)[1].strip()
                        if "/" in hp_part:
                            current, max_hp = hp_part.split("/")
                            char_data["hp"] = int(current.strip())
                            char_data["max_hp"] = int(max_hp.strip())
                        else:
                            char_data["hp"] = int(hp_part)
                            char_data["max_hp"] = int(hp_part)
                    except:
                        pass
                elif "ac:" in line_lower or "armor class:" in line_lower:
                    try:
                        char_data["ac"] = int(line.split(":", 1)[1].strip())
                    except:
                        pass
                # Migrate from old keys
                if "race:" in line_lower:
                    char_data["species"] = line.split(":", 1)[1].strip()
            
            update_character(interaction.user.id, interaction.guild.id, char_data)
            
            embed = discord.Embed(
                title="✅ Character Imported",
                description=f"**{char_data['name']}** ready for adventure!",
                color=0x2ECC71
            )
            embed.add_field(name="HP", value=f"{char_data['hp']}/{char_data['max_hp']}", inline=True)
            embed.add_field(name="AC", value=str(char_data['ac']), inline=True)
            if 'species' in char_data:
                embed.add_field(name="Species", value=char_data['species'], inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error importing character: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="roll_initiative", description="Roll initiative for combat")
    @is_dnd_player()
    async def roll_initiative(self, interaction: discord.Interaction):
        """Roll initiative and start combat mode"""
        await interaction.response.defer()
        
        valid, *_ = self.validate_dnd_thread(interaction)
        if not valid:
            await interaction.followup.send("❌ Not a valid D&D thread", ephemeral=True)
            return
        
        update_game_mode(interaction.guild.id, "Combat")
        
        char = get_character(interaction.user.id, interaction.guild.id)
        char_name = char.get('name', interaction.user.display_name) if char else interaction.user.display_name
        
        initiative = random.randint(1, 20)
        if char and 'dex' in char:
            initiative += (char['dex'] - 10) // 2
        
        add_combatant(
            interaction.channel.id,
            interaction.user.id,
            char_name,
            initiative,
            char.get('hp', 10) if char else 10,
            char.get('max_hp', 10) if char else 10
        )
        
        combatants = get_combat_order(interaction.channel.id)
        
        embed = discord.Embed(
            title="⚔️ Initiative Rolled",
            description=f"{char_name} rolls **{initiative}** for initiative!",
            color=0xE74C3C
        )
        
        if combatants:
            order = "\n".join([f"{i+1}. {name} ({score})" for i, (_, name, score, _, _, _, _) in enumerate(combatants)])
            embed.add_field(name="Combat Order", value=order, inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="long_rest", description="Take a long rest to heal and recover")
    @is_dnd_player()
    async def long_rest(self, interaction: discord.Interaction):
        """Take a long rest"""
        await interaction.response.defer()
        
        perform_long_rest_db(interaction.channel.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="⛺ Long Rest Complete",
            description="The party rests, recovering hit points and abilities.",
            color=0x3498DB
        )
        embed.add_field(name="Effects", value="• Full HP recovery\n• Conditions removed\n• Heroic Inspiration regained", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="time_skip", description="Advance to next Phase with randomized time skip")
    @app_commands.default_permissions(manage_guild=True)
    async def time_skip(self, interaction: discord.Interaction):
        """Advance campaign phase with dynamic Chronos Engine (randomized time skips)"""
        await interaction.response.defer()
        
        phase, _ = get_dnd_campaign_data(interaction.guild.id)
        
        # Determine target phase
        if phase == 1:
            target_phase = 2
        elif phase == 2:
            target_phase = 3
        else:
            await interaction.followup.send("❌ Campaign already complete (Phase 3)", ephemeral=True)
            return
        
        # Generate randomized time skip using Chronos Engine
        years, time_flavor = TimeSkipManager.generate_time_skip(target_phase)
        generations = TimeSkipManager.calculate_generations(years)
        
        # Update total years elapsed
        total_years = update_total_years(interaction.guild.id, years)
        
        config = get_dnd_config(interaction.guild.id)
        party = json.loads(config[6]) if config and config[6] else []
        
        # For Phase 2->3 transition, create legacy data and soul remnants
        if target_phase == 3:
            for user_id in party:
                if not str(user_id).startswith("npc_"):
                    char = get_character(user_id, interaction.guild.id)
                    if char:
                        legacy_data = {
                            "user_id": user_id,
                            "p2_character_name": char.get('name', 'Unknown'),
                            "class": char.get('class', 'Unknown'),
                            "destiny_roll": char.get('destiny_roll', 0),
                            "time_skip_years": years,
                            "biome_conquered": config[1] if config else 'unknown'
                        }
                        legacy_data["signature_move"] = f"{char.get('name', 'Legend')}'s Legendary Strike"
                        legacy_data["legacy_buff"] = LevelProgression.generate_legacy_buff(legacy_data)
                        
                        # Save to legacy system
                        save_legacy_data(interaction.guild.id, user_id, char.get('name', 'Unknown'), legacy_data)
        
        # Store surviving legends
        legends = []
        for user_id in party:
            if not str(user_id).startswith("npc_"):
                char = get_character(user_id, interaction.guild.id)
                if char:
                    legends.append({
                        "id": user_id,
                        "name": char.get('name', f"Player {user_id}"),
                        "status": "Legend" if target_phase == 2 else "Ancestor",
                        "phase": phase,
                        "destiny_roll": char.get('destiny_roll', 0)
                    })
        
        advance_campaign_phase(interaction.guild.id, target_phase, legends)
        
        # Update quest to next phase
        if config and config[10]:
            try:
                quest_data = json.loads(config[10])
                path_key = quest_data.get('path_key', random.choice(list(VOID_CYCLE_BIOMES.keys())))
                if path_key in VOID_CYCLE_BIOMES:
                    biome_key = f"p{target_phase}" if target_phase in [2, 3] else "p1"
                    if biome_key in VOID_CYCLE_BIOMES[path_key]:
                        update_quest_data(interaction.guild.id, json.dumps(VOID_CYCLE_BIOMES[path_key][biome_key]))
                        update_dnd_location(interaction.guild.id, path_key)
            except:
                pass
        
        # Create narrative summary for time skip
        summary = f"**{years} Years Have Passed...**\n\n"
        if target_phase == 2:
            summary += f"{time_flavor}\n\nThe legends must face new threats in an changed world. {generations['generations']} generations have come and gone."
        else:  # Phase 3
            summary += f"{time_flavor}\n\nThe descendants of heroes must break the cycle. {generations['generations']} generations separate them from their ancestors' glory."
        
        update_dnd_summary(interaction.guild.id, summary)
        
        # Create detailed embed with Chronos Engine info
        embed = discord.Embed(
            title="⏳ Chronos Engine: Time Skip",
            description=time_flavor,
            color=0xF1C40F
        )
        embed.add_field(name="Years Elapsed", value=f"{years} years", inline=True)
        embed.add_field(name="Phase Transition", value=f"Phase {phase} → Phase {target_phase}", inline=True)
        embed.add_field(name="Generations Passed", value=f"{generations['generations']} generations (~{generations['generations'] * 25} years each)", inline=False)
        embed.add_field(name="Dynasties Changed", value=str(generations['dynasties']), inline=True)
        embed.add_field(name="Total Time Elapsed", value=f"{total_years} years since campaign start", inline=True)
        embed.add_field(name="Cultural Shifts", value=f"{generations['cultural_shifts']} major shifts", inline=False)
        embed.add_field(name="Surviving Legends", value=str(len(legends)) if legends else "None", inline=True)
        
        if target_phase == 3:
            embed.add_field(name="🔮 Phase 3 Info", value="New generation characters must be created. Phase 1/2 characters become Soul Remnants.", inline=False)
        
        embed.set_footer(text="The world has shifted. Old heroes fade to legend.")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="roll_destiny", description="Roll for protagonist status (d100)")
    @is_dnd_player()
    async def roll_destiny(self, interaction: discord.Interaction):
        """Roll destiny score for narrative weight"""
        char = get_character(interaction.user.id, interaction.guild.id)
        if not char:
            await interaction.response.send_message("❌ Import a character sheet first", ephemeral=True)
            return
        
        roll = random.randint(1, 100)
        update_character_destiny(interaction.user.id, interaction.guild.id, roll)
        
        protagonist, score = get_session_protagonist(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔮 Destiny Roll",
            description=f"{char.get('name', interaction.user.display_name)} rolls **{roll}**",
            color=0x9B59B6
        )
        embed.add_field(name="Your Roll", value=f"🎲 **{roll}**", inline=True)
        
        if protagonist:
            embed.add_field(name="Current Protagonist", value=f"👑 {protagonist} ({score})", inline=True)
        
        if roll >= 80:
            embed.add_field(name="Destiny", value="**Major Plot Figure**", inline=False)
        elif roll >= 50:
            embed.add_field(name="Destiny", value="**Important Character**", inline=False)
        else:
            embed.add_field(name="Destiny", value="**Supporting Role**", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="end_session", description="End the current D&D session")
    @is_dnd_player()
    async def end_session(self, interaction: discord.Interaction):
        """Cleanly end the session and disable all views"""
        # ===== IMMEDIATE DEFER (Required within 3 seconds) =====
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction expired, can't respond
            print("[end_session] Interaction expired before defer")
            return
        except Exception as e:
            print(f"[end_session] Defer error: {e}")
            return
        
        try:
            clear_combat(interaction.channel.id)
            
            # Disable all views in the channel
            try:
                async for message in interaction.channel.history(limit=50):
                    if message.components:
                        try:
                            await message.edit(view=None)
                        except:
                            pass
            except:
                pass
            
            if interaction.guild.id in self.voice_clients:
                vc = self.voice_clients[interaction.guild.id]
                if vc and vc.is_connected():
                    await vc.disconnect()
                self.voice_clients.pop(interaction.guild.id, None)
            
            embed = discord.Embed(
                title="🎬 Session Ended",
                description=f"Session ended by {interaction.user.mention}\nAll interactive elements have been disabled.",
                color=0x95A5A6
            )
            embed.set_footer(text="Use /start_session to continue your adventure")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[end_session] Error: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Error ending session: {str(e)[:100]}",
                    ephemeral=True
                )
            except:
                pass
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="reset_campaign", description="Reset campaign to Phase 1")
    @app_commands.default_permissions(manage_guild=True)
    async def reset_campaign_cmd(self, interaction: discord.Interaction):
        """Reset campaign data - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can reset campaigns!",
                ephemeral=True
            )
            return
        
        reset_campaign(interaction.guild.id, interaction.channel.id)
        
        theme = random.choice(list(CONQUEST_PATHS.keys()))
        quest_data = CONQUEST_PATHS[theme]["p1"]
        quest_data["path_key"] = theme
        update_quest_data(interaction.guild.id, json.dumps(quest_data))
        update_dnd_location(interaction.guild.id, quest_data["theme"])
        
        await interaction.followup.send(
            f"🔄 Campaign reset! New quest: **{quest_data['name']}** (reset by {interaction.user.mention})", 
            ephemeral=True
        )
    
    @app_commands.command(name="add_lore", description="Add lore to the campaign")
    @app_commands.default_permissions(manage_guild=True)
    async def add_lore(self, interaction: discord.Interaction, topic: str, description: str):
        """Manually add lore - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can add lore!",
                ephemeral=True
            )
            return
        
        if len(topic) > 100 or len(description) > 500:
            await interaction.followup.send("❌ Topic or description too long", ephemeral=True)
            return
        
        add_lore(interaction.guild.id, topic, description)
        
        embed = discord.Embed(
            title="📖 Lore Added",
            description=f"**{topic}**\n\n{description}",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="ingest_rulebook", description="[ADMIN] Import markdown rulebook into database")
    @app_commands.describe(
        filename="Filename in srd/ folder (e.g., 'RulesGlossary.md')",
        source="Source attribution (default: 'SRD 2024')"
    )
    @app_commands.default_permissions(administrator=True)
    async def ingest_rulebook(self, interaction: discord.Interaction, filename: str, source: str = "SRD 2024"):
        """Import markdown rulebook with streaming parser (1GB RAM optimized)"""
        
        # Admin permission check
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(VP.denied, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Construct path
            file_path = os.path.join("srd", filename)
            
            # Ingest with stats
            stats = RulebookIngestor.ingest_markdown_rulebook(file_path, source)
            
            # Report results
            embed = discord.Embed(
                title="📚 Rulebook Ingestion Complete",
                color=discord.Color.green()
            )
            embed.add_field(name="File", value=filename, inline=False)
            embed.add_field(name="Inserted/Updated", value=str(stats['inserted']), inline=True)
            embed.add_field(name="Skipped", value=str(stats['skipped']), inline=True)
            embed.set_footer(text=f"Source: {source} | Memory-optimized streaming parser")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except FileNotFoundError as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ingestion failed: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="lookup_rule", description="Look up a D&D rule by keyword")
    @app_commands.describe(
        keyword="Rule to search for (e.g., 'advantage', 'attack', 'concentration')",
        precise="Use stricter matching for technical terms (default: False)",
        follow_links="Follow 'See also' references for more context (default: False)"
    )
    async def lookup_rule_cmd(self, interaction: discord.Interaction, keyword: str, precise: bool = False, follow_links: bool = False):
        """Look up a rule from the rulebook with optional 'See also' link following"""
        await interaction.response.defer()
        
        rules = RulebookRAG.lookup_rule(keyword, limit=3, require_precision=precise, follow_see_also=follow_links)
        
        if not rules:
            await interaction.followup.send(f"❌ No rules found for '{keyword}'")
            return
        
        embed = discord.Embed(
            title=f"📖 Rules for '{keyword}'",
            color=discord.Color.blue()
        )
        
        for rule_keyword, rule_text in rules:
            # Truncate long rules
            display_text = rule_text[:400] + "..." if len(rule_text) > 400 else rule_text
            embed.add_field(
                name=f"📌 {rule_keyword.title()}",
                value=display_text,
                inline=False
            )
        
        if follow_links:
            embed.set_footer(text="✨ 'See also' references included")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="campaign_status", description="Check current campaign status")
    @is_dnd_player()
    async def campaign_status(self, interaction: discord.Interaction):
        """Display campaign information"""
        await interaction.response.defer()
        
        phase, legends = get_dnd_campaign_data(interaction.guild.id)
        config = get_dnd_config(interaction.guild.id)
        
        quest_name = "Unknown Quest"
        quest_theme = "tavern"
        if config and config[10]:
            try:
                quest_data = json.loads(config[10])
                quest_name = quest_data.get('name', quest_name)
                quest_theme = quest_data.get('theme', quest_theme)
            except:
                pass
        
        embed = discord.Embed(
            title="📊 Campaign Status (2024)",
            color=LOCATION_THEMES.get(quest_theme, 0x3498DB)
        )
        
        embed.add_field(name="Quest", value=quest_name, inline=True)
        embed.add_field(name="Phase", value=str(phase), inline=True)
        embed.add_field(name="Rules", value="2024 Edition", inline=True)
        
        if config and config[1]:
            embed.add_field(name="Current Location", value=config[1], inline=False)
        
        if config and config[2]:
            summary = config[2][:200] + "..." if len(config[2]) > 200 else config[2]
            embed.add_field(name="Story Summary", value=summary, inline=False)
        
        if phase > 1 and legends:
            legend_names = [l.get('name', 'Unknown') for l in legends[:5]]
            legends_text = ", ".join(legend_names)
            if len(legends) > 5:
                legends_text += f" and {len(legends) - 5} more..."
            embed.add_field(name="Legends", value=legends_text, inline=False)
        
        protagonist, score = get_session_protagonist(interaction.guild.id)
        if protagonist:
            embed.add_field(name="Protagonist", value=f"{protagonist} (Destiny: {score})", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    # --- ENHANCED COMMANDS ---
    
    @app_commands.command(name="rule", description="Look up a D&D rule with precision filtering")
    @app_commands.describe(keyword="Rule to look up (e.g., 'fireball', 'concentration')", 
                           precise="Use precision filtering (default: True)")
    async def rule_lookup(self, interaction: discord.Interaction, keyword: str, precise: bool = True):
        """Rulebook RAG lookup with precision filtering"""
        await interaction.response.defer()
        
        rules = RulebookRAG.lookup_rule(keyword, limit=3, require_precision=precise)
        
        if not rules:
            await interaction.followup.send(
                f"No rules found for '{keyword}'. Try being more specific or disable precision filtering.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(title=f"📚 Rule: {keyword}", color=0x3498DB)
        
        for i, (rule_name, rule_text) in enumerate(rules, 1):
            embed.add_field(
                name=f"{i}. {rule_name.title()}",
                value=rule_text[:250] + ("..." if len(rule_text) > 250 else ""),
                inline=False
            )
        
        if precise:
            embed.set_footer(text="Precision filtering enabled - showing most relevant rules")
        else:
            embed.set_footer(text="Broad search - may include less relevant results")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="mechanics", description="View truth block accuracy stats and mechanics analysis")
    @app_commands.describe(days="Number of days to analyze (default: 7)")
    async def mechanics_stats(self, interaction: discord.Interaction, days: int = 7):
        """Display truth block accuracy statistics and usage patterns"""
        await interaction.response.defer()
        
        # Get accuracy stats for this guild
        stats = TruthBlockLogger.get_accuracy_stats(guild_id=interaction.guild.id, days=days)
        
        if 'error' in stats:
            await interaction.followup.send(
                f"❌ Error retrieving stats: {stats['error']}\nNo data logged yet.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="⚙️ Truth Block Accuracy Statistics",
            description=f"Analysis of AI mechanics adherence over the last {days} days",
            color=0x3498DB
        )
        
        # Overall stats
        embed.add_field(
            name="📊 Overall Usage",
            value=f"Total Uses: **{stats['total_uses']}**\n"
                  f"AI Acknowledged: **{stats['ai_acknowledged']}**\n"
                  f"Acknowledgment Rate: **{stats['acknowledgment_rate']:.1f}%**",
            inline=False
        )
        
        # Feature breakdown
        embed.add_field(
            name="🎲 Feature Usage",
            value=f"Attack Rolls: **{stats['attack_uses']}**\n"
                  f"Saving Throws: **{stats['save_uses']}**\n"
                  f"Damage Rolls: **{stats['damage_uses']}**",
            inline=False
        )
        
        # Interpretation
        if stats['acknowledgment_rate'] >= 90:
            quality = "✅ Excellent - AI is following truth blocks very consistently"
        elif stats['acknowledgment_rate'] >= 75:
            quality = "✔️ Good - AI generally follows truth blocks"
        elif stats['acknowledgment_rate'] >= 50:
            quality = "⚠️ Fair - AI sometimes deviates from truth blocks"
        else:
            quality = "❌ Poor - AI frequently deviates from truth blocks"
        
        embed.add_field(
            name="📈 Quality Assessment",
            value=quality,
            inline=False
        )
        
        embed.set_footer(text=f"Data logged to {TruthBlockLogger.LOG_FILE}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="add_rule", description="Add a custom rule to the rulebook")
    @app_commands.default_permissions(manage_guild=True)
    async def add_rule_cmd(self, interaction: discord.Interaction, 
                          keyword: str, 
                          rule_text: str,
                          rule_type: str = "custom"):
        """Add custom rule - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can add rules!",
                ephemeral=True
            )
            return
        
        RulebookRAG.add_rule(keyword, rule_text, rule_type, "custom")
        
        embed = discord.Embed(
            title="✅ Rule Added",
            description=f"**{keyword}** added to rulebook",
            color=0x2ECC71
        )
        embed.add_field(name="Rule", value=rule_text[:200], inline=False)
        embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Type", value=rule_type, inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="spell", description="Look up a spell from SRD")
    async def spell_lookup(self, interaction: discord.Interaction, spell_name: str):
        """SRD spell lookup using database"""
        await interaction.response.defer()
        
        # Try to get spell from database
        try:
            from database import get_spell_by_name
            spell = get_spell_by_name(spell_name)
        except:
            spell = None
        
        if not spell:
            # Fallback to JSON library
            spells = SRDLibrary.search_srd("spells", spell_name, limit=1)
            if spells:
                spell = spells[0]
            else:
                spell = {
                    "name": spell_name.title(),
                    "level": "?",
                    "school": "Unknown",
                    "description": "No spell data available. Consider adding to SRD."
                }
        
        embed = discord.Embed(
            title=f"✨ {spell.get('name', spell_name).title()}",
            color=0x9B59B6
        )
        
        if "level" in spell:
            embed.add_field(name="Level", value=str(spell["level"]), inline=True)
        if "school" in spell:
            embed.add_field(name="School", value=spell["school"], inline=True)
        if "casting_time" in spell:
            embed.add_field(name="Casting Time", value=spell["casting_time"], inline=True)
        if "range" in spell:
            embed.add_field(name="Range", value=spell["range"], inline=True)
        if "components" in spell:
            embed.add_field(name="Components", value=spell["components"], inline=True)
        if "duration" in spell:
            embed.add_field(name="Duration", value=spell["duration"], inline=True)
        if "description" in spell:
            embed.description = str(spell["description"])[:1000]
        
        embed.set_footer(text="Local SRD • PHB 2024")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="monster", description="Look up a monster from SRD")
    async def monster_lookup(self, interaction: discord.Interaction, monster_name: str):
        """SRD monster lookup using database"""
        await interaction.response.defer()
        
        # Try to get monster from database
        try:
            from database import get_monster_by_name
            monster = get_monster_by_name(monster_name)
        except:
            monster = None
        
        if not monster:
            await interaction.followup.send(f"❌ Monster '{monster_name}' not found in SRD.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"👹 {monster.get('name', monster_name).title()}",
            color=0xE74C3C
        )
        
        if "type" in monster:
            embed.add_field(name="Type", value=monster["type"], inline=True)
        if "size" in monster:
            embed.add_field(name="Size", value=monster["size"], inline=True)
        if "alignment" in monster:
            embed.add_field(name="Alignment", value=monster["alignment"], inline=True)
        
        if "ac" in monster:
            embed.add_field(name="AC", value=str(monster["ac"]), inline=True)
        if "hp" in monster:
            embed.add_field(name="HP", value=str(monster["hp"]), inline=True)
        if "challenge_rating" in monster or "cr" in monster:
            cr = monster.get("challenge_rating") or monster.get("cr")
            embed.add_field(name="Challenge", value=str(cr), inline=True)
        
        # Ability scores
        abilities = []
        for ability in ["str", "dex", "con", "int", "wis", "cha"]:
            if ability in monster:
                abilities.append(f"{ability.upper()}: {monster[ability]}")
        if abilities:
            embed.add_field(name="Abilities", value=" • ".join(abilities), inline=False)
        
        if "description" in monster and monster["description"]:
            embed.description = str(monster["description"])[:500]
        
        embed.set_footer(text="Local SRD • MM 2024")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="damage_ref", description="Damage enemy by reference number")
    @app_commands.describe(ref="Enemy reference number", damage="Damage amount")
    async def damage_by_ref(self, interaction: discord.Interaction, ref: int, damage: int):
        """Damage using combat tracker abbreviation"""
        await interaction.response.defer()
        
        result = CombatTracker.apply_damage_by_ref(interaction.channel.id, ref, damage)
        
        if not result:
            await interaction.followup.send(f"No enemy with reference [{ref}]", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚔️ Damage Applied",
            color=0xE74C3C if damage > 0 else 0x2ECC71
        )
        
        if result.get("status") == "defeated":
            embed.description = f"**[{ref}] {result['name']}** defeated! (-{damage} HP)"
        else:
            embed.description = f"**[{ref}] {result['name']}**: {result['hp']}/{result['max_hp']} HP (-{damage})"
        
        if damage > 0 and result.get("conditions", "").lower().count("concentrating"):
            dc = max(10, damage // 2)
            embed.add_field(
                name="⚠️ Concentration Check",
                value=f"{result['name']} must make DC {dc} CON save",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="combat_status", description="Show compact combat status")
    async def combat_status(self, interaction: discord.Interaction):
        """Show optimized combat tracker"""
        await interaction.response.defer()
        
        summary = CombatTracker.get_combat_summary(interaction.channel.id)
        
        embed = discord.Embed(
            title="⚔️ Combat Status",
            description=summary,
            color=0xE74C3C
        )
        
        embed.add_field(
            name="Quick Commands",
            value="`/damage_ref [number] [amount]` - Damage enemy\n`/attack [ref]` - Attack enemy",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="session_report", description="Generate session summary")
    async def session_report(self, interaction: discord.Interaction):
        """Generate session scribe report"""
        await interaction.response.defer()
        
        summary = await HistoryManager.summarize_history(
            interaction.guild.id, 
            interaction.channel.id,
            force=True
        )
        
        embed = SessionScribe.generate_session_embed(
            interaction.guild.id,
            interaction.channel.id,
            "Session Report"
        )
        
        if embed:
            if summary:
                embed.add_field(name="📝 Summary", value=summary, inline=False)
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("No session data to report")
    
    @app_commands.command(name="check_destiny", description="Check destiny milestones")
    async def check_destiny(self, interaction: discord.Interaction):
        """Check destiny triggers"""
        await interaction.response.defer()
        
        triggers = DestinyManager.check_destiny_triggers(
            interaction.guild.id, 
            interaction.user.id
        )
        
        char = get_character(interaction.user.id, interaction.guild.id)
        if not char:
            await interaction.followup.send("No character found", ephemeral=True)
            return
        
        destiny_score = char.get('destiny_roll', 0)
        
        embed = discord.Embed(
            title="🔮 Destiny Check",
            color=0x9B59B6
        )
        
        embed.add_field(
            name="Your Destiny Score",
            value=f"**{destiny_score}** / 100",
            inline=True
        )
        
        next_milestone = None
        for threshold in sorted(DestinyManager.DESTINY_MILESTONES.keys()):
            if destiny_score < threshold:
                next_milestone = threshold
                break
        
        if next_milestone:
            embed.add_field(
                name="Next Milestone",
                value=f"{next_milestone} ({next_milestone - destiny_score} points away)",
                inline=True
            )
        
        if triggers:
            embed.add_field(
                name="🎉 New Milestones!",
                value="\n".join(triggers),
                inline=False
            )
        
        milestones = char.get('milestones', [])
        if milestones:
            achieved = [m.replace('milestone_', '') for m in milestones]
            embed.add_field(
                name="Achieved Milestones",
                value=f"Levels: {', '.join(achieved)}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="dm_suggest", description="Get AI suggestions for DM response")
    @app_commands.describe(player_action="The player's action to respond to")
    @app_commands.default_permissions(manage_guild=True)
    async def dm_suggest(self, interaction: discord.Interaction, player_action: str):
        """DM oversight mode"""
        await interaction.response.defer(ephemeral=True)
        
        history = HistoryManager.get_optimized_history(interaction.channel.id, limit=5)
        context = "\n".join([f"{role}: {content}" for role, content in history])
        
        suggestions = await DMOversight.suggest_outcome(
            interaction.guild.id,
            player_action,
            context
        )
        
        embed = discord.Embed(
            title="👻 DM Suggestions",
            description=f"For action: *{player_action[:100]}*",
            color=0x7289DA
        )
        
        options = suggestions.get("options", [])
        for i, option in enumerate(options[:3], 1):
            embed.add_field(
                name=f"Option {i}",
                value=option[:150],
                inline=False
            )
        
        recommended = suggestions.get("recommended", 0)
        embed.set_footer(text=f"Suggested: Option {recommended + 1}")
        
        class SuggestionView(discord.ui.View):
            def __init__(self, cog, options):
                super().__init__(timeout=60)
                self.cog = cog
                self.options = options
            
            @discord.ui.button(label="Use Option 1", style=discord.ButtonStyle.primary)
            async def use_option1(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[0]}")
                self.stop()
            
            @discord.ui.button(label="Use Option 2", style=discord.ButtonStyle.primary)
            async def use_option2(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[1]}")
                self.stop()
            
            @discord.ui.button(label="Use Option 3", style=discord.ButtonStyle.primary)
            async def use_option3(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[2]}")
                self.stop()
        
        view = SuggestionView(self, options)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="summarize", description="Force history summarization")
    @app_commands.default_permissions(manage_guild=True)
    async def force_summarize(self, interaction: discord.Interaction):
        """Force history summarization"""
        await interaction.response.defer()
        
        summary = await HistoryManager.summarize_history(
            interaction.guild.id,
            interaction.channel.id,
            force=True
        )
        
        if summary:
            embed = discord.Embed(
                title="📚 History Summarized",
                description=summary,
                color=0x95A5A6
            )
            embed.set_footer(text="Old entries condensed to save memory")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Nothing to summarize")
    
    @app_commands.command(name="migrate_to_2024", description="Migrate campaign to 2024 rules")
    @app_commands.default_permissions(manage_guild=True)
    async def migrate_to_2024(self, interaction: discord.Interaction):
        """Migrate from legacy 2014 to 2024 rules"""
        await interaction.response.defer(ephemeral=True)
        
        update_dnd_rulebook(interaction.guild.id, "2024")
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id, guild_id, char_data FROM dnd_characters WHERE guild_id=?", (str(interaction.guild.id),))
        characters = c.fetchall()
        
        migrated = 0
        for uid, gid, char_json in characters:
            try:
                data = json.loads(char_json)
                
                if "race" in data:
                    data["species"] = data.pop("race")
                
                if "has_inspiration" in data:
                    data["heroic_inspiration"] = data.pop("has_inspiration")
                
                c.execute("UPDATE dnd_characters SET char_data=? WHERE user_id=? AND guild_id=?", 
                         (json.dumps(data), uid, gid))
                migrated += 1
                
            except Exception as e:
                print(f"Error migrating character {uid}: {e}")
        
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Migration Complete",
            description=f"Successfully migrated {migrated} characters to 2024 rules.",
            color=0x2ECC71
        )
        embed.add_field(name="Changes Applied", 
                       value="• 'Race' → 'Species'\n• 'Inspiration' → 'Heroic Inspiration'\n• Rulebook set to 2024", 
                       inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- GENERATIONAL VOID CYCLE COMMANDS ---
    
    @app_commands.command(name="initialize_void_cycle", description="Start a Void Cycle campaign in Phase 1")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        unique_point="Select the world's environmental anchor (1-12)",
        campaign_name="Name for this campaign"
    )
    async def initialize_void_cycle(self, interaction: discord.Interaction, unique_point: int = None, campaign_name: str = None):
        """Initialize a new Void Cycle campaign (3-phase generational campaign)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from database import save_void_cycle_data
            
            # If no unique point specified, show selection menu
            if unique_point is None:
                view = discord.ui.View()
                unique_points = list(UniquePointSystem.UNIQUE_POINTS.keys())
                
                select = discord.ui.Select(
                    placeholder="Choose your world's environmental anchor...",
                    options=[
                        discord.SelectOption(
                            label=name.replace("_", " ").title(),
                            value=str(idx + 1),
                            description=UniquePointSystem.UNIQUE_POINTS[name].get("description", "")[:100]
                        )
                        for idx, name in enumerate(unique_points[:24])
                    ],
                    min_values=1,
                    max_values=1
                )
                
                async def select_point(interaction: discord.Interaction):
                    point_idx = int(select.values[0]) - 1
                    point_name = unique_points[point_idx]
                    
                    # Save configuration
                    save_void_cycle_data(
                        interaction.guild.id,
                        phase=1,
                        world_unique_point=point_name,
                        generation=1
                    )
                    
                    point_data = UniquePointSystem.UNIQUE_POINTS[point_name]
                    embed = discord.Embed(
                        title="🌍 Void Cycle Initialized",
                        description=f"**Phase 1: The Founder Era**\nYour world's anchor has been set.",
                        color=0x1ABC9C
                    )
                    embed.add_field(
                        name="Unique Point",
                        value=point_name.replace("_", " ").title(),
                        inline=False
                    )
                    embed.add_field(
                        name="Description",
                        value=point_data.get("description", "A unique environmental location."),
                        inline=False
                    )
                    embed.add_field(
                        name="Phase 1 Law",
                        value=point_data.get("phase_1_law", "TBD"),
                        inline=False
                    )
                    embed.add_field(
                        name="Next Steps",
                        value="1. Create Phase 1 founder character\n2. Begin your campaign\n3. Use `/advance_phase` when ready for Phase 2",
                        inline=False
                    )
                    embed.set_footer(text="Players start as founders. Their descendants will inherit specializations in Phase 3.")
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                
                select.callback = select_point
                view.add_item(select)
                
                embed = discord.Embed(
                    title="🌍 Initialize Void Cycle Campaign",
                    description="Choose your world's environmental anchor point. This determines Phase 3 conversion laws.",
                    color=0x9B59B6
                )
                embed.add_field(
                    name="Campaign Phases",
                    value="**Phase 1 (Founder Era):** 0 years - Your founders establish a legacy\n"
                          "**Phase 2 (Legend Era):** 20-50 years later - Consequences become visible\n"
                          "**Phase 3 (Integrated Era):** 500-1000+ years later - Tech & magic unified, descendants face prophecy",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                # Direct point selection
                unique_points = list(UniquePointSystem.UNIQUE_POINTS.keys())
                if 1 <= unique_point <= len(unique_points):
                    point_name = unique_points[unique_point - 1]
                    
                    save_void_cycle_data(
                        interaction.guild.id,
                        phase=1,
                        world_unique_point=point_name,
                        generation=1
                    )
                    
                    point_data = UniquePointSystem.UNIQUE_POINTS[point_name]
                    embed = discord.Embed(
                        title="✅ Void Cycle Initialized",
                        description=f"**Phase 1: The Founder Era**",
                        color=0x1ABC9C
                    )
                    embed.add_field(
                        name="Unique Point",
                        value=point_name.replace("_", " ").title(),
                        inline=False
                    )
                    embed.add_field(
                        name="Phase 1 Mechanics",
                        value=point_data.get("phase_1_law", "Standard rules apply."),
                        inline=False
                    )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Invalid unique point (1-{len(unique_points)})", ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            print(f"Error in initialize_void_cycle: {e}")
    
    @app_commands.command(name="advance_phase", description="Progress to next Void Cycle phase (DM only)")
    @app_commands.default_permissions(manage_guild=True)
    async def advance_phase(self, interaction: discord.Interaction):
        """DM command to advance to next phase with time skip and descendant prompts"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from database import get_void_cycle_data, save_void_cycle_data
            
            phase, unique_point, generation = get_void_cycle_data(interaction.guild.id)
            
            if phase == 0 or unique_point == "uninitialized":
                await interaction.followup.send("❌ Campaign not initialized. Use `/initialize_void_cycle` first.", ephemeral=True)
                return
            elif phase >= 3:
                await interaction.followup.send("✅ Campaign already in Phase 3 (final phase). Use `/chronicles` to view victory.", ephemeral=True)
                return
            
            # Roll time skip
            if phase == 1:
                # Phase 1 → 2: 20-50 years
                years = sum(int(random.random() * 12) + 1 for _ in range(20))
                next_phase = 2
                phase_name = "Legend Era"
            else:
                # Phase 2 → 3: 500-1000+ years
                years = sum(int(random.random() * 12) + 1 for _ in range(500))
                next_phase = 3
                phase_name = "Integrated Era"
            
            # Update phase
            save_void_cycle_data(
                interaction.guild.id,
                phase=next_phase,
                generation=generation + 1
            )
            
            embed = discord.Embed(
                title=f"⏳ Phase Transition: Phase {phase} → Phase {next_phase}",
                description=f"**The {phase_name}**",
                color=0xE74C3C
            )
            embed.add_field(
                name="🕰️ Time Skip",
                value=f"**{years} years** have passed...",
                inline=False
            )
            embed.add_field(
                name="🌍 The World Evolves",
                value=f"Magic and technology converge.\nThe Void's influence spreads.\nA new generation must rise.",
                inline=False
            )
            
            if next_phase == 3:
                embed.add_field(
                    name="👶 Descendant Creation",
                    value="Players must create Phase 3 descendants of their Phase 1/2 characters.\n\n"
                          "**Specialization Locking:**\n"
                          "• Martial ancestors → Aura Acceleration available\n"
                          "• Caster ancestors → Systematic Sorcery available\n"
                          "• Dual-classed ancestors → Choice of either path",
                    inline=False
                )
                embed.add_field(
                    name="📍 Unique Point Conversion",
                    value="Phase 3 mechanics differ based on your world's unique point.",
                    inline=False
                )
            
            embed.set_footer(text="Use `/import_character` to create a new descendant character.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            print(f"Error in advance_phase: {e}")
    
    @app_commands.command(name="mode_select", description="Choose Architect (auto) or Scribe (manual) mode")
    @app_commands.default_permissions(manage_guild=True)
    async def mode_select(self, interaction: discord.Interaction, mode: str = None):
        """Select session mode: Architect (Vespera controls tone/biome) or Scribe (players choose)"""
        await interaction.response.defer(ephemeral=True)
        
        # Create selection view if no mode specified
        if not mode:
            view = discord.ui.View()
            
            async def select_architect(interaction: discord.Interaction):
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.ARCHITECT)
                except:
                    # Table migration not complete yet, will work after restart
                    pass
                await interaction.response.send_message(
                    "✅ **Architect Mode Enabled**\n\nVespera now controls:\n"
                    "• Automatic tone shifting based on scene context\n"
                    "• Biome selection (random each session)\n"
                    "• All major narrative decisions",
                    ephemeral=True
                )
            
            async def select_scribe(interaction: discord.Interaction):
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.SCRIBE)
                except:
                    # Table migration not complete yet, will work after restart
                    pass
                await interaction.response.send_message(
                    "✅ **Scribe Mode Enabled**\n\nPlayers can:\n"
                    "• Select their starting biome from a menu\n"
                    "• Pick a persistent tone for the session\n"
                    "• Have more control over narrative direction",
                    ephemeral=True
                )
            
            architect_btn = discord.ui.Button(label="🏗️ Architect Mode", style=discord.ButtonStyle.primary)
            architect_btn.callback = select_architect
            view.add_item(architect_btn)
            
            scribe_btn = discord.ui.Button(label="📜 Scribe Mode", style=discord.ButtonStyle.secondary)
            scribe_btn.callback = select_scribe
            view.add_item(scribe_btn)
            
            embed = discord.Embed(
                title="⚙️ Session Mode Selection",
                description="Choose how you want to run your D&D campaign!",
                color=0x9B59B6
            )
            embed.add_field(
                name="🏗️ Architect Mode (Default DM)",
                value="Vespera manages the entire narrative:\n"
                      "• Auto biome selection\n"
                      "• Automatic tone shifting\n"
                      "• Full narrative control",
                inline=False
            )
            embed.add_field(
                name="📜 Scribe Mode (DM Assistant)",
                value="Players get manual overrides:\n"
                      "• Select starting biome from menu\n"
                      "• Pick persistent tone for session\n"
                      "• More narrative agency",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # Direct mode selection
            if mode.lower() in ["architect", "arch"]:
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.ARCHITECT)
                except:
                    pass  # Table migration not complete yet
                await interaction.followup.send("✅ **Architect Mode** activated!", ephemeral=True)
            elif mode.lower() in ["scribe", "scr"]:
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.SCRIBE)
                except:
                    pass  # Table migration not complete yet
                await interaction.followup.send("✅ **Scribe Mode** activated!", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Unknown mode '{mode}'. Use: architect or scribe", ephemeral=True)
    
    @app_commands.command(name="chronicles", description="View campaign chronicles and victory scroll")
    @is_dnd_player()
    async def chronicles(self, interaction: discord.Interaction):
        """Display the Chronicles scroll with generational credits"""
        await interaction.response.defer()
        
        # Check if Phase 3 is complete
        phase, legends = get_dnd_campaign_data(interaction.guild.id)
        
        if phase < 3:
            await interaction.followup.send(
                f"⏳ Chronicles not yet available.\nCurrent Phase: {phase}/3\n\n"
                f"Complete Phase 3 to generate your campaign chronicles!",
                ephemeral=True
            )
            return
        
        # Get chronicles if they exist
        chronicle = get_chronicles(interaction.guild.id)
        
        if not chronicle:
            # Generate default chronicles if Phase 3 but no chronicle saved yet
            config = get_dnd_config(interaction.guild.id)
            party = json.loads(config[6]) if config and config[6] else []
            
            founder = "Unknown Founder"
            founder_id = "N/A"
            legend = "Unknown Legend"
            legend_id = "N/A"
            savior = "Unknown Savior"
            savior_id = "N/A"
            
            for user_id in party:
                if not str(user_id).startswith("npc_"):
                    char = get_character(user_id, interaction.guild.id)
                    if char:
                        if not founder or founder == "Unknown Founder":
                            founder = char.get('name', 'Unknown Founder')
                            founder_id = str(user_id)
                        elif not legend or legend == "Unknown Legend":
                            legend = char.get('name', 'Unknown Legend')
                            legend_id = str(user_id)
                        else:
                            savior = char.get('name', 'Unknown Savior')
                            savior_id = str(user_id)
            
            total_years = config[14] if config and len(config) > 14 else 0
            generations = max(1, total_years // 25)
            
            chronicle_data = {
                "campaign_name": config[3][:50] if config and config[3] else "Legacy Campaign",
                "phase_1_founder": founder,
                "phase_1_founder_id": founder_id,
                "phase_2_legend": legend,
                "phase_2_legend_id": legend_id,
                "phase_3_savior": savior,
                "phase_3_savior_id": savior_id,
                "total_years_elapsed": int(total_years),
                "total_generations": generations,
                "biome_name": config[1] if config else "The Void",
                "cycles_broken": 1,
                "eternal_guardians": [],
                "final_boss_name": "The Void Singularity"
            }
            
            save_chronicles(interaction.guild.id, chronicle_data)
            chronicle = get_chronicles(interaction.guild.id)
        
        # Build the Chronicles embed
        if chronicle:
            chronicle_id, campaign_name, founder, legend, savior, total_years, generations, biome, eternal_guardians, final_boss, victory_date = chronicle
            
            embed = discord.Embed(
                title="📜 THE CHRONICLES OF AGES PAST 📜",
                description=f"*A chronicle of the {total_years}-year saga across {generations} generations*",
                color=0xD4AF37
            )
            
            embed.add_field(
                name="⚔️ PHASE 1: THE FOUNDER",
                value=f"**{founder}** (The Conquest)\nFirst hero to face the void.",
                inline=False
            )
            
            embed.add_field(
                name="👑 PHASE 2: THE LEGEND",
                value=f"**{legend}** (The Transcendence)\n{total_years // 2} years after the Founder's deeds.",
                inline=False
            )
            
            embed.add_field(
                name="🌟 PHASE 3: THE SAVIOR",
                value=f"**{savior}** (The Legacy)\nDescendant who broke the cycle.",
                inline=False
            )
            
            embed.add_field(
                name="📍 REALM",
                value=f"The {biome}",
                inline=True
            )
            
            embed.add_field(
                name="⏳ TIME ELAPSED",
                value=f"{total_years} years\n{generations} generations",
                inline=True
            )
            
            embed.add_field(
                name="🏆 FINAL VICTORY",
                value=f"Defeated: **{final_boss}**",
                inline=True
            )
            
            if eternal_guardians:
                try:
                    guardians = json.loads(eternal_guardians)
                    if guardians:
                        embed.add_field(
                            name="🛡️ ETERNAL GUARDIANS",
                            value=", ".join(guardians[:5]),
                            inline=False
                        )
                except:
                    pass
            
            embed.set_footer(text="Thus ends the chronicle of the Void Cycle")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "❌ Chronicles not yet generated.\n\n"
                "Defeat the final Phase 3 boss to create your campaign's eternal chronicle!",
                ephemeral=True
            )
    
    # --- EVENT LISTENERS ---
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-rule lookup on spell mentions"""
        if message.author.bot or not message.guild:
            return
        
        if not isinstance(message.channel, discord.Thread):
            return
        
        spell_pattern = r'(?:cast|use|prepares?)\s+([a-zA-Z\s]+)(?:spell)?'
        matches = re.findall(spell_pattern, message.content.lower())
        
        for match in matches:
            spell_name = match.strip()
            if len(spell_name) > 3:
                rules = RulebookRAG.lookup_rule(spell_name, limit=1)
                if rules:
                    rule_name, rule_text = rules[0]
                    
                    embed = discord.Embed(
                        title=f"📖 {rule_name.title()}",
                        description=rule_text[:250] + "...",
                        color=0x3498DB
                    )
                    embed.set_footer(text="Auto-rule lookup • Use /rule for full text")
                    
                    await message.reply(embed=embed, mention_author=False)
                    break
    
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Auto-summarize after many commands"""
        if not isinstance(ctx.channel, discord.Thread):
            return
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM dnd_history WHERE thread_id=?", (str(ctx.channel.id),))
        count = c.fetchone()[0]
        conn.close()
        
        if count >= 30 and count % 15 == 0:
            await HistoryManager.summarize_history(ctx.guild.id, ctx.channel.id)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-join voice when players join during active session"""
        if member.bot or not after.channel:
            return
        
        try:
            config = get_dnd_config(member.guild.id)
            if not config or not config[2] or config[2] == "New Campaign Started.":
                return
            
            guild_vc = member.guild.voice_client
            if guild_vc and guild_vc.is_connected():
                return
            
            try:
                vc = await after.channel.connect()
                self.voice_clients[member.guild.id] = vc
                
                current_loc = config[1] or 'tavern'
                audio_file = f"{AUDIO_PATH}{current_loc}.ogg"
                if os.path.exists(audio_file):
                    if vc.is_playing():
                        vc.stop()
                    vc.play(discord.FFmpegPCMAudio(audio_file))
            except Exception as e:
                print(f"[DND] Voice connect error: {e}")
                
        except Exception as e:
            print(f"[DND] Voice state error: {e}")

async def setup(bot):
    """Setup function for the cog"""
    RulebookRAG.init_rulebook_table()
    
    os.makedirs("./srd", exist_ok=True)
    
    srd_path = "./srd/spells.json"
    if not os.path.exists(srd_path):
        minimal_srd = {
            "fireball": {
                "name": "Fireball",
                "level": 3,
                "school": "Evocation",
                "casting_time": "1 action",
                "range": "150 feet",
                "components": "V, S, M (a tiny ball of bat guano and sulfur)",
                "duration": "Instantaneous",
                "description": "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one. The fire spreads around corners. It ignites flammable objects in the area that aren't being worn or carried."
            },
            "cure_wounds": {
                "name": "Cure Wounds",
                "level": 1,
                "school": "Evocation",
                "casting_time": "1 action",
                "range": "Touch",
                "components": "V, S",
                "duration": "Instantaneous",
                "description": "A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier. This spell has no effect on undead or constructs."
            }
        }
        
        with open(srd_path, 'w', encoding='utf-8') as f:
            json.dump(minimal_srd, f, indent=2)
    
    await bot.add_cog(DNDCog(bot))
# --- END OF FILE dnd_cog.py ---