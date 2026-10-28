/**
 * ApexAI - Chat Interface Controller
 * Handles real-time messaging, local markdown rendering, 
 * Web Speech API (STT & TTS), drawer interactions, and quick prompts.
 */

let isAudioReadingEnabled = false;
let speechRecognizer = null;
let isRecordingVoice = false;

document.addEventListener("DOMContentLoaded", () => {
    initSpeechRecognition();
    scrollChatToBottom();
});

/* ==========================================================================
   Chat Submission & API Integration
   ========================================================================== */

function handleChatSubmit(event) {
    if (event) event.preventDefault();
    
    const input = document.getElementById("userMessageInput");
    const message = input.value.trim();
    if (!message) return;

    // 1. Render User Message in stream
    appendUserMessage(message);
    input.value = "";
    autoResizeTextarea(input);

    // 2. Display Typing Indicator
    showTypingIndicator();
    scrollChatToBottom();

    // 3. Dispatch to Flask API
    fetch("/api/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server returned status ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        hideTypingIndicator();
        if (data.success) {
            appendAssistantMessage(data.answer, data.source, data.intent);
            if (isAudioReadingEnabled) {
                speakText(data.answer);
            }
        } else {
            appendAssistantMessage("⚠️ Error: " + (data.error || "Unable to process query."), "Error", "error");
        }
        scrollChatToBottom();
    })
    .catch(err => {
        hideTypingIndicator();
        console.error("Chat API error:", err);
        appendAssistantMessage("⚠️ Connection error: Failed to reach college assistant service. Please check your connection.", "Network Error", "error");
        scrollChatToBottom();
    });
}

function handleTextareaKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleChatSubmit();
    }
}

function autoResizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
}

function sendQuickPrompt(promptText) {
    const input = document.getElementById("userMessageInput");
    input.value = promptText;
    autoResizeTextarea(input);
    handleChatSubmit();
}

/* ==========================================================================
   DOM Message Rendering
   ========================================================================== */

function insertMessageInChat(element) {
    const container = document.getElementById("chatMessages");
    const anchor = document.getElementById("chatScrollAnchor");
    if (anchor && anchor.parentNode === container) {
        container.insertBefore(element, anchor);
    } else {
        container.appendChild(element);
    }
}

function appendUserMessage(text) {
    const timeStr = getCurrentTime();

    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message user-message";
    msgDiv.innerHTML = `
        <div class="message-avatar">
            <div class="user-icon">You</div>
        </div>
        <div class="message-content-wrapper">
            <div class="message-header">
                <span class="message-sender">You</span>
                <span class="message-time">${timeStr}</span>
            </div>
            <div class="message-bubble">
                <p>${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    insertMessageInChat(msgDiv);
}

function appendAssistantMessage(rawText, sourceStr, intent) {
    const timeStr = getCurrentTime();

    let tagClass = "rag";
    if (intent === "timetable") tagClass = "timetable";
    else if (intent === "attendance") tagClass = "attendance";
    else if (intent === "greeting") tagClass = "system";

    const formattedHtml = formatMarkdown(rawText);

    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message assistant-message";
    msgDiv.innerHTML = `
        <div class="message-avatar">
            <div class="bot-icon">AI</div>
        </div>
        <div class="message-content-wrapper">
            <div class="message-header">
                <span class="message-sender">Apex Assistant</span>
                <span class="message-time">${timeStr}</span>
                <span class="source-tag ${tagClass}">${escapeHtml(sourceStr || "College Assistant")}</span>
            </div>
            <div class="message-bubble">
                ${formattedHtml}
            </div>
            <div class="message-actions">
                <button type="button" class="msg-action-btn" onclick="readMessageAudio(this)" title="Read aloud">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
                    <span>Speak</span>
                </button>
                <button type="button" class="msg-action-btn" onclick="copyMessageText(this)" title="Copy text">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    <span>Copy</span>
                </button>
            </div>
        </div>
    `;
    insertMessageInChat(msgDiv);
}

function showTypingIndicator() {
    if (document.getElementById("typingIndicator")) return;

    const indDiv = document.createElement("div");
    indDiv.id = "typingIndicator";
    indDiv.className = "chat-message assistant-message";
    indDiv.innerHTML = `
        <div class="message-avatar">
            <div class="bot-icon">AI</div>
        </div>
        <div class="message-content-wrapper">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    insertMessageInChat(indDiv);
}

function hideTypingIndicator() {
    const el = document.getElementById("typingIndicator");
    if (el) el.remove();
}

function scrollChatToBottom(smooth = true) {
    const container = document.getElementById("chatMessages");
    const anchor = document.getElementById("chatScrollAnchor");
    if (!container) return;

    // 1. Direct scroll
    container.scrollTop = container.scrollHeight;

    // 2. Scroll into view on anchor
    if (anchor) {
        try {
            anchor.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" });
        } catch (e) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // 3. Multi-phase timeouts to ensure layout recalculations are scrolled
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });

    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
        if (anchor) {
            try { anchor.scrollIntoView({ behavior: "smooth", block: "end" }); } catch(e){}
        }
    }, 60);

    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 180);
}

function clearConversation() {
    if (!confirm("Are you sure you want to clear your conversation?")) return;
    const container = document.getElementById("chatMessages");
    const welcome = document.getElementById("welcome-msg");
    const anchor = document.getElementById("chatScrollAnchor");
    container.innerHTML = "";
    if (welcome) container.appendChild(welcome);
    if (anchor) container.appendChild(anchor);
    scrollChatToBottom(false);
}

/* ==========================================================================
   Lightweight Client-Side Markdown Parser
   ========================================================================== */

function formatMarkdown(text) {
    if (!text) return "";
    let safe = text;

    // Code blocks ```code```
    safe = safe.replace(/```([\s\S]*?)```/g, (match, code) => {
        return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
    });

    // Inline code `code`
    safe = safe.replace(/`([^`]+)`/g, (match, code) => {
        return `<code>${escapeHtml(code)}</code>`;
    });

    // Bold **text**
    safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Italic *text*
    safe = safe.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // Horizontal Rule ---
    safe = safe.replace(/^---$/gm, "<hr>");

    // Split lines for list and paragraph processing
    const lines = safe.split("\n");
    let inList = false;
    let listType = ""; // 'ul' or 'ol'
    let result = [];

    for (let line of lines) {
        const trimmed = line.trim();

        // Unordered list item (- or *)
        const ulMatch = trimmed.match(/^[-*]\s+(.*)$/);
        // Ordered list item (1. 2.)
        const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);

        if (ulMatch) {
            if (!inList || listType !== "ul") {
                if (inList) result.push(`</${listType}>`);
                result.push("<ul>");
                inList = true;
                listType = "ul";
            }
            result.push(`<li>${ulMatch[1]}</li>`);
        } else if (olMatch) {
            if (!inList || listType !== "ol") {
                if (inList) result.push(`</${listType}>`);
                result.push("<ol>");
                inList = true;
                listType = "ol";
            }
            result.push(`<li>${olMatch[2]}</li>`);
        } else {
            if (inList) {
                result.push(`</${listType}>`);
                inList = false;
                listType = "";
            }
            if (trimmed.length > 0) {
                // If line starts with a block tag like <pre> or <hr>, don't wrap in <p>
                if (trimmed.startsWith("<pre>") || trimmed.startsWith("<hr>")) {
                    result.push(trimmed);
                } else {
                    result.push(`<p>${trimmed}</p>`);
                }
            }
        }
    }

    if (inList) {
        result.push(`</${listType}>`);
    }

    return result.join("\n");
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getCurrentTime() {
    const d = new Date();
    let hours = d.getHours();
    let minutes = d.getMinutes();
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? "0" + minutes : minutes;
    return `${hours}:${minutes} ${ampm}`;
}

/* ==========================================================================
   Voice Input & Speech Synthesis
   ========================================================================== */

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        const btn = document.getElementById("voice-record-btn");
        if (btn) btn.title = "Voice recognition not supported in this browser";
        return;
    }

    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = false;
    speechRecognizer.lang = "en-US";

    speechRecognizer.onstart = () => {
        isRecordingVoice = true;
        const btn = document.getElementById("voice-record-btn");
        if (btn) btn.classList.add("recording");
    };

    speechRecognizer.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById("userMessageInput");
        if (input) {
            input.value = transcript;
            autoResizeTextarea(input);
            handleChatSubmit();
        }
    };

    speechRecognizer.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        stopVoiceRecording();
    };

    speechRecognizer.onend = () => {
        stopVoiceRecording();
    };
}

function toggleVoiceInput() {
    if (!speechRecognizer) {
        alert("Speech Recognition is not supported by your current browser. Try Chrome or Edge.");
        return;
    }

    if (isRecordingVoice) {
        speechRecognizer.stop();
        stopVoiceRecording();
    } else {
        try {
            speechRecognizer.start();
        } catch (e) {
            console.error("Speech recognition start failed:", e);
        }
    }
}

function stopVoiceRecording() {
    isRecordingVoice = false;
    const btn = document.getElementById("voice-record-btn");
    if (btn) btn.classList.remove("recording");
}

function toggleAudioReading() {
    isAudioReadingEnabled = !isAudioReadingEnabled;
    const btn = document.getElementById("tts-toggle-btn");
    const label = document.getElementById("tts-label");

    if (isAudioReadingEnabled) {
        btn.classList.add("active");
        label.innerText = "Voice: ON";
    } else {
        btn.classList.remove("active");
        label.innerText = "Voice: OFF";
        if (window.speechSynthesis) window.speechSynthesis.cancel();
    }
}

function speakText(rawText) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    // Clean markdown symbols for cleaner pronunciation
    const plain = rawText
        .replace(/[*_#`~>-]/g, " ")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .trim();

    const utterance = new SpeechSynthesisUtterance(plain);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}

function readMessageAudio(btn) {
    const bubble = btn.closest(".message-content-wrapper").querySelector(".message-bubble");
    if (bubble) {
        speakText(bubble.innerText);
    }
}

function copyMessageText(btn) {
    const bubble = btn.closest(".message-content-wrapper").querySelector(".message-bubble");
    if (!bubble) return;

    navigator.clipboard.writeText(bubble.innerText).then(() => {
        const span = btn.querySelector("span");
        const original = span.innerText;
        span.innerText = "Copied!";
        setTimeout(() => span.innerText = original, 1800);
    }).catch(err => {
        console.error("Failed to copy:", err);
    });
}

/* ==========================================================================
   Side Drawer Handling
   ========================================================================== */

function openDrawer(tabName) {
    const drawer = document.getElementById("sideDrawer");
    const backdrop = document.getElementById("drawerBackdrop");
    if (!drawer || !backdrop) return;

    switchDrawerTab(tabName);
    drawer.classList.add("active");
    backdrop.classList.add("active");
}

function closeDrawer() {
    const drawer = document.getElementById("sideDrawer");
    const backdrop = document.getElementById("drawerBackdrop");
    if (drawer) drawer.classList.remove("active");
    if (backdrop) backdrop.classList.remove("active");
}

function switchDrawerTab(tabName) {
    const timetableTab = document.getElementById("drawer-tab-timetable");
    const attendanceTab = document.getElementById("drawer-tab-attendance");
    const paneTimetable = document.getElementById("pane-timetable");
    const paneAttendance = document.getElementById("pane-attendance");

    if (tabName === "attendance") {
        if (timetableTab) timetableTab.classList.remove("active");
        if (attendanceTab) attendanceTab.classList.add("active");
        if (paneTimetable) paneTimetable.classList.remove("active");
        if (paneAttendance) paneAttendance.classList.add("active");
    } else {
        if (attendanceTab) attendanceTab.classList.remove("active");
        if (timetableTab) timetableTab.classList.add("active");
        if (paneAttendance) paneAttendance.classList.remove("active");
        if (paneTimetable) paneTimetable.classList.add("active");
    }
}
