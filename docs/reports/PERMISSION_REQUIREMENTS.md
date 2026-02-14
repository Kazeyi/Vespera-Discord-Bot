# Vespera Bot - Feature Permission Requirements

**Principle:** Least Privilege Access Control  
**Review Date:** January 15, 2026

---

## 🎯 Core Question: What Does Each Feature Actually Need?

### Translation System (`/subtitle`, `Translate`)

**What it does:**
- Translates text to target language with specific tone
- Supports 4 tones: Formal, Informal, Slang, Lyrical
- Optional romanization for Asian languages

**Who needs it:** Everyone
**Who can use it:** Everyone

**Permissions Required:**
- ❌ manage_guild - NO
- ❌ administrator - NO
- ❌ send_messages - NO (responder does this)
- ✅ message_content intent - YES (to read if using context menu)
- ✅ read_message_history - Implicit in default

**Rate Limit:** 5 seconds per user (prevents API abuse)

**Why 5s?**
- Gemini/Groq API costs money per call
- Without limit: 1 user = 720 calls/hour
- With 5s limit: 1 user = 144 calls/hour (safer)

**Input Limits:**
- Text: 2000 chars (API token limit)
- Language: 50 chars (enum protection)
- Style: Dropdown only (no user input)

---

### TL;DR System (`/tldr`, `TL;DR`)

**What it does:**
- Summarizes last N chat messages
- Highlights VIPs (with star emoji)
- Context analysis mode (right-click)

**Who needs it:** Everyone
**Who can use it:** Everyone

**Permissions Required:**
- ❌ manage_guild - NO
- ❌ administrator - NO
- ✅ message_content intent - YES (to read messages)
- ✅ read_message_history - YES (to fetch chat history)

**Rate Limit:** 10 seconds per user

**Why 10s?**
- Requires reading up to 100 messages from history
- AI call to summarize
- Heavier operation than translate

**Input Limits:**
- Message limit: 1-100 (user input)
- Language: Auto-detected from user preference

---

### D&D System (`/do`, `/init`, `/long_rest`, etc.)

**What it does:**
- Complete tabletop RPG engine
- Party management, combat tracking
- AI-driven dungeon master

**Who needs it:** D&D campaign participants
**Who can use it:** Configurable per server

**Permissions Required:**
- ✅ members intent - YES (for role checking)
- ✅ manage_guild - YES (for setup/config)
- ❌ administrator - NO (moderate access sufficient)

**Role-Based Access Control:**
```
Priority Order:
1. Bot Owner (always allowed)
2. User has manage_guild permission
3. User has D&D role (if configured)
4. User in D&D parent channel
5. Public access (if no role configured)
```

**Rate Limits:**
- `/do` action: 3 seconds per user (most intensive)
- Other commands: No limit (already access-controlled)

**Input Limits:**
- Action: 200 chars (AI prompt limit)
- NPC name: 100 chars
- Lore topic: 100 chars
- Lore description: 500 chars

**Why members intent is needed:**
- Must check user's roles in guild
- Validates D&D access permissions
- Cannot be done without members intent

---

### Moderation System (`/setup_mod`, `/my_rep`, `/settings`)

**What it does:**
- Tracks user toxicity scores
- Configurable per-server moderation
- AI model selection per server

**Who needs it:** Moderators
**Who can use it:** Everyone (for `/my_rep`)

**Permissions Required:**
- ❌ message_content - NO (not reading messages)
- ❌ members - NO (not checking roles)
- ✅ manage_guild - YES (for setup/settings)

**Role-Based Access:**
- `/setup_mod` - Moderator (manage_guild)
- `/settings` - Moderator (manage_guild)
- `/setmodel` - Owner only
- `/my_rep` - Public
- `/test_alert` - Administrator

---

### Admin System (`/status`)

**What it does:**
- Shows VPS health metrics
- CPU usage, RAM, uptime
- Operational efficiency %

**Who needs it:** Bot administrator
**Who can use it:** Bot owner only

**Permissions Required:**
- ❌ message_content - NO
- ❌ members - NO
- ❌ guilds - NO
- ✅ is_owner - YES (checked via Discord Dev Portal)

**Why owner-only?**
- Exposes system resource metrics
- Could reveal infrastructure details
- Should be restricted to trust circle

---

### Help System (`/help`)

**What it does:**
- Displays available commands
- Conditional sections based on access

**Who needs it:** Everyone
**Who can use it:** Everyone

**Permissions Required:**
- ✅ members intent - YES (to check if user can access D&D)
- ❌ manage_guild - NO (used for checks only)

**Conditional Sections:**
- D&D section: Shown if user is D&D player OR manage_guild
- Admin section: Shown if user has manage_guild
- Owner section: Shown if bot owner

---

## 📊 Intent Permission Mapping

### Intent: `message_content`

**Required By:**
- ✅ `/subtitle` (read message context)
- ✅ `Translate` context menu (read message to translate)
- ✅ `/tldr` (read message history)
- ✅ `TL;DR` context menu (read context messages)

**Risk Level:** MEDIUM
- Allows bot to read all message text
- Required for text analysis features
- Cannot be eliminated without breaking translate/tldr

**Mitigation:**
- No message logging
- No message storage (analyzed on-the-fly)
- Responses are ephemeral
- Rate limiting prevents mass collection

---

### Intent: `members`

**Required By:**
- ✅ D&D access control (check user roles)
- ✅ `/help` visibility (check access level)
- ✅ `/setup_dnd` (validate permissions)
- ✅ TLDR formatting (identify VIP roles)

**Risk Level:** LOW
- Only checks if user has role
- No member data storage
- No member monitoring
- No presence tracking

**Mitigation:**
- Only used for permission checks
- Discarded after validation
- No caching of member lists
- Access control verified multiple times

---

## ❌ Removed Intents

### `voice_states` - ✅ REMOVED
**Was it used?**
- Previously: D&D voice connection tracking
- Currently: Manual voice connect (not automated)
- Reason: Feature was disabled, intent no longer needed

**Risk of having it:**
- Tracks user voice channel changes
- Unnecessary surveillance capability

---

### `presences` - ✅ REMOVED
**Was it used?**
- Never used in any command
- Was implicit in `discord.Intents.default()`
- Reason: Bot doesn't track user online status

**Risk of having it:**
- Tracks when users go online/offline
- Tracks user activities
- Major privacy concern for unused feature

---

## 🔐 Permission Decision Tree

```
NEW COMMAND? USE THIS FLOW:

┌─────────────────────────────┐
│ What data does it access?   │
└────────────────┬────────────┘
       ┌─────────┼─────────┐
       ▼         ▼         ▼
    Messages  Members   None
       │         │        │
       ▼         ▼        ▼
    Need        Need    No Intent
   message_    members  Needed
   content     intent
       │         │        │
       ▼         ▼        ▼
    ┌────────────┴─────────┐
    │ Who should use this? │
    └────────┬─────────────┘
       ┌─────┼─────┬──────┐
       ▼     ▼     ▼      ▼
    Public Admin Mod  Owner
       │     │    │      │
       ▼     ▼    ▼      ▼
     No   Use   Use   Use
    Perm admin manage @is_owner
        perm   guild
       │     │    │      │
       ▼     ▼    ▼      ▼
    Rate  No   Verify  No
   Limit Rate  Config  Ratelimit
       │    Limit
       ▼
    Is it AI?
    ├─Yes → Rate limit (3-10s)
    └─No → No rate limit
```

---

## ✅ Permission Checklist Template

When adding a new command:

```python
@app_commands.command(name="mycommand")
# Step 1: Add permission check
@app_commands.default_permissions(manage_guild=True)  # OR
@app_commands.check(is_bot_owner)                    # OR
# Leave empty for public
async def my_command(self, interaction, user_input):
    # Step 2: Rate limit if needed
    if self.is_rate_limited(interaction.user.id):
        return await interaction.response.send_message("⏳ Slow down!")
    
    # Step 3: Validate input length
    if len(user_input) > MAX_LENGTH:
        return await interaction.response.send_message("❌ Too long!")
    
    # Step 4: Sanitize input
    user_input = sanitize_input(user_input, max_length=MAX_LENGTH)
    
    # Step 5: Defer if async work
    await interaction.response.defer()
    
    # Step 6: Do work
    result = await do_something(user_input)
    
    # Step 7: Respond (ephemeral if sensitive)
    await interaction.followup.send(result, ephemeral=True)
```

---

## 📋 Permission Change Log

### January 15, 2026 - Security Hardening
- ✅ Removed `voice_states` intent (unused)
- ✅ Removed `presences` intent (privacy)
- ✅ Added rate limiting to translate
- ✅ Added rate limiting to D&D `/do`
- ✅ Added input sanitization to all AI commands
- ✅ Added length validation to all user inputs
- ✅ Documented complete permission matrix

### January 10, 2026 - D&D Personality
- ✅ Added Vespera personality to D&D embeds
- ✅ Verified D&D access control logic

### January 8, 2026 - Initial Refactor
- ✅ Restored commands from legacy codebase
- ✅ Fixed syntax errors
- ✅ Verified all 6 cogs load

---

## 🎯 Current State Summary

| Feature | Public | Mod | Owner | Rate Limit | Validated | Intents |
|---------|--------|-----|-------|-----------|-----------|---------|
| Translate | ✅ | - | - | 5s | ✅ | message_content |
| TLDR | ✅ | - | - | 10s | ✅ | message_content |
| D&D | ✅* | ✅ | - | 3s | ✅ | members |
| Moderator | ✅* | ✅ | - | - | ✅ | - |
| Admin | - | - | ✅ | - | ✅ | - |
| Help | ✅ | ✅ | ✅ | - | - | members |

*D&D and Moderator commands have role-based access (custom in DB)

---

## 🔍 Verification Commands

**Check current intents:**
```python
# In main.py
print(f"Message Content: {intents.message_content}")
print(f"Members: {intents.members}")
```

**Test rate limiting:**
```
1. Run /subtitle "test" english Formal
2. Wait 0.5 seconds
3. Run /subtitle "test2" english Formal
   → Should get "⏳ Slow down!"
4. Wait 5 seconds
5. Run /subtitle "test3" english Formal
   → Should succeed
```

**Verify permissions:**
```
As non-admin:
/setup_mod → Should fail (ephemeral "denied")
/my_rep → Should succeed (show reputation)

As admin:
/setup_mod → Should succeed
/setmodel → Should fail (owner only)

As owner:
/setmodel → Should succeed
/status → Should show health metrics
```

---

## 📞 Questions?

**Q: Why does TLDR need message_content intent?**
A: Must read message text to summarize it. Without this intent, can't access message.content.

**Q: Why does D&D need members intent?**
A: Must check if user has D&D role assigned. Without this, can't validate access.

**Q: Can we remove either?**
A: No. Both are essential to feature function. Any removal breaks those systems.

**Q: Is this really "least privilege"?**
A: Yes. We use 2/19 intents (10.5%). We could use more but these 2 are the only truly necessary ones.

**Q: What if we add voice features later?**
A: Re-enable `voice_states` intent only then. Current setup is optimal for existing features.

**Q: Is the bot secure?**
A: Yes. Rate limiting, input validation, sanitization, and role-based access implemented throughout.

