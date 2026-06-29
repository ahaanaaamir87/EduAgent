// ---------- AI Chat ----------
function initChat() {
  const form = document.getElementById("chat-form");
  if (!form) return;

  const input = document.getElementById("chat-input");
  const messages = document.getElementById("chat-messages");
  const sendBtn = document.getElementById("chat-send-btn");
  const ragToggle = document.getElementById("rag-toggle");

  function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }
  scrollToBottom();

  function appendMessage(role, text, badge) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = role === "user" ? "🧑" : "🤖";
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>") + (badge ? `<div style="margin-top:6px"><span class="tag-pill">📚 Used your documents</span></div>` : "");
    wrap.appendChild(avatar);
    wrap.appendChild(bubble);
    messages.appendChild(wrap);
    scrollToBottom();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function setPrompt(text) {
    input.value = text;
    input.focus();
  }
  document.querySelectorAll(".chip[data-prompt]").forEach((chip) => {
    chip.addEventListener("click", () => setPrompt(chip.dataset.prompt));
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    appendMessage("user", text, false);
    input.value = "";
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span>';

    // Show animated typing indicator while waiting for AI
    if (window.showTypingIndicator) window.showTypingIndicator();

    const fd = new FormData();
    fd.append("message", text);
    fd.append("use_rag", ragToggle && ragToggle.checked ? "true" : "false");

    try {
      const res = await fetch("/chat/send", { method: "POST", body: fd });
      const data = await res.json();
      if (window.hideTypingIndicator) window.hideTypingIndicator();
      if (data.error) {
        appendMessage("assistant", "Sorry, something went wrong: " + data.error, false);
      } else {
        appendMessage("assistant", data.reply, data.used_rag);
      }
    } catch (err) {
      if (window.hideTypingIndicator) window.hideTypingIndicator();
      appendMessage("assistant", "Network error. Please check your connection and try again.", false);
    } finally {
      sendBtn.disabled = false;
      sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" width="18" height="18"><path d="M22 2 11 13" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M22 2 15 22l-4-9-9-4 20-7Z" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>';
    }
  });

  // Document upload
  const uploadInput = document.getElementById("doc-upload-input");
  const docList = document.getElementById("doc-list");
  if (uploadInput) {
    uploadInput.addEventListener("change", async () => {
      const file = uploadInput.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);

      const li = document.createElement("div");
      li.className = "doc-item";
      li.innerHTML = `<span class="spinner"></span><span class="name">Processing ${file.name}...</span>`;
      docList.prepend(li);

      try {
        const res = await fetch("/chat/upload", { method: "POST", body: fd });
        const data = await res.json();
        if (data.error) {
          li.innerHTML = `<span>⚠️</span><span class="name">${data.error}</span>`;
        } else {
          li.innerHTML = `<span>📄</span><span class="name">${data.filename}</span><span style="color:var(--text-muted)">${data.num_chunks} chunks</span>`;
          if (ragToggle) ragToggle.checked = true;
        }
      } catch (err) {
        li.innerHTML = `<span>⚠️</span><span class="name">Upload failed</span>`;
      }
      uploadInput.value = "";
    });
  }
}

// ---------- Flashcards ----------
function initFlashcards() {
  document.querySelectorAll(".flip-card").forEach((card) => {
    card.addEventListener("click", () => card.classList.toggle("flipped"));
  });
}

// ---------- Quiz ----------
let _quizSelections = {};
let _quizSubmitBound = false;

function initQuiz() {
  const quizForm = document.getElementById("quiz-take-form");
  if (!quizForm) return;

  const selections = _quizSelections;

  document.querySelectorAll(".quiz-option").forEach((opt) => {
    opt.addEventListener("click", () => {
      const qIdx = opt.dataset.qIdx;
      const oIdx = parseInt(opt.dataset.oIdx, 10);
      selections[qIdx] = oIdx;
      document.querySelectorAll(`.quiz-option[data-q-idx="${qIdx}"]`).forEach((el) => el.classList.remove("selected"));
      opt.classList.add("selected");
    });
  });

  if (_quizSubmitBound) return;
  _quizSubmitBound = true;

  quizForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById("quiz-submit-btn");
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Grading...';

    const fd = new FormData();
    fd.append("answers", JSON.stringify(selections));
    const quizId = quizForm.dataset.quizId;

    try {
      const res = await fetch(`/quiz/${quizId}/submit`, { method: "POST", body: fd });
      const data = await res.json();
      renderQuizResults(data);
    } catch (err) {
      alert("Could not submit quiz. Please try again.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit Answers";
    }
  });

  function renderQuizResults(data) {
    data.results.forEach((r, i) => {
      document.querySelectorAll(`.quiz-option[data-q-idx="${i}"]`).forEach((el) => {
        const oIdx = parseInt(el.dataset.oIdx, 10);
        if (oIdx === r.correct_index) el.classList.add("correct");
        else if (oIdx === r.chosen_index && !r.is_correct) el.classList.add("incorrect");
      });
    });

    const banner = document.getElementById("quiz-score-banner");
    banner.style.display = "block";
    banner.innerHTML = `
      <div class="pct">${data.score_pct}%</div>
      <div style="color:var(--text-secondary); font-size:13.5px; margin-top:4px;">You got ${data.correct} out of ${data.total} correct</div>
    `;
    banner.scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("quiz-submit-btn").style.display = "none";
  }
}



// =====================================================================
// EduAgent — Gryffindor / HP Theme Animations
// =====================================================================

// --- Splash Screen ---
function initSplash() {
  const splash = document.getElementById("edu-splash");
  if (!splash) return;
  // Hide after progress bar finishes (1.2s animation + 0.6s delay + 0.4s fade = ~2.2s total)
  setTimeout(() => {
    splash.classList.add("hiding");
    setTimeout(() => { splash.style.display = "none"; }, 420);
  }, 1800);
}

// --- Floating Magic Particles ---
function initMagicParticles() {
  const symbols = ["✦", "★", "✧", "⚡", "✦", "✦", "✧"];
  const count = 12;
  for (let i = 0; i < count; i++) {
    const el = document.createElement("div");
    el.className = "magic-particle";
    el.textContent = symbols[Math.floor(Math.random() * symbols.length)];
    el.style.left = Math.random() * 100 + "vw";
    el.style.top = (100 + Math.random() * 20) + "vh";
    el.style.fontSize = (8 + Math.random() * 10) + "px";
    el.style.animationDuration = (8 + Math.random() * 16) + "s";
    el.style.animationDelay = (Math.random() * 10) + "s";
    el.style.opacity = 0;
    document.body.appendChild(el);
  }
}

// --- Stat counter animation (dashboard) ---
function initStatCounters() {
  document.querySelectorAll(".stat-value").forEach(el => {
    const raw = el.textContent.trim();
    const num = parseFloat(raw.replace(/[^0-9.]/g, ""));
    if (isNaN(num) || num === 0) return;
    const isFloat = raw.includes(".");
    const decimals = isFloat ? (raw.split(".")[1] || "").length : 0;
    const duration = 1200;
    const steps = 40;
    const increment = num / steps;
    let current = 0;
    let step = 0;
    el.classList.add("counting");
    const timer = setInterval(() => {
      step++;
      current = Math.min(current + increment, num);
      el.textContent = isFloat ? current.toFixed(decimals) : Math.floor(current).toLocaleString();
      if (step >= steps) {
        clearInterval(timer);
        el.textContent = isFloat ? num.toFixed(decimals) : num.toLocaleString();
      }
    }, duration / steps);
  });
}

// --- Button ripple effect ---
function initRippleEffects() {
  document.querySelectorAll(".btn").forEach(btn => {
    btn.addEventListener("click", function(e) {
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const ripple = document.createElement("span");
      ripple.className = "ripple-wave";
      const size = Math.max(rect.width, rect.height);
      ripple.style.cssText = `width:${size}px;height:${size}px;left:${x - size/2}px;top:${y - size/2}px;`;
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 700);
    });
  });
}

// --- HP cursor trail (optional subtle gold sparks on mousemove) ---
function initCursorTrail() {
  let lastTime = 0;
  document.addEventListener("mousemove", (e) => {
    const now = Date.now();
    if (now - lastTime < 80) return; // throttle
    lastTime = now;
    const spark = document.createElement("div");
    spark.style.cssText = `
      position:fixed; left:${e.clientX}px; top:${e.clientY}px;
      width:4px; height:4px; border-radius:50%;
      background:#D4AF37; pointer-events:none; z-index:9998;
      transform:translate(-50%,-50%);
      animation: ripple 0.6s linear forwards;
      opacity:0.7;
    `;
    document.body.appendChild(spark);
    setTimeout(() => spark.remove(), 650);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSplash();
  initMagicParticles();
  initStatCounters();
  initRippleEffects();
  initCursorTrail();
  initChat();
  initFlashcards();
  initQuiz();
});
