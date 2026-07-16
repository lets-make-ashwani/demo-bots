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

import io
import sys
from dotenv import load_dotenv

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

# Monkeypatch Pyrogram's internal surrogate parser to prevent UnicodeDecodeErrors on messages with emojis/Hindi text
import pyrogram.parser.utils

def safe_remove_surrogates(text):
    if not text:
        return text
    try:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", errors="replace")
    except Exception:
        try:
            return text.encode("utf-16", errors="replace").decode("utf-16", errors="replace")
        except Exception:
            return text

def safe_add_surrogates(text):
    if not text:
        return text
    try:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", errors="replace")
    except Exception:
        try:
            return text.encode("utf-16", errors="replace").decode("utf-16", errors="replace")
        except Exception:
            return text

pyrogram.parser.utils.remove_surrogates = safe_remove_surrogates
pyrogram.parser.utils.add_surrogates = safe_add_surrogates

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, UserAlreadyParticipant, FileReferenceExpired
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


from PIL import Image, ImageEnhance

# Load environment variables
load_dotenv()

# API Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "pipeline_session")

# Chat Configurations
SOURCE_CHAT = (os.getenv("SOURCE_CHAT_PIPELINE") or os.getenv("SOURCE_CHAT", "https://t.me/videos_down")).strip()
TARGET_CHAT = (os.getenv("TARGET_CHAT_PIPELINE") or os.getenv("TARGET_CHAT", "https://t.me/allpost1234")).strip()
TARGET_BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "DiskWalaFileUploaderBot").strip().lower()



DB_FILE = os.getenv("DB_FILE", "pipeline_progress.db")
COOLDOWN = int(os.getenv("COOLDOWN_BETWEEN_POSTS", "15"))
MAX_RETRIES = 3

# Global Event & Tracking State
reply_event = asyncio.Event()
reply_link = None
reply_retry = False
current_item = None

def analyze_diskwala_reply(text: str) -> dict:
    if not text:
        return {"status": "unknown", "extracted_link": None, "reason": "Empty text"}

    text_lower = text.lower()
    match = re.search(r'(https?://(?:www\.)?diskwala\.com/app/[a-zA-Z0-9]+)', text)
    if match:
        return {"status": "link_found", "extracted_link": match.group(1), "reason": "Regex match"}
    elif "forward me this" in text_lower or "send again" in text_lower or "same post" in text_lower:
        return {"status": "retry_requested", "extracted_link": None, "reason": "Keyword match"}
    return {"status": "unknown", "extracted_link": None, "reason": "Unknown"}

SESSION_STRING = os.getenv("SESSION_STRING_PIPELINE") or os.getenv("SESSION_STRING")
if SESSION_STRING:
    app = Client("session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH, no_updates=True)
else:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, no_updates=True)


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

def is_already_sent(msg_id):
    try:
        return db_conn["pipeline_sent"].find_one({"_id": msg_id}) is not None
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return False

def mark_as_sent(msg_id):
    try:
        db_conn["pipeline_sent"].update_one({"_id": msg_id}, {"$set": {"msg_id": msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

def get_last_processed_id():
    try:
        row = db_conn["pipeline_progress"].find_one({"_id": "last_id"})
        return row["last_msg_id"] if row else 0
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return 0

def save_last_processed_id(msg_id):
    try:
        db_conn["pipeline_progress"].update_one({"_id": "last_id"}, {"$set": {"last_msg_id": msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

def get_sent_msg_id(msg_id):
    try:
        row = db_conn["pipeline_uploads"].find_one({"_id": msg_id})
        return row["sent_msg_id"] if row else None
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return None

def save_diskwala_upload(msg_id, sent_msg_id):
    try:
        db_conn["pipeline_uploads"].update_one({"_id": msg_id}, {"$set": {"sent_msg_id": sent_msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")




# ================= CHAT RESOLVER =================
async def resolve_chat_id(chat_value: str) -> int:
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
        except UserAlreadyParticipant:
            pass
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

# ================= THUMBNAIL ENHANCER =================
def enhance_thumbnail(input_path: str, output_path: str):
    try:
        img = Image.open(input_path)

        # 1. Upscale (2x)
        width, height = img.size
        img = img.resize((width * 2, height * 2), Image.Resampling.LANCZOS)

        # 2. Enhance sharpness
        img = ImageEnhance.Sharpness(img).enhance(1.8)

        # 3. Enhance color
        img = ImageEnhance.Color(img).enhance(1.3)

        # 4. Enhance contrast
        img = ImageEnhance.Contrast(img).enhance(1.2)

        # 5. Brightness adjustment
        img = ImageEnhance.Brightness(img).enhance(1.1)

        img.save(output_path, quality=95)
        return True
    except Exception as e:
        print(f"[x] Pillow enhancement failed: {e}")
        return False

# ================= SAFE FIELD EXTRACTORS =================
def get_safe_caption(msg):
    if not msg:
        return ""
    try:
        return msg.caption or ""
    except Exception:
        return ""

def get_safe_text(msg):
    if not msg:
        return ""
    try:
        return msg.text or ""
    except Exception:
        return ""

# ================= UPLOAD TO DISKWALA =================
async def send_to_diskwala_safely(media_msg):
    while True:
        try:
            msg = await app.get_messages(SOURCE_CHAT_RESOLVED, media_msg.id)
            
            sent_msg = None
            if msg.video:
                sent_msg = await app.send_video(TARGET_BOT_USERNAME, msg.video.file_id, caption=get_safe_caption(msg))
            elif msg.document:
                sent_msg = await app.send_document(TARGET_BOT_USERNAME, msg.document.file_id, caption=get_safe_caption(msg))
            
            return sent_msg.id if sent_msg else None
        except FileReferenceExpired:
            print("[-] File reference expired. Refetching message...")
            await asyncio.sleep(2)
        except FloodWait as e:
            wait_time = e.value + 5
            print(f"[-] FloodWait in send_to_diskwala. Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[x] Error uploading to DiskWala bot: {e}")
            return False

# ================= PUBLISH COMPILED POST =================
async def publish_compiled_post(item, diskwala_link):
    source_msg = item["media_msg"]
    orig_caption = item["caption"]
    
    thumb_path = None
    enhanced_thumb_path = None
    
    # Fetch a fresh copy of the message to ensure file references are valid
    caption_entities = None
    try:
        fresh_msg = await app.get_messages(SOURCE_CHAT_RESOLVED, source_msg.id)
        media_obj = fresh_msg.video or fresh_msg.document
        caption_entities = fresh_msg.caption_entities
    except Exception as e:
        print(f"[!] Failed to refetch message: {e}")
        media_obj = source_msg.video or source_msg.document
        caption_entities = getattr(source_msg, "caption_entities", None)

    if media_obj and media_obj.thumbs:
        print("[-] Downloading video thumbnail...")
        try:
            os.makedirs("temp_thumbs", exist_ok=True)
            raw_path = f"temp_thumbs/raw_{source_msg.id}.jpg"
            
            # Pass the Thumbnail object directly instead of file_id string
            thumb_path = await app.download_media(media_obj.thumbs[0], file_name=raw_path)
            
            if thumb_path and os.path.exists(thumb_path):
                enhanced_path = f"temp_thumbs/enhanced_{source_msg.id}.jpg"
                if enhance_thumbnail(thumb_path, enhanced_path):
                    enhanced_thumb_path = enhanced_path
        except FileReferenceExpired:
            print("[-] File reference expired on thumbnail download. Attempting fallback download...")
            try:
                # Force a fresh fetch of the message from Telegram
                fresh_msg = await app.get_messages(SOURCE_CHAT_RESOLVED, source_msg.id)
                new_media = fresh_msg.video or fresh_msg.document
                if new_media and new_media.thumbs:
                    thumb_path = await app.download_media(new_media.thumbs[0], file_name=raw_path)
                    if thumb_path and os.path.exists(thumb_path):
                        enhanced_path = f"temp_thumbs/enhanced_{source_msg.id}.jpg"
                        if enhance_thumbnail(thumb_path, enhanced_path):
                            enhanced_thumb_path = enhanced_path
            except Exception as fe:
                print(f"[!] Fallback download failed: {fe}")
        except Exception as e:
            print(f"[!] Thumbnail processing failed: {e}")

    # Format caption exactly matching Image 1: original caption, divider, watch here, link
    if orig_caption:
        caption_text = f"{orig_caption}\n\n──────────\n🎬 Watch Here 👇\n{diskwala_link}"
    else:
        caption_text = f"🎬 Watch Here 👇\n{diskwala_link}"

    print(f"[-] Publishing compiled post to target channel...")
    try:
        if enhanced_thumb_path and os.path.exists(enhanced_thumb_path):
            await app.send_photo(
                chat_id=TARGET_CHAT_RESOLVED,
                photo=enhanced_thumb_path,
                caption=caption_text,
                caption_entities=caption_entities
            )
        else:
            await app.send_message(
                chat_id=TARGET_CHAT_RESOLVED,
                text=caption_text,
                entities=caption_entities
            )
        print(f"[+] Post published successfully for message {source_msg.id}!")
    except Exception as e:
        print(f"[x] Failed to publish post: {e}")

    try:
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        if enhanced_thumb_path and os.path.exists(enhanced_thumb_path):
            os.remove(enhanced_thumb_path)
    except Exception:
        pass

# NOTE: Update listener disabled because no_updates=True is used to prevent background update crashes.
# All replies are retrieved by scanning TARGET_BOT_USERNAME chat history.

# ================= DUPLICATE CAPTION CHECK =================
async def is_caption_already_published(caption: str) -> bool:
    caption = caption.strip()
    if not caption:
        return False
    try:
        async for target_msg in app.get_chat_history(TARGET_CHAT_RESOLVED, limit=200):
            target_text = (get_safe_caption(target_msg) or get_safe_text(target_msg)).strip()
            if not target_text:
                continue
            if caption in target_text:
                return True
    except Exception as e:
        print(f"[!] Error checking target history for duplicate caption: {e}")
    return False

# ================= PIPELINE LOOP =================
async def run_pipeline():
    global reply_link, reply_retry, current_item
    
    try:
        while True:
            last_id = get_last_processed_id()
            messages = []

            # Pre-cache last 200 target captions to avoid Telegram GetHistory FloodWait limits
            published_captions = set()
            try:
                print("[-] Pre-caching last 200 published captions from target channel...")
                async for target_msg in app.get_chat_history(TARGET_CHAT_RESOLVED, limit=200):
                    text = (get_safe_caption(target_msg) or get_safe_text(target_msg)).strip()
                    if text:
                        published_captions.add(text)
                print(f"[+] Pre-cached {len(published_captions)} target captions.")
            except Exception as e:
                print(f"[!] Error pre-caching target history: {e}")

            print("[-] Scanning source channel for new messages...")
            async for msg in app.get_chat_history(SOURCE_CHAT_RESOLVED):
                if msg.id <= last_id:
                    break
                
                is_video = False
                if msg.video:
                    is_video = True
                elif msg.document and (
                    (msg.document.mime_type or "").startswith("video/") or
                    (msg.document.file_name or "").lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v'))
                ):
                    is_video = True

                if is_video:
                    messages.append(msg)

            if messages:
                # Reverse order to process from OLDEST to NEWEST (chronological)
                messages.reverse()
                print(f"[-] Found {len(messages)} new video messages to process.")
                
                # Track the highest already sent message id to update checkpoint once, avoiding 4000+ sequential disk commits
                highest_skipped_id = last_id
                unsent_messages = []
                
                for msg in messages:
                    if is_already_sent(msg.id):
                        highest_skipped_id = max(highest_skipped_id, msg.id)
                    else:
                        unsent_messages.append(msg)
                
                if highest_skipped_id > last_id:
                    save_last_processed_id(highest_skipped_id)
                    
                if not unsent_messages:
                    print("[-] All discovered video messages were already processed.")
                else:
                    # Filter unsent messages locally to check if their captions are already published
                    # This avoids writing database updates on every loop iteration
                    already_published_ids = []
                    actual_unsent_messages = []
                    
                    for msg in unsent_messages:
                        caption_str = get_safe_caption(msg).strip()
                        already_published = False
                        if caption_str:
                            for published_text in published_captions:
                                if caption_str in published_text:
                                    already_published = True
                                    break
                        
                        if already_published:
                            already_published_ids.append(msg.id)
                            highest_skipped_id = max(highest_skipped_id, msg.id)
                        else:
                            actual_unsent_messages.append(msg)
                    
                    # Batch commit all already published IDs to database at once
                    if already_published_ids:
                        print(f"[-] Skipping {len(already_published_ids)} already published video posts...")
                        try:
                            for m_id in already_published_ids:
                                db_conn["pipeline_sent"].update_one({"_id": m_id}, {"$set": {"msg_id": m_id}}, upsert=True)
                        except Exception as db_err:
                            print(f"[ERROR] Database batch insert failed: {db_err}")
                        save_last_processed_id(highest_skipped_id)


                    # In-place overwrite unsent_messages to preserve loop indentation
                    unsent_messages = actual_unsent_messages

                    if not unsent_messages:
                        print("[-] All discovered video messages are already published.")
                    else:
                        print(f"[-] Processing {len(unsent_messages)} actual new unsent video messages...")
                
                for msg in unsent_messages:

                    print(f"\n[-] Processing message {msg.id} | Caption: {get_safe_caption(msg)[:40]}...")
                    
                    # Reset active tracking state
                    current_item = {
                        "msg_id": msg.id,
                        "caption": get_safe_caption(msg),
                        "media_msg": msg,
                        "sent_msg_id": None
                    }
                    reply_link = None
                    retry_count = 0

                    # Check if this message was already sent to DiskWala before shutdown
                    sent_msg_id = get_sent_msg_id(msg.id)
                    if sent_msg_id:
                        current_item["sent_msg_id"] = sent_msg_id
                        print(f"[-] Video {msg.id} was already sent to DiskWala (Sent Message ID: {sent_msg_id}).")
                        print("[-] Checking chat history for reply link...")
                        found_link = None
                        async for reply in app.get_chat_history(TARGET_BOT_USERNAME, limit=30):
                            reply_to_id = None
                            if reply.reply_to_message:
                                reply_to_id = reply.reply_to_message.id
                            elif hasattr(reply, "reply_to_message_id") and reply.reply_to_message_id:
                                reply_to_id = reply.reply_to_message_id

                            if reply_to_id == sent_msg_id:
                                text = (get_safe_text(reply) or get_safe_caption(reply)).strip()
                                analysis = analyze_diskwala_reply(text)
                                if analysis.get("status") == "link_found" and analysis.get("extracted_link"):
                                    found_link = analysis["extracted_link"]
                                    print(f"[+] Found matching reply link in history: {found_link}")
                                    break
                        if found_link:
                            reply_link = found_link
                    else:
                        # Send file to DiskWala Bot
                        sent_msg_id = await send_to_diskwala_safely(msg)
                        if not sent_msg_id:
                            print(f"[x] Skipping message {msg.id} due to upload failure.")
                            save_last_processed_id(msg.id)
                            current_item = None
                            continue
                        save_diskwala_upload(msg.id, sent_msg_id)
                        current_item["sent_msg_id"] = sent_msg_id

                    # Wait for link or retry callback via history polling
                    if not reply_link:
                        start_time = time.time()
                        timeout = 300  # 5 minutes
                        
                        while True:
                            found_link = None
                            retry_requested = False
                            error_occurred = False
                            
                            try:
                                async for reply in app.get_chat_history(TARGET_BOT_USERNAME, limit=10):
                                    reply_to_id = None
                                    if reply.reply_to_message:
                                        reply_to_id = reply.reply_to_message.id
                                    elif hasattr(reply, "reply_to_message_id") and reply.reply_to_message_id:
                                        reply_to_id = reply.reply_to_message_id

                                    if reply_to_id == sent_msg_id:
                                        text = (get_safe_text(reply) or get_safe_caption(reply)).strip()
                                        analysis = analyze_diskwala_reply(text)
                                        status = analysis.get("status")
                                        
                                        if status == "link_found" and analysis.get("extracted_link"):
                                            found_link = analysis["extracted_link"]
                                            break
                                        elif status == "retry_requested":
                                            retry_requested = True
                                            break
                                        elif status == "error":
                                            error_occurred = True
                                            break
                            except Exception as e:
                                print(f"[!] Error scanning history in poll loop: {e}")

                            if found_link:
                                reply_link = found_link
                                break
                            
                            if retry_requested:
                                if retry_count >= MAX_RETRIES:
                                    print(f"[x] Max retries reached for message {msg.id}. Skipping.")
                                    break
                                retry_count += 1
                                print(f"[-] DiskWala bot requested retry (Attempt {retry_count}/{MAX_RETRIES}). Resending video...")
                                sent_msg_id = await send_to_diskwala_safely(msg)
                                if sent_msg_id:
                                    save_diskwala_upload(msg.id, sent_msg_id)
                                    current_item["sent_msg_id"] = sent_msg_id
                                start_time = time.time()  # Reset timeout
                                await asyncio.sleep(5)
                                continue
                                
                            if error_occurred:
                                print(f"[x] DiskWala bot replied with an error for message {msg.id}. Skipping.")
                                break

                            # Check timeout
                            if time.time() - start_time > timeout:
                                print(f"[x] Timeout waiting for reply for message {msg.id}. Skipping.")
                                break
                            
                            # Wait 3 seconds before next poll
                            await asyncio.sleep(3)

                    # If we successfully retrieved the link, publish it
                    if reply_link:
                        await publish_compiled_post(current_item, reply_link)
                        mark_as_sent(msg.id)

                    # Save checkpoint and sleep
                    save_last_processed_id(msg.id)
                    current_item = None

                    print(f"[-] Cooldown: sleeping for {COOLDOWN} seconds...")
                    await asyncio.sleep(COOLDOWN)
            else:
                # If no new video messages, check if there are any new text messages to advance checkpoint
                async for newest_msg in app.get_chat_history(SOURCE_CHAT_RESOLVED, limit=1):
                    if newest_msg.id > last_id:
                        save_last_processed_id(newest_msg.id)
                        print(f"[-] Advancing scanned checkpoint ID to: {newest_msg.id}")

                print("[-] No new video messages found. Sleeping for 30 seconds...")
                await asyncio.sleep(30)
    except asyncio.CancelledError:
        print("\n[!] Pipeline background task cancelled. Exiting loop cleanly...")


async def run_pipeline_wrapper():
    while True:
        try:
            await run_pipeline()
        except asyncio.CancelledError:
            print("\n[!] Pipeline wrapper task cancelled.")
            break
        except Exception as e:
            import traceback
            print(f"[!] Pipeline loop crashed with error:\n{traceback.format_exc()}")
            print("[-] Restarting pipeline background loop in 10 seconds...")
            await asyncio.sleep(10)

# ================= RUN =================
async def main():
    global SOURCE_CHAT_RESOLVED, TARGET_CHAT_RESOLVED

    if not API_ID or not API_HASH:
        print("[x] Error: API_ID and API_HASH are missing from the environment/'.env' file.")
        return

    print("==================================================")
    print("[*] UNIFIED MOVIE DISTRIBUTION PIPELINE BOT STARTED")
    print("==================================================")



    print("\n[*] Resolving channels...")
    try:
        SOURCE_CHAT_RESOLVED = await resolve_chat_id(SOURCE_CHAT)
        TARGET_CHAT_RESOLVED = await resolve_chat_id(TARGET_CHAT)
        print(f"[-] Source Chat Resolved: {SOURCE_CHAT_RESOLVED}")
        print(f"[-] Target Chat Resolved: {TARGET_CHAT_RESOLVED}")
    except Exception as e:
        print(e)
        return

    # Start loop
    pipeline_task = asyncio.create_task(run_pipeline_wrapper())
    try:
        await idle()
    except (KeyboardInterrupt, SystemExit):
        print("\n[!] Interrupted by user. Cleaning up...")
    finally:
        print("[-] Stopping pipeline background task...")
        pipeline_task.cancel()
        try:
            await pipeline_task
        except asyncio.CancelledError:
            pass
        print("[+] Pipeline stopped cleanly.")

if __name__ == "__main__":
    app.start()
    app.run(main())
