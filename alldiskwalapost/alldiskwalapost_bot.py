import os
import re
import time
import asyncio

# Fix event loop initialization for Python 3.12+ where get_event_loop() raises RuntimeError
try:
    asyncio.get_event_loop()
except RuntimeError:
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import sys
import io
from dotenv import load_dotenv
import random

# Configure UTF-8 encoding for standard output/error to prevent encoding issues on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', write_through=True)

# Monkeypatch Pyrogram's internal ID limits to support newer 64-bit Telegram IDs
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000
pyrogram.utils.MIN_CHAT_ID = -99999999999999
pyrogram.utils.MAX_USER_ID = 99999999999999

from pyrogram import Client, idle
from pyrogram.errors import FloodWait, FileReferenceExpired
from pymongo import MongoClient
from groq import Groq

# Load environment variables
load_dotenv(override=True)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "alldiskwalapost_session")

SOURCE_CHAT = (os.getenv("SOURCE_CHAT_ALLDISKWALAPOST") or os.getenv("SOURCE_CHAT", "https://t.me/organisepost")).strip()
TARGET_CHAT = (os.getenv("TARGET_CHAT_ALLDISKWALAPOST") or os.getenv("TARGET_CHAT", "https://t.me/diskwalapost")).strip()

MONGO_URI = os.getenv("MONGO_URI", "").strip()
COOLDOWN = int(os.getenv("COOLDOWN_BETWEEN_POSTS", "15"))
SCAN_COOLDOWN = int(os.getenv("SCAN_COOLDOWN", "300"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

# ================= SYSTEM PROMPT FOR GROQ =================
GROQ_SYSTEM_PROMPT = """You are a precise metadata extraction assistant for movie and web-series files. 
Your task is to analyze the raw Telegram caption provided by the user, extract the key metadata, and output it in a clean, structured list.

Follow these strict rules:
1. Do NOT include any introductory text, greetings, explanations, or conversational filler.
2. Do NOT include any outro text, pleasantries, or sign-offs.
3. Output ONLY the formatted metadata fields.
4. Extract ONLY these fields:
   - **Title**: [Clean name of the movie or web series]
   - **Season**: [Season number, e.g. S01]
   - **Episodes**: [Episode numbers, e.g. E01-08]
   - **Resolution**: [e.g. 1080p, 720p, 480p]
   - **Languages**: [Comma-separated list of audio languages]
   - **Subtitles**: [e.g. ESub, MSub]
   - **Link**: [The full diskwala.com URL found in the post]

5. CRITICAL: If a field is not present in the original text or is not applicable (like Season/Episodes for a movie), do NOT output that field's line at all. Do NOT output empty labels (e.g., do NOT print "* Season:" or "**Season**:" if it has no value). Only output lines that have actual extracted data.
6. Make sure the output format is a clean bulleted list using "* **Field Name**: Value" (e.g. * **Title**: The Hobbit)."""

# ================= DATABASE CONNECTION =================
def init_db():
    if not MONGO_URI:
        print("[ERROR] MONGO_URI is missing from the environment/'.env' file.")
        sys.exit(1)
    
    print("[*] Connecting to MongoDB Atlas...")
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        print("[OK] Connected to MongoDB Atlas successfully!")
        return client["telegram_bots_progress"]
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        sys.exit(1)

db_conn = init_db()

def is_already_processed(msg_id):
    try:
        return db_conn["alldiskwalapost_processed"].find_one({"_id": msg_id}) is not None
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return False

def mark_as_processed(msg_id):
    try:
        db_conn["alldiskwalapost_processed"].update_one({"_id": msg_id}, {"$set": {"msg_id": msg_id, "timestamp": time.time()}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

def get_last_processed_id():
    try:
        row = db_conn["alldiskwalapost_progress"].find_one({"_id": "last_id"})
        return row["last_msg_id"] if row else 0
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return 0

def save_last_processed_id(msg_id):
    try:
        db_conn["alldiskwalapost_progress"].update_one({"_id": "last_id"}, {"$set": {"last_msg_id": msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

# ================= CHAT RESOLVER =================
async def resolve_chat_id(app: Client, chat_value: str) -> int:
    chat_value = chat_value.strip()

    if (chat_value.startswith("-") and chat_value[1:].isdigit()) or chat_value.isdigit():
        try:
            resolved = await app.get_chat(int(chat_value))
            return resolved.id
        except Exception:
            pass

    if "t.me/+" in chat_value or chat_value.startswith("+"):
        try:
            chat = await app.join_chat(chat_value)
            print(f"[+] Joined private chat: '{chat.title}' ({chat.id})")
            return chat.id
        except Exception as e:
            print(f"[!] Failed to join invite link: {e}")

    if chat_value.startswith("https://t.me/"):
        chat_value = chat_value.replace("https://t.me/", "").split("/")[0]

    if not chat_value.startswith("@") and not chat_value.startswith("-") and not chat_value.isdigit():
        chat_value = "@" + chat_value

    try:
        chat = await app.get_chat(chat_value)
        return chat.id
    except Exception as e:
        raise ValueError(
            f"[x] Could not resolve chat '{chat_value}'. Reason: {e}\n"
            f"Please verify you have joined the channel or that the username/invite link is correct."
        )

# ================= GROQ API METADATA EXTRACTOR =================
def extract_metadata_via_groq(caption_text: str) -> str:
    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY is missing from .env.")
        raise ValueError("GROQ_API_KEY is missing")
    
    attempt = 0
    max_attempts = 5
    while attempt < max_attempts:
        try:
            groq_client = Groq(api_key=GROQ_API_KEY)
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                    {"role": "user", "content": caption_text}
                ],
                model=GROQ_MODEL,
                temperature=0.1  # Low temperature for highly precise output
            )
            result = chat_completion.choices[0].message.content
            return result.strip()
        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower() or "429" in err_str or "rate limit" in err_str.lower():
                wait_time = 60  # default
                # Extract wait time from error message: "Please try again in 1m30.72s."
                match = re.search(r'try again in (?:(\d+)m)?([\d.]+)s', err_str)
                if match:
                    mins = int(match.group(1)) if match.group(1) else 0
                    secs = float(match.group(2))
                    wait_time = int(mins * 60 + secs) + 5  # Add 5s safety buffer
                
                print(f"[!] Groq Rate Limit (429) hit. Sleeping for {wait_time}s before retry {attempt + 1}/{max_attempts}...")
                time.sleep(wait_time)
                attempt += 1
            else:
                print(f"[x] Groq API call failed: {e}")
                raise e
    
    raise RuntimeError("Max retries exceeded for Groq API call due to Rate Limits.")

# ================= PHOTO DOWNLOAD HELPER (REFETCH IF EXPIRED) =================
async def download_photo_with_refetch(app: Client, source_chat_id: int, msg, temp_file: str) -> str | None:
    # Cleanup any existing file first
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except Exception:
            pass

    try:
        # First attempt: download using the reference in msg
        path = await app.download_media(msg.photo, file_name=temp_file)
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception as e:
        print(f"[!] First download attempt failed: {e}")

    # If first attempt failed or returned a 0-byte file, retry after refetching the message
    print("[-] File reference might be expired. Refetching message from origin context...")
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except Exception:
            pass

    try:
        fresh_msg = await app.get_messages(source_chat_id, msg.id)
        if fresh_msg and fresh_msg.photo:
            path = await app.download_media(fresh_msg.photo, file_name=temp_file)
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                print("[+] Successfully downloaded photo after refetching!")
                return path
    except Exception as e:
        print(f"[!] Refetch download attempt failed: {e}")

    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except Exception:
            pass
            
    return None

# ================= PROCESS & PUBLISH =================
async def process_message(app: Client, msg, source_chat_id: int, target_chat_id: int):
    print(f"\n[-] Processing message ID: {msg.id}")
    
    # Extract raw caption/text
    raw_caption = msg.caption or msg.text or ""
    if not raw_caption:
        print(f"[-] Skipping message {msg.id}: Empty caption/text.")
        mark_as_processed(msg.id)
        return

    print(f"[-] Raw caption text:\n---\n{raw_caption}\n---")

    # Look for DiskWala link in the caption
    diskwala_match = re.search(r'(https?://(?:www\.)?diskwala\.com/app/[a-zA-Z0-9]+)', raw_caption)
    if not diskwala_match:
        print(f"[-] Skipping message {msg.id}: No diskwala link found in caption.")
        mark_as_processed(msg.id)
        return
    
    diskwala_link = diskwala_match.group(1)
    print(f"[-] Extracted DiskWala Link: {diskwala_link}")
    
    # Call Groq to extract metadata
    print("[-] Sending caption to Groq for metadata extraction...")
    metadata_output = extract_metadata_via_groq(raw_caption)
    
    if not metadata_output:
        raise RuntimeError("Groq metadata extraction returned empty output.")

    print(f"[-] Groq API Response:\n---\n{metadata_output}\n---")

    # Verify that the link is present in the output. If not, append it.
    if diskwala_link not in metadata_output:
        metadata_output += f"\n* **Link**: {diskwala_link}"

    # Handle media/thumbnail download
    thumb_path = None
    if msg.photo:
        os.makedirs("temp_photos", exist_ok=True)
        temp_file = f"temp_photos/photo_{msg.id}.jpg"
        thumb_path = await download_photo_with_refetch(app, source_chat_id, msg, temp_file)
        if thumb_path:
            print(f"[+] Downloaded photo to: {thumb_path} (Size: {os.path.getsize(thumb_path)} bytes)")
    else:
        print("[-] Post does not contain a photo (text-only post).")

    # Post to Target Channel
    try:
        if thumb_path and os.path.exists(thumb_path):
            print("[-] Publishing post with photo to target channel...")
            await app.send_photo(
                chat_id=target_chat_id,
                photo=thumb_path,
                caption=metadata_output
            )
        else:
            print("[-] Publishing text-only post to target channel...")
            await app.send_message(
                chat_id=target_chat_id,
                text=metadata_output
            )
        print(f"[+] Post successfully published for message {msg.id}!")
        mark_as_processed(msg.id)
    except FloodWait as fw:
        print(f"[!] FloodWait in publishing. Sleeping for {fw.value} seconds...")
        await asyncio.sleep(fw.value)
        # Retry once
        if thumb_path and os.path.exists(thumb_path):
            await app.send_photo(chat_id=target_chat_id, photo=thumb_path, caption=metadata_output)
        else:
            await app.send_message(chat_id=target_chat_id, text=metadata_output)
        print(f"[+] Post successfully published after FloodWait!")
        mark_as_processed(msg.id)
    except Exception as e:
        print(f"[x] Failed to publish post: {e}")
        raise e
    finally:
        # Cleanup temp photo
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

# ================= RUNNER LOOP =================
async def run_workflow(app: Client, source_chat_id: int, target_chat_id: int):
    try:
        while True:
            last_id = get_last_processed_id()
            print(f"[-] Scanning source channel from checkpoint ID: {last_id}")
            
            messages = []
            async for msg in app.get_chat_history(source_chat_id):
                if msg.id <= last_id:
                    break
                
                # Check if already processed (secondary check)
                if not is_already_processed(msg.id):
                    messages.append(msg)
            
            if messages:
                # Reverse to process chronologically (oldest to newest)
                messages.reverse()
                print(f"[-] Found {len(messages)} new posts to process.")
                
                for msg in messages:
                    try:
                        await process_message(app, msg, source_chat_id, target_chat_id)
                        save_last_processed_id(msg.id)
                        print(f"[-] Sleeping for {COOLDOWN} seconds cooldown...")
                        await asyncio.sleep(COOLDOWN)
                    except Exception as msg_err:
                        print(f"[!] Error processing message {msg.id}: {msg_err}")
                        print("[-] Pausing workflow due to processing failure. Will retry on next scan.")
                        break
            else:
                print("[-] No new posts found in scan.")
                
                # If there are messages in history, advance checkpoint to the absolute newest message ID
                async for newest_msg in app.get_chat_history(source_chat_id, limit=1):
                    if newest_msg.id > last_id:
                        save_last_processed_id(newest_msg.id)
                        print(f"[-] Checkpoint advanced to newest ID: {newest_msg.id}")
            
            print(f"[-] Scan complete. Sleeping for {SCAN_COOLDOWN} seconds...")
            await asyncio.sleep(SCAN_COOLDOWN)
            
    except asyncio.CancelledError:
        print("\n[!] Workflow loop cancelled.")

# ================= MAIN =================
async def main():
    if not API_ID or not API_HASH:
        print("[x] Error: API_ID and API_HASH are missing from the environment/'.env' file.")
        return

    print("==================================================")
    # Corrected string literal for print formatting
    print("[*] ALLDISKWALAPOST WORKFLOW BOT STARTED")
    print("==================================================")

    # Initialize Client with no_updates=True
    SESSION_STRING = os.getenv("SESSION_STRING_ALLDISKWALAPOST") or os.getenv("SESSION_STRING")
    if SESSION_STRING:
        app = Client("session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH, no_updates=True)
    else:
        app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, no_updates=True)

    async with app:
        print("[+] Logged in successfully!")
        print("\n[*] Resolving chats...")
        try:
            source_chat_id = await resolve_chat_id(app, SOURCE_CHAT)
            target_chat_id = await resolve_chat_id(app, TARGET_CHAT)
            print(f"[-] Source Chat Resolved: {source_chat_id}")
            print(f"[-] Target Chat Resolved: {target_chat_id}")
        except Exception as e:
            print(f"[x] Chat resolution failed: {e}")
            return

        workflow_task = asyncio.create_task(run_workflow(app, source_chat_id, target_chat_id))
        
        try:
            await idle()
        except (KeyboardInterrupt, SystemExit):
            print("\n[!] Interrupted by user. Cleaning up...")
        finally:
            print("[-] Stopping background loop...")
            workflow_task.cancel()
            try:
                await workflow_task
            except asyncio.CancelledError:
                pass
            print("[+] Workflow stopped cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
