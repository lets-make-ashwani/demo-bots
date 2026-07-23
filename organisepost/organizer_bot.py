import os
import re
import time
import sqlite3
import asyncio

# Fix event loop initialization for Python 3.12+ / 3.14+ where get_event_loop() raises RuntimeError
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import json
from dotenv import load_dotenv
import random
import sys
import io

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

# Load environment variables
load_dotenv(override=True)

# API Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "organizer_session")

# Channel & Bot configurations
TARGET_CHAT = (os.getenv("TARGET_CHAT_ORGANIZER") or os.getenv("TARGET_CHAT", "")).strip()

TARGET_BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "DiskWalaFileUploaderBot").strip().lower()

DB_FILE = os.getenv("DB_FILE", "organizer_progress.db")
COOLDOWN = int(os.getenv("COOLDOWN_BETWEEN_POSTS", "15"))
SCAN_COOLDOWN = int(os.getenv("SCAN_COOLDOWN", "300"))



# ================= DATABASE HELPERS =================
from pymongo import MongoClient

# Use environment variable
MONGO_URI = os.getenv("MONGO_URI", "").strip()

def init_db():
    if not MONGO_URI:
        print("[ERROR] MONGO_URI is missing from the environment/'.env' file.")
        sys.exit(1)
        
    print("[*] Connecting to MongoDB Atlas...")
    try:
        client = MongoClient(MONGO_URI)
        # Test connection
        client.admin.command('ping')
        print("[OK] Connected to MongoDB Atlas successfully!")
        return client["telegram_bots_progress"]
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        sys.exit(1)

db_conn = init_db()

def is_already_processed(reply_msg_id):
    try:
        return db_conn["organizer_replies"].find_one({"_id": reply_msg_id}) is not None
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return False

def mark_as_processed(reply_msg_id):
    try:
        db_conn["organizer_replies"].update_one({"_id": reply_msg_id}, {"$set": {"reply_msg_id": reply_msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

def get_last_processed_id():
    try:
        row = db_conn["organizer_progress"].find_one({"_id": "last_id"})
        return row["last_msg_id"] if row else 0
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return 0

def save_last_processed_id(msg_id):
    try:
        db_conn["organizer_progress"].update_one({"_id": "last_id"}, {"$set": {"last_msg_id": msg_id}}, upsert=True)
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



async def download_media_with_retry(app: Client, media, file_path: str, max_retries: int = 3) -> str:
    # Remove any existing file at file_path to avoid old or 0-byte files
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    for attempt in range(max_retries):
        try:
            path = await app.download_media(media, file_name=file_path)
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            else:
                print(f"[!] Downloaded file is empty or missing: {path}")
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        except FloodWait as fe:
            wait_time = fe.value + 2
            print(f"[!] FloodWait during media download. Waiting for {wait_time} seconds before retrying...")
            await asyncio.sleep(wait_time)
        except FileReferenceExpired:
            # Let FileReferenceExpired bubble up so the caller can refetch the message/media
            raise
        except Exception as e:
            print(f"[!] Download attempt {attempt + 1} failed: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            await asyncio.sleep(2)
    return None


async def process_and_publish_post(app: Client, target_chat_id: int, original_msg, diskwala_link: str, reply_msg):
    reply_msg_id = reply_msg.id

    # Check if original message is empty or missing media
    is_original_msg_valid = original_msg and not getattr(original_msg, "empty", False)

    raw_caption = ""
    is_copyrighted = False

    if is_original_msg_valid:
        media_obj = original_msg.video or original_msg.document
        raw_caption = original_msg.caption or ""
        msg_text = original_msg.text or ""

        # Detect copyright infringement block texts
        if "copyright infringement" in raw_caption.lower() or "couldn't be displayed" in raw_caption.lower():
            is_copyrighted = True
        if "copyright infringement" in msg_text.lower() or "couldn't be displayed" in msg_text.lower():
            is_copyrighted = True

        if is_copyrighted:
            print(f"[-] Skipping message {reply_msg_id}: Video was removed due to copyright infringement.")
            mark_as_processed(reply_msg_id)
            return

        if not raw_caption and media_obj and hasattr(media_obj, "file_name") and media_obj.file_name:
            # If caption is missing, use the video filename
            raw_caption = media_obj.file_name
            # Clean up filename dots/underscores for cleaner presentation
            raw_caption = raw_caption.replace(".", " ").replace("_", " ")
    else:
        # Fallback if original video is deleted/missing
        print(f"[!] Original message missing/deleted for reply {reply_msg_id}. Trying webpage or media fallback...")
        if reply_msg.web_page:
            raw_caption = reply_msg.web_page.title or reply_msg.web_page.description or ""
        
        # Try media filename as fallback
        if not raw_caption:
            for attr in ["animation", "video", "document"]:
                media = getattr(reply_msg, attr, None)
                if media and getattr(media, "file_name", None):
                    raw_caption = media.file_name.replace(".", " ").replace("_", " ")
                    break

        if not raw_caption:
            raw_caption = "Watch Video"

    # Combine original caption text and watch link
    caption_text = (
        f"{raw_caption}\n\n"
        f"🎬 Watch Here 👇\n"
        f"{diskwala_link}"
    )

    thumb_path = None
    os.makedirs("temp_thumbs", exist_ok=True)
    raw_path = f"temp_thumbs/raw_{reply_msg_id}.jpg"

    # 1. Attempt to download from reply_msg.web_page.photo first (link preview)
    if reply_msg.web_page and reply_msg.web_page.photo:
        print("[-] Downloading thumbnail from DiskWala link preview...")
        thumb_path = await download_media_with_retry(app, reply_msg.web_page.photo, file_path=raw_path)

    # 2. Attempt to download from reply_msg.animation.thumbs[0] (GIF/Animation)
    if not thumb_path and getattr(reply_msg, "animation", None) and reply_msg.animation.thumbs:
        print("[-] Downloading thumbnail from DiskWala GIF/animation reply...")
        thumb_path = await download_media_with_retry(app, reply_msg.animation.thumbs[0], file_path=raw_path)

    # 3. Attempt to download from reply_msg.photo (Photo)
    if not thumb_path and getattr(reply_msg, "photo", None):
        print("[-] Downloading thumbnail from DiskWala photo reply...")
        thumb_path = await download_media_with_retry(app, reply_msg.photo, file_path=raw_path)

    # 4. Attempt to download from reply_msg.video.thumbs[0] (Video)
    if not thumb_path and getattr(reply_msg, "video", None) and reply_msg.video.thumbs:
        print("[-] Downloading thumbnail from DiskWala video reply...")
        thumb_path = await download_media_with_retry(app, reply_msg.video.thumbs[0], file_path=raw_path)

    # 5. Attempt to download from reply_msg.document.thumbs[0] (Document)
    if not thumb_path and getattr(reply_msg, "document", None) and reply_msg.document.thumbs:
        print("[-] Downloading thumbnail from DiskWala document reply...")
        thumb_path = await download_media_with_retry(app, reply_msg.document.thumbs[0], file_path=raw_path)

    # Fallback to original message's thumbnail if link preview and media download failed or weren't available
    if not thumb_path and is_original_msg_valid:
        media_obj = original_msg.video or original_msg.document
        if media_obj and media_obj.thumbs:
            print("[-] Downloading video thumbnail from original file...")
            try:
                # Pass the Thumbnail object directly to download cleanly
                thumb_path = await download_media_with_retry(app, media_obj.thumbs[0], file_path=raw_path)
            except FileReferenceExpired:
                print("[-] File reference expired on thumbnail download. Attempting refetch...")
                try:
                    fresh_msg = await app.get_messages(original_msg.chat.id, original_msg.id)
                    new_media = fresh_msg.video or fresh_msg.document
                    if new_media and new_media.thumbs:
                        thumb_path = await download_media_with_retry(app, new_media.thumbs[0], file_path=raw_path)
                except Exception as fe:
                    print(f"[!] Fallback download failed: {fe}")
            except Exception as e:
                print(f"[!] Thumbnail processing failed: {e}")

    # Publish compiled post to target channel
    print("[-] Publishing post to organized channel...")
    try:
        if thumb_path and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            await app.send_photo(
                chat_id=target_chat_id,
                photo=thumb_path,
                caption=caption_text
            )
        else:
            print("[!] No valid thumbnail found. Publishing post text only...")
            await app.send_message(
                chat_id=target_chat_id,
                text=caption_text
            )
        msg_id_log = original_msg.id if is_original_msg_valid else f"reply_{reply_msg_id}"
        print(f"[+] Post published successfully for message {msg_id_log}!")
        mark_as_processed(reply_msg_id)
    except Exception as e:
        print(f"[x] Failed to publish post: {e}")

    # Cleanup temp photos
    try:
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
    except Exception:
        pass

# ================= RUN LOOP =================
async def run_organizer(app: Client, target_chat_id: int):
    try:
        while True:
            try:
                print("[-] Scanning DiskWala Bot chat history...")
                
                diskwala_history = []
                offset_id = 0
                limit = 50
                
                while True:
                    chunk = []
                    async for msg in app.get_chat_history(TARGET_BOT_USERNAME, limit=limit, offset_id=offset_id):
                        chunk.append(msg)
                        
                    if not chunk:
                        break
                        
                    # Prepare offset for the next page fetch
                    offset_id = chunk[-1].id
                    
                    unprocessed_in_chunk = 0
                    links_in_chunk = 0
                    
                    for msg in chunk:
                        if msg.from_user and msg.from_user.is_bot:
                            text = msg.text or msg.caption or ""
                            # Regex match for DiskWala links
                            match = re.search(r'(https?://(?:www\.)?diskwala\.com/app/[a-zA-Z0-9]+)', text)
                            if match:
                                links_in_chunk += 1
                                if not is_already_processed(msg.id):
                                    diskwala_history.append((msg, match.group(1)))
                                    unprocessed_in_chunk += 1
                                    
                    # If this chunk contained DiskWala link replies, but ALL of them
                    # were already processed, we can safely stop scanning backward.
                    if links_in_chunk > 0 and unprocessed_in_chunk == 0:
                        print("[-] Reached history page where all links are already processed. Stopping scan.")
                        break
                        
                    if len(chunk) < limit:
                        break

                if diskwala_history:
                    # Reverse order to process from OLDEST to NEWEST
                    diskwala_history.reverse()
                    print(f"[-] Found {len(diskwala_history)} replies containing links.")
                    
                    for reply_msg, link in diskwala_history:
                        if is_already_processed(reply_msg.id):
                            continue
                            
                        # Find the video message this reply references
                        reply_to_id = None
                        if reply_msg.reply_to_message:
                            reply_to_id = reply_msg.reply_to_message.id
                        elif hasattr(reply_msg, "reply_to_message_id") and reply_msg.reply_to_message_id:
                            reply_to_id = reply_msg.reply_to_message_id
                            
                        if not reply_to_id:
                            # Not a reply message, cannot find the original video
                            mark_as_processed(reply_msg.id)
                            continue
                            
                        print(f"\n[-] Found unprocessed reply ID: {reply_msg.id} (Reply to Msg ID: {reply_to_id})")
                        
                        try:
                            # Fetch the original video message sent to DiskWala Bot
                            original_msg = None
                            try:
                                original_msg = await app.get_messages(TARGET_BOT_USERNAME, reply_to_id)
                            except Exception as fetch_err:
                                print(f"[!] Original message fetch failed: {fetch_err}. Proceeding with reply web preview...")

                            # process_and_publish_post handles missing/deleted messages gracefully
                            await process_and_publish_post(app, target_chat_id, original_msg, link, reply_msg)
                        except Exception as e:
                            print(f"[!] Error fetching original message: {e}")
                            
                        # Cooldown between compiling/publishing posts
                        sleep_seconds = random.randint(10, 30)
                        print(f"[-] Cooldown: sleeping for {sleep_seconds} seconds...")
                        await asyncio.sleep(sleep_seconds)
                else:
                    print("[+] No new messages found in history scan.")
                    
            except Exception as cycle_error:
                print(f"[x] Error during scan cycle: {cycle_error}. Retrying in 30 seconds...")
                await asyncio.sleep(30)
                continue
                
            # Scan cooldown sleep
            print(f"[-] Scan complete. Sleeping for {SCAN_COOLDOWN} seconds before checking again...")
            await asyncio.sleep(SCAN_COOLDOWN)
            
    except asyncio.CancelledError:
        print("\n[!] Organizer background task cancelled.")

async def main():
    if not API_ID or not API_HASH:
        print("[x] Error: API_ID and API_HASH are missing from the environment/'.env' file.")
        return
        
    if not TARGET_CHAT:
        print("[x] Error: TARGET_CHAT is missing from the environment/'.env' file.")
        return

    print("==================================================")
    print("[*] STANDALONE CAPTION ORGANIZER BOT STARTED")
    print("==================================================")

    # Initialize Pyrogram client with no_updates=True
    SESSION_STRING = os.getenv("SESSION_STRING_ORGANIZER") or os.getenv("SESSION_STRING")
    if SESSION_STRING:
        app = Client("session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH, no_updates=True)
    else:
        app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, no_updates=True)

    
    async with app:
        print("[+] Logged in successfully!")
        print("\n[*] Resolving target chat...")
        try:
            target_chat_id = await resolve_chat_id(app, TARGET_CHAT)
            print(f"[-] Target Chat Resolved: {target_chat_id}")
        except Exception as e:
            print(e)
            return

        # Start loop task
        organizer_task = asyncio.create_task(run_organizer(app, target_chat_id))
        
        try:
            await idle()
        except (KeyboardInterrupt, SystemExit):
            print("\n[!] Interrupted by user. Cleaning up...")
        finally:
            print("[-] Stopping background loop...")
            organizer_task.cancel()
            try:
                await organizer_task
            except asyncio.CancelledError:
                pass
            print("[+] Organizer stopped cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
