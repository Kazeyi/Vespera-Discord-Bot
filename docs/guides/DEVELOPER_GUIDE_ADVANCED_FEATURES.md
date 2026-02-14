# Developer Guide: Advanced Features Code Examples

## 1. Smart Action Reaction Engine - Code Examples

### Basic Usage
```python
from cogs.dnd import ReactionSuggestionEngine

# Analyze a threat in combat
threat = ReactionSuggestionEngine.analyze_threat(
    action="The enemy wizard casts Fireball at you!",
    character_data={
        'class': 'Wizard',
        'spellcasting_ability': 'Intelligence',
        'level': 8
    },
    combat_context="In the dungeon, surrounded by enemies"
)

print(threat['threat_type'])           # "AoE Spell"
print(threat['threat_level'])          # "HIGH"
print(threat['suggested_reactions'])   # ["Cast Counterspell", "Evasive Maneuver", "Take Cover"]
```

### Adding Custom Threats
```python
# Add a new threat type
ReactionSuggestionEngine.THREAT_KEYWORDS["psychic scream"] = {
    "threat": "Mental Attack",
    "reactions": ["Mind Shield", "Psychic Defense", "Mental Fortitude"]
}

# Now it will detect the threat automatically
threat = ReactionSuggestionEngine.analyze_threat(
    action="The creature releases a psychic scream!"
)
# Returns: threat_type="Mental Attack", threat_level="MEDIUM"
```

### Integrating into Custom Commands
```python
@app_commands.command(name="analyze_threat", description="Get suggested reactions to a threat")
async def analyze_threat_cmd(self, interaction: discord.Interaction, threat_description: str):
    char = get_character(interaction.user.id, interaction.guild.id)
    
    threat = ReactionSuggestionEngine.analyze_threat(
        action=threat_description,
        character_data=char,
        combat_context="During active combat"
    )
    
    embed = discord.Embed(
        title=f"⚠️ {threat['threat_type']}",
        description=threat['context'],
        color=0xFF0000 if threat['threat_level'] == "HIGH" else 0xFFA500
    )
    
    embed.add_field(
        name="Suggested Reactions",
        value="\n".join([f"• {r}" for r in threat['suggested_reactions']]),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
```

### Adding Class-Specific Reactions
```python
# Extend the analyze_threat method to add custom reactions
def analyze_threat_with_features(action: str, character_data: dict) -> dict:
    threat = ReactionSuggestionEngine.analyze_threat(action, character_data)
    
    class_type = character_data.get('class', '').lower()
    subclass = character_data.get('subclass', '').lower()
    
    # Barbarian: Can rage
    if 'barbarian' in class_type:
        threat['suggested_reactions'].append("Enter Rage")
    
    # Paladin with specific oath
    if 'paladin' in class_type and 'devotion' in subclass:
        threat['suggested_reactions'].append("Protective Bond")
    
    # Sorcerer: Can twinspell
    if 'sorcerer' in class_type:
        threat['suggested_reactions'].append("Twinspell Reaction")
    
    return threat
```

---

## 2. Legacy Item Hand-me-downs - Code Examples

### Phase 1: Storing Legacy Items
```python
from cogs.dnd import LegacyVaultSystem

# When character is locked at end of Phase 1
async def lock_phase1_character(guild_id, user_id, character_name, item_to_pass):
    success = LegacyVaultSystem.add_legacy_item(
        guild_id=guild_id,
        character_id=str(user_id),
        character_name=character_name,
        generation=1,
        item_name=item_to_pass['name'],
        item_description=item_to_pass['description'],
        owner=character_name
    )
    
    if success:
        return f"✅ {item_to_pass['name']} stored in the legacy vault!"
    else:
        return "❌ Failed to store item"
```

### Phase 3: Discovering Legacy Items
```python
from cogs.dnd import LegacyVaultSystem

# When Phase 3 character enters the game
async def spawn_phase3_character(guild_id, character_data):
    # Discover all legacy items from ancestors
    legacy_items = LegacyVaultSystem.discover_legacy_items(
        guild_id=guild_id,
        character_id=str(character_data['id']),
        current_generation=3
    )
    
    # Add to character inventory
    if legacy_items:
        if 'inventory' not in character_data:
            character_data['inventory'] = []
        
        for item in legacy_items:
            character_data['inventory'].append({
                'name': item['item_name'],
                'original_owner': item['original_owner'],
                'buff': item['scarring_effect'],
                'corruption': item['corruption_drawback'],
                'lore': item['lore'],
                'is_void_scarred': True
            })
        
        update_character(character_data['user_id'], guild_id, character_data)
        
        return legacy_items
    
    return []
```

### Creating a /legacy_items Command (Admin)
```python
@app_commands.command(name="legacy_items", description="Manage legacy vault items")
@app_commands.checks.has_permissions(manage_guild=True)
async def legacy_items_cmd(self, interaction: discord.Interaction):
    """View and manage legacy items in the vault"""
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''SELECT item_name, owner, is_void_scarred, scarring_effect 
                FROM legacy_vault 
                WHERE guild_id = ?
                ORDER BY created_at DESC''', (str(interaction.guild.id),))
    
    items = c.fetchall()
    conn.close()
    
    if not items:
        await interaction.response.send_message("No legacy items in vault.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📿 Legacy Vault",
        color=0x9370DB,
        timestamp=datetime.now()
    )
    
    for item_name, owner, is_scarred, effect in items:
        status = "✨ Void-Scarred" if is_scarred else "📦 Stored"
        effect_text = f"Effect: {effect}" if effect else "Awaiting discovery..."
        
        embed.add_field(
            name=f"{status}: {item_name}",
            value=f"From: {owner}\n{effect_text}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
```

### Custom Scarring Effects
```python
# Override default scarring to match campaign theme
def generate_void_scarring_custom(item_name: str, owner: str, campaign_theme: str = "standard") -> tuple:
    """Generate scarring with theme-specific effects"""
    
    if campaign_theme == "corrupted_void":
        buffs = [
            "Immunity to fear",
            "+2 to necrotic spell damage",
            "See in magical darkness",
        ]
        corruptions = [
            "Double damage from holy sources",
            "Must consume life force weekly",
            "Slowly consume sanity (WIS check each long rest)"
        ]
    elif campaign_theme == "celestial_blessing":
        buffs = [
            "+2 to radiant damage",
            "Healing spells +1d4",
            "Allies within 10ft have +1 AC",
        ]
        corruptions = [
            "Take double damage from unholy sources",
            "Must meditate 1 hour daily or exhaustion",
            "Compelled to help evil creatures' victims"
        ]
    else:  # Default
        buffs = [
            "+1 to attack rolls and damage rolls",
            "Resistance to one damage type of your choice",
            "Once per day: Gain advantage on a saving throw",
        ]
        corruptions = [
            "Disadvantage on Insight checks about the void",
            "You cannot speak lies about the item's void-scarred nature",
            "Once per day, the item whispers (distracting)"
        ]
    
    return random.choice(buffs), random.choice(corruptions)
```

---

## 3. Kill Cam Narration - Code Examples

### Basic Usage
```python
from cogs.dnd import KillCamNarrator
import asyncio

async def trigger_kill_cam(character_name: str, monster_name: str, action: str, damage: int):
    """Generate and send kill cam narration"""
    
    narration = await KillCamNarrator.generate_kill_cam(
        character_name=character_name,
        monster_name=monster_name,
        player_action=action,
        final_damage=damage,
        attack_type="spell"  # or "melee", "ranged", "unknown"
    )
    
    embed = KillCamNarrator.create_kill_cam_embed(
        character_name=character_name,
        monster_name=monster_name,
        narration=narration
    )
    
    return embed

# Usage in Discord handler
embed = asyncio.run(trigger_kill_cam(
    character_name="Lyra",
    monster_name="Shadow Wraith",
    player_action="Final holy smite with divine light",
    damage=47,
    attack_type="spell"
))
await interaction.followup.send(embed=embed)
```

### Advanced: Custom Prompt Templates
```python
async def generate_kill_cam_custom(
    character_name: str,
    monster_name: str,
    action: str,
    damage: int,
    tone: str = "epic"  # "epic", "dark", "comedic", "tragic"
) -> str:
    """Generate kill cam with custom tone"""
    
    tone_prompts = {
        "epic": "Make it a glorious victory. Use heroic language.",
        "dark": "Make it brutal and grim. Emphasize the darkness.",
        "comedic": "Make it humorous and over-the-top.",
        "tragic": "Make it bittersweet. Victory comes with loss.",
    }
    
    tone_instruction = tone_prompts.get(tone, tone_prompts["epic"])
    
    prompt = f"""Describe the final blow in 1-2 sentences. {tone_instruction}
    
    Victor: {character_name}
    Defeated: {monster_name}
    Action: {action}
    Damage: {damage} HP
    
    Make it memorable and fit the tone."""
    
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: GROQ_CLIENT.chat.completions.create(
                    model=FAST_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,
                    max_tokens=150
                )
            ),
            timeout=10.0
        )
        
        return response.choices[0].message.content.strip()
    except:
        return f"{character_name} defeats {monster_name}. The battle is won."
```

### Integrating with Combat Statistics
```python
class CombatStatistics:
    """Track kill cam moments for statistics"""
    
    def __init__(self):
        self.kills = []
    
    async def record_kill(self, character_name, monster_name, damage, narration):
        """Record a kill moment"""
        self.kills.append({
            'timestamp': datetime.now(),
            'character': character_name,
            'monster': monster_name,
            'damage': damage,
            'narration': narration,
            'memorable': len(narration) > 100  # Longer = more detailed
        })
    
    def get_most_memorable_kill(self):
        """Get the most dramatic kill"""
        return max(self.kills, key=lambda k: len(k['narration']))
    
    async def create_kills_summary_embed(self):
        """Create an embed showing all kills this session"""
        embed = discord.Embed(
            title="⚔️ Kill Summary",
            color=0xC0392B
        )
        
        for kill in self.kills:
            embed.add_field(
                name=f"{kill['character']} vs {kill['monster']}",
                value=f"{kill['damage']} damage\n_{kill['narration'][:100]}..._",
                inline=False
            )
        
        return embed

# Usage
stats = CombatStatistics()
narration = await KillCamNarrator.generate_kill_cam(...)
await stats.record_kill("Lyra", "Wraith", 47, narration)

# Later, show summary
summary_embed = await stats.create_kills_summary_embed()
await channel.send(embed=summary_embed)
```

---

## Integration Testing

### Full Integration Test
```python
import asyncio
from cogs.dnd import (
    ReactionSuggestionEngine,
    LegacyVaultSystem,
    KillCamNarrator
)

async def test_all_features():
    """Test all three advanced features together"""
    
    print("Testing Smart Action Engine...")
    threat = ReactionSuggestionEngine.analyze_threat(
        action="Enemy casts lightning bolt",
        character_data={'class': 'Wizard'}
    )
    assert threat['threat_level'] in ['HIGH', 'MEDIUM']
    print("✅ Smart Action Engine working")
    
    print("Testing Legacy Items...")
    success = LegacyVaultSystem.add_legacy_item(
        guild_id=123,
        character_id="test_char",
        character_name="TestChar",
        generation=1,
        item_name="Test Sword",
        item_description="A test item",
        owner="Tester"
    )
    assert success
    print("✅ Legacy Items working")
    
    print("Testing Kill Cam...")
    narration = await KillCamNarrator.generate_kill_cam(
        character_name="Lyra",
        monster_name="Goblin",
        player_action="Strike",
        final_damage=25
    )
    assert len(narration) > 10
    print("✅ Kill Cam working")
    
    print("\n✅ All features tested successfully!")

# Run tests
asyncio.run(test_all_features())
```

---

## Performance Notes

### Smart Action Engine
```python
# O(n) where n = number of keywords (fixed at ~10)
# Runs in <1ms
threat = ReactionSuggestionEngine.analyze_threat(action, char)
```

### Legacy Items
```python
# Database query: O(log n) with index
# Scarring generation: O(1)
# Best case: <10ms
items = LegacyVaultSystem.discover_legacy_items(guild_id, char_id, gen)
```

### Kill Cam
```python
# Async API call: 5-10s (with 10s timeout)
# Fallback: <1ms
narration = await KillCamNarrator.generate_kill_cam(...)
```

---

## Error Handling Examples

```python
# Safe threat analysis
try:
    threat = ReactionSuggestionEngine.analyze_threat(action, None)
except Exception as e:
    print(f"Threat analysis failed: {e}")
    threat = {"threat_level": "UNKNOWN", "suggested_reactions": []}

# Safe legacy item operations
try:
    items = LegacyVaultSystem.discover_legacy_items(guild_id, char_id, gen)
except sqlite3.Error as e:
    print(f"Database error: {e}")
    items = []

# Safe kill cam with fallback
try:
    narration = await KillCamNarrator.generate_kill_cam(...)
except asyncio.TimeoutError:
    narration = "The enemy is defeated!"
except Exception as e:
    print(f"Kill cam error: {e}")
    narration = "Victory!"
```

---

**Last Updated:** January 28, 2026  
**Version:** 1.0  
**Status:** Production Ready ✅
