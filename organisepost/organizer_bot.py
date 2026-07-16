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
from PIL import Image, ImageEnhance
from google import genai
from google.genai import types

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Configure Gemini if API key is present and not the placeholder
gemini_enabled = False
gemini_client = None
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        gemini_enabled = True
        print("[+] Gemini AI configured successfully with Google Search Grounding (google-genai).")
    except Exception as e:
        print(f"[!] Failed to configure Gemini AI: {e}. Fallback parser will be used.")
else:
    print("[!] Warning: GEMINI_API_KEY is not configured in .env. Fallback regex parser will be used.")

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

# ================= LOCAL FALLBACK PARSER =================
def parse_caption_locally(raw_text: str) -> dict:
    if not raw_text:
        return {
            "title": "Untitled Movie",
            "year": "N/A",
            "type": "Movie",
            "country": "Unknown",
            "episodes_or_part": None,
            "quality": "HD",
            "languages": ["Unknown"],
            "genres": ["Entertainment"],
            "hashtags": ["#Movie"]
        }
        
    # Remove file extensions like .mkv, .mp4, etc.
    clean_text = re.sub(r'\.(mkv|mp4|avi|srt)$', '', raw_text, flags=re.IGNORECASE)
    # Replace dots and underscores with spaces
    clean_text = clean_text.replace(".", " ").replace("_", " ")
    
    # Try to extract year (1900-2099)
    year_match = re.search(r'\b((?:19|20)\d{2})\b', clean_text)
    year = year_match.group(1) if year_match else "N/A"
    
    # Try to extract quality
    quality_match = re.search(r'\b(\d{3,4}p|HEVC|x265|x264|WEB-DL|HDRip|BluRay)\b', clean_text, re.IGNORECASE)
    quality = quality_match.group(1).upper() if quality_match else "HD"
    
    # Try to extract languages
    langs = []
    if re.search(r'\b(hin|hindi)\b', clean_text, re.IGNORECASE):
        langs.append("Hindi")
    if re.search(r'\b(eng|english)\b', clean_text, re.IGNORECASE):
        langs.append("English")
    if re.search(r'\b(ben|bengali)\b', clean_text, re.IGNORECASE):
        langs.append("Bengali")
    if re.search(r'\b(kor|korean)\b', clean_text, re.IGNORECASE):
        langs.append("Korean")
    if re.search(r'\b(tam|tamil)\b', clean_text, re.IGNORECASE):
        langs.append("Tamil")
    if re.search(r'\b(tel|telugu)\b', clean_text, re.IGNORECASE):
        langs.append("Telugu")
    if not langs:
        langs = ["Unknown"]
        
    # Try to extract episodes/parts - put longest/most specific patterns first!
    ep_match = re.search(r'(S\d+(?:\s?(?:COMBINED|COMPLETE|EPISODES?|EP)?\s?(?:\[E\d+-E\d+\]|\(E\d+-E\d+\)|\[EP\d+-EP\d+\]|\(EP\d+-EP\d+\)|EP\s?\(?\d+-\d+\)?|EP\d+|E\d+))?|Part\s?\d+)', clean_text, re.IGNORECASE)
    episodes_or_part = ep_match.group(1).strip() if ep_match and ep_match.group(1) else None
    
    # Clean the title (everything before the year or first quality indicator)
    title = clean_text
    # Cut off at year
    if year_match:
        title = title.split(year_match.group(0))[0]
    # Cut off at quality indicator if present
    if quality_match and quality_match.group(0) in title:
        title = title.split(quality_match.group(0))[0]
    # Cut off at episode if present
    if episodes_or_part and episodes_or_part in title:
        title = title.split(episodes_or_part)[0]
        
    # Clean up trailing punctuation or open brackets from the title
    title = title.rstrip("()[]- :+=\\/").strip()
    if not title:
        title = "Untitled Movie"
        
    # Generate hashtags
    hashtags = []
    # Strip any special symbols/brackets from title before making it a hashtag
    clean_hashtag_title = re.sub(r'[^\w\s]', '', title)
    title_hashtag = "#" + "".join(clean_hashtag_title.split())
    if len(title_hashtag) > 1:
        hashtags.append(title_hashtag)
    for l in langs:
        if l != "Unknown":
            hashtags.append("#" + l)
    if year != "N/A":
        hashtags.append("#" + year)
    if quality != "HD":
        hashtags.append("#" + quality)
    if not hashtags:
        hashtags = ["#Movie"]
        
    return {
        "title": title,
        "year": year,
        "type": "Movie" if "S0" not in clean_text.upper() and "E0" not in clean_text.upper() else "Web Series",
        "country": "South Korea" if "korean" in clean_text.lower() or "kor" in clean_text.lower() else ("India" if "hindi" in clean_text.lower() or "bengali" in clean_text.lower() or "tamil" in clean_text.lower() else "Unknown"),
        "episodes_or_part": episodes_or_part,
        "quality": quality,
        "languages": langs,
        "genres": ["Entertainment"],
        "hashtags": hashtags
    }

# ================= OLLAMA LOCAL PARSER =================
def parse_caption_with_ollama(raw_caption: str) -> dict:
    url = "http://localhost:11434/api/generate"
    
    prompt = (
        f"Analyze the raw movie/series title: \"{raw_caption}\". "
        "Extract details and format your response strictly as a JSON object matching this structure: "
        "{\n"
        "  \"title\": \"Movie Title\",\n"
        "  \"year\": \"Release Year (or 'N/A')\",\n"
        "  \"type\": \"Movie or Web Series\",\n"
        "  \"country\": \"Country of production (e.g. India, South Korea)\",\n"
        "  \"episodes_or_part\": \"Season/Episode/Part details if present (e.g. S01 [E01-E06], Part 02) or null if none\",\n"
        "  \"quality\": \"Resolution (e.g. 720p, 1080p, HEVC)\",\n"
        "  \"languages\": [\"Audio languages found (e.g. Hindi, Korean)\"],\n"
        "  \"genres\": [\"Genres (e.g. Action, Comedy)\"],\n"
        "  \"hashtags\": [\"#Hashtags (e.g. #Hindi, #Action)\"]\n"
        "}"
    )
    
    data = {
        "model": "qwen3.6:latest",
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    try:
        import urllib.request
        import urllib.parse
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        # Timeout after 8 seconds to fail fast if Ollama is not running
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content_text = res_data.get("response", "").strip()
            result = json.loads(content_text)
            return result
    except Exception as e:
        print(f"[!] Ollama parse failed: {e}")
        return None

# ================= GEMINI CAPTION PARSER =================
async def verify_caption_with_gemini(raw_caption: str) -> dict:
    fallback_data = parse_caption_locally(raw_caption)

    if not gemini_enabled:
        print("[-] Gemini disabled. Trying local Ollama (Qwen) parser...")
        ollama_res = parse_caption_with_ollama(raw_caption)
        if ollama_res:
            print("[+] Successfully parsed using local Ollama!")
            return ollama_res
        return fallback_data

    # Structured prompt requesting Search Grounding verify & clean
    prompt = (
        f"You are a movie database verifier. Analyze the following raw movie/series title: \"{raw_caption}\"\n\n"
        "Instructions:\n"
        "1. Search Google using the movie name to check the official IMDb/Wikipedia title spelling and release year.\n"
        "2. Correct any typos or spelling mistakes in the title.\n"
        "3. Find the correct release year.\n"
        "4. Find the production country/country of origin of the movie or show.\n"
        "5. Identify if there are any specific episode, season, or part details mentioned in the raw title (e.g., S01, E01-E06, Part 2, S01E01) and capture them exactly.\n"
        "6. Determine if it is a 'Movie' or 'Web Series'.\n"
        "7. Respond ONLY with a JSON object matching this structure (do not include any conversational text or markdown codeblock wrapper):\n"
        "{\n"
        "  \"title\": \"Official Correct Movie Title\",\n"
        "  \"year\": \"Official Release Year (or 'N/A')\",\n"
        "  \"type\": \"Movie or Web Series\",\n"
        "  \"country\": \"Country of production (e.g. India, South Korea, United States)\",\n"
        "  \"episodes_or_part\": \"Season/Episode/Part details found in raw title (e.g. S01 [E01-E06], Part 02) or null if none\",\n"
        "  \"quality\": \"Extracted resolution/format (e.g. 720p, 1080p, HEVC)\",\n"
        "  \"languages\": [\"Extracted audio languages (e.g. Hindi, Korean, Dual Audio)\"],\n"
        "  \"genres\": [\"Official genres from search (e.g. Action, Drama)\"],\n"
        "  \"hashtags\": [\"#Hashtags (e.g. #Hindi, #Action, #Movie, #Year)\"]\n"
        "}"
    )

    retries = 3
    for attempt in range(retries):
        try:
            config = types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.0
            )
            
            # Request Gemini response
            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model='gemini-2.5-flash',
                contents=prompt,
                config=config
            )
            
            # Extract text content
            content_text = response.text.strip()
            
            # Strip markdown block wrappers if model added them
            if content_text.startswith("```"):
                content_text = re.sub(r"^```(?:json)?\n", "", content_text)
                content_text = re.sub(r"\n```$", "", content_text)
                content_text = content_text.strip()
                
            result = json.loads(content_text)
            return result
        except json.JSONDecodeError as je:
            print(f"[!] JSON parsing error from Gemini on attempt {attempt+1}: {je}")
            # Try to extract JSON manually
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        except Exception as e:
            # Handle rate limiting or other API issues
            if "429" in str(e) or "quota" in str(e).lower():
                wait_time = (attempt + 1) * 10
                print(f"[-] Gemini API Rate limit hit. Waiting for {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                print(f"[!] Gemini API call failed on attempt {attempt+1}: {e}")
                break
                
    print("[-] Gemini failed. Trying local Ollama (Qwen) parser...")
    try:
        ollama_res = await asyncio.to_thread(parse_caption_with_ollama, raw_caption)
        if ollama_res:
            print("[+] Successfully parsed using local Ollama!")
            return ollama_res
    except Exception as oe:
        print(f"[!] Local Ollama parser thread call failed: {oe}")

    print("[-] Falling back to local parsed caption.")
    return fallback_data

async def process_and_publish_post(app: Client, target_chat_id: int, original_msg, diskwala_link: str, reply_msg_id: int):
    # Check if original message is empty or missing media
    if not original_msg or getattr(original_msg, "empty", False):
        print(f"[-] Skipping message {reply_msg_id}: Original message was deleted.")
        mark_as_processed(reply_msg_id)
        return

    media_obj = original_msg.video or original_msg.document
    raw_caption = original_msg.caption or ""
    msg_text = original_msg.text or ""

    # Detect copyright infringement block texts
    is_copyrighted = False
    if "copyright infringement" in raw_caption.lower() or "couldn't be displayed" in raw_caption.lower():
        is_copyrighted = True
    if "copyright infringement" in msg_text.lower() or "couldn't be displayed" in msg_text.lower():
        is_copyrighted = True

    if is_copyrighted or not media_obj:
        print(f"[-] Skipping message {reply_msg_id}: Video was removed due to copyright infringement.")
        mark_as_processed(reply_msg_id)
        return

    if not raw_caption and media_obj and hasattr(media_obj, "file_name") and media_obj.file_name:
        # If caption is missing, use the video filename
        raw_caption = media_obj.file_name
        # Clean up filename dots/underscores for cleaner parsing
        raw_caption = raw_caption.replace(".", " ").replace("_", " ")

    print(f"[-] Parsing caption with Gemini: \"{raw_caption[:40]}...\"")
    
    # Clean/Verify data via Gemini
    info = await verify_caption_with_gemini(raw_caption)
    
    # Format tags/genres nicely
    langs_str = ", ".join(info.get("languages", ["Unknown"]))
    genres_str = ", ".join(info.get("genres", ["Entertainment"]))
    hashtags_str = " ".join(info.get("hashtags", ["#Movie"]))
    title_display = info.get("title", "Untitled Movie").upper()
    year_display = info.get("year", "N/A")
    quality_display = info.get("quality", "HD")
    type_display = info.get("type", "Movie")
    country_display = info.get("country", "Unknown")
    ep_part = info.get("episodes_or_part")

    # Combine title, year, and episode/parts on the first line
    title_line = f"🔥 {title_display}"
    if year_display and year_display != "N/A":
        title_line += f" ({year_display})"
    if ep_part:
        title_line += f" {ep_part.upper()}"

    # Retrieve raw original caption or filename for display
    display_original_caption = original_msg.caption or (media_obj.file_name if media_obj and hasattr(media_obj, "file_name") else "N/A")

    # Final post visual template
    caption_text = (
        f"Original Caption: {display_original_caption}\n\n"
        f"{title_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎥 Type: {type_display}\n"
        f"🌍 Country: {country_display}\n"
        f"🗣️ Language: {langs_str}\n"
        f"🎭 Genre: {genres_str}\n"
        f"📺 Quality: {quality_display}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 Watch Here 👇\n"
        f"{diskwala_link}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{hashtags_str}"
    )

    thumb_path = None
    enhanced_thumb_path = None
    media_obj = original_msg.video or original_msg.document

    # Attempt to download and enhance the thumbnail
    if media_obj and media_obj.thumbs:
        print("[-] Downloading video thumbnail...")
        try:
            os.makedirs("temp_thumbs", exist_ok=True)
            raw_path = f"temp_thumbs/raw_{original_msg.id}.jpg"
            
            # Pass the Thumbnail object directly to download cleanly
            thumb_path = await app.download_media(media_obj.thumbs[0], file_name=raw_path)
            
            if thumb_path and os.path.exists(thumb_path):
                enhanced_path = f"temp_thumbs/enhanced_{original_msg.id}.jpg"
                if enhance_thumbnail(thumb_path, enhanced_path):
                    enhanced_thumb_path = enhanced_path
        except FileReferenceExpired:
            print("[-] File reference expired on thumbnail download. Attempting refetch...")
            try:
                fresh_msg = await app.get_messages(original_msg.chat.id, original_msg.id)
                new_media = fresh_msg.video or fresh_msg.document
                if new_media and new_media.thumbs:
                    thumb_path = await app.download_media(new_media.thumbs[0], file_name=raw_path)
                    if thumb_path and os.path.exists(thumb_path):
                        enhanced_path = f"temp_thumbs/enhanced_{original_msg.id}.jpg"
                        if enhance_thumbnail(thumb_path, enhanced_path):
                            enhanced_thumb_path = enhanced_path
            except Exception as fe:
                print(f"[!] Fallback download failed: {fe}")
        except Exception as e:
            print(f"[!] Thumbnail processing failed: {e}")

    # Publish compiled post to target channel
    print("[-] Publishing post to organized channel...")
    try:
        if enhanced_thumb_path and os.path.exists(enhanced_thumb_path):
            await app.send_photo(
                chat_id=target_chat_id,
                photo=enhanced_thumb_path,
                caption=caption_text
            )
        else:
            await app.send_message(
                chat_id=target_chat_id,
                text=caption_text
            )
        print(f"[+] Post published successfully for message {original_msg.id}!")
        mark_as_processed(reply_msg_id)
    except Exception as e:
        print(f"[x] Failed to publish post: {e}")

    # Cleanup temp photos
    try:
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        if enhanced_thumb_path and os.path.exists(enhanced_thumb_path):
            os.remove(enhanced_thumb_path)
    except Exception:
        pass

# ================= RUN LOOP =================
async def run_organizer(app: Client, target_chat_id: int):
    try:
        while True:
            try:
                print("[-] Scanning DiskWala Bot chat history...")
                
                # Fetch recent messages from DiskWala bot
                diskwala_history = []
                async for msg in app.get_chat_history(TARGET_BOT_USERNAME):
                    # We are looking for messages sent by DiskWala (incoming replies)
                    # and that contain a download/watch URL
                    if msg.from_user and msg.from_user.is_bot:
                        text = msg.text or msg.caption or ""
                        # Regex match for DiskWala links
                        match = re.search(r'(https?://(?:www\.)?diskwala\.com/app/[a-zA-Z0-9]+)', text)
                        if match:
                            diskwala_history.append((msg, match.group(1)))

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
                            original_msg = await app.get_messages(TARGET_BOT_USERNAME, reply_to_id)
                            if original_msg and not original_msg.empty:
                                await process_and_publish_post(app, target_chat_id, original_msg, link, reply_msg.id)
                            else:
                                print(f"[!] Original video message {reply_to_id} not found or deleted from chat. Skipping.")
                                mark_as_processed(reply_msg.id)
                        except Exception as e:
                            print(f"[!] Error fetching original message: {e}")
                            
                        # Cooldown between compiling/publishing posts
                        sleep_seconds = random.randint(60, 120)
                        print(f"[-] Cooldown: sleeping for {sleep_seconds} seconds...")
                        await asyncio.sleep(sleep_seconds)
                else:
                    print("[+] No messages found in history scan.")
                    
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
