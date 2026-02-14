# Discord Developer Portal - Permission Configuration

**Bot Name:** Vespera  
**Date:** January 15, 2026  
**Principle:** Least Privilege Access

---

## 🎯 INTENTS Configuration

### Current Settings (CORRECT)
```
✅ ENABLED:
   └─ Message Content Intent
   └─ Server Members Intent

❌ DISABLED (Remove if enabled):
   └─ Presence Intent ........... REMOVE (privacy concern)
   └─ All others ................ Leave disabled
```

### Why Each Intent

| Intent | Status | Reason |
|--------|--------|--------|
| Message Content | ✅ ENABLE | Need to read message text for /tldr, /subtitle, D&D analysis |
| Server Members | ✅ ENABLE | Need to check user roles for D&D access control |
| Presence | ❌ DISABLE | Not used - remove this |
| Guild Messages | ✅ Implicit | Already enabled via default intents |
| All others | ❌ DISABLE | Not needed |

**INTENTS SUMMARY:** Enable only 2/19 intents (Message Content, Server Members)

---

## 🔐 TEXT CHANNEL PERMISSIONS

### REQUIRED Permissions (Enable These)

```
✅ REQUIRED (Enable all of these):

1. View Channel
   └─ Why: Must see channels to read/send messages

2. Send Messages
   └─ Why: Send command responses and embeds

3. Read Message History
   └─ Why: /tldr needs to read past messages
           D&D /do needs context from earlier turns
           Context menu commands need message access

4. Embed Links
   └─ Why: All bot responses use Discord embeds
           /help, /tldr, /subtitle, /status all embed-based

5. Send Messages in Threads
   └─ Why: D&D games run in threads
           Must respond to commands in threads
           Critical for /do, /init, /long_rest in thread channels
```

### NOT NEEDED Permissions (Disable These)

```
❌ NOT NEEDED (Disable or leave disabled):

1. Attach Files
   └─ Why: Bot doesn't upload files
   └─ Note: Audio is played via voice, not file upload

2. Manage Messages
   └─ Why: Bot doesn't delete/edit other messages
   └─ Note: Not needed for functionality

3. Mention Everyone
   └─ Why: Bot never uses @everyone/@here
   └─ Note: Role pings work without this permission

4. Use External Emoji
   └─ Why: Bot uses Discord's built-in emojis only
   └─ Examples: 🎲, ✅, ❌, 📝, 🔮, etc.
   └─ No custom emoji dependencies
```

### REACTION PERMISSIONS (REQUIRED for Flag Translation & TLDR)

```
✅ REQUIRED (Enable these):

1. Add Reactions
   └─ Why: /translate uses flag emoji reactions (🇺🇸, 🇮🇩, 🇯🇵)
   └─ Feature: React with flag to auto-translate message
   └─ Why 2: /tldr uses 📝 emoji to trigger summary
   └─ Why 3: D&D adds emoji to story messages
   └─ Status: CORE FEATURE - essential for workflow
```

2. Speak
   └─ Why: Plays location-based background music
   └─ Features: 11 theme songs (combat.ogg, forest_day.ogg, tavern.ogg, etc.)
   └─ Behavior: Auto-loops when connected to voice
```

---

## ✅ DISCORD DEV PORTAL CHECKLIST

### INTENTS Section
```
TURN ON:
☑ Message Content Intent ................... REQUIRED
☑ Server Members Intent ................... REQUIRED

TURN OFF (if currently on):
☐ Presence Intent ......................... REMOVE
☐ All others ............................ Leave OFF
```

### OAUTH2 → BOT PERMISSIONS Section

**Numerical Permission Code Needed:**
- View Channel (1024)
- Send Messages (2048)
- Read Message History (65536)
- Embed Links (16384)
- Send Messages in Threads (8388608)
- Add Reactions (64)
- Connect (1048576)
- Speak (2097152)

**Total:** 11272448

**To Get This Code:**
1. Go to Discord Developer Portal
2. Your App → OAuth2 → URL Generator
3. Check ONLY these permissions:
   - View Channel
   - Send Messages
   - Read Message History
   - Embed Links
   - Send Messages in Threads
   - Add Reactions
   - Connect
   - Speak
4. Copy the generated URL
5. Invite bot with that URL

---

## 📋 Step-by-Step Setup

### Step 1: Configure Intents
```
Go to: Discord Developer Portal
       → Your App
       → Bot (left sidebar)

GATEWAY INTENTS section:
✅ Message Content Intent ........... CLICK TO ENABLE
✅ Server Members Intent ............ CLICK TO ENABLE
❌ Presence Intent .................. CLICK TO DISABLE (if on)

Save changes
```

### Step 2: Configure Permissions
```
Go to: Discord Developer Portal
       → Your App
       → OAuth2 → URL Generator (left sidebar)

SCOPES:
☑ bot (just this one)

BOT PERMISSIONS:
☑ View Channel
☑ Send Messages
☑ Read Message History
☑ Embed Links
☑ Send Messages in Threads

Copy the generated URL below
Use that URL to re-invite your bot
```

### Step 3: Verify
```
In Discord:
1. Right-click bot in member list
2. Click "View Profile"
3. Check "Roles" section
4. Verify bot has correct permissions in each channel
```

---

## 📊 Permission vs Feature Mapping

### Translation Features
```
/subtitle "text" english Formal
/Translate (context menu)
├─ Needs: Message Content Intent ✅
├─ Needs: Send Messages ✅
├─ Needs: Embed Links ✅
└─ Needs: Read Message History ✅ (for context menu)
```

### TL;DR Features
```
/tldr 50
/TL;DR (context menu)
├─ Needs: Message Content Intent ✅
├─ Needs: Read Message History ✅ (must read past messages)
├─ Needs: Send Messages ✅
└─ Needs: Embed Links ✅
```

### D&D Features
```
/do "I cast fireball"
/init, /roll_npc, etc.
├─ Needs: Server Members Intent ✅ (role checking)
├─ Needs: View Channel ✅
├─ Needs: Send Messages ✅
├─ Needs: Send Messages in Threads ✅ (games in threads)
├─ Needs: Read Message History ✅ (context reading)
└─ Needs: Embed Links ✅
```

### Admin Features
```
/status (owner only)
├─ Needs: Send Messages ✅
└─ Needs: Embed Links ✅
```

### Moderation Features
```
/setup_mod, /settings, /my_rep
├─ Needs: Send Messages ✅
└─ Needs: Embed Links ✅
```

---

## 🚫 NOT NEEDED - Why Some Are Off

### Add Reactions
- **What it does:** Bot can add emoji reactions to messages
- **Does Vespera need it?** NO
- **Why?** Bot doesn't add reactions; users add reactions that bot listens to
- **User reactions are different:** They work without this permission
- **Keep it:** DISABLED ❌

### Attach Files
- **What it does:** Bot can upload files/images
- **Does Vespera need it?** NO
- **Why?** Bot sends text and embeds only, no file uploads
- **Keep it:** DISABLED ❌

### Connect / Speak
- **What it does:** Bot can join voice channels and play audio
- **Does Vespera need it?** OPTIONAL
- **Why?** D&D background music is optional feature
- **Current setup:** Manual voice connect (user invokes)
- **Recommendation:** Leave DISABLED unless you enable auto-voice
- **Keep it:** DISABLED ❌

### Manage Messages
- **What it does:** Bot can delete/edit other users' messages
- **Does Vespera need it?** NO
- **Why?** Bot only sends its own messages, doesn't moderate
- **Keep it:** DISABLED ❌

### Mention Everyone
- **What it does:** Bot can use @everyone/@here/@role mentions
- **Does Vespera need it?** NO
- **Why?** Bot never mass-mentions, works with individuals
- **Keep it:** DISABLED ❌

### Use External Emoji
- **What it does:** Bot can use emoji from other servers
- **Does Vespera need it?** NO
- **Why?** Bot uses Discord's built-in emoji (no external needed)
- **Examples:** ✅ ❌ 🎲 🔮 📝 all built-in
- **Keep it:** DISABLED ❌

---

## ✅ FINAL CHECKLIST

### Discord Developer Portal - Intents Tab
```
Gateway Intents:
☑ Message Content Intent (ON) ...................... ✅ REQUIRED
☑ Server Members Intent (ON) ....................... ✅ REQUIRED
☐ Presence Intent (OFF) ............................ ✅ DISABLED
☐ Guild Members (implicit) ......................... ✅ OK
☐ All others (OFF) ................................ ✅ OK
```

### Discord Developer Portal - OAuth2 URL Generator
```
Scopes:
☑ bot

Permissions:
☑ View Channel ..................................... ✅ REQUIRED
☑ Send Messages .................................... ✅ REQUIRED
☑ Read Message History ............................. ✅ REQUIRED
☑ Embed Links ...................................... ✅ REQUIRED
☑ Send Messages in Threads ......................... ✅ REQUIRED
☐ Add Reactions .................................... ✅ DISABLED
☐ Attach Files ..................................... ✅ DISABLED
☐ Connect .......................................... ✅ DISABLED
☐ Speak ............................................ ✅ DISABLED
☐ Manage Messages .................................. ✅ DISABLED
☐ Mention Everyone ................................. ✅ DISABLED
☐ Use External Emoji ............................... ✅ DISABLED
```

### Summary
- **Total Intents Enabled:** 2/19 (10.5%)
- **Total Permissions Enabled:** 5 (View Channel, Send Messages, Read History, Embed Links, Send in Threads)
- **All others:** DISABLED (not needed)

---

## 🔐 Why This Is Secure

### Minimal Attack Surface
- Only 2 intents = fewer event handlers = less processing
- Only 5 permissions = bot can't delete messages, edit messages, or spam mentions
- No unnecessary external dependencies

### No Over-Privilege
- ❌ Can't manage other messages (no moderation overreach)
- ❌ Can't mention everyone (no spam capability)
- ❌ Can't upload files (no malware vector)
- ❌ Can't use external emoji (no external dependencies)
- ✅ Can only read and respond

### Clear Permission Scope
- Message Content: Only for analysis, not storage
- Members: Only for role validation
- Read History: Only for context (not logging)
- Send Messages: Only for responses (not automation)

---

## 📞 If Your Bot Gets Denied

**Error:** "Bot lacks permissions"

**Solution:**
1. Check Discord Developer Portal settings match this guide
2. Check channel permissions override (per-channel overrides guild perms)
3. Verify bot role position (must be above any restricted roles)
4. Re-invite bot using correct OAuth2 URL from URL Generator

**To re-invite:**
```
1. Remove bot from server
2. Go to Discord Developer Portal → OAuth2 → URL Generator
3. Select ONLY: bot (scope)
4. Select ONLY these permissions:
   - View Channel
   - Send Messages
   - Read Message History
   - Embed Links
   - Send Messages in Threads
5. Copy and visit the generated URL
6. Select server and authorize
```

---

## 🎯 Your Current vs. Recommended

### INTENTS

**Your Current:**
- ✅ Presence Intent (you have this)
- ✅ Server Members Intent (you have this)
- ✅ Message Content Intent (you have this)

**Recommended:**
- ❌ **DISABLE Presence Intent** (privacy, unused)
- ✅ **KEEP Server Members Intent** (needed for D&D roles)
- ✅ **KEEP Message Content Intent** (needed for TLDR/Translate)

**Action:** Turn OFF Presence Intent

### PERMISSIONS

**You mentioned planning to add:**
- Add Reactions ........................ ❌ NOT NEEDED
- Attach Files ........................ ❌ NOT NEEDED
- Connect ............................ ❌ NOT NEEDED (optional voice)
- Embed Links ........................ ✅ REQUIRED
- Manage Messages .................... ❌ NOT NEEDED
- Mention Everyone ................... ❌ NOT NEEDED
- Read Message History .............. ✅ REQUIRED
- Send Messages ..................... ✅ REQUIRED
- Send Messages in Threads ......... ✅ REQUIRED
- Speak ............................. ❌ NOT NEEDED (optional voice)
- Use External Emoji ............... ❌ NOT NEEDED
- View Channel ..................... ✅ REQUIRED

**Summary:**
- Add: Embed Links, Read Message History (if not already), Send Messages in Threads
- Keep: Send Messages, View Channel
- Remove: All others (especially Connect, Speak, Manage Messages, Mention Everyone)

---

## 📋 Quick Reference Card

Print this and keep it handy:

```
VESPERA BOT - DISCORD DEV PORTAL SETTINGS

INTENTS (Gateway):
  ✅ Message Content Intent
  ✅ Server Members Intent
  ❌ Presence Intent (DISABLE THIS)

PERMISSIONS (OAuth2 URL Generator):
  ✅ View Channel
  ✅ Send Messages
  ✅ Read Message History
  ✅ Embed Links
  ✅ Send Messages in Threads

ALL OTHERS: ❌ DISABLED

Permission Code: 8494592
```

---

**Setup Complete!** Your Discord Developer Portal is now configured with least privilege access. The bot has exactly what it needs - no more, no less.
