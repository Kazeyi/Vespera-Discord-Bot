# 🛡️ Utility Core

The Utility Core is the shared infrastructure layer powering Vespera's everyday capabilities. It manages personality consistency, memory budgeting, language processing, and automated moderation.

---

## VesperaPersonality — Singleton

All 15+ cogs import their prompts, embed colors, and error messages from a single `VesperaPersonality` static class. This prevents **Personality Drift** — where the bot sounds like a corporate assistant in one command and a pirate in another.

```python
class VesperaPersonality:
    NAME = "Vespera"
    TITLE = "The Silent Architect"

    class Colors:
        PRIMARY = 0x2C2F33   # Dark grey (base)
        SUCCESS = 0x57F287   # Muted green
        ERROR   = 0xED4245   # Red
        MYSTIC  = 0x9B59B6   # Purple (D&D)
        CLOUD   = 0x38BDF8   # Sky blue (Cloud)
```

Changing Vespera's tone requires editing **one file** — the change propagates instantly across all modules.

---

## 🌍 Translator

**Status:** `Lazy Glossary Optimized` · `Personality Integrated`

AI-powered translation with deep awareness of D&D and Cloud Engineering terminology.

### Translation Styles

| Style | Description |
|-------|-------------|
| **Formal** | Professional, business-appropriate tone |
| **Informal** | Casual conversation style |
| **Slang** | Internet slang and idioms |
| **Lyrical** | Poetic or dramatic — great for D&D narration |

### Smart Glossaries

- **D&D Glossary**: *Fireball, Saving Throw, Advantage, Concentration...*
- **Cloud Glossary**: *Kubernetes, Docker, Serverless, VPC, IAM...*

### Triggers

- Slash command: `/translate <text> <language> <style>`
- Reaction trigger: Add a flag emoji (🇺🇸 🇯🇵 🇩🇪) to any message to auto-translate it

### Technical Highlight — Lazy Glossary Injection

!!! tip "95% Prompt Size Reduction"
    The glossary is NOT injected by default. The system scans the input text for known technical keywords first. Only terms present in the input are added to the prompt.

    | Without Lazy Injection | With Lazy Injection |
    |------------------------|---------------------|
    | ~2,000 token glossary sent every time | ~100 tokens of relevant terms only |
    | RAM: ~60MB | RAM: ~25MB |

---

## 📝 TL;DR

**Status:** `JSON Optimized` · `String Interned`

Instant summarization of Discord chat logs or uploaded text files, optimized for low-memory environments.

### Modes

| Mode | Output |
|------|--------|
| **Summarize** | General overview paragraph |
| **Action Items** | Extracted to-do list and assignments |
| **Key Points** | Bulleted list of critical information |

### Input Support

- Last N messages from Discord chat history
- Uploaded `.txt`, `.md`, or `.log` files

### Technical Highlight — String Interning

!!! tip "Memory Optimization Detail"
    When summarizing a long chat log, usernames and common headers repeat thousands of times. The TL;DR module uses `sys.intern()` on repeated strings, ensuring that if `"User_Kazeyi"` appears 1,000 times, only **one string object** exists in memory — not 1,000 copies.

    Large files are also processed in **stream-safe chunks** to avoid loading the entire file into RAM at once.

---

## 🛡️ Moderator

**Status:** `Vespera Integrated`

Automated threat analysis using AI sentiment and context scoring — far beyond simple keyword REGEX.

### How it works

1. The message and surrounding context are passed to the AI with a structured `[Reasoning]` block requirement
2. The model must reason through: *"User said X, context is Y, therefore hostility is..."* before committing to a score
3. A **Hostility Score (0–10)** is returned and acted upon

### Technical Highlight — Chain-of-Thought for Moderation

!!! warning "Why CoT matters here"
    If a model is allowed to start its response with `"This message is safe"`, it is statistically biased to justify that conclusion — even when wrong (false negatives).

    By forcing a `[Reasoning]` block **first**, the model must step through its logic before committing to a verdict, significantly reducing both false positives and false negatives in moderation.

### Optimizations

- **LRU Cache**: Analysis results for frequently repeated phrases are cached (max 128 entries), avoiding redundant API calls for known-safe content
- **Personality Integration**: All violation embeds use `VP.Colors.ERROR` and Vespera's firm but professional tone — no robotic automated-sounding warnings
