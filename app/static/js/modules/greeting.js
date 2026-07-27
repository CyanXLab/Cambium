// Module: greeting
// Auto-extracted from app.js
(function() {
// ===== AI Greeting — Cambium speaks first =====
  async function loadAiGreeting() {
    const block = document.getElementById('aiGreetingBlock');
    const textEl = document.getElementById('aiGreetingText');
    const hintEl = document.getElementById('aiGreetingHint');
    if (!block || !textEl) return;
    try {
      const r = await fetch('/api/greeting').then(r => r.json());
      if (r.greeting && r.greeting.length > 5) {
        textEl.textContent = r.greeting;
        block.style.display = '';
        // Hide hint after 10 seconds
        if (hintEl) {
          setTimeout(() => { hintEl.style.opacity = '0'; }, 10000);
        }
      }
    } catch (e) {
      console.error('loadAiGreeting failed', e);
    }
  }

  
})();
