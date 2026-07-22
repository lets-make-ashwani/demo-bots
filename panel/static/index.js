// Dictionary to store active WebSocket connections for logs
const sockets = {
    scraper: null,
    pipeline: null,
    organizer: null,
    ai_assistant: null
};

// Periodic polling interval handle
let statusInterval = null;

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
    updateStatus();
    // Poll status every 2 seconds
    statusInterval = setInterval(updateStatus, 2000);
});

// Update Status indicators and metric values
async function updateStatus() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) throw new Error("Status query failed");
        
        const data = await response.json();
        
        for (const [botKey, bot] of Object.entries(data)) {
            const card = document.getElementById(`card-${botKey}`);
            const badge = card.querySelector(".status-badge");
            const dot = badge.querySelector(".status-dot");
            const text = badge.querySelector(".status-text");
            
            const btnStart = card.querySelector(".btn-start");
            const btnStop = card.querySelector(".btn-stop");
            
            // Metrics
            document.getElementById(`mem-${botKey}`).textContent = bot.memory;
            document.getElementById(`cpu-${botKey}`).textContent = bot.cpu;
            document.getElementById(`log-${botKey}`).textContent = bot.log_size;

            if (bot.running) {
                // Set badge status to Running
                badge.className = "status-badge running";
                text.textContent = "Running";
                
                // Toggle Button states
                btnStart.disabled = true;
                btnStop.disabled = false;
                
                // Glow card border
                card.classList.add("active-glow");
                
                // Auto-connect log stream if not active
                if (!sockets[botKey]) {
                    connectLogs(botKey);
                }
            } else {
                // Set badge status to Stopped
                badge.className = "status-badge stopped";
                text.textContent = "Stopped";
                
                // Toggle Button states
                btnStart.disabled = false;
                btnStop.disabled = true;
                
                // Remove glowing borders
                card.classList.remove("active-glow");
                
                // Disconnect log stream if active
                if (sockets[botKey]) {
                    sockets[botKey].close();
                    sockets[botKey] = null;
                }
            }
        }
    } catch (err) {
        console.error("[x] Dashboard status sync failed:", err);
    }
}

// Start Bot command call
async function startBot(botName) {
    appendLog(botName, "[SYSTEM] Starting bot process on server...", "system");
    try {
        const response = await fetch(`/api/start/${botName}`, { method: "POST" });
        const resData = await response.json();
        if (response.ok) {
            appendLog(botName, `[SYSTEM] Subprocess started successfully (PID: ${resData.pid})`, "success");
            updateStatus();
        } else {
            appendLog(botName, `[ERROR] Failed to start: ${resData.detail || "Server error"}`, "error");
        }
    } catch (err) {
        appendLog(botName, `[ERROR] Connection error: ${err.message}`, "error");
    }
}

// Stop Bot command call
async function stopBot(botName) {
    appendLog(botName, "[SYSTEM] Stopping bot process...", "system");
    try {
        const response = await fetch(`/api/stop/${botName}`, { method: "POST" });
        const resData = await response.json();
        if (response.ok) {
            appendLog(botName, `[SYSTEM] Subprocess stopped successfully.`, "success");
            updateStatus();
        } else {
            appendLog(botName, `[ERROR] Failed to stop: ${resData.detail || "Server error"}`, "error");
        }
    } catch (err) {
        appendLog(botName, `[ERROR] Connection error: ${err.message}`, "error");
    }
}

// WebSocket connection to stream terminal logs
function connectLogs(botName) {
    if (sockets[botName]) {
        sockets[botName].close();
    }
    
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/logs/${botName}`;
    
    const ws = new WebSocket(wsUrl);
    sockets[botName] = ws;
    
    ws.onopen = () => {
        appendLog(botName, "[SYSTEM] Real-time log stream established successfully.", "success");
    };
    
    ws.onmessage = (event) => {
        appendLog(botName, event.data);
    };
    
    ws.onclose = () => {
        appendLog(botName, "[SYSTEM] Log stream closed.", "system");
        sockets[botName] = null;
    };
    
    ws.onerror = (err) => {
        appendLog(botName, `[SYSTEM LOG ERROR] Stream connection failure.`, "error");
        sockets[botName] = null;
    };
}

// Helper to append logs to custom terminal viewports
function appendLog(botName, message, type = "") {
    const terminal = document.getElementById(`term-${botName}`);
    if (!terminal) return;
    
    const logLine = document.createElement("div");
    logLine.className = "log-line";
    if (type) {
        logLine.classList.add(type);
    }
    
    // Auto-detect errors and successes from text contents if type is normal
    if (!type) {
        const lowerMsg = message.toLowerCase();
        if (lowerMsg.includes("[+]") || lowerMsg.includes("success")) {
            logLine.classList.add("success");
        } else if (lowerMsg.includes("[!]") || lowerMsg.includes("[x]") || lowerMsg.includes("error") || lowerMsg.includes("failed")) {
            logLine.classList.add("error");
        }
    }
    
    logLine.textContent = message.trimEnd();
    terminal.appendChild(logLine);
    
    // Auto-scroll terminal viewport to bottom
    terminal.scrollTop = terminal.scrollHeight;
    
    // Performance guard: limit output log history to max 400 lines
    while (terminal.childElementCount > 400) {
        terminal.removeChild(terminal.firstChild);
    }
}

// Clear logs on UI terminal
function clearTerminal(botName) {
    const terminal = document.getElementById(`term-${botName}`);
    if (terminal) {
        terminal.innerHTML = '<div class="log-line system">Terminal cleared. Waiting for logs...</div>';
    }
}
