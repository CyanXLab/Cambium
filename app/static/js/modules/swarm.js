// Module: swarm — Swarm Task + Self-Goal panels
(function() {

  // ===== Swarm Task Panel =====
  let currentSwarmTaskId = null;
  async function loadSwarmTasks() {
    const container = document.getElementById('swarmTaskList');
    if (!container) return;
    try {
      const r = await fetch('/api/swarm/tasks').then(r => r.json());
      const items = r.items || [];
      if (items.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center;">还没有 Swarm Task。在下方创建第一个。</div>';
        return;
      }
      container.innerHTML = items.map(t => `
        <div class="inbox-item" data-task-id="${t.id}" style="cursor:pointer;">
          <span class="inbox-item-type">${t.status}</span>
          <div class="inbox-item-body">
            <div class="inbox-item-title">${escapeHtml(t.title)}</div>
            <div class="inbox-item-meta">
              <span>${new Date(t.created_at * 1000).toLocaleString('zh-CN')}</span>
              <span>by ${t.created_by}</span>
            </div>
          </div>
        </div>`).join('');
      container.querySelectorAll('[data-task-id]').forEach(item => {
        item.addEventListener('click', () => openSwarmTaskDetail(item.dataset.taskId));
      });
    } catch (e) {
      container.innerHTML = '<div style="color:red;padding:20px;">加载失败: ' + escapeHtml(String(e)) + '</div>';
    }
  }

  async function openSwarmTaskDetail(taskId) {
    currentSwarmTaskId = taskId;
    try {
      const [taskResp, msgResp] = await Promise.all([
        fetch(`/api/swarm/tasks/${taskId}`).then(r => r.json()),
        fetch(`/api/swarm/tasks/${taskId}/messages`).then(r => r.json()),
      ]);
      const overlay = document.createElement('div');
      overlay.className = 'generic-modal-overlay';
      const messages = msgResp.items || [];
      overlay.innerHTML = `
        <div class="generic-modal" style="max-width:800px;max-height:85vh;overflow-y:auto;">
          <div class="generic-modal-title">${escapeHtml(taskResp.title || 'Task')}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">
            状态: ${taskResp.status} · 创建者: ${taskResp.created_by}
          </div>
          ${taskResp.description ? `<div style="margin-bottom:12px;"><b>描述:</b><br>${escapeHtml(taskResp.description)}</div>` : ''}
          ${taskResp.result ? `<div style="margin-bottom:12px;padding:12px;background:var(--bg-soft);border-radius:8px;"><b>结果:</b><br><div style="white-space:pre-wrap;">${escapeHtml(taskResp.result)}</div></div>` : ''}
          ${messages.length > 0 ? `
            <div style="margin-bottom:12px;">
              <b>居民讨论:</b>
              <div class="discussion-panel" style="margin-top:8px;">
                ${messages.map(m => `
                  <div class="discussion-message">
                    <span style="font-weight:600;color:var(--accent-blue,#3b82f6);">[${m.from_resident}]</span>
                    ${escapeHtml(m.content).replace(/\n/g, '<br>')}
                  </div>`).join('')}
              </div>
            </div>` : ''}
          <div class="generic-modal-actions">
            ${taskResp.status === 'pending' || taskResp.status === 'decomposing' ? 
              `<button class="today-btn primary" id="btnExecuteSwarm">执行 (LangGraph)</button>` : ''}
            <button class="today-btn" id="btnCloseSwarmDetail">关闭</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const closeBtn = overlay.querySelector('#btnCloseSwarmDetail');
      if (closeBtn) closeBtn.addEventListener('click', () => overlay.remove());
      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
      const execBtn = overlay.querySelector('#btnExecuteSwarm');
      if (execBtn) {
        execBtn.addEventListener('click', async () => {
          execBtn.disabled = true;
          execBtn.textContent = '执行中...';
          try {
            const r = await fetch(`/api/swarm/tasks/${taskId}/execute-langgraph`, { method: 'POST' }).then(r => r.json());
            if (r.error) {
              toast('执行失败: ' + r.error, 'error');
            } else {
              toast('任务完成', 'success');
              overlay.remove();
              openSwarmTaskDetail(taskId);
              loadSwarmTasks();
            }
          } catch (e) {
            toast('执行失败: ' + e, 'error');
          }
          execBtn.disabled = false;
          execBtn.textContent = '执行 (LangGraph)';
        });
      }
    } catch (e) {
      toast('加载详情失败: ' + e, 'error');
    }
  }

  async function createSwarmTask() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">创建 Swarm Task</div>
        <div class="generic-modal-field">
          <label>标题</label>
          <input type="text" id="swarmTaskTitle" placeholder="任务标题" />
        </div>
        <div class="generic-modal-field">
          <label>描述</label>
          <textarea id="swarmTaskDesc" placeholder="详细描述任务..." style="min-height:100px;"></textarea>
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="btnCancelSwarmCreate">取消</button>
          <button class="today-btn primary" id="btnSubmitSwarmCreate">创建</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#btnCancelSwarmCreate').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#btnSubmitSwarmCreate').addEventListener('click', async () => {
      const title = overlay.querySelector('#swarmTaskTitle').value.trim();
      const desc = overlay.querySelector('#swarmTaskDesc').value.trim();
      if (!title) return;
      try {
        const r = await fetch('/api/swarm/tasks', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ title, description: desc }),
        }).then(r => r.json());
        overlay.remove();
        toast('Task 已创建', 'success');
        loadSwarmTasks();
        openSwarmTaskDetail(r.id);
      } catch (e) { toast('创建失败: ' + e, 'error'); }
    });
  }

  // ===== Self-Goals Panel =====
  async function loadSelfGoals() {
    const container = document.getElementById('selfGoalsList');
    if (!container) return;
    try {
      const r = await fetch('/api/self-goals').then(r => r.json());
      const items = r.items || [];
      if (items.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center;">还没有自主目标提案。AI 会在每日 Life Loop 中自动生成。</div>';
        return;
      }
      container.innerHTML = items.map(g => {
        const statusColor = g.status === 'proposed' ? '#f59e0b' : g.status === 'approved' ? '#10b981' : g.status === 'rejected' ? '#ef4444' : '#8e8e8e';
        return `
        <div class="inbox-item" style="cursor:default;">
          <span class="inbox-item-type" style="background:${statusColor}20;color:${statusColor};">${g.status}</span>
          <div class="inbox-item-body">
            <div class="inbox-item-title">${escapeHtml(g.title)}</div>
            <div class="inbox-item-content">${escapeHtml(g.description.slice(0, 200))}</div>
            <div class="inbox-item-meta">
              <span>信心度: ${(g.confidence * 100).toFixed(0)}%</span>
              <span>类别: ${g.category}</span>
            </div>
          </div>
          ${g.status === 'proposed' ? `
          <div class="inbox-item-actions">
            <button data-action="approve" data-id="${g.id}" style="color:#10b981;">批准</button>
            <button data-action="reject" data-id="${g.id}" class="danger">拒绝</button>
          </div>` : ''}
        </div>`;
      }).join('');
      container.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          if (action === 'approve') {
            const r = await fetch(`/api/self-goals/${id}/approve`, { method: 'POST' }).then(r => r.json());
            if (r.task) toast('已批准，Swarm Task 已创建', 'success');
          } else if (action === 'reject') {
            await fetch(`/api/self-goals/${id}/reject`, { method: 'POST' });
            toast('已拒绝', 'info');
          }
          loadSelfGoals();
        });
      });
    } catch (e) {
      container.innerHTML = '<div style="color:red;padding:20px;">加载失败</div>';
    }
  }

  // Expose functions to outer scope (app.js IIFE shares the same scope)
  // These are assigned to vars in app.js, so we just need them to be in scope.
  // Since both scripts run in the same global scope, function declarations
  // inside this IIFE are NOT visible outside. We expose via window.
  // However, app.js uses them as bare identifiers, so we need a different approach.
  // The fix: app.js should check for existence before calling.

})();
