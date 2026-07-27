// Module: philosophy
// Auto-extracted from app.js
(function() {
// ===== Philosophy view =====
  let currentPhilosophyTypeFilter = 'all';
  async function loadPhilosophyView() {
    if (!el.philosophyViewContainer) return;
    try {
      const url = currentPhilosophyTypeFilter === 'all'
        ? '/api/philosophy'
        : `/api/philosophy?type=${currentPhilosophyTypeFilter}`;
      const r = await fetch(url).then(r => r.json());
      const items = r.items || [];
      if (items.length === 0) {
        el.philosophyViewContainer.innerHTML = '<div class="philosophy-empty">还没有原则。点击"新增"添加第一条。</div>';
        return;
      }
      el.philosophyViewContainer.innerHTML = `
        <div class="philosophy-grid">
          ${items.map(p => `
            <div class="philosophy-card type-${p.type}">
              <div class="philosophy-card-head">
                <span class="philosophy-card-type">${p.type}</span>
                <span class="philosophy-card-confidence">${(p.confidence * 100).toFixed(0)}%</span>
              </div>
              <div class="philosophy-card-content">${escapeHtml(p.content)}</div>
              ${p.rationale ? `<div class="philosophy-card-rationale">${escapeHtml(p.rationale)}</div>` : ''}
              <div class="philosophy-card-actions">
                <button data-action="retire" data-id="${p.id}">退役</button>
                <button data-action="delete" data-id="${p.id}" class="danger">删除</button>
              </div>
            </div>`).join('')}
        </div>`;
      el.philosophyViewContainer.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          if (action === 'retire') {
            await fetch(`/api/philosophy/${id}/retire`, { method: 'POST' });
          } else if (action === 'delete') {
            if (!confirm('删除这条原则？')) return;
            await fetch(`/api/philosophy/${id}`, { method: 'DELETE' });
          }
          loadPhilosophyView();
        });
      });
    } catch (e) {
      console.error('loadPhilosophyView failed', e);
    }
  }

  function openPhilosophyCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">新增原则</div>
        <div class="generic-modal-field">
          <label>类型</label>
          <select id="newPhilType">
            <option value="principle">原则 (做事的规则)</option>
            <option value="value">价值观 (什么重要)</option>
            <option value="belief">信念 (相信什么)</option>
            <option value="anti_goal">反目标 (要避免什么)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>内容</label>
          <input type="text" id="newPhilContent" placeholder="例如：Simple > Complex" />
        </div>
        <div class="generic-modal-field">
          <label>理由 (为什么)</label>
          <textarea id="newPhilRationale" placeholder="为什么这条重要？"></textarea>
        </div>
        <div class="generic-modal-field">
          <label>信心度 (0-1)</label>
          <input type="number" id="newPhilConfidence" value="0.8" min="0" max="1" step="0.1" />
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newPhilCancel">取消</button>
          <button class="today-btn primary" id="newPhilSubmit">添加</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newPhilCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newPhilSubmit').addEventListener('click', async () => {
      const content = overlay.querySelector('#newPhilContent').value.trim();
      if (!content) { overlay.querySelector('#newPhilContent').focus(); return; }
      const payload = {
        type: overlay.querySelector('#newPhilType').value,
        content,
        rationale: overlay.querySelector('#newPhilRationale').value,
        confidence: parseFloat(overlay.querySelector('#newPhilConfidence').value) || 0.8,
        source: 'user',
      };
      try {
        await fetch('/api/philosophy', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        overlay.remove();
        loadPhilosophyView();
      } catch (e) {
        alert('添加失败：' + e);
      }
    });
  }

  
})();
