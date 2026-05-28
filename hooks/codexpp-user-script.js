(() => {
  const bridgeUrl = "http://127.0.0.1:57422/state";
  const source = "codexpp";
  const idleDelayMs = 2500;
  const minSendIntervalMs = 350;

  let lastSignature = "";
  let lastSentState = "";
  let lastSentAt = 0;
  let idleTimer = 0;
  let submittedRecentlyUntil = 0;

  function sendState(state) {
    const now = Date.now();
    if (state === lastSentState && now - lastSentAt < minSendIntervalMs) return;
    lastSentState = state;
    lastSentAt = now;
    const payload = { state, source };
    if (typeof window.__codexSessionDeleteBridge === "function") {
      window.__codexSessionDeleteBridge("/traffic-light/state", payload).catch(() => fallbackFetch(payload));
      return;
    }
    fallbackFetch(payload);
  }

  function fallbackFetch(payload) {
    fetch(bridgeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {});
  }

  function scheduleIdle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => sendState("idle"), idleDelayMs);
  }

  function markWorking() {
    sendState("working");
    scheduleIdle();
  }

  function markSubmitted() {
    submittedRecentlyUntil = Date.now() + 8000;
    markWorking();
  }

  function textSignature() {
    const root = document.querySelector(".thread-scroll-container") || document.querySelector("main") || document.body;
    return [
      location.href,
      root?.textContent?.length || 0,
      document.querySelectorAll("[data-message-author-role], [data-testid='conversation-turn'], main .prose").length,
    ].join(":");
  }

  function userMessageCount() {
    const root = document.querySelector(".thread-scroll-container") || document.querySelector("main") || document.body;
    return root.querySelectorAll([
      "[data-message-author-role='user']",
      "[data-testid='conversation-turn'][data-message-author-role='user']",
      "[data-testid='conversation-turn'] [data-message-author-role='user']",
      ".group.flex.w-full.flex-col.items-end.justify-end.gap-1 > [class*='bg-token-foreground/5']",
    ].join(", ")).length;
  }

  function observeConversationChanges() {
    const root = document.querySelector(".thread-scroll-container") || document.querySelector("main") || document.body;
    if (!root || root.__aiTrafficLightCodexPlusObserved) return;
    root.__aiTrafficLightCodexPlusObserved = true;
    lastSignature = textSignature();
    let lastUserMessageCount = userMessageCount();

    const observer = new MutationObserver(() => {
      const nextSignature = textSignature();
      if (nextSignature === lastSignature) return;
      lastSignature = nextSignature;

      const nextUserMessageCount = userMessageCount();
      const hasNewUserMessage = nextUserMessageCount > lastUserMessageCount;
      lastUserMessageCount = nextUserMessageCount;
      if (hasNewUserMessage || Date.now() < submittedRecentlyUntil) {
        markWorking();
      }
    });
    observer.observe(root, { childList: true, subtree: true, characterData: true });
  }

  function installSubmitListeners() {
    if (window.__aiTrafficLightCodexPlusListenersInstalled) return;
    window.__aiTrafficLightCodexPlusListenersInstalled = true;

    document.addEventListener("submit", () => markSubmitted(), true);
    document.addEventListener("click", (event) => {
      const target = event.target;
      const button = target?.closest?.("button");
      if (!button) return;
      const label = `${button.getAttribute("aria-label") || ""} ${button.textContent || ""}`.toLowerCase();
      if (/(send|发送|submit|继续|resume|run)/i.test(label)) markSubmitted();
    }, true);
  }

  function scan() {
    installSubmitListeners();
    observeConversationChanges();
  }

  scan();
  clearInterval(window.__aiTrafficLightCodexPlusScanTimer);
  window.__aiTrafficLightCodexPlusScanTimer = setInterval(scan, 1500);
})();
