#!/usr/bin/env python3
"""One-shot admin script to list and remove duplicate App (context/menu) commands.

Usage:
  DISCORD_TOKEN=your_bot_token python3 scripts/clean_app_commands.py

Behavior:
  - Logs in the bot (read-only) to discover application id and guilds.
  - Lists global and guild-scoped application commands.
  - For duplicate command names, deletes global commands when a guild-scoped one exists.
  - If multiple global commands with same name exist, keeps the first and deletes the rest.

Run this only once; inspect printed output before and after.
"""
import os
import asyncio
import argparse
import aiohttp
import discord
import json
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("ERROR: Set DISCORD_TOKEN environment variable and rerun.")
    raise SystemExit(1)

# Normalize token name used below
TOKEN = DISCORD_TOKEN

API_BASE = "https://discord.com/api/v10"


async def fetch_json(session, url):
    async with session.get(url) as r:
        return await r.json()


async def delete(session, url):
    async with session.delete(url) as r:
        return r.status, await r.text(), r


async def delete_with_retries(session, url, max_attempts=6):
    backoff = 1.0
    last_status = None
    last_text = None
    for attempt in range(1, max_attempts + 1):
        try:
            status, text, resp = await delete(session, url)
            last_status, last_text = status, text
            if status == 204:
                return status, text
            if status == 429:
                # Try to read retry_after from body or header
                retry_after = None
                try:
                    j = json.loads(text)
                    retry_after = float(j.get('retry_after', 0))
                except Exception:
                    pass
                if not retry_after:
                    try:
                        retry_after = float(resp.headers.get('Retry-After', 1.0))
                    except Exception:
                        retry_after = 1.0
                await asyncio.sleep(retry_after + 0.5)
                continue
            if status >= 500:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            # other non-success statuses, return as-is
            return status, text
        except Exception as e:
            last_text = str(e)
            await asyncio.sleep(backoff)
            backoff *= 2
    return last_status, last_text


async def main():
    parser = argparse.ArgumentParser(description='Clean duplicate app commands')
    parser.add_argument('-y', '--yes', action='store_true', help='Auto-confirm deletions')
    parser.add_argument('--purge-name', '-p', action='append', help='Purge all commands with this name (global+guild). Can be given multiple times.')
    parser.add_argument('--delete-guild', action='store_true', help='Allow deleting guild-scoped commands as well (use with care).')
    args, _ = parser.parse_known_args()
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        app_id = client.application_id
        guilds = list(client.guilds)
        print(f"Logged in. App ID: {app_id}. Guilds: {len(guilds)}")

        headers = {"Authorization": f"Bot {TOKEN}"}

        # Create session here and ensure we close it in a finally block
        session = aiohttp.ClientSession(headers=headers)
        try:
            # Fetch global commands
            global_url = f"{API_BASE}/applications/{app_id}/commands"
            global_cmds = await fetch_json(session, global_url)

            # Fetch guild commands for each guild
            guild_cmds_map = {}
            for g in guilds:
                url = f"{API_BASE}/applications/{app_id}/guilds/{g.id}/commands"
                guild_cmds_map[g.id] = await fetch_json(session, url)

            # Build name -> list mapping
            by_name = {}
            for cmd in global_cmds:
                name = cmd.get('name')
                by_name.setdefault(name, []).append(('global', None, cmd))
            for gid, cmds in guild_cmds_map.items():
                for cmd in cmds:
                    name = cmd.get('name')
                    by_name.setdefault(name, []).append(('guild', gid, cmd))

            # Determine duplicates
            actions = []

            # If user requested purge by name, schedule deletions for all matching commands
            purge_names = set(args.purge_name or [])
            if purge_names:
                for pname in purge_names:
                    items = by_name.get(pname, [])
                    if not items:
                        print(f"No commands found with name '{pname}'")
                        continue
                    print(f"Purge requested for '{pname}' -> {len(items)} entries")
                    for scope, gid, cmd in items:
                        if scope == 'global':
                            actions.append(('delete_global', cmd['id'], pname))
                        else:
                            actions.append(('delete_guild', gid, cmd['id'], pname))

            # Regular duplicate detection: prefer keeping guild-scoped commands and delete globals
            for name, items in by_name.items():
                if len(items) < 2:
                    continue
                print(f"Duplicate command name found: '{name}' -> {len(items)} entries")
                # If there's at least one guild-scoped, delete global ones
                has_guild = any(scope == 'guild' for scope, _, _ in items)
                if has_guild:
                    for scope, gid, cmd in items:
                        if scope == 'global':
                            actions.append(('delete_global', cmd['id'], name))
                else:
                    # multiple global commands: keep the first, delete rest
                    for scope, gid, cmd in items[1:]:
                        actions.append(('delete_global', cmd['id'], name))

            # If the caller allowed guild deletions, detect duplicate guild commands with same name across guilds
            if args.delete_guild:
                # Find names that appear multiple times with guild scope and delete duplicates (keep first per guild)
                for name, items in by_name.items():
                    guild_items = [it for it in items if it[0] == 'guild']
                    if len(guild_items) > 1:
                        print(f"Multiple guild-scoped commands found for '{name}' -> {len(guild_items)} entries; scheduling deletions (keep first)")
                        for scope, gid, cmd in guild_items[1:]:
                            actions.append(('delete_guild', gid, cmd['id'], name))

            if not actions:
                print("No duplicates found.")
            else:
                print("Planned actions:")
                for a in actions:
                    print(" ", a)
                if not args.yes:
                    confirm = input("Proceed to delete the above commands? (y/N): ")
                    if confirm.lower() != 'y':
                        print("Aborted by user.")
                        await client.close()
                        return
                else:
                    print("Auto-confirm enabled: proceeding to delete listed commands.")

                # Execute deletions (with rate-limit handling)
                for a in actions:
                    if a[0] == 'delete_global':
                        _, cmd_id, name = a
                        url = f"{API_BASE}/applications/{app_id}/commands/{cmd_id}"
                        status, text = await delete_with_retries(session, url, max_attempts=8)
                        print(f"Delete global '{name}' ({cmd_id}) -> {status}: {text}")
                    elif a[0] == 'delete_guild':
                        _, gid, cmd_id, name = a
                        url = f"{API_BASE}/applications/{app_id}/guilds/{gid}/commands/{cmd_id}"
                        status, text = await delete_with_retries(session, url, max_attempts=8)
                        print(f"Delete guild '{name}' (guild={gid} id={cmd_id}) -> {status}: {text}")
        finally:
            # Ensure the aiohttp session is properly closed
            try:
                await session.close()
            except Exception:
                pass
        # After work is done, close the Discord client to exit program
        try:
            await client.close()
        except Exception:
            pass

    try:
        await client.start(TOKEN)
    finally:
        try:
            await client.close()
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(main())
