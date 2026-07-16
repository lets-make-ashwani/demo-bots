import os
import sys
import io
import json
import asyncio
import subprocess
import psutil
import glob
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Configure UTF-8 encoding for standard output/error to prevent encoding issues on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', write_through=True)

app = FastAPI(title="Bot Control Panel Dashboard")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "panel", "logs")
STATIC_DIR = os.path.join(BASE_DIR, "panel", "static")
PIDS_DIR = os.path.join(BASE_DIR, "panel", "pids")

# Ensure required directories exist
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(PIDS_DIR, exist_ok=True)

# ─────────────────────────────────────────
# PID FILE HELPERS
# Persist PID to disk so process tracking survives dashboard restarts
# ─────────────────────────────────────────
def _pid_file(bot_name: str) -> str:
    return os.path.join(PIDS_DIR, f"{bot_name}.pid")

def _save_pid(bot_name: str, pid: int):
    with open(_pid_file(bot_name), "w") as f:
        f.write(str(pid))

def _load_pid(bot_name: str) -> int | None:
    path = _pid_file(bot_name)
    if os.path.exists(path):
        try:
            return int(open(path).read().strip())
        except (ValueError, IOError):
            pass
    return None

def _clear_pid(bot_name: str):
    path = _pid_file(bot_name)
    if os.path.exists(path):
        os.remove(path)

def _is_pid_alive(pid: int) -> bool:
    """Check if a PID is still a running Python process."""
    try:
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

def _kill_pid_tree(pid: int):
    """Kill a process and all its children recursively."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        print(f"[cleanup] Killed orphaned process tree rooted at PID {pid}")
    except psutil.NoSuchProcess:
        pass

def _clean_session_locks(bot_cwd: str):
    """
    Delete stale Pyrogram session lock files (.session-journal, .session-wal, .session-shm)
    that are left behind after a crash and cause 'database is locked' errors.
    """
    patterns = ["*.session-journal", "*.session-wal", "*.session-shm"]
    removed = []
    for pattern in patterns:
        for lock_file in glob.glob(os.path.join(bot_cwd, pattern)):
            try:
                os.remove(lock_file)
                removed.append(os.path.basename(lock_file))
            except OSError as e:
                print(f"[cleanup] Could not remove {lock_file}: {e}")
    if removed:
        print(f"[cleanup] Removed stale session lock files: {removed}")

# Central Registry for Bot configuration and active subprocess handles
BOTS_REGISTRY = {
    "scraper": {
        "name": "Scraper Bot",
        "description": "Monitors and forwards links from target channels",
        "script": os.path.join(BASE_DIR, "scraper", "forwarder.py"),
        "cwd": os.path.join(BASE_DIR, "scraper"),
        "log_file": os.path.join(LOGS_DIR, "scraper.log"),
        "process": None
    },
    "pipeline": {
        "name": "Pipeline Bot",
        "description": "Processes messages and classifies links",
        "script": os.path.join(BASE_DIR, "pipeline", "pipeline_bot.py"),
        "cwd": os.path.join(BASE_DIR, "pipeline"),
        "log_file": os.path.join(LOGS_DIR, "pipeline.log"),
        "process": None
    },
    "organizer": {
        "name": "Organizer Bot",
        "description": "Organizes captions and posts with thumbnails to target channel",
        "script": os.path.join(BASE_DIR, "organisepost", "organizer_bot.py"),
        "cwd": os.path.join(BASE_DIR, "organisepost"),
        "log_file": os.path.join(LOGS_DIR, "organizer.log"),
        "process": None
    }
}

# Mount static files folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>index.html not created yet in static directory</h2>")

@app.get("/api/status")
def get_status():
    status_data = {}
    for key, bot in BOTS_REGISTRY.items():
        proc = bot["process"]
        is_running = False
        pid = None
        memory_usage = "0.0 MB"
        cpu_usage = "0.0%"
        
        # ── Check 1: in-memory process handle ──
        if proc and proc.poll() is None:
            is_running = True
            pid = proc.pid
        else:
            bot["process"] = None
            # ── Check 2: PID file (catches processes that outlived a dashboard restart) ──
            saved_pid = _load_pid(key)
            if saved_pid and _is_pid_alive(saved_pid):
                is_running = True
                pid = saved_pid
            else:
                _clear_pid(key)  # Tidy up stale PID file

        if is_running and pid:
            try:
                p = psutil.Process(pid)
                mem = p.memory_info().rss / (1024 * 1024)
                memory_usage = f"{mem:.1f} MB"
                cpu = p.cpu_percent(interval=None)
                cpu_usage = f"{cpu:.1f}%"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                is_running = False
                pid = None
                _clear_pid(key)

        status_data[key] = {
            "name": bot["name"],
            "description": bot["description"],
            "running": is_running,
            "pid": pid,
            "memory": memory_usage,
            "cpu": cpu_usage,
            "log_size": f"{os.path.getsize(bot['log_file']) / 1024:.1f} KB" if os.path.exists(bot['log_file']) else "0.0 KB"
        }
    return status_data

@app.post("/api/start/{bot_name}")
def start_bot(bot_name: str):
    if bot_name not in BOTS_REGISTRY:
        raise HTTPException(status_code=404, detail="Bot not found")
        
    bot = BOTS_REGISTRY[bot_name]
    proc = bot["process"]
    
    # ── Guard 1: In-memory process handle still alive ──
    if proc and proc.poll() is None:
        return {"status": "already_running", "pid": proc.pid}

    # ── Guard 2: PID file check — catches orphans after dashboard restart ──
    # If the dashboard was reloaded/restarted, bot["process"] is None but the
    # old OS-level process may still be running and holding the session lock.
    saved_pid = _load_pid(bot_name)
    if saved_pid and _is_pid_alive(saved_pid):
        print(f"[!] {bot_name} already running as orphan PID {saved_pid}. Returning existing.")
        return {"status": "already_running", "pid": saved_pid}

    # ── Cleanup: Kill any dead/zombie orphan and remove its PID file ──
    if saved_pid and not _is_pid_alive(saved_pid):
        print(f"[cleanup] Stale PID {saved_pid} for {bot_name} — removing.")
        _clear_pid(bot_name)

    # ── Cleanup: Remove stale Pyrogram session lock files ──
    # This prevents 'sqlite3.OperationalError: database is locked' on restart
    _clean_session_locks(bot["cwd"])

    # Open the log file in write mode to clear past sessions, write unbuffered python logs
    try:
        log_fd = open(bot["log_file"], "w", encoding="utf-8")
        
        # Start python in unbuffered mode (-u)
        cmd = [sys.executable, "-u", bot["script"]]
        
        # Create a new subprocess group to avoid breaking our server on interrupts
        if sys.platform == "win32":
            p = subprocess.Popen(
                cmd,
                cwd=bot["cwd"],
                stdout=log_fd,
                stderr=log_fd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            p = subprocess.Popen(
                cmd,
                cwd=bot["cwd"],
                stdout=log_fd,
                stderr=log_fd
            )
            
        bot["process"] = p
        _save_pid(bot_name, p.pid)  # Persist PID to disk for crash recovery
        print(f"[+] Started {bot_name} successfully with PID {p.pid}")
        return {"status": "started", "pid": p.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start bot: {e}")

@app.post("/api/stop/{bot_name}")
def stop_bot(bot_name: str):
    if bot_name not in BOTS_REGISTRY:
        raise HTTPException(status_code=404, detail="Bot not found")
        
    bot = BOTS_REGISTRY[bot_name]
    proc = bot["process"]
    
    # Also check the PID file for orphans that outlived a dashboard restart
    saved_pid = _load_pid(bot_name)
    
    if (not proc or proc.poll() is not None) and not (saved_pid and _is_pid_alive(saved_pid)):
        bot["process"] = None
        _clear_pid(bot_name)
        return {"status": "not_running"}

    # Determine the target PID — prefer in-memory handle, fall back to saved PID file
    target_pid = proc.pid if (proc and proc.poll() is None) else saved_pid

    try:
        print(f"[*] Stopping {bot_name} (PID: {target_pid})...")
        _kill_pid_tree(target_pid)
            
        if proc:
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
                
        bot["process"] = None
        _clear_pid(bot_name)  # Remove PID file after successful stop
        print(f"[+] Stopped {bot_name} cleanly.")
        return {"status": "stopped", "pid": target_pid}
    except Exception as e:
        _clear_pid(bot_name)
        raise HTTPException(status_code=500, detail=f"Failed to stop bot: {e}")

@app.websocket("/ws/logs/{bot_name}")
async def websocket_logs(websocket: WebSocket, bot_name: str):
    if bot_name not in BOTS_REGISTRY:
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    bot = BOTS_REGISTRY[bot_name]
    log_file = bot["log_file"]

    # Ensure file exists
    if not os.path.exists(log_file):
        open(log_file, "a", encoding="utf-8").close()

    try:
        # Open in read mode and read last 100 lines first
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            # Read last 100 lines to display immediately
            lines = f.readlines()
            last_lines = lines[-100:]
            for line in last_lines:
                await websocket.send_text(line)

            # Move cursor to end of file to tail new inputs
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    await websocket.send_text(line)
                else:
                    await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        print(f"[-] Client disconnected from logs: {bot_name}")
    except Exception as e:
        print(f"[!] WebSocket error for {bot_name}: {e}")

if __name__ == "__main__":
    import uvicorn
    # Start FastAPI server on port 8000
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=True)
