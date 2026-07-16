# PRD: Raw Video Scraper & Forwarder Component

## 1. Component Overview
The **Scraper** component (`scraper/`) is a low-latency, state-preserving raw Telegram message copy engine. Its primary purpose is to mirror video files from a source chat folder list or channel into a secondary staging channel (`https://t.me/videos_down`), acting as the buffer/harvesting stage of the media pipeline.

---

## 2. Goals & User Requirements
*   **Source Folder Support**: Must be able to automatically accept a Telegram Chat Folder (addlist) link, scan its contents, and join all channels dynamically on startup.
*   **Video Extraction**: Must identify video files, including native Telegram video messages and document uploads matching video mime types (`video/*`) or common extensions (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`).
*   **Chronological Execution**: Must process source messages sequentially from **oldest to newest**.
*   **Interruption Recovery**: Must checkpoint its state to a local SQLite database after every message. If interrupted or crashed, it must resume exactly where it left off traceback-free.
*   **Duplicate Elimination by Caption**: After successfully forwarding a movie to the staging channel (`https://t.me/videos_down`), the bot checks the target channel's history for any existing posts with the same caption. If a duplicate caption is found, it automatically deletes the newly forwarded message.

---

## 3. Architecture & Code Map
*   **[forwarder.py](file:///c:/Users/ashwani/Desktop/demo/scraper/forwarder.py)**: The main execution script containing the scraper logic, folder invite processing, and rate-limiting handler.
*   **[requirements.txt](file:///c:/Users/ashwani/Desktop/demo/scraper/requirements.txt)**: Core package definitions (`pyrogram`, `tgcrypto`).
*   **[.env](file:///c:/Users/ashwani/Desktop/demo/scraper/.env)**: Environment configurations.
*   **[forwarder_progress.db](file:///c:/Users/ashwani/Desktop/demo/scraper/forwarder_progress.db)**: SQLite database tracking progress.
*   **[forwarder_session.session](file:///c:/Users/ashwani/Desktop/demo/scraper/forwarder_session.session)**: Pyrogram Telegram user session storage.

---

## 4. Key Functions & Logic

### A. Folder Invite Handler (`join_chat_folder`)
Invokes raw Telegram schema methods (`CheckChatlistInvite` and `JoinChatlistInvite`) to parse `CHAT_FOLDER_LINK` (`t.me/addlist/...`) and join any missing channels inside the folder.

### B. Chat ID Resolver (`resolve_chat_id`)
Translates alphanumeric strings (public usernames, invite links, private joins) and numeric IDs into standard Telegram 64-bit destination integers.

### C. Safe Forwarding & Rate Limiting (`safe_forward`)
Wraps message forwarding in an exception block. If a rate limit (`FloodWait`) occurs, it pauses execution for the requested cooldown duration plus a small buffer before retrying.

### D. Main Execution Loop
1. Resolves source and target chat IDs.
2. Checks DB checkpoint to resume scanning.
3. Downloads source channel history.
4. Filters and reverses sequence to maintain chronology.
5. Forwards video and writes progress state.

### E. Duplicate Deletion by Caption
After a video is successfully forwarded, the bot retrieves the forwarded message object. If it has a non-empty caption:
1. It queries the target channel's history (limit 100 messages).
2. It looks for any other message with the same caption (excluding the newly forwarded message's ID).
3. If a match is found, it immediately deletes the duplicate from the target channel `https://t.me/videos_down` using `app.delete_messages()`.

---

## 5. Database Schema (`forwarder_progress.db`)

### `sent_messages`
Tracks message IDs that have been successfully copied.
*   `msg_id` (`INTEGER PRIMARY KEY`): The message ID of the processed source file.

### `progress`
Stores execution checkpoints.
*   `key` (`TEXT PRIMARY KEY`): Config name (default `last_id`).
*   `last_msg_id` (`INTEGER`): ID of the latest processed source message.

---

## 6. Environment Configurations (`.env`)

| Variable | Description |
| :--- | :--- |
| `API_ID` | Telegram API ID from my.telegram.org. |
| `API_HASH` | Telegram API Hash from my.telegram.org. |
| `SESSION_NAME` | Session file basename. |
| `SOURCE_CHAT` | Channel ID, username, or invite link for source media. |
| `TARGET_CHAT` | Destination chat ID or username (usually `@videos_down`). |
| `CHAT_FOLDER_LINK` | Optional Telegram chat folder link to join dynamically. |
| `DB_FILE` | Progress DB filename (`forwarder_progress.db`). |

---

## 7. Execution Guide
To run the scraper:
```bash
cd scraper
python forwarder.py
```
To stop the scraper safely, send a single interrupt (`Ctrl+C`). It will checkpoint the last successfully forwarded video, stop cleanly without stack traces, and exit.
