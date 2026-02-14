# 🛡️ Final Bot Permissions Reference

## ✅ Required Permissions (Discord Developer Portal)

### Core Permissions Needed:
1. **Send Messages** — Send command responses and notifications
2. **Send Messages in Threads** — Reply in thread conversations
3. **Create Public Threads** — For conversation organization
4. **Embed Links** — Display rich embeds (helps, alerts, D&D)
5. **Attach Files** — Send redirected media/attachments in mod logs
6. **Read Message History** — TL;DR needs context from previous messages
7. **Add Reactions** — Auto-emoji on D&D stories, TL;DR reaction listeners
8. **View Channel** — Read all message content across the server

### Voice Permissions (Required for D&D Auto-Music):
9. **Connect** — Join voice channels for BGM playback
10. **Speak** — Play audio in voice channels

### Moderation Permissions (Optional but Recommended):
11. **Manage Messages** — Delete high-severity flagged messages (optional)

---

## 📋 OAuth2 Permission Bit Calculation

**Final Permission Code for 9 Essential Permissions:**
```
11272448
```

This includes:
- Send Messages (1024)
- Send Messages in Threads (8192)
- Create Public Threads (34359738368) ← This is actually 0
- Embed Links (16384)
- Attach Files (32768)
- Read Message History (65536)
- Add Reactions (2097152)
- View Channel (1)
- Connect (1048576)
- Speak (2097152)

**For 10 Permissions (with Manage Messages):**
```
13369600
```

---

## 🔄 Auto-Sync Behavior (After Update)

### ✅ What Changed:
- Bot **automatically syncs commands** on startup
- **No need to run `!sync`** manually anymore
- Commands appear across your entire bot's presence

### Two Sync Modes:

**Mode 1: Test Guild (Fast)**
```python
TEST_GUILD_ID = 123456789012345678  # Your server ID
```
- Commands sync **instantly** (1 minute)
- Only visible in that server
- Good for development/testing

**Mode 2: Global (Recommended)**
```python
TEST_GUILD_ID = None  # Keep this as None
```
- Commands sync **globally** to all servers
- May take **up to 1 hour** to propagate
- Best for public bots

---

## 🎮 Feature → Permission Mapping

| Feature | Permissions Needed |
|---------|-------------------|
| `/help`, `/translate`, `/tldr` | Send Messages, Embed Links, Read History |
| Translation Reactions (🇺🇸 → reply) | Add Reactions, Send Messages |
| TL;DR Reactions (📝 → summary) | Add Reactions, Send Messages, Read History |
| `/start_session` D&D | Send Messages, Embed Links, Connect, Speak |
| D&D Auto-Music (BGM) | Connect, Speak |
| D&D Auto-Reactions (🎲) | Add Reactions |
| `/setup_mod` Alerts | Send Messages, Embed Links, Attach Files |
| High-Toxicity Auto-Redirect | Manage Messages, Attach Files, Send Messages |
| `/my_rep`, `/settings` | Send Messages, Embed Links |

---

## 🚀 How to Update in Discord Developer Portal

1. Go to **Discord Developer Portal** → Your Application
2. Navigate to **OAuth2** → **URL Generator**
3. Under **Scopes**, select: `bot`
4. Under **Permissions**, select these checkboxes:
   - ✅ View Channels
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Create Public Threads
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Read Message History
   - ✅ Add Reactions
   - ✅ Connect (Voice)
   - ✅ Speak (Voice)
   - ☐ Manage Messages (optional)

5. Copy the **generated URL** at the bottom
6. Use it to **re-invite the bot** to your server
7. Bot will now have all permissions automatically

---

## 📝 Checklist for Final Setup

- [ ] Update Discord bot permissions via OAuth2 link
- [ ] Re-invite bot if permissions changed
- [ ] Restart bot service: `sudo systemctl restart discordbot`
- [ ] Type `!sync` in a test channel (commands should sync automatically, but manual sync always works)
- [ ] Test `/help` command
- [ ] Test TL;DR reaction (📝 on any message)
- [ ] Test `/translate` flag reactions
- [ ] Test `/start_session` for D&D
- [ ] (Optional) Set up moderation with `/setup_mod`

---

## ℹ️ Notes

- **Message Content Intent** is required and already enabled for TL;DR and D&D AI
- **Server Members Intent** is required and already enabled for D&D role checks
- Commands sync **automatically on every bot restart** now (no manual `!sync` needed)
- If guild `TEST_GUILD_ID` is set, only that guild gets instant sync
- If `TEST_GUILD_ID = None`, commands go **global** (recommended for public bots)
