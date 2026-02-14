# 📖 Rulebook Ingestor - DM Guide

## What This Does

Transform your static rulebook markdown files into a **dynamic, searchable knowledge base** that updates automatically. Perfect for homebrewed campaigns where rules change mid-adventure.

### Real-World Scenario

**Before Rulebook Ingestor:**
```
Player: "Wait, what's Advantage again?"
DM: *flips through PHB* "Okay, so you roll two d20s..."
AI DM: *no context, might contradict earlier ruling*
```

**After Rulebook Ingestor:**
```
Player: "/lookup_rule keyword:advantage"
Bot: *instantly returns full rule + related mechanics*
AI DM: *automatically includes Advantage/Disadvantage context*
```

---

## For Dungeon Masters

### Setup (One-Time)

1. **Place your rulebook in `bot/srd/` folder**

   ```
   bot/
   └── srd/
       ├── RulesGlossary.md      ← Main rulebook (already there!)
       ├── homebrew_feats.md     ← Your custom rules
       ├── campaign_rules.md     ← Campaign-specific mechanics
       └── spell_modifications.md
   ```

2. **Create markdown files with this format:**

   ```markdown
   # Campaign Rules

   ## Core Mechanics

   #### Inspiration [Mechanic]

   In this campaign, you gain Inspiration when:
   - You roleplay your character's flaw
   - You help another player succeed at something
   
   You can spend Inspiration to reroll a d20.
   
   *See also* "Heroic Inspiration" and "Reroll".

   #### Reroll [Mechanic]

   A reroll allows you to roll a d20 again instead of
   using your original result. You must use the new roll.

   #### Custom Feat: Lucky Charm [Ability]

   Once per long rest, you can gain advantage on one
   ability check of your choice.
   ```

3. **Ingest via Discord (Admin Only):**

   ```
   /ingest_rulebook filename:homebrew_feats.md source:Campaign 2024
   ```

   **Bot responds:**
   ```
   📚 Rulebook Ingestion Complete
   File: homebrew_feats.md
   Inserted/Updated: 8
   Skipped: 0
   Source: Campaign 2024 | Memory-optimized streaming parser
   ```

### During Play

#### Let Players Look Up Rules

```
Player: "Can I do this?"
You: "/lookup_rule keyword:custom follow_links:True"
Bot: *displays full rule + anything referenced in "See also"*
```

#### Check Your Campaign Rules Anytime

```
/lookup_rule keyword:inspiration
# Returns your custom Inspiration mechanic
```

#### Verify Action Validity

ActionEconomyValidator **automatically** uses your custom rules:

- Player tries action not in standard D&D
- Validator queries database for [Action] tagged rules
- Uses your custom actions if present
- No bot restart needed!

### Mid-Campaign Rule Changes

**Scenario:** You want to nerf a spell during the campaign.

1. Update `spell_modifications.md`:
   ```markdown
   #### Fireball [Spell Modification]
   
   (Original: 8d6 damage. Modified for this campaign:)
   
   Fireball now deals 6d6 fire damage instead of 8d6.
   Area remains 20-foot radius.
   
   *See also* "Evocation Spells" and "Area of Effect".
   ```

2. Ingest it:
   ```
   /ingest_rulebook filename:spell_modifications.md source:Campaign Update 2024
   ```

3. **Next session:** Everyone sees the updated rule!
   ```
   /lookup_rule keyword:fireball
   # Returns: Updated 6d6 version
   ```

---

## Markdown Format Reference

### Headers

```markdown
#### Keyword [Type]
```

**Required:** `#### Keyword`  
**Optional:** `[Type]` (defaults to "general")

**Common Types:**
- [Action] - Takes an action during turn
- [Bonus Action] - Takes a bonus action
- [Reaction] - Reaction trigger
- [Mechanic] - Game mechanic
- [Condition] - Status effect (blinded, prone, etc.)
- [Spell] - Spell description
- [Ability] - Character ability/feat
- [Equipment] - Item or gear

### "See Also" References

```markdown
*See also* "Linked Rule" and "Another Rule".
```

These are automatically extracted and provided when players lookup related rules.

**Variations:**
- `*See also* "Rule1" and "Rule2"`
- `*See also* "Rule1", "Rule2", and "Rule3"`
- `*See also* "Rule1"; "Rule2"`

### Examples

#### Complete Rule Entry

```markdown
#### Hold Person [Spell]

**Casting Time:** 1 action  
**Range:** 60 feet  
**Duration:** Concentration, up to 1 minute

A humanoid creature that you can see within range must
succeed on a Wisdom saving throw or be paralyzed for
the duration.

At the end of each of the creature's turns, it can
repeat the saving throw.

*See also* "Concentration", "Paralyzed Condition", and "Saving Throws".

#### Paralyzed [Condition]

A paralyzed creature can't move or speak, and fails any
Strength or Dexterity saving throw. Attack rolls against
the creature have advantage if the attacker is within 5 feet.

*See also* "Conditions" and "Saving Throws".
```

---

## Real-World Examples

### Example 1: Homebrew Subclass Rules

**File:** `srd/homebrew_subclasses.md`

```markdown
# Homebrew Subclasses

#### Wild Magic Warlock [Subclass]

Pact of the Wild Magic grants you:

- Bonus Spell: Magic Missile (no components)
- Wild Surge: On crit, roll d8:
  - 1-4: Spell backfires (you take damage)
  - 5-8: Spell triggers twice

*See also* "Warlock", "Crit", and "Magic Missile".

#### Crit [Mechanic]

A natural 20 on an attack roll is a critical hit.
You roll all damage dice twice and add them together.

*See also* "Attack Roll" and "Damage".
```

**Ingest:**
```
/ingest_rulebook filename:homebrew_subclasses.md source:Campaign 2024
```

### Example 2: Campaign-Specific Mechanics

**File:** `srd/void_cycle_rules.md`

```markdown
# Void Cycle Campaign Rules

#### Soul Remnant [Mechanic]

When a character dies in Phase 1, their Soul becomes:
- A corrupted mini-boss in Phase 3
- Uses their original abilities (modified)
- Treats all players as enemies

Defeating your Soul Remnant grants:
- 1000 XP
- Redemption Point (use in Phase 3)

*See also* "Phase 3", "Campaign Phases", and "Mini-Boss".

#### Redemption Point [Currency]

Special currency earned in Phase 3 by:
- Defeating your ancestor's Soul Remnant
- Completing legacy quests
- Answering the Call of your bloodline

Spend Redemption Points to:
- Restore 10 HP
- Reroll a saving throw
- Gain advantage on next attack

*See also* "Soul Remnant" and "Phase 3".
```

**Ingest:**
```
/ingest_rulebook filename:void_cycle_rules.md source:Void Cycle Campaign
```

### Example 3: Spell House Rules

**File:** `srd/spell_balance.md`

```markdown
# Spell Balance Changes

#### Fireball [Spell - House Rule]

**OFFICIAL:** 8d6 fire damage, 20-foot radius  
**HOUSE RULE:** 6d6 fire damage, 20-foot radius

Why: Too powerful at mid-levels. Reduced to maintain
challenge while keeping spell viable.

Duration, range, and casting time unchanged.

*See also* "Fireball (Official)" and "Evocation Spells".

#### Wish [Spell - Restricted]

This spell is banned from our campaign due to its
reality-bending nature. Talk to DM if you want to
attempt wishes through roleplay.

*See also* "Banned Spells".
```

**Ingest:**
```
/ingest_rulebook filename:spell_balance.md source:House Rules 2024
```

---

## Checking What's Ingested

### Via Discord

```
/lookup_rule keyword:fireball
# Shows: Fireball rule you ingested
```

### Via Database (Direct Query)

```bash
# See all custom rules
sqlite3 bot_database.db "SELECT keyword, rule_type FROM dnd_rulebook WHERE source LIKE '%Campaign%';"

# Count by category
sqlite3 bot_database.db "SELECT rule_type, COUNT(*) FROM dnd_rulebook WHERE source='Campaign 2024' GROUP BY rule_type;"

# Find all rules with "spell" in name
sqlite3 bot_database.db "SELECT keyword FROM dnd_rulebook WHERE keyword LIKE '%spell%';"
```

---

## Tips & Tricks

### Tip 1: Progressive Ingestion

Don't put everything in one file. Create separate files for:
- Core campaign rules
- Homebrew classes
- Spell modifications
- Condition changes
- Quest-specific mechanics

**Why:** Easier to update individual sections without re-ingesting everything.

### Tip 2: Clear Organization

Use consistent formatting:
```markdown
#### [KEYWORD] [Type]
[Rule text]
*See also* "Related Rule"
```

### Tip 3: Link Your Rules

Use "See also" extensively. This creates a web of related rules that players can explore:

```
Know Advantage?
→ See also "Disadvantage"
  → See also "D20 Test"
    → See also "Ability Checks"
```

### Tip 4: Version Your Rules

Include date or version in source:

```
/ingest_rulebook filename:spells_v2.md source:Campaign 2024-01-15
/ingest_rulebook filename:spells_v3.md source:Campaign 2024-02-01
```

Then players see when a rule was last updated.

### Tip 5: Test Before Campaign

Run the test script to see how your rules ingested:

```bash
python3 test_rulebook_ingestor.py
```

This shows:
- How many rules were found
- Memory efficiency
- Auto-refresh of action keywords

---

## Troubleshooting

### "File not found"

```
❌ /ingest_rulebook filename:my_rules.md
❌ Error: Rulebook not found: srd/my_rules.md
```

**Fix:**
1. Create `bot/srd/my_rules.md`
2. Use exact filename (case-sensitive)
3. Try again

### "Empty results on lookup"

```
❌ /lookup_rule keyword:myfeature
❌ No rules found for 'myfeature'
```

**Debugging:**

1. Check if rule was ingested:
   ```bash
   sqlite3 bot_database.db "SELECT * FROM dnd_rulebook WHERE keyword='myfeature';"
   ```

2. Check formatting of rule header:
   ```markdown
   #### MyFeature [Ability]  ← Must be #### (4 #'s)
   ```

3. Re-ingest file:
   ```
   /ingest_rulebook filename:my_rules.md
   ```

### "Old version still showing"

Rulebooks are **added/updated**, not replaced.

**Solution:** Delete and re-ingest

```bash
# Delete all rules from that source
sqlite3 bot_database.db "DELETE FROM dnd_rulebook WHERE source='Campaign 2024';"

# Re-ingest the file
# /ingest_rulebook filename:campaign.md source:Campaign 2024
```

---

## Advanced: Bulk Edit

**Update all spell damage in one file:**

```markdown
#### Fireball [Spell] 
6d6 fire damage (was 8d6)

#### Lightning Bolt [Spell]
6d6 lightning damage (was 8d6)

#### Cone of Cold [Spell]
6d6 cold damage (was 8d6)
```

**Ingest once:**
```
/ingest_rulebook filename:spell_balance.md source:Nerf Patch 2024
```

**All at once:**
- ✅ 3 spells updated
- ✅ Players see changes immediately
- ✅ No restart needed
- ✅ Old versions auto-replaced

---

## Best Practices

✅ **DO:**
- Create one file per topic (spells, feats, conditions)
- Use "See also" to link related rules
- Version your rules (include date)
- Test in a private channel first
- Keep rules concise and clear

❌ **DON'T:**
- Put 1000 rules in one file (slow to edit)
- Forget the `####` header (won't parse)
- Mix multiple languages in one file
- Delete rules you think aren't used (they might be!)

---

## Summary

**Rulebook Ingestor gives you:**

✅ **Community-Ready Rulebooks** - Players can look up any rule  
✅ **Live Updates** - Change rules mid-campaign  
✅ **Smart Context** - Related rules auto-fetched  
✅ **Memory Efficient** - Works on 1GB RAM  
✅ **Backward Compatible** - Standard D&D rules still work  

**3-Step Process:**
1. Create markdown file in `bot/srd/`
2. `/ingest_rulebook filename:yourrules.md`
3. Players: `/lookup_rule keyword:yourfeature`

**That's it!** 🎉

Your rulebook is now community-ready and your AI DM has context.
