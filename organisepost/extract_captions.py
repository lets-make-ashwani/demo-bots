import os
import sys
import asyncio
import subprocess

# Ensure required libraries are installed
try:
    import pandas as pd
except ImportError:
    print("[-] pandas is not installed. Installing it...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
    import pandas as pd

try:
    import openpyxl
except ImportError:
    print("[-] openpyxl is not installed. Installing it...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl

try:
    from pyrogram import Client
    from pyrogram.errors import FloodWait
except ImportError:
    print("[-] pyrogram is not installed. Installing it...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyrogram tgcrypto"])
    from pyrogram import Client
    from pyrogram.errors import FloodWait

from dotenv import load_dotenv

# Monkeypatch Pyrogram's internal ID limits to support newer 64-bit Telegram IDs
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999
pyrogram.utils.MAX_CHANNEL_ID = -1000000000000
pyrogram.utils.MIN_CHAT_ID = -99999999999999
pyrogram.utils.MAX_USER_ID = 99999999999999

# Load environment variables
load_dotenv(override=True)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "organizer_session")
TARGET_CHANNEL = "videos_down"  # Target channel username/ID

async def extract_captions():
    if not API_ID or not API_HASH:
        print("[x] Error: API_ID and API_HASH are missing from the .env file.")
        return

    print("==================================================")
    print(f"[*] Extracting captions from @{TARGET_CHANNEL}")
    print("==================================================")

    # Initialize Pyrogram client with no_updates=True
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, no_updates=True)

    data = []
    
    async with app:
        print("[+] Logged in successfully!")
        
        # Resolve the chat
        try:
            chat = await app.get_chat(TARGET_CHANNEL)
            print(f"[+] Target Channel Resolved: '{chat.title}' (ID: {chat.id})")
        except Exception as e:
            print(f"[x] Error: Could not resolve channel '{TARGET_CHANNEL}'. Reason: {e}")
            return

        print("[-] Fetching history. This may take a while depending on the channel size...")
        count = 0
        
        try:
            async for message in app.get_chat_history(chat.id):
                # Retrieve the original caption or text
                caption = message.caption or message.text or ""
                
                # We only want messages with captions/text
                data.append({
                    "Message ID": message.id,
                    "Original Caption": caption
                })
                
                count += 1
                if count % 100 == 0:
                    print(f"[-] Fetched {count} messages...")
                    
        except FloodWait as e:
            print(f"[!] Hit FloodWait. Sleeping for {e.value} seconds...")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"[x] Error during message retrieval: {e}")
            
    print(f"[+] Finished fetching history. Total messages processed: {len(data)}")
    
    # Save to Excel
    output_file = "videos_down_captions.xlsx"
    print(f"[-] Saving to Excel sheet: {output_file}...")
    try:
        df = pd.DataFrame(data)
        # Ensure only the two requested columns are kept and order is correct
        df = df[["Message ID", "Original Caption"]]
        
        # Write to Excel
        df.to_excel(output_file, index=False)
        print(f"[+] Successfully saved {len(data)} items to {output_file}!")
    except Exception as e:
        print(f"[x] Failed to save Excel file: {e}")

if __name__ == "__main__":
    asyncio.run(extract_captions())
