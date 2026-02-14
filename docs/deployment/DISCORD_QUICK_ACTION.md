# Discord Dev Portal - Quick Action List

## 🎯 WHAT YOU NEED TO DO RIGHT NOW

### INTENTS (Gateway Intents)
Your current status + what to change:

| Intent | Your Status | Action | Why |
|--------|-------------|--------|-----|
| Message Content | ✅ ON | KEEP ✅ | Required for reading messages |
| Server Members | ✅ ON | KEEP ✅ | Required for D&D role checks |
| **Presence** | ✅ ON | **DISABLE ❌** | Privacy concern, not used |

**Action:** Go to Developer Portal → Bot → Gateway Intents → Turn OFF Presence Intent

---

### PERMISSIONS (OAuth2)
From your list - WHAT TO ENABLE and WHAT TO SKIP:

| Permission | Your Plan | Vespera Needs? | Action |
|-----------|-----------|----------------|--------|
| View Channel | - | ✅ YES | **ENABLE** |
| Send Messages | - | ✅ YES | **ENABLE** |
| Read Message History | - | ✅ YES | **ENABLE** |
| Embed Links | - | ✅ YES | **ENABLE** |
| Send Messages in Threads | - | ✅ YES | **ENABLE** |
| **Add Reactions** | Planned? | ✅ **YES** | **ENABLE** |
| **Connect** | Planned? | ✅ **YES** | **ENABLE** |
| **Speak** | Planned? | ✅ **YES** | **ENABLE** |
| **Attach Files** | Planned? | ❌ NO | **SKIP** |
| **Manage Messages** | Planned? | ❌ NO | **SKIP** |
| **Mention Everyone** | Planned? | ❌ NO | **SKIP** |
| **Use External Emoji** | Planned? | ❌ NO | **SKIP** |

---

## 🚀 Step-by-Step Instructions

### Step 1: Disable Presence Intent (2 minutes)
```
1. Go to Discord Developer Portal
2. Click on your Vespera app
3. Left sidebar → Bot
4. Scroll to "Gateway INTENTS"
5. Find "Presence Intent" → Click to DISABLE
6. Click "Save Changes"
```

### Step 2: Get Correct OAuth2 URL (5 minutes)
```
1. Go to Discord Developer Portal
2. Click on your Vespera app
3. Left sidebar → OAuth2 → URL Generator
4. Check ONLY: bot (Scope)
5. Check ONLY these (Permissions):
   ☑ View Channel
   ☑ Send Messages
   ☑ Read Message History
   ☑ Embed Links
   ☑ Send Messages in Threads
   ☑ Add Reactions
   ☑ Connect
   ☑ Speak
6. Leave all others UNCHECKED
7. Copy the generated URL
```

### Step 3: Re-invite Bot (3 minutes)
```
1. Go to your Discord server
2. Right-click Vespera bot → Kick
3. Visit the URL you copied in Step 2
4. Select your server
5. Click "Authorize"
6. Complete CAPTCHA if asked
```

### Step 4: Verify (1 minute)
```
1. Right-click Vespera in member list
2. Click "View Profile"
3. Scroll to "Roles and Permissions"
4. Verify you see exactly these 8 permissions:
   ✅ View Channel
   ✅ Send Messages
   ✅ Read Message History
   ✅ Embed Links
   ✅ Send Messages in Threads
   ✅ Add Reactions
   ✅ Connect
   ✅ Speak
```

**Total time:** ~10 minutes

---

## 📋 Summary

### INTENTS (What you're changing)
```
DISABLE:  Presence Intent
KEEP ON:  Message Content Intent
KEEP ON:  Server Members Intent
```

### PERMISSIONS (What to add to Discord)
```
ENABLE ONLY THESE 8:
✅ View Channel
✅ Send Messages
✅ Read Message History
✅ Embed Links
✅ Send Messages in Threads
✅ Add Reactions (flag reactions for translate/TLDR/D&D)
✅ Connect (D&D auto-joins voice channels for background music)
✅ Speak (D&D plays 11 location theme songs during gameplay)

DISABLE EVERYTHING ELSE:
❌ Attach Files
❌ Manage Messages
❌ Mention Everyone
❌ Use External Emoji
```

---

## ❓ Why These Specific Permissions?

### THE 5 REQUIRED

**View Channel** - Bot must see channels to know they exist and work in them
- Without this: Bot can't see where to send responses

**Send Messages** - Bot sends command responses and information
- Without this: Users can't see bot responses

**Read Message History** - `/tldr` needs to read previous messages
- Without this: Can't access message history for summarization

**Embed Links** - All bot responses use embedded messages (fancy formatted boxes)
- Without this: Embeds won't display properly

**Send Messages in Threads** - D&D games run in threads, bot needs to respond there
- Without this: Bot can't respond to commands in thread channels

### WHY NOT THE OTHERS?

| Permission | What it's for | Does Vespera need it? |
|-----------|---------------|----------------------|
| Add Reactions | Bot adds emoji reactions | NO - Users add reactions, bot just listens |
| Attach Files | Bot uploads files/images | NO - Bot only sends text and embeds |
| Connect | Bot joins voice channels | NO - Voice is optional, manual |
| Manage Messages | Bot deletes/edits other messages | NO - Bot never modifies messages |
| Mention Everyone | Bot uses @everyone/@here | NO - Bot never mass mentions |
| Speak | Bot plays audio in voice | NO - Voice is optional, manual |
| Use External Emoji | Bot uses emoji from other servers | NO - Uses Discord's built-in emojis only |

---

## ✅ Verification Checklist

After re-inviting with new permissions:

- [ ] Presence Intent is DISABLED in Developer Portal
- [ ] Message Content Intent is ENABLED in Developer Portal
- [ ] Server Members Intent is ENABLED in Developer Portal
- [ ] Bot has exactly 5 permissions listed in "View Profile"
- [ ] `/subtitle` command works
- [ ] `/tldr` command works
- [ ] `/do` command works (D&D)
- [ ] `/help` command works
- [ ] Bot shows correct permissions when you right-click it

---

## 🆘 Troubleshooting

**Bot says "missing permissions"?**
→ Re-invite using the OAuth2 URL from Step 2 above

**Can't see bot in member list?**
→ Go to Server Settings → Roles → Check if Vespera role is enabled

**Permissions won't update?**
→ Remove bot, wait 30 seconds, re-invite with new URL

**Need the permission code?**
→ Use: `8494592`

---

**That's it!** Your bot will now have exactly what it needs - no more, no less. Maximum security with full functionality.
