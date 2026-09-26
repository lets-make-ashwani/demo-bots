import os
import time
import sqlite3
import asyncio

# Fix event loop initialization for Python 3.12+ / 3.14+ where get_event_loop() raises RuntimeError
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from dotenv import load_dotenv

# Monkeypatch Pyrogram's internal ID limits to support newer 64-bit Telegram IDs
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000
pyrogram.utils.MIN_CHAT_ID = -99999999999999
pyrogram.utils.MAX_USER_ID = 99999999999999

from pyrogram import Client
from pyrogram.errors import FloodWait, UserAlreadyParticipant
from pyrogram.raw.functions.chatlists import CheckChatlistInvite, JoinChatlistInvite
from pyrogram.raw.types.chatlists import ChatlistInvite, ChatlistInviteAlready

# Load environment variables
load_dotenv()

# API Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "forwarder_session")

# Chat Configurations
SOURCE_CHAT = (os.getenv("SOURCE_CHAT_SCRAPER") or os.getenv("SOURCE_CHAT", "-1003733985584")).strip()
TARGET_CHAT = (os.getenv("TARGET_CHAT_SCRAPER") or os.getenv("TARGET_CHAT", "-1003224058374")).strip()
CHAT_FOLDER_LINK = os.getenv("CHAT_FOLDER_LINK", "").strip()
DB_FILE = os.getenv("DB_FILE", "forwarder_progress.db")
SCAN_COOLDOWN = int(os.getenv("COOLDOWN_SCAN_INTERVAL", "600"))


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

def is_already_sent(db_conn, msg_id):
    try:
        return db_conn["scraper_sent"].find_one({"_id": msg_id}) is not None
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return False

def mark_as_sent(db_conn, msg_id):
    try:
        db_conn["scraper_sent"].update_one({"_id": msg_id}, {"$set": {"msg_id": msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")

def get_last_processed_id(db_conn):
    try:
        row = db_conn["scraper_progress"].find_one({"_id": "last_id"})
        return row["last_msg_id"] if row else 0
    except Exception as e:
        print(f"[ERROR] Database read error: {e}")
        return 0

def save_last_processed_id(db_conn, msg_id):
    try:
        db_conn["scraper_progress"].update_one({"_id": "last_id"}, {"$set": {"last_msg_id": msg_id}}, upsert=True)
    except Exception as e:
        print(f"[ERROR] Database write error: {e}")


# ================= CHAT LIST / FOLDER JOINER =================
async def join_chat_folder(app: Client, link: str) -> bool:
    """
    Checks and joins all channels in a Telegram Chat Folder (addlist) link.
    """
    if "t.me/addlist/" not in link:
        print("[!] Warning: Provided CHAT_FOLDER_LINK is not a valid chat list link.")
        return False

    slug = link.split("t.me/addlist/")[-1].split("/")[0].strip()
    print(f"\n[*] Checking Telegram Chat Folder: {link}")

    try:
        invite = await app.invoke(CheckChatlistInvite(slug=slug))
        peers_to_join = []
        folder_title = "Folder"

        if isinstance(invite, ChatlistInvite):
            peers_to_join = invite.peers
            folder_title = invite.title
            print(f"[-] Folder '{folder_title}' contains {len(peers_to_join)} channels.")
        elif isinstance(invite, ChatlistInviteAlready):
            peers_to_join = invite.missing_peers
            print(f"[-] Folder is already added. Found {len(peers_to_join)} new/missing channels to join.")

        if peers_to_join:
            print("[-] Joining channels inside the folder...")
            await app.invoke(JoinChatlistInvite(slug=slug, peers=peers_to_join))
            print(f"[+] Successfully joined all {len(peers_to_join)} channels from the folder '{folder_title}'!")
        else:
            print(f"[+] Already joined all channels in the folder '{folder_title}'.")

        return True
    except Exception as e:
        print(f"[x] Failed to join folder list channels: {e}")
        return False

# ================= CHAT RESOLVER =================
async def resolve_chat_id(app: Client, chat_value: str) -> int:
    """
    Resolves a string/integer chat value to its Telegram numerical ID.
    Supports: Numeric IDs, usernames, and invite links.
    """
    chat_value = chat_value.strip()

    # If it is a private invite link
    if "t.me/+" in chat_value or chat_value.startswith("+"):
        try:
            chat = await app.join_chat(chat_value)
            print(f"[+] Joined private chat: '{chat.title}' ({chat.id})")
            return chat.id
        except UserAlreadyParticipant:
            pass
        except Exception as e:
            print(f"[!] Failed to join invite link: {e}")

    # Remove t.me domain if user pasted a link
    if chat_value.startswith("https://t.me/"):
        chat_value = chat_value.replace("https://t.me/", "").split("/")[0]

    # If numeric ID (e.g. -1004350704894)
    if (chat_value.startswith("-") and chat_value[1:].isdigit()) or chat_value.isdigit():
        target_int = int(chat_value)
        try:
            chat = await app.get_chat(target_int)
            return chat.id
        except Exception:
            # Pyrogram hasn't cached this channel's peer access hash yet on this session.
            # Load dialogs to populate Pyrogram's peer cache.
            print(f"[-] Populating peer cache from dialogs for ID {target_int}...")
            try:
                async for dialog in app.get_dialogs():
                    if dialog.chat and dialog.chat.id == target_int:
                        return dialog.chat.id
            except Exception as de:
                print(f"[!] Error iterating dialogs: {de}")

            # Try get_chat again after dialogs loop
            try:
                chat = await app.get_chat(target_int)
                return chat.id
            except Exception as e:
                raise ValueError(
                    f"[x] Could not resolve chat ID '{chat_value}'. Reason: {e}\n"
                    f"Please verify your account is a member of this channel/group."
                )

    # Prefix public usernames
    if not chat_value.startswith("@"):
        chat_value = "@" + chat_value

    try:
        chat = await app.get_chat(chat_value)
        return chat.id
    except Exception as e:
        raise ValueError(
            f"[x] Could not resolve chat '{chat_value}'. Reason: {e}\n"
            f"Please verify you have joined the channel or that the username/invite link is correct."
        )

# ================= SAFE FORWARD =================
async def safe_forward(app, source_id, target_id, msg_id):
    while True:
        try:
            result = await app.forward_messages(
                chat_id=target_id,
                from_chat_id=source_id,
                message_ids=msg_id
            )
            return result
        except FloodWait as e:
            wait_time = e.value + 2
            print(f"[-] FloodWait encountered. Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[x] Failed to forward message {msg_id}: {e}")
            return None

# ================= MAIN PIPELINE =================
async def main():
    if not API_ID or not API_HASH:
        print("[x] Error: API_ID and API_HASH are missing from the environment/'.env' file.")
        return

    conn = init_db()
    SESSION_STRING = os.getenv("SESSION_STRING_SCRAPER") or os.getenv("SESSION_STRING")
    if SESSION_STRING:
        app = Client("session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH, no_updates=True)
    else:
        app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, no_updates=True)


    async with app:
        print("[+] Logged in successfully!")

        # If a chat folder invite link is provided, join it first
        if CHAT_FOLDER_LINK:
            await join_chat_folder(app, CHAT_FOLDER_LINK)
        
        print(f"\n[*] Resolving chats...")
        try:
            source_id = await resolve_chat_id(app, SOURCE_CHAT)
            target_id = await resolve_chat_id(app, TARGET_CHAT)
            print(f"[-] Source Chat resolved: {source_id}")
            print(f"[-] Target Chat resolved: {target_id}")
        except Exception as e:
            print(e)
            return

        try:
            while True:
                try:
                    last_processed_id = get_last_processed_id(conn)
                    print(f"[-] Resuming scan from source chat ({source_id}) message ID > {last_processed_id}")

                    # Fetch messages newer than the last processed message ID
                    messages = []
                    async for msg in app.get_chat_history(source_id):
                        if msg.id <= last_processed_id:
                            break
                        messages.append(msg)

                    if not messages:
                        print("[+] No new messages found to process.")
                    else:
                        # Reverse order to process from OLDEST to NEWEST (chronological)
                        messages.reverse()
                        print(f"[-] Found {len(messages)} new messages in history to scan.")

                        forwarded_count = 0
                        for msg in messages:
                            msg_id = msg.id

                            # Detect native video message OR video files uploaded as documents
                            is_video = False
                            if msg.video:
                                is_video = True
                            elif msg.document and (
                                (msg.document.mime_type or "").startswith("video/") or
                                (msg.document.file_name or "").lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v'))
                            ):
                                is_video = True

                            # If it's not a video, skip it
                            if not is_video:
                                save_last_processed_id(conn, msg_id)
                                continue

                            # Skip if already forwarded
                            if is_already_sent(conn, msg_id):
                                save_last_processed_id(conn, msg_id)
                                continue

                            print(f"[-] Forwarding video/document message {msg_id}...")
                            forwarded_msg = await safe_forward(app, source_id, target_id, msg_id)
                            if forwarded_msg:
                                mark_as_sent(conn, msg_id)
                                forwarded_count += 1
                                
                                actual_msg = forwarded_msg
                                if isinstance(forwarded_msg, list):
                                    actual_msg = forwarded_msg[0] if forwarded_msg else None
                                
                                if actual_msg:
                                    print(f"[+] Successfully forwarded message {msg_id} (New Message ID: {actual_msg.id})")
                                    
                                    # Remove duplicate by caption in target channel (videos_down)
                                    caption = (actual_msg.caption or "").strip()
                                    if caption:
                                        async for target_msg in app.get_chat_history(target_id, limit=100):
                                            if target_msg.id == actual_msg.id:
                                                continue
                                            target_caption = (target_msg.caption or "").strip()
                                            if target_caption == caption:
                                                print(f"[!] Duplicate caption found in target channel: '{caption[:50]}...'. Deleting newly forwarded message {actual_msg.id}...")
                                                try:
                                                    await app.delete_messages(target_id, actual_msg.id)
                                                except Exception as de:
                                                    print(f"[x] Failed to delete duplicate message: {de}")
                                                break
                                else:
                                    print(f"[+] Successfully forwarded message {msg_id}")
                            
                            save_last_processed_id(conn, msg_id)
                            await asyncio.sleep(1.5)
                        
                        print(f"[+] Done! Total videos forwarded this run: {forwarded_count}")
                except Exception as cycle_error:
                    print(f"[x] Error during scan cycle: {cycle_error}. Retrying in 30 seconds...")
                    await asyncio.sleep(30)
                    continue

                print(f"[-] Cooldown: sleeping for {SCAN_COOLDOWN} seconds before the next scan cycle...")
                await asyncio.sleep(SCAN_COOLDOWN)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[!] Process stopped by user (Ctrl+C). Saving progress and exiting gracefully...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Script terminated by user.")

