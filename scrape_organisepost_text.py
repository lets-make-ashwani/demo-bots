"""
Scrape All Posts Text from Telegram Channel (@organisepost)
============================================================
Extracts the text/caption of every post from https://t.me/organisepost
and saves the output to:
  1. An Excel Sheet (.xlsx) / CSV (.csv)
  2. A Clean Formatted Text File (.txt)

Uses existing Telegram session files / strings from the workspace.
"""

import os
import sys
import io
import csv
import asyncio
from datetime import datetime

# Configure UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True)

# Monkeypatch Pyrogram's internal ID limits for 64-bit Telegram IDs
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000
pyrogram.utils.MIN_CHAT_ID = -99999999999999
pyrogram.utils.MAX_USER_ID = 99999999999999

from pyrogram import Client
from pyrogram.errors import FloodWait

# Optional openpyxl / pandas for Excel export
HAS_PANDAS = False
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pass

# ================= CONFIGURATION =================
API_ID = 28675574
API_HASH = "b4086c0ad6e85161beef7a23df4ef3b5"

# Target Channel
TARGET_CHANNEL = "organisepost"  # https://t.me/organisepost

# Output File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_TXT = os.path.join(BASE_DIR, "organisepost_all_texts.txt")
OUTPUT_EXCEL = os.path.join(BASE_DIR, "organisepost_all_texts.xlsx")
OUTPUT_CSV = os.path.join(BASE_DIR, "organisepost_all_texts.csv")


def get_client() -> Client:
    """
    Finds the first available valid session string or local .session file.
    """
    # 1. Check if SESSION_STRING is in environment
    session_string = os.getenv("SESSION_STRING_ORGANIZER") or os.getenv("SESSION_STRING")
    
    # 2. Check SESSION_STRINGS_SAVE_THIS.txt
    if not session_string:
        txt_path = os.path.join(BASE_DIR, "SESSION_STRINGS_SAVE_THIS.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Try finding ORGANISER BOT session string
                import re
                match = re.search(r"--- ORGANISER BOT.*?Value:\s*([A-Za-z0-9_-]+)", content, re.DOTALL)
                if not match:
                    match = re.search(r"--- PIPELINE BOT.*?Value:\s*([A-Za-z0-9_-]+)", content, re.DOTALL)
                if not match:
                    match = re.search(r"--- SCRAPER BOT.*?Value:\s*([A-Za-z0-9_-]+)", content, re.DOTALL)
                if match:
                    session_string = match.group(1).strip()

    if session_string:
        print("[*] Connecting with Pyrogram using SESSION_STRING...")
        return Client("scrape_session", session_string=session_string, api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)

    # 3. Check for local .session files in subfolders
    session_candidates = [
        os.path.join(BASE_DIR, "organisepost", "organizer_session"),
        os.path.join(BASE_DIR, "pipeline", "pipeline_session"),
        os.path.join(BASE_DIR, "scraper", "forwarder_session"),
        os.path.join(BASE_DIR, "alldiskwalapost", "alldiskwalapost_session")
    ]

    for candidate in session_candidates:
        if os.path.exists(f"{candidate}.session"):
            print(f"[*] Found local session: {os.path.basename(candidate)}.session")
            return Client(candidate, api_id=API_ID, api_hash=API_HASH, no_updates=True)

    raise RuntimeError("No active Telegram session string or .session file found!")


async def main():
    print("=" * 65)
    print(" 📥 SCRAPING ALL POST TEXTS FROM @organisepost")
    print("=" * 65)

    app = get_client()

    messages_data = []

    async with app:
        print("[+] Logged into Telegram successfully!")
        
        # Resolve target channel
        print(f"[*] Resolving channel @{TARGET_CHANNEL}...")
        try:
            chat = await app.get_chat(TARGET_CHANNEL)
            print(f"[OK] Found Channel: '{chat.title}' (ID: {chat.id})")
        except Exception as e:
            print(f"[!] Could not resolve @{TARGET_CHANNEL}: {e}")
            return

        print(f"[*] Fetching messages history from '{chat.title}'...")
        count = 0
        text_count = 0

        try:
            async for msg in app.get_chat_history(chat.id):
                count += 1

                # Extract text or caption
                raw_text = (msg.text or msg.caption or "").strip()

                if raw_text:
                    text_count += 1
                    post_date = msg.date.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.date else "Unknown"
                    post_link = f"https://t.me/{chat.username}/{msg.id}" if chat.username else f"https://t.me/c/{str(chat.id)[4:]}/{msg.id}"

                    messages_data.append({
                        "message_id": msg.id,
                        "date": post_date,
                        "link": post_link,
                        "text": raw_text,
                        "char_count": len(raw_text)
                    })

                if count % 100 == 0:
                    print(f"  [-] Scanned {count} messages (found {text_count} posts with text)...")

        except FloodWait as fw:
            print(f"[!] Hit Telegram FloodWait. Waiting {fw.value}s...")
            await asyncio.sleep(fw.value)
        except Exception as err:
            print(f"[!] Exception during chat history fetch: {err}")

    # Process and sort chronologically (oldest to newest)
    messages_data.reverse()
    total_found = len(messages_data)
    print(f"\n[+] Total channel messages scanned: {count}")
    print(f"[+] Total posts with text/captions extracted: {total_found}")

    if total_found == 0:
        print("[!] No text content found to export.")
        return

    # ─────────────────────────────────────────────────────────
    # 1. SAVE TO TEXT FILE (.txt)
    # ─────────────────────────────────────────────────────────
    print(f"[*] Writing to TXT file: {OUTPUT_TXT}...")
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"TELEGRAM CHANNEL ARCHIVE: @{TARGET_CHANNEL}\n")
        f.write(f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"Total Posts: {total_found}\n")
        f.write("=" * 80 + "\n\n")

        for idx, item in enumerate(messages_data, 1):
            f.write(f"--- [POST #{idx} | ID: {item['message_id']} | Date: {item['date']}] ---\n")
            f.write(f"Link: {item['link']}\n")
            f.write("-" * 40 + "\n")
            f.write(item["text"] + "\n")
            f.write("\n" + "=" * 80 + "\n\n")

    print(f"[OK] Successfully saved text file: {OUTPUT_TXT}")

    # ─────────────────────────────────────────────────────────
    # 2. SAVE TO CSV (.csv) - Universal Spreadsheet
    # ─────────────────────────────────────────────────────────
    print(f"[*] Writing to CSV file: {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Message ID", "Date (UTC)", "Post Link", "Character Count", "Post Text"])
        for idx, item in enumerate(messages_data, 1):
            writer.writerow([idx, item["message_id"], item["date"], item["link"], item["char_count"], item["text"]])

    print(f"[OK] Successfully saved CSV file: {OUTPUT_CSV}")

    # ─────────────────────────────────────────────────────────
    # 3. SAVE TO EXCEL (.xlsx)
    # ─────────────────────────────────────────────────────────
    if HAS_PANDAS:
        try:
            print(f"[*] Writing to Excel file (.xlsx): {OUTPUT_EXCEL}...")
            df = pd.DataFrame([
                {
                    "#": idx,
                    "Message ID": item["message_id"],
                    "Date (UTC)": item["date"],
                    "Post Link": item["link"],
                    "Length": item["char_count"],
                    "Post Text": item["text"]
                }
                for idx, item in enumerate(messages_data, 1)
            ])
            df.to_excel(OUTPUT_EXCEL, index=False, engine="openpyxl")
            print(f"[OK] Successfully saved Excel file: {OUTPUT_EXCEL}")
        except Exception as e:
            print(f"[!] Could not export .xlsx via openpyxl: {e}. Note: CSV is ready and can be opened in Excel.")
    else:
        print("[!] pandas/openpyxl not installed yet. (CSV is ready and opens directly in Excel).")

    print("\n" + "=" * 65)
    print(" ✅ SCRAPING & EXPORT COMPLETE!")
    print(f" 📄 TXT File:   {OUTPUT_TXT}")
    print(f" 📊 Excel File: {OUTPUT_EXCEL}")
    print(f" 📁 CSV File:   {OUTPUT_CSV}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
