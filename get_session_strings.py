"""
Session String Generator for Render.com Deployment
====================================================
Run this script ONCE on your PC to convert your .session files
into session strings that can be used as environment variables on Render.

Usage:
    python get_session_strings.py

Requirements:
    pip install pyrogram tgcrypto
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import os
import sys

try:
    from pyrogram import Client
except ImportError:
    print("❌ Pyrogram not installed! Run: pip install pyrogram tgcrypto")
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# YOUR CREDENTIALS (already from your .env files)
# ─────────────────────────────────────────────────────────
API_ID   = 28675574
API_HASH = "b4086c0ad6e85161beef7a23df4ef3b5"

# ─────────────────────────────────────────────────────────
# SESSION FILES (relative paths from demo/ folder)
# ─────────────────────────────────────────────────────────
SESSIONS = [
    {
        "name": "Scraper Bot (forwarder)",
        "session_file": os.path.join("scraper", "forwarder_session"),
        "env_var": "SESSION_STRING  (for demo-scraper on Render)"
    },
    {
        "name": "Pipeline Bot",
        "session_file": os.path.join("pipeline", "pipeline_session"),
        "env_var": "SESSION_STRING  (for demo-pipeline on Render)"
    },
    {
        "name": "Organiser Bot",
        "session_file": os.path.join("organisepost", "organizer_session"),
        "env_var": "SESSION_STRING  (for demo-organiser on Render)"
    },
    {
        "name": "All DiskWala Post Bot",
        "session_file": os.path.join("alldiskwalapost", "alldiskwalapost_session"),
        "env_var": "SESSION_STRING  (for demo-alldiskwalapost on Render)"
    },
]


# ─────────────────────────────────────────────────────────
async def export_session(name: str, session_file: str, env_var: str):
    print(f"\n{'='*60}")
    print(f"[BOT] Processing: {name}")
    print(f"{'='*60}")

    session_path = session_file + ".session"

    if not os.path.exists(session_path):
        print(f"[WARNING] Session file not found: {session_path}")
        print(f"   Skipping...")
        return None

    try:
        async with Client(
            session_file,
            api_id=API_ID,
            api_hash=API_HASH,
        ) as app:
            me = await app.get_me()
            session_string = await app.export_session_string()

            print(f"\n[OK] Logged in as: {me.first_name} (@{me.username})")
            print(f"\n[KEY] Copy this SESSION_STRING for -> {env_var}")
            print(f"\n{'─'*60}")
            print(session_string)
            print(f"{'─'*60}")
            print(f"\n[Render] Add this as environment variable:")
            print(f"   Key:   SESSION_STRING")
            print(f"   Value: (the long string above)")

            return session_string

    except Exception as e:
        print(f"[ERROR] {e}")
        print(f"   Make sure you ran this from the demo/ folder")
        return None


async def main():
    print("\n" + "=" * 60)
    print("   SESSION STRING GENERATOR FOR RENDER.COM")
    print("=" * 60)
    print("\nThis will read your existing .session files and export")
    print("session strings you can paste into Render.com as env vars.\n")

    results = {}

    for session_info in SESSIONS:
        result = await export_session(
            session_info["name"],
            session_info["session_file"],
            session_info["env_var"]
        )
        if result:
            results[session_info["name"]] = result

    # ── Summary ──────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("SUMMARY -- Copy these to Render.com")
    print(f"{'='*60}\n")

    if not results:
        print("[WARNING] No sessions exported. Check that you ran this script")
        print("   from inside the demo/ folder:\n")
        print("   cd C:\\Users\\ashwani\\Desktop\\demo")
        print("   python get_session_strings.py\n")
    else:
        for name, string in results.items():
            print(f"[OK] {name}:")
            print(f"   SESSION_STRING = {string[:40]}...{string[-10:]}")
            print()

    print("\nNext Steps:")
    print("  1. Copy each session string above")
    print("  2. Go to Render.com dashboard")
    print("  3. Open your service -> Environment -> Add variable")
    print("     Key: SESSION_STRING")
    print("     Value: (paste the full string)")
    print("  4. Save -> service will redeploy automatically")
    print("\n[DONE] Your bots will authenticate on Render without .session files\n")


if __name__ == "__main__":
    # Run from demo/ folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"[DIR] Working directory: {script_dir}")

    asyncio.run(main())
