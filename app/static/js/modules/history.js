// Module: history
// Auto-extracted from app.js
(function() {
// ===== History rendering =====
  function renderHistory() {
    el.historyList.innerHTML = '';
    // Update badge count
    const badge = document.getElementById('historyBadge');
    const convCount = state.conversations.filter(c => !c.temporary).length;
    if (badge) badge.textContent = convCount;
    if (state.conversations.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.textContent = '暂无历史对话';
      el.historyList.appendChild(empty);
      return;
    }
    // Don't show temporary conversations in sidebar
    const sorted = [...state.conversations].filter(c => !c.temporary).sort((a,b) => b.updatedAt - a.updatedAt);
    const groups = { '今天': [], '昨天': [], '前 7 天': [], '更早': [] };
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;
    const weekStart = todayStart - 7 * 86400000;
    sorted.forEach(c => {
      if (c.updatedAt >= todayStart) groups['今天'].push(c);
      else if (c.updatedAt >= yesterdayStart) groups['昨天'].push(c);
      else if (c.updatedAt >= weekStart) groups['前 7 天'].push(c);
      else groups['更早'].push(c);
    });
    for (const [title, convs] of Object.entries(groups)) {
      if (convs.length === 0) continue;
      const t = document.createElement('div');
      t.className = 'history-section-title';
      t.textContent = title;
      el.historyList.appendChild(t);
      convs.forEach(c => {
        const item = document.createElement('div');
        item.className = 'history-item' + (c.id === state.currentId ? ' active' : '');
        item.dataset.id = c.id;
        item.innerHTML = `
          <span class="h-title">${escapeHtml(c.title || '新对话')}</span>
          <span class="h-actions">
            <button class="h-action" data-action="rename" title="重命名"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
            <button class="h-action" data-action="delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>
          </span>`;
        item.addEventListener('click', (e) => {
          if (e.target.closest('.h-action')) return;
          switchConversation(c.id);
        });
        item.querySelector('[data-action="rename"]').addEventListener('click', (e) => {
          e.stopPropagation();
          // Inline rename: replace title with input
          const titleEl = item.querySelector('.h-title');
          const oldTitle = c.title;
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'h-rename-input';
          input.value = oldTitle;
          input.style.cssText = 'flex:1;background:transparent;border:none;outline:none;color:var(--text-primary);font-size:14px;font-family:inherit;padding:0;min-width:0;';
          titleEl.replaceWith(input);
          input.focus();
          input.select();
          const finish = (save) => {
            const newTitle = input.value.trim();
            if (save && newTitle && newTitle !== oldTitle) {
              c.title = newTitle;
              saveState();
            }
            renderHistory();
          };
          input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
            else if (ev.key === 'Escape') { finish(false); }
          });
          input.addEventListener('blur', () => finish(true));
        });
        item.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
          e.stopPropagation();
          // Inline delete confirmation: replace item with confirm UI
          const origHTML = item.innerHTML;
          item.innerHTML = `
            <span class="h-title" style="color:var(--text-muted)">删除「${escapeHtml(c.title)}」？</span>
            <span class="h-actions" style="display:flex">
              <button class="h-action" data-action="confirm-delete" style="color:#ef4444" title="确认删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></button>
              <button class="h-action" data-action="cancel-delete" title="取消"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
            </span>`;
          item.querySelector('[data-action="confirm-delete"]').addEventListener('click', (ev) => {
            ev.stopPropagation();
            deleteConversation(c.id);
          });
          item.querySelector('[data-action="cancel-delete"]').addEventListener('click', (ev) => {
            ev.stopPropagation();
            renderHistory();
          });
        });
        el.historyList.appendChild(item);
      });
    }
  }

  function deleteConversation(id) {
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.currentId === id) state.currentId = null;
    saveState();
    renderHistory();
    renderConversation();
    // Cascade delete chat vectors on server
    if (state.settings.chat_vectors_enabled) {
      fetch('/api/conversations/delete', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id }),
      }).catch(e => console.warn('delete conv vectors failed', e));
    }
  }

  function switchConversation(id) {
    state.currentId = id;
    saveState();
    renderHistory();
    renderConversation();
    if (window.innerWidth < 769) toggleSidebarMobile(false);
  }

  function newConversation(initialPrompt) {
    // Just switch to a fresh empty state — DON'T create sidebar entry yet.
    // The conversation will be created and shown in sidebar only when first message is sent.
    // Preserve temporary mode (switching conversations doesn't exit temporary mode).
    state.currentId = null;
    renderHistory();
    renderConversation();
    if (initialPrompt) { el.composerInput.value = initialPrompt; autoResize(); }
    el.composerInput.focus();
    if (window.innerWidth < 769) toggleSidebarMobile(false);
  }

  
})();
