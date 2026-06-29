// ==========================================================================
// EduAgent — Animations JS
// Handles: splash removal, button ripples, stat counters, typing indicator
// ==========================================================================

// ---------- Splash screen ----------
(function removeSplash() {
  const splash = document.getElementById("edu-splash");
  if (!splash) return;
  // CSS animation fades it out over 2.8s; remove from DOM after that
  setTimeout(() => {
    splash.style.display = "none";
  }, 2900);
})();

// ---------- Button ripple effect ----------
document.addEventListener("click", function (e) {
  const btn = e.target.closest(".btn");
  if (!btn) return;

  const ripple = document.createElement("span");
  ripple.className = "btn-ripple";

  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  ripple.style.width = ripple.style.height = size + "px";
  ripple.style.left = e.clientX - rect.left - size / 2 + "px";
  ripple.style.top = e.clientY - rect.top - size / 2 + "px";

  btn.appendChild(ripple);
  setTimeout(() => ripple.remove(), 600);
});

// ---------- Animated stat counters (dashboard) ----------
function animateCounter(el, target, duration) {
  const start = performance.now();
  const startVal = 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(startVal + (target - startVal) * eased);

    // Preserve one decimal place if target has it (e.g. 98.6)
    if (String(target).includes(".")) {
      el.textContent = (startVal + (target - startVal) * eased).toFixed(1);
    } else {
      el.textContent = current.toLocaleString();
    }

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.classList.add("counting");
      setTimeout(() => el.classList.remove("counting"), 400);
    }
  }
  requestAnimationFrame(update);
}

document.addEventListener("DOMContentLoaded", () => {
  // Find all .stat-value elements with a data-target attribute
  // (we'll add these in the dashboard template)
  document.querySelectorAll(".stat-value[data-target]").forEach((el) => {
    const raw = el.dataset.target;
    const target = parseFloat(raw);
    if (!isNaN(target)) {
      // Stagger based on element order
      const idx = [...document.querySelectorAll(".stat-value[data-target]")].indexOf(el);
      setTimeout(() => animateCounter(el, target, 1200), idx * 150);
    }
  });
});

// ---------- Typing indicator for chat ----------
// Called by app.js before/after a chat request

window.showTypingIndicator = function () {
  const messages = document.getElementById("chat-messages");
  if (!messages) return;

  // Remove any existing one first
  const existing = document.getElementById("typing-indicator-msg");
  if (existing) existing.remove();

  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  wrap.id = "typing-indicator-msg";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar thinking";
  avatar.textContent = "🤖";

  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.innerHTML = `
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
  `;

  wrap.appendChild(avatar);
  wrap.appendChild(indicator);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
};

window.hideTypingIndicator = function () {
  const el = document.getElementById("typing-indicator-msg");
  if (el) el.remove();
};

// ---------- Intersection Observer: animate cards when scrolled into view ----------
(function observeCards() {
  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.animationPlayState = "running";
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll(".card").forEach((card) => {
    card.style.animationPlayState = "paused";
    observer.observe(card);
  });
})();
