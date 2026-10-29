/**
 * app.js — Frontend logic for the Insurance Claims RAG Web UI.
 *
 * Handles:
 *  - Chat message sending/receiving via /api/chat
 *  - Health check on load
 *  - Strategy toggle (hybrid / vector)
 *  - Quick-question buttons & welcome cards
 *  - Source citation expand/collapse
 *  - Auto-resize textarea
 *  - Mobile sidebar toggle
 */

(function () {
    "use strict";

    // ── DOM references ───────────────────────────────────────────────────
    const chatForm = document.getElementById("chatForm");
    const questionInput = document.getElementById("questionInput");
    const sendBtn = document.getElementById("sendBtn");
    const chatArea = document.getElementById("chatArea");
    const welcomeScreen = document.getElementById("welcomeScreen");
    const messagesContainer = document.getElementById("messagesContainer");
    const clearChat = document.getElementById("clearChat");
    const strategyBadge = document.getElementById("strategyBadge");
    const statusIndicator = document.getElementById("statusIndicator");
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");

    let currentStrategy = "hybrid";
    let isLoading = false;

    // ── Initialize ───────────────────────────────────────────────────────

    function init() {
        checkHealth();
        setupStrategyToggle();
        setupQuickQuestions();
        setupWelcomeCards();
        setupTextareaAutoResize();
        setupMobileSidebar();

        chatForm.addEventListener("submit", handleSubmit);
        clearChat.addEventListener("click", handleClear);
    }

    // ── Health check ─────────────────────────────────────────────────────

    async function checkHealth() {
        const dot = statusIndicator.querySelector(".status-dot");
        const text = statusIndicator.querySelector(".status-text");

        try {
            const res = await fetch("/api/health");
            const data = await res.json();

            if (data.status === "ok" && data.groq_key_set) {
                dot.className = "status-dot online";
                text.textContent = "System online";
            } else if (!data.groq_key_set) {
                dot.className = "status-dot offline";
                text.textContent = "API key not set";
            }
        } catch {
            dot.className = "status-dot offline";
            text.textContent = "Server offline";
        }
    }

    // ── Strategy toggle ──────────────────────────────────────────────────

    function setupStrategyToggle() {
        const buttons = document.querySelectorAll(".strategy-btn");
        buttons.forEach((btn) => {
            btn.addEventListener("click", () => {
                buttons.forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                currentStrategy = btn.dataset.strategy;
                strategyBadge.textContent =
                    currentStrategy === "hybrid" ? "Hybrid Search" : "Vector Only";
            });
        });
    }

    // ── Quick questions (sidebar) ────────────────────────────────────────

    function setupQuickQuestions() {
        document.querySelectorAll(".quick-q-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const q = btn.dataset.question;
                questionInput.value = q;
                autoResize(questionInput);
                closeMobileSidebar();
                submitQuestion(q);
            });
        });
    }

    // ── Welcome cards ────────────────────────────────────────────────────

    function setupWelcomeCards() {
        document.querySelectorAll(".welcome-card").forEach((card) => {
            card.addEventListener("click", () => {
                const q = card.dataset.question;
                questionInput.value = q;
                autoResize(questionInput);
                submitQuestion(q);
            });
        });
    }

    // ── Textarea auto-resize ─────────────────────────────────────────────

    function setupTextareaAutoResize() {
        questionInput.addEventListener("input", () => autoResize(questionInput));
        questionInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event("submit"));
            }
        });
    }

    function autoResize(el) {
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }

    // ── Mobile sidebar ───────────────────────────────────────────────────

    function setupMobileSidebar() {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
            toggleOverlay(sidebar.classList.contains("open"));
        });
    }

    function closeMobileSidebar() {
        sidebar.classList.remove("open");
        toggleOverlay(false);
    }

    function toggleOverlay(show) {
        let overlay = document.querySelector(".sidebar-overlay");
        if (show && !overlay) {
            overlay = document.createElement("div");
            overlay.className = "sidebar-overlay visible";
            overlay.addEventListener("click", closeMobileSidebar);
            document.body.appendChild(overlay);
        } else if (!show && overlay) {
            overlay.remove();
        }
    }

    // ── Form submit ──────────────────────────────────────────────────────

    function handleSubmit(e) {
        e.preventDefault();
        const q = questionInput.value.trim();
        if (!q || isLoading) return;
        submitQuestion(q);
    }

    // ── Clear chat ───────────────────────────────────────────────────────

    function handleClear() {
        messagesContainer.innerHTML = "";
        welcomeScreen.style.display = "flex";
    }

    // ── Submit question ──────────────────────────────────────────────────

    async function submitQuestion(question) {
        if (isLoading) return;

        // Hide welcome screen
        welcomeScreen.style.display = "none";

        // Show user message
        appendUserMessage(question);

        // Clear input
        questionInput.value = "";
        questionInput.style.height = "auto";

        // Show loading
        const loadingEl = appendLoadingMessage();
        setLoading(true);

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: question,
                    strategy: currentStrategy,
                }),
            });

            const data = await res.json();

            // Remove loading
            loadingEl.remove();

            if (data.error) {
                appendErrorMessage(data.error);
            } else {
                appendAssistantMessage(data);
            }
        } catch (err) {
            loadingEl.remove();
            appendErrorMessage("Failed to connect to server. Is it running?");
        } finally {
            setLoading(false);
        }
    }

    // ── Set loading state ────────────────────────────────────────────────

    function setLoading(loading) {
        isLoading = loading;
        sendBtn.disabled = loading;
        questionInput.disabled = loading;
    }

    // ── Append user message ──────────────────────────────────────────────

    function appendUserMessage(text) {
        const html = `
            <div class="message user">
                <div class="message-avatar">👤</div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">You</span>
                        <span class="message-time">${formatTime()}</span>
                    </div>
                    <div class="message-body">${escapeHtml(text)}</div>
                </div>
            </div>
        `;
        messagesContainer.insertAdjacentHTML("beforeend", html);
        scrollToBottom();
    }

    // ── Append loading message ───────────────────────────────────────────

    function appendLoadingMessage() {
        const div = document.createElement("div");
        div.className = "message assistant";
        div.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">Assistant</span>
                </div>
                <div class="message-body">
                    <div class="loading-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(div);
        scrollToBottom();
        return div;
    }

    // ── Append assistant message ─────────────────────────────────────────

    function appendAssistantMessage(data) {
        const msgId = "msg-" + Date.now();

        let answerHtml;
        if (data.is_refusal) {
            answerHtml = `<div class="message-refusal">${escapeHtml(data.answer)}</div>`;
        } else {
            answerHtml = formatAnswer(data.answer);
        }

        let sourcesHtml = "";
        if (data.sources && data.sources.length > 0) {
            const sourceItems = data.sources
                .map(
                    (s) => `
                <div class="source-item">
                    <span class="source-rank">#${s.rank}</span>
                    <div class="source-details">
                        <div class="source-meta">
                            <span class="source-meta-tag">📄 ${escapeHtml(s.form_number)}</span>
                            <span class="source-meta-tag">§ ${escapeHtml(s.clause_id)}</span>
                            <span class="source-meta-tag">⚡ ${s.score.toFixed(4)}</span>
                        </div>
                        <div class="source-snippet">${escapeHtml(s.snippet)}</div>
                    </div>
                </div>
            `
                )
                .join("");

            sourcesHtml = `
                <div class="message-sources">
                    <button class="sources-toggle" onclick="toggleSources('${msgId}')">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                        ${data.sources.length} source${data.sources.length !== 1 ? "s" : ""} cited
                    </button>
                    <div class="sources-list" id="${msgId}-sources">
                        ${sourceItems}
                    </div>
                </div>
            `;
        }

        let timingHtml = "";
        if (data.timing) {
            timingHtml = `
                <div class="message-timing">
                    <span class="timing-tag">🔍 retrieval: ${data.timing.retrieval_ms}ms</span>
                    <span class="timing-tag">💬 generation: ${data.timing.generation_ms}ms</span>
                    <span class="timing-tag">⏱ total: ${data.timing.total_ms}ms</span>
                    <span class="timing-tag">📡 ${data.strategy_used}</span>
                </div>
            `;
        }

        const html = `
            <div class="message assistant" id="${msgId}">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">Assistant</span>
                        <span class="message-time">${formatTime()}</span>
                    </div>
                    <div class="message-body">${answerHtml}</div>
                    ${sourcesHtml}
                    ${timingHtml}
                </div>
            </div>
        `;
        messagesContainer.insertAdjacentHTML("beforeend", html);
        scrollToBottom();
    }

    // ── Append error message ─────────────────────────────────────────────

    function appendErrorMessage(error) {
        const html = `
            <div class="message assistant">
                <div class="message-avatar">⚠️</div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">System Error</span>
                        <span class="message-time">${formatTime()}</span>
                    </div>
                    <div class="message-body">
                        <div class="message-refusal">${escapeHtml(error)}</div>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.insertAdjacentHTML("beforeend", html);
        scrollToBottom();
    }

    // ── Toggle sources ───────────────────────────────────────────────────

    window.toggleSources = function (msgId) {
        const list = document.getElementById(msgId + "-sources");
        const toggle = list.previousElementSibling;
        list.classList.toggle("visible");
        toggle.classList.toggle("open");
    };

    // ── Format answer text ───────────────────────────────────────────────

    function formatAnswer(text) {
        // Convert line breaks to paragraphs
        const paragraphs = text.split(/\n\n+/);
        let html = paragraphs
            .map((p) => {
                p = p.trim();
                if (!p) return "";

                // Highlight [SOURCE: ...] citations
                p = p.replace(
                    /\[SOURCE:\s*([^\]]+)\]/g,
                    '<span style="font-family: var(--font-mono); font-size: 0.75em; color: var(--primary-300); background: rgba(99, 102, 241, 0.1); padding: 1px 6px; border-radius: 4px; border: 1px solid rgba(99, 102, 241, 0.15);">📎 $1</span>'
                );

                // Bold text
                p = p.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

                return `<p>${p}</p>`;
            })
            .join("");
        return html;
    }

    // ── Utilities ────────────────────────────────────────────────────────

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime() {
        return new Date().toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatArea.scrollTop = chatArea.scrollHeight;
        });
    }

    // ── Start ────────────────────────────────────────────────────────────
    init();
})();
