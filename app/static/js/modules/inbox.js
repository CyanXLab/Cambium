// Module: inbox
// Auto-extracted from app.js
(function() {
// ===== Inbox view =====
  let inboxFilter = 'all';
  async function loadInboxList() {
    if (!el.inboxListContainer) return;
    try {
      const params = new URLSearchParams();
      if (inboxFilter !== 'all') params.set('status', inboxFilter);
      params.set('limit', '100');
      const resp = await fetch('/api/inbox/items?' + params.toString());
      const data = await resp.json();
      const items = data.items || [];
      if (items.length === 0) {
        el.inboxListContainer.innerHTML = '<div class="inbox-empty">Inbox 是空的。点击 "新建捕获" 添加任何东西。</div>';
        return;
      }
      el.inboxListContainer.innerHTML = items.map(it => {
        const ts = new Date(it.created_at * 1000).toLocaleString('zh-CN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
        const statusLabel = it.status === 'pending' ? '待处理' : (it.status === 'processed' ? '已处理→' + (it.destination || '') : (it.status === 'archived' ? '已归档' : it.status));
        return `<div class="inbox-item" data-id="${it.id}">
          <span class="inbox-item-type">${it.type}</span>
          <div class="inbox-item-body">
            ${it.title ? `<div class="inbox-item-title">${escapeHtml(it.title)}</div>` : ''}
            <div class="inbox-item-content">${escapeHtml(it.content.slice(0, 300))}${it.content.length > 300 ? '…' : ''}</div>
            <div class="inbox-item-meta">
              <span class="inbox-item-status ${it.status}">${statusLabel}</span>
              <span>${ts}</span>
              ${it.suggested_destination ? `<span class="inbox-item-suggested">建议: ${it.suggested_destination}</span>` : ''}
            </div>
          </div>
          <div class="inbox-item-actions">
            ${it.status === 'pending' ? `<button data-action="process" data-id="${it.id}" data-dest="${it.suggested_destination || 'note'}">处理</button>` : ''}
            ${it.status !== 'archived' ? `<button data-action="archive" data-id="${it.id}">归档</button>` : ''}
            <button data-action="delete" data-id="${it.id}" class="danger">删除</button>
          </div>
        </div>`;
      }).join('');
      // Wire action buttons
      el.inboxListContainer.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          if (action === 'delete') {
            if (!confirm('删除这个 Inbox 项？')) return;
            await fetch(`/api/inbox/items/${id}`, { method: 'DELETE' });
          } else if (action === 'archive') {
            await fetch(`/api/inbox/items/${id}/archive`, { method: 'POST' });
          } else if (action === 'process') {
            const dest = btn.dataset.dest || 'note';
            await fetch(`/api/inbox/items/${id}/process`, {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ destination: dest })
            });
          }
          loadInboxList();
        });
      });
    } catch (e) {
      el.inboxListContainer.innerHTML = '<div class="inbox-empty">加载失败：' + escapeHtml(String(e)) + '</div>';
    }
  }

  function openInboxCaptureModal(prefillType = 'text', prefillContent = '') {
    // Remove existing
    const existing = document.querySelector('.inbox-capture-overlay');
    if (existing) existing.remove();
    let currentType = prefillType;
    const overlay = document.createElement('div');
    overlay.className = 'inbox-capture-overlay';
    overlay.innerHTML = `
      <div class="inbox-capture-modal">
        <div class="inbox-capture-title">捕获到 Inbox</div>
        <div class="inbox-capture-types">
          ${['text','url','todo','idea','note'].map(t => `
            <button class="inbox-capture-type-btn ${t === currentType ? 'active' : ''}" data-type="${t}">${t}</button>
          `).join('')}
        </div>
        <textarea class="inbox-capture-input" placeholder="输入任何东西... 想法、链接、待办、灵感。Life Loop 会自动归类。">${escapeHtml(prefillContent)}</textarea>
        <div class="inbox-capture-suggested">建议归类：<span id="captureSuggested">...</span></div>
        <div class="inbox-capture-actions">
          <button class="today-btn" id="captureCancel">取消</button>
          <button class="today-btn primary" id="captureSubmit">保存</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const ta = overlay.querySelector('.inbox-capture-input');
    const suggestedEl = overlay.querySelector('#captureSuggested');
    const updateSuggested = async () => {
      try {
        const r = await fetch('/api/inbox/route-suggest', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ content: ta.value, type: currentType })
        });
        const d = await r.json();
        suggestedEl.textContent = d.destination;
      } catch (e) { suggestedEl.textContent = '...'; }
    };
    overlay.querySelectorAll('.inbox-capture-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        currentType = btn.dataset.type;
        overlay.querySelectorAll('.inbox-capture-type-btn').forEach(b => b.classList.toggle('active', b === btn));
        updateSuggested();
      });
    });
    ta.addEventListener('input', () => { if (ta.value.length % 10 === 0) updateSuggested(); });
    overlay.querySelector('#captureCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#captureSubmit').addEventListener('click', async () => {
      const content = ta.value.trim();
      if (!content) { ta.focus(); return; }
      try {
        await fetch('/api/inbox/items', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ type: currentType, content, source: 'manual' })
        });
        overlay.remove();
        if (el.inboxView && el.inboxView.style.display !== 'none') loadInboxList();
        // Refresh badge
        try {
          const stats = await fetch('/api/inbox/stats').then(r => r.json());
          if (el.inboxBadge) {
            if (stats.pending > 0) { el.inboxBadge.style.display = ''; el.inboxBadge.textContent = stats.pending; }
            else { el.inboxBadge.style.display = 'none'; }
          }
        } catch (e) {}
      } catch (e) {
        alert('保存失败：' + e);
      }
    });
    ta.focus();
    updateSuggested();
  }

  
})();
