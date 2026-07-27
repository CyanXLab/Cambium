// Module: sessions
// Auto-extracted from app.js
(function() {
// ===== Sessions management =====
  async function loadSessions() {
    if (!el.sessionsList) return;
    try {
      const resp = await fetch('/api/sessions');
      const data = await resp.json();
      const sessions = data.sessions || [];
      if (sessions.length === 0) {
        el.sessionsList.innerHTML = '<div class="rag-empty">还没有后台会话。可以让 AI 通过 sessions_spawn 工具启动，或点击右上角手动启动。</div>';
        return;
      }
      el.sessionsList.innerHTML = '';
      for (const s of sessions) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const date = s.created_at ? new Date(s.created_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }) : '';
        const statusColor = s.status === 'completed' ? '#10a37f' : s.status === 'running' ? '#a8c7fa' : s.status === 'failed' ? '#ef4444' : '#8e8e8e';
        const result = s.assistant_result ? s.assistant_result.slice(0, 200) + (s.assistant_result.length > 200 ? '...' : '') : '';
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(s.title || s.id)}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${statusColor};">${s.status}</span>
            <button class="skill-delete">删除</button>
          </div>
          <div class="skill-item-desc" style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
            ${date} · ${s.model || ''} · ${s.id}
          </div>
          ${result ? `<div class="skill-item-desc">${escapeHtml(result)}</div>` : ''}
          ${s.user_message ? `<div class="skill-item-desc" style="margin-top:6px; padding:6px 8px; background:rgba(255,255,255,0.03); border-radius:4px; font-size:12px;"><b>任务:</b> ${escapeHtml(s.user_message.slice(0, 300))}</div>` : ''}`;
        item.style.cursor = 'pointer';
        item.addEventListener('click', (e) => {
          if (e.target.classList.contains('skill-delete')) return;
          openSessionDetail(s.id, s);
        });
        item.querySelector('.skill-delete').addEventListener('click', async (e) => {
          e.stopPropagation();
          if (!(await uiConfirm(`确认删除会话 ${s.title || s.id}？`))) return;
          await fetch(`/api/sessions/${s.id}`, { method: 'DELETE' });
          toast('已删除', 'success');
          loadSessions();
        });
        el.sessionsList.appendChild(item);
      }
    } catch (e) {
      el.sessionsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function openSessionDetail(sessionId, sessionData) {
    try {
      const resp = await fetch(`/api/sessions/${sessionId}`);
      const s = resp.ok ? await resp.json() : sessionData;
      const overlay = document.createElement('div');
      overlay.className = 'generic-modal-overlay';
      overlay.innerHTML = `
        <div class="generic-modal" style="max-width:700px;max-height:80vh;overflow-y:auto;">
          <div class="generic-modal-title">${escapeHtml(s.title || s.id || '会话详情')}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">
            ${s.status || ''} · ${s.model || ''} · ${s.id || sessionId}
          </div>
          ${s.user_message ? `<div style="margin-bottom:12px;"><b>任务:</b><br>${escapeHtml(s.user_message)}</div>` : ''}
          ${s.assistant_result ? `<div style="margin-bottom:12px;"><b>结果:</b><br><div style="white-space:pre-wrap;">${escapeHtml(s.assistant_result)}</div></div>` : ''}
          <div class="generic-modal-actions">
            <button class="today-btn" id="closeSessionDetail">关闭</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.querySelector('#closeSessionDetail').addEventListener('click', () => overlay.remove());
      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    } catch (e) {
      toast('加载会话详情失败: ' + e, 'error');
    }
  }

  async function spawnSessionManual() {
    const title = await uiPrompt('会话标题（如：研究旅行计划）：');
    if (!title) return;
    const message = await uiPrompt('任务描述（AI 要做什么）：');
    if (!message) return;
    try {
      const resp = await fetch('/api/sessions/spawn', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title, message }),
      });
      const data = await resp.json();
      if (data.session_id) {
        toast(`已启动会话: ${title}`, 'success');
        loadSessions();
      } else {
        toast(`启动失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('启动失败: ' + e.message, 'error');
    }
  }

  
})();
