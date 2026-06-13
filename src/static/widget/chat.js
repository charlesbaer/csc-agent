(function () {
  const SESSION_KEY = "csc-chat-session-id";
  const MAX_HISTORY_TURNS = 6;

  function getSessionId() {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  const sessionId = getSessionId();
  const messagesEl = document.getElementById("messages");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");

  let history = [];

  // Order matters: mailto: links, then bare emails, then bare/scheme URLs.
  const LINK_RE =
    /(mailto:[^\s<]+)|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})|((?:https?:\/\/)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:\/[^\s<]*)?)/g;

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function linkify(text) {
    return text.replace(LINK_RE, (match, mailto, email, url) => {
      if (mailto) {
        return `<a href="${mailto}" target="_blank" rel="noopener">${mailto.slice(7)}</a>`;
      }
      if (email) {
        return `<a href="mailto:${email}" target="_blank" rel="noopener">${email}</a>`;
      }
      const href = /^https?:\/\//i.test(url) ? url : `https://${url}`;
      return `<a href="${href}" target="_blank" rel="noopener">${url}</a>`;
    });
  }

  function formatMessage(text) {
    return linkify(escapeHtml(text)).replace(/\n/g, "<br>");
  }

  function addMessage(role, text) {
    const el = document.createElement("div");
    el.className = `msg ${role === "user" ? "user" : "bot"}`;
    el.innerHTML = formatMessage(text);
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "msg bot typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  async function sendMessage(text) {
    addMessage("user", text);
    history.push({ role: "user", content: text });
    inputEl.value = "";
    inputEl.disabled = true;
    sendBtn.disabled = true;

    const typingEl = showTyping();
    let reply = "Sorry, something went wrong. Please try again in a moment.";

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          history: history.slice(0, -1).slice(-MAX_HISTORY_TURNS),
        }),
      });
      const data = await res.json().catch(() => null);
      if (data && data.reply) {
        reply = data.reply;
      }
    } catch (err) {
      // Network error — fall back to the default message above.
    }

    typingEl.remove();
    addMessage("bot", reply);
    history.push({ role: "assistant", content: reply });
    if (history.length > MAX_HISTORY_TURNS * 2) {
      history = history.slice(-MAX_HISTORY_TURNS * 2);
    }

    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;
    sendMessage(text);
  });

  addMessage(
    "bot",
    "Hi! I'm the Community Swim Club virtual assistant. Ask me about pool hours, " +
      "membership, events, tennis courts, and more."
  );
})();
