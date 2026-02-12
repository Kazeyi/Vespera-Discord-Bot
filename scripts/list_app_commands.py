#!/usr/bin/env python3
"""List application commands (global + guild) and highlight duplicates by name.

Usage:
  DISCORD_TOKEN=your_bot_token python3 scripts/list_app_commands.py
"""
import os
import asyncio
import aiohttp
import discord
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("ERROR: set DISCORD_TOKEN environment variable")
    raise SystemExit(1)

API_BASE = "https://discord.com/api/v10"


async def fetch_json(session, url):
    async with session.get(url) as r:
        return await r.json()


async def main():
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        app_id = client.application_id
        guilds = list(client.guilds)
        print(f"Logged in. App ID: {app_id}. Guilds: {len(guilds)}")

        headers = {"Authorization": f"Bot {TOKEN}"}
        session = aiohttp.ClientSession(headers=headers)
        try:
            global_url = f"{API_BASE}/applications/{app_id}/commands"
            global_cmds = await fetch_json(session, global_url)

            print("\nGlobal commands:")
            for cmd in global_cmds:
                print(f" - {cmd.get('name')} (id={cmd.get('id')}) desc={cmd.get('description')}")

            print("\nGuild commands:")
            by_name = {}
            for g in guilds:
                url = f"{API_BASE}/applications/{app_id}/guilds/{g.id}/commands"
                cmds = await fetch_json(session, url)
                print(f"\n Guild {g.id} ({g.name}) - {len(cmds)} commands")
                for cmd in cmds:
                    print(f"  - {cmd.get('name')} (id={cmd.get('id')}) desc={cmd.get('description')}")
                    by_name.setdefault(cmd.get('name'), []).append(('guild', g.id, cmd.get('id')))

            # include globals in duplicate map
            for cmd in global_cmds:
                by_name.setdefault(cmd.get('name'), []).append(('global', None, cmd.get('id')))

            print('\nSummary: command name -> count')
            for name, items in sorted(by_name.items(), key=lambda x: (-len(x[1]), x[0])):
                if len(items) > 1:
                    print(f" * {name}: {len(items)} entries -> {items}")

        finally:
            await session.close()
            await client.close()

    await client.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
