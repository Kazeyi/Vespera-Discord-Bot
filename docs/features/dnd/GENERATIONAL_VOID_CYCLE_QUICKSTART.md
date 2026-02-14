# Generational Void Cycle - Quick Start Guide

## 🎯 Getting Started

The new Generational Void Cycle system is now integrated into your D&D cog. Here's how to use it:

---

## 📌 Step 1: Choose Your Mode

**Command**: `/mode_select`

Choose how your campaign will be run:

### 🏗️ **Architect Mode** (Recommended - Default)
Vespera (the bot) manages everything:
- Automatically selects biomes
- Shifts narrative tone based on scene context
- Full control over story progression
- Best for hands-off DM experience

### 📜 **Scribe Mode** (Manual Override)
Players get more control:
- Manually select starting biome
- Pick a persistent tone for the session
- More player agency in narrative
- Best for collaborative storytelling

---

## ⏳ Step 2: Run Sessions Across Three Phases

### **Phase 1: The 12 Conquest** (Levels 1-20)
- Players start as new heroes
- Face mini-bosses and a boss appropriate to chosen biome
- Build legendary status through destiny rolls

### **Phase 2: Transcendence** (Levels 21-30, ~20-30 years later)
- Time skip happens automatically with `/time_skip`
- Original heroes return as legends in an aged world
- Face epic-level threats
- Achieve legendary status through completing the phase

### **Phase 3: The Legacy** (~500-1000 years later)
- New generation of characters (descendants)
- Phase 1/2 heroes locked out - become "Soul Remnants" (mini-bosses)
- Fight Double Mini-Boss Gauntlet
- Defeat the Void Boss to break the cycle
- Get recorded in eternal Chronicles

---

## 🔄 Time Skip System

### **How Chronos Engine Works**:

**Phase 1→2**:
- Random time skip: **20-30 years** (≈0.8-1.2 generations)
- Use `/time_skip` command to advance

**Phase 2→3**:
- Random time skip: **500-1000 years** (≈20-40 generations!)
- Legacy data automatically created for all Phase 2 characters
- Soul Remnants generated for Phase 3 encounters

### **Example Output**:
```
⏳ Chronos Engine: Time Skip
Years Elapsed: 847 years
Phase Transition: Phase 2 → Phase 3
Generations Passed: 33 generations
Dynasties Changed: 8
Total Time Elapsed: 877 years since campaign start
```

---

## 🎨 Tone Shifting System (Architect Mode)

The bot automatically shifts tone based on what's happening:

| Scene Context | Tone | Narrative Style |
|---------------|------|-----------------|
| Combat starts | Gritty | Visceral, brutal, high-danger |
| Boss defeated | Dramatic | Epic, cinematic, world-changing |
| Time skip | Melancholy | Poetic, reflective, passage of time |
| Boss appears | Mysterious | Riddling, ominous, eerie |
| NPC meeting | Humorous | Witty, playful, clever |
| Default | Standard | Balanced high-fantasy adventure |

No action needed - the bot detects context automatically!

---

## 👥 Character Management

### **Phase 1 & 2**:
- Import characters normally with `/import_character`
- Characters level up through adventures
- Destiny rolls determine narrative importance

### **Phase 3** (New Generation):
1. Phase 1/2 characters are **automatically locked**
2. They become "Soul Remnants" - mini-bosses to fight
3. Players create **descendant characters**:
   - Start at Level 1 (reset)
   - Inherit "Legacy Buff" from ancestor
   - Legacy buff examples:
     - +2 to saving throws
     - Resistance to psychic damage
     - Advantage on related ability checks
     - Occasional guaranteed success

---

## 📜 Chronicles: Victory Scroll

### **What Is It?**:
Permanent record of your entire campaign across all 3 phases

### **How to View**: 
```
/chronicles
```

### **What It Shows**:
- **The Founder**: Phase 1 hero who started everything
- **The Legend**: Phase 2 hero who drove the story forward
- **The Savior**: Phase 3 hero who broke the cycle
- **Timeline**: Total years, generations, dynasties, cultural shifts
- **Realm**: Which biome the story took place in
- **Final Victory**: The boss that was defeated
- **Eternal Guardians**: Heroes recorded for future campaigns

### **Example**:
```
📜 THE CHRONICLES OF AGES PAST 📜

⚔️ PHASE 1: THE FOUNDER
Thralor the Brave (The Conquest)
First hero to face the void.

👑 PHASE 2: THE LEGEND
Silvara the Wise (The Transcendence)
847 years after the Founder's deeds.

🌟 PHASE 3: THE SAVIOR
Kael of the New Age (The Legacy)
Descendant who broke the cycle.

📍 REALM: The Ocean

⏳ TIME ELAPSED: 847 years, 33 generations

🏆 FINAL VICTORY: Defeated the Abyssal Singularity
```

---

## 🌍 The Six Biomes

Each biome has unique encounters across all three phases:

### **Ocean** (Color: Blue)
- P1: Face the Kraken → Boss: Leviathan
- P2: Face Jormungandr → Boss: Cetus
- P3: Echo Leviathan + The Abyssal Singularity

### **Volcano** (Color: Red)
- P1: Face Fire Drake → Boss: Red Dragon
- P2: Face Nidhogg → Boss: Magma Titan
- P3: Echo Red Dragon + The Eternal Cinder

### **Desert** (Color: Orange)
- P1: Face Sandworm → Boss: Grootslag
- P2: Face Behemoth → Boss: Elder Sphinx
- P3: Echo Grootslag + The Entropy Siphon

### **Forest** (Color: Green)
- P1: Face Giant Spider → Boss: Leshy
- P2: Face Green Dragon → Boss: World-Root
- P3: Echo Leshy + The Withered Heart

### **Tundra** (Color: Blue-Grey)
- P1: Face Yeti → Boss: Frost Giant
- P2: Face Cryo-Hydra → Boss: Rime-Worm
- P3: Echo Frost Giant + The Absolute Zero

### **Sky** (Color: Light Blue)
- P1: Face Wyvern → Boss: Storm Roc
- P2: Face Quetzalcoatl → Boss: Sky-Shatterer
- P3: Echo Storm Roc + The Void Horizon

In **Architect Mode**: Biome selected randomly each session  
In **Scribe Mode**: Players choose their biome

---

## 🔐 Soul Remnants Explained

When Phase 3 begins:

1. **All Phase 1/2 characters become "Soul Remnants"**
   - Corrupted echoes of the original heroes
   - Appear as mini-bosses in Phase 3 dungeons
   - Mix of their original stats + void corruption

2. **Double Mini-Boss Gauntlet**:
   - First: Face the "Echo" (shadow of previous phase boss)
   - Second: Face the "Soul Remnant" (corrupted original PC)
   - Both must be defeated to progress

3. **Example Battle**:
   ```
   🌀 Phase 3 Encounter
   
   First Boss: Echo Leviathan
   → Distorted version of the original Phase 1 boss
   → Attacks: Reality Tears, Memory Leaks
   
   Second Boss: Soul Remnant (Thralor)
   → Corrupted version of Phase 1 founder Thralor
   → Uses his signature move but twisted
   → Emotional battle against a hero gone wrong
   ```

---

## 📋 Command Reference

| Command | Permission | Use |
|---------|-----------|-----|
| `/mode_select` | Server Manager | Choose Architect or Scribe mode |
| `/time_skip` | Server Manager | Advance to next phase with random time jump |
| `/chronicles` | Players | View campaign victory scroll |
| `/setup_dnd` | Server Manager | Initial D&D setup (unchanged) |
| `/start_session` | Players | Begin a session (unchanged) |
| `/do` | Players | Take an action (unchanged) |
| `/import_character` | Players | Import character sheet (unchanged) |
| `/roll_initiative` | Players | Start combat (unchanged) |

---

## 🎲 Sample Campaign Flow

### **Week 1-2: Phase 1**
```
1. /setup_dnd <channel> - Configure D&D
2. /mode_select - Choose Architect (recommended)
3. Players: /import_character
4. /start_session - Begin Phase 1
5. Run sessions with /do
6. Build up legend status
```

### **Week 3: Phase 2 Transition**
```
1. /time_skip - Advance to Phase 2
   → "847 years have passed..."
   → New generation arrives
   → 33 generations changed
2. Original Phase 1 heroes can continue as "Legends"
3. New NPCs and challenges in aged world
```

### **Week 4-5: Phase 2**
```
1. Continue sessions at epic levels (21-30)
2. Face Phase 2 bosses
3. Build new legends
```

### **Week 6: Phase 3 Transition**
```
1. /time_skip - Advance to Phase 3
   → "500-1000 years have passed..."
   → Huge time jump!
   → Phase 1/2 characters become Soul Remnants
2. Players create descendant characters
3. Legacy buffs inherited from ancestors
```

### **Week 7-8: Phase 3**
```
1. New generation runs Phase 3
2. Face Soul Remnants of past heroes
3. Defeat Void Boss
4. Campaign victory!
```

### **Campaign Complete**
```
1. /chronicles - View victory scroll
2. Campaign recorded with all three heroes
3. Create next campaign - eternal guardians become legacy!
```

---

## 💡 Pro Tips

1. **For Architects (Hands-off)**:
   - Let Architect Mode handle everything
   - Focus on enjoying the story
   - Let tone shift naturally

2. **For Scribes (Collaborative)**:
   - Use Scribe Mode for player input
   - Let players choose biome
   - Negotiate tone preferences

3. **For Maximizing Drama**:
   - Use Phase 3 Soul Remnants as emotional encounters
   - Reference Phase 1/2 hero achievements
   - Make descendants feel the weight of legacy

4. **For Multiple Campaigns**:
   - Record Eternal Guardians from previous campaigns
   - Link future campaigns to past successes
   - Create world history through cycles

---

## ❓ FAQ

**Q: Do I have to use all the new features?**  
A: No! Existing commands work as before. New features are opt-in.

**Q: Can I switch modes mid-campaign?**  
A: Yes! Use `/mode_select` anytime to switch.

**Q: What if Phase 3 is too hard?**  
A: Adjust difficulty using `/difficulty` or remove Soul Remnants.

**Q: How many campaigns can I run?**  
A: Unlimited! Each biome can have infinite Phase cycles.

**Q: Can players create characters at different levels in Phase 2?**  
A: Yes, but they should match (Levels 21-30) to be epic-appropriate.

**Q: What if a player misses Phase 2?**  
A: They become NPC legends. New players join as Phase 3 descendants.

---

## 🚀 Ready to Begin!

1. Run `/mode_select` to choose your mode
2. Use `/setup_dnd` if not already done
3. Have players `/import_character`
4. Run `/start_session` and begin adventuring!
5. When ready: `/time_skip` to advance phases

**May your campaigns be legendary!** 🎲✨
