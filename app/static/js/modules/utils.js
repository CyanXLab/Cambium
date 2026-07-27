// Module: utils
// Auto-extracted from app.js
(function() {
// ===== Utilities =====
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function toast(message, type = 'info') {
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = message;
    el.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3200);
  }
  function getConversation(id) { return state.conversations.find(c => c.id === id); }
  function currentConversation() { return getConversation(state.currentId); }

  
})();
