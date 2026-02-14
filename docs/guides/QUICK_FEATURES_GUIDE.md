# Quick Reference: Advanced Features

## 1. Smart Action Reaction Engine 🎯

**What it does:** Automatically suggests tactical reactions when enemies use threatening actions.

### How it works:
```
Player action: "The wizard casts fireball!"
↓
ReactionSuggestionEngine detects "fireball" → "AoE Spell" threat
↓
Suggests reactions: ["Cast Counterspell", "Evasive Maneuver", "Take Cover"]
↓
Button suggestions in next turn include these reactions
```

### Threat Categories:
| Threat Type | Detection | Reactions |
|---|---|---|
| AoE Spell | fireball, lightning bolt, meteor storm | Counterspell, Dodge, Take Cover |
| Direct Spell | magic missile, scorching ray | Counterspell, Shield |
| Melee Attack | attack, strike, swing | Parry, Dodge, Riposte |
| Grapple | grapple, grab, wrestle | Break Free, Escape Artist, Reversal |
| Environmental | falling, fire, poison | Cover, Antitoxin, Featherfall |

### Character-Specific:
- **Rogue** → Gets "Cunning Action" option
- **Ranger** → Gets "Hunter's Reaction" option  
- **Warlock** → Gets "Eldritch Reaction" option
- **Spellcasters** → Gets "Counterspell" prioritized for HIGH threats

---

## 2. Legacy Item Hand-me-downs 📿

**What it does:** Items from Phase 1 characters pass down to Phase 3 descendants, enhanced with void-scarring.

### Phase 1: Locking a Character
```
At end of Phase 1, when character is locked:
1. Player selects an item to pass down
2. Item stored with generation=1, owner={character_name}
3. Item description preserved for lore
```

### Phase 3: Discovering Legacy Items
```
When Phase 3 character enters game:
1. Bot checks legacy_vault for ancestor items
2. Applies void-scarring automatically:
   - Random BUFF (ability boost)
   - Random CORRUPTION (drawback)
3. Items appear in character inventory with full lore
```

### Example Progression:
```
PHASE 1: Theron's Sword of Heroes
├─ Basic +1 enchantment
├─ Stored in legacy vault
└─ generation=1

[Centuries pass in the void...]

PHASE 3: Kael discovers ancestor's sword
├─ BUFF: +1 to ALL damage rolls
├─ CORRUPTION: Can't speak lies about its void-nature
├─ Lore: "This was Theron's blade. The void has marked it."
└─ Theron's name whispers when used
```

### Possible Buffs:
- +1 to attack rolls and damage rolls
- Resistance to one damage type
- Once/day advantage on saving throws
- Emits magical light
- Extra 1d6 force damage (recharge long rest)
- Advantage vs charm/fear effects

### Possible Corruptions:
- WIS save DC 12 or act aggressive
- Disadvantage on void-related Insight checks
- Haunting dreams during rests
- Disadvantage on necrotic saves
- Can't lie about item's nature
- Item whispers (1 min/day, distracting)

---

## 3. Kill Cam Narration ☠️

**What it does:** Generates cinematic finishing move descriptions when enemies are defeated.

### How it works:
```
Player defeats final enemy
↓
run_dnd_turn() detects: HP ≤ 0 AND is_monster == 1
↓
KillCamNarrator generates dramatic narration via AI
↓
Sends embed: "☠️ FINAL BLOW ☠️"
↓
Shows victor name + defeated monster name + narration
```

### Embed Format:
```
┌─────────────────────────────────┐
│     ☠️ FINAL BLOW ☠️            │
│                                 │
│ The blade pierces through the   │
│ shadow's heart with a sickening │
│ crunch. Victory is theirs.      │
│                                 │
│ Victor: Lyra                    │
│ Defeated: Shadow Wraith         │
└─────────────────────────────────┘
```

### Example Narrations:
```
Combat Action: "Final strike with lightning bolt"
→ "The arcane bolt engulfs the creature in brilliant 
   blue light. Thunder echoes as it collapses, defeated 
   at last."

Combat Action: "Backstab the final goblin"
→ "Steel finds its mark with surgical precision. The 
   goblin gasps, then falls silent. The battle is won."

Combat Action: "Holy smite from the paladin"
→ "Divine light erupts from your weapon, searing the 
   creature's form. It crumbles to ash before you."
```

### If API Times Out:
Automatically uses fallback narrations:
- "{Character} strikes the final, decisive blow. {Monster} falls."
- "With one last surge of power, {Character} brings {Monster} to its knees."
- "The battle is over. {Monster} lies defeated by {Character}'s determination."

---

## How to Trigger Each Feature

### Feature 1: Smart Actions
✅ **Automatic** - Happens during any turn
- When threat keyword detected in AI/player action
- Suggestions automatically added to next turn buttons
- No player action needed

### Feature 2: Legacy Items
**Phase 1 → Phase 3:**
1. At end of Phase 1 (when locking character):
   - Player selects item to pass down via modal
   - `LegacyVaultSystem.add_legacy_item()` called
   
2. When Phase 3 character spawned:
   - `discover_legacy_items()` automatically called
   - Items added to character inventory
   - Void-scarring effects applied

**Manual addition (for DMs):**
```python
# Add item to vault manually
LegacyVaultSystem.add_legacy_item(
    guild_id=123456789,
    character_id="987654321",
    character_name="Kael",
    generation=1,
    item_name="Sword of Heroes",
    item_description="A legendary blade passed through generations",
    owner="Theron"
)
```

### Feature 3: Kill Cam
✅ **Automatic** - Happens when enemy dies
- When monster HP reduced to 0 or below
- `KillCamNarrator.generate_kill_cam()` called
- Narration embed sent automatically
- No player action needed

---

## Database Structure

### legacy_vault table:
```sql
SELECT * FROM legacy_vault WHERE guild_id = '123456789';

id | guild_id | character_id | item_name | owner | is_void_scarred | scarring_effect
1  | 123456789| alice_id     | Sword     | Alice | 0               | NULL
2  | 123456789| bob_id       | Amulet    | Bob   | 0               | NULL

-- After Phase 3 discovery:
2  | 123456789| bob_id       | Amulet    | Bob   | 1               | "+1 damage"
```

---

## Troubleshooting

**Q: Why isn't the smart engine suggesting actions?**  
A: Check if the threat keyword is in the THREAT_KEYWORDS dict. Add custom keywords in ReactionSuggestionEngine if needed.

**Q: Legacy items not showing in Phase 3?**  
A: Verify legacy_vault table was created. Check that `discover_legacy_items()` is called when Phase 3 character spawns.

**Q: Kill cam narration is generic/fallback?**  
A: Check API timeout (10s). Try again - may be API rate limit. Generic fallback is intentional.

**Q: Can I customize scarring effects?**  
A: Yes! Modify `_generate_void_scarring()` to add custom buffs/corruptions.

---

## API Integration

All three features integrate with:
- ✅ Discord.py 2.0 (buttons, embeds, modals)
- ✅ Groq API (only Kill Cam uses async API call)
- ✅ SQLite3 database (Legacy Items only)
- ✅ PrecomputationEngine (already in codebase)

---

**Status:** ✅ All features active and tested  
**Last Updated:** January 28, 2026  
**Version:** 1.0
