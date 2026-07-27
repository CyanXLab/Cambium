// Module: residents
// Auto-extracted from app.js
(function() {
// ===== Residents view =====
  let currentResidentId = null;
  async function loadResidentsView() {
    if (!el.residentsView) return;
    try {
      const r = await fetch('/api/residents').then(r => r.json());
      const items = r.items || [];
      if (el.residentsListSidebar) {
        if (items.length === 0) {
          el.residentsListSidebar.innerHTML = '<div class="history-empty">还没有居民</div>';
        } else {
          el.residentsListSidebar.innerHTML = items.map(res => `
            <div class="history-item ${res.id === currentResidentId ? 'active' : ''}" data-resident-id="${res.id}">
              <div class="history-item-title">${escapeHtml(res.name)}</div>
              <div class="history-item-preview">${res.role} · ${res.status}</div>
            </div>`).join('');
          el.residentsListSidebar.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
              currentResidentId = item.dataset.residentId;
              loadResidentDetail(currentResidentId);
              loadResidentsView(); // refresh active state
            });
          });
        }
      }
      // Auto-select first if none selected
      if (!currentResidentId && items.length > 0) {
        currentResidentId = items[0].id;
        loadResidentDetail(currentResidentId);
      }
    } catch (e) {
      console.error('loadResidentsView failed', e);
    }
  }

  async function loadResidentDetail(residentId) {
    if (!el.residentsViewContainer) return;
    try {
      const r = await fetch(`/api/residents/${residentId}`).then(r => r.json());
      const runsR = await fetch(`/api/residents/${residentId}/runs?limit=5`).then(r => r.json());
      const runs = runsR.items || [];
      if (el.residentTitle) el.residentTitle.textContent = r.name;
      const traits = r.personality_traits || {};
      const traitLabels = { rigor: '严谨', curiosity: '好奇', pushback: '反驳', patience: '耐心' };
      const traitsHtml = Object.keys(traitLabels).map(k => {
        const v = traits[k] || 0;
        return `<div class="resident-trait">
          <div class="resident-trait-label">${traitLabels[k]} (${(v*100).toFixed(0)}%)</div>
          <div class="resident-trait-bar"><div class="resident-trait-fill" style="width:${v*100}%"></div></div>
        </div>`;
      }).join('');

      const concerns = r.current_concerns || [];
      const concernsHtml = concerns.length > 0
        ? concerns.map(c => `<div class="resident-concern">${escapeHtml(c.title || c)}</div>`).join('')
        : '<div style="color:var(--text-muted); font-style:italic; font-size:13px;">暂无当前关注</div>';

      const runsHtml = runs.length > 0
        ? runs.map(run => `<div class="resident-run">
            <span class="resident-run-status ${run.status}">${run.status}</span>
            <span class="resident-run-trigger">${escapeHtml(run.trigger)}</span>
            <span class="resident-run-time">${new Date(run.created_at * 1000).toLocaleString('zh-CN')}</span>
          </div>`).join('')
        : '<div style="color:var(--text-muted); font-style:italic; font-size:13px;">还没有运行记录</div>';

      el.residentsViewContainer.innerHTML = `
        <div class="resident-detail">
          <div class="resident-detail-header">
            <div class="resident-avatar">${escapeHtml(r.name.charAt(0).toUpperCase())}</div>
            <div>
              <div class="resident-name">${escapeHtml(r.name)}
                <span class="resident-status ${r.status}">${r.status}</span>
              </div>
              <div class="resident-role">${r.role} · 运行 ${r.run_count} 次</div>
            </div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">人格设定</div>
            <div class="resident-system-prompt">${escapeHtml(r.system_prompt || '(空)')}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">个性特征</div>
            <div class="resident-traits">${traitsHtml}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">当前在想的事</div>
            <div class="resident-concerns-list">${concernsHtml}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">最近运行</div>
            <div class="resident-runs">${runsHtml}</div>
          </div>
        </div>`;
    } catch (e) {
      console.error('loadResidentDetail failed', e);
      el.residentsViewContainer.innerHTML = '<div class="residents-empty">加载失败</div>';
    }
  }

  function openResidentCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">创建新居民</div>
        <div class="generic-modal-field">
          <label>名字</label>
          <input type="text" id="newResName" placeholder="例如：Debugger" />
        </div>
        <div class="generic-modal-field">
          <label>角色</label>
          <select id="newResRole">
            <option value="custom">自定义</option>
            <option value="architect">Architect (架构师)</option>
            <option value="researcher">Researcher (研究员)</option>
            <option value="writer">Writer (作家)</option>
            <option value="planner">Planner (规划师)</option>
            <option value="historian">Historian (史官)</option>
            <option value="designer">Designer (设计师)</option>
            <option value="critic">Critic (批评者)</option>
            <option value="debugger">Debugger (调试员)</option>
            <option value="explorer">Explorer (探索者)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>系统提示词 (人格设定)</label>
          <textarea id="newResPrompt" placeholder="描述这个居民的性格、专长、说话方式..."></textarea>
        </div>
        <div class="generic-modal-field">
          <label>运行模式</label>
          <select id="newResMode">
            <option value="async">异步 (后台排队)</option>
            <option value="sync">同步 (内联)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>最大重试次数</label>
          <input type="number" id="newResRetries" value="3" min="0" max="10" />
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newResCancel">取消</button>
          <button class="today-btn primary" id="newResSubmit">创建</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newResCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newResSubmit').addEventListener('click', async () => {
      const name = overlay.querySelector('#newResName').value.trim();
      if (!name) { overlay.querySelector('#newResName').focus(); return; }
      const payload = {
        name,
        role: overlay.querySelector('#newResRole').value,
        system_prompt: overlay.querySelector('#newResPrompt').value,
        mode: overlay.querySelector('#newResMode').value,
        max_retries: parseInt(overlay.querySelector('#newResRetries').value) || 3,
        personality_traits: { rigor: 0.7, curiosity: 0.7, pushback: 0.5, patience: 0.7 },
      };
      try {
        const r = await fetch('/api/residents', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        }).then(r => r.json());
        overlay.remove();
        currentResidentId = r.id;
        await loadResidentsView();
        await loadResidentDetail(r.id);
      } catch (e) {
        alert('创建失败：' + e);
      }
    });
  }

  async function runResidentManually() {
    if (!currentResidentId) return;
    const btn = el.btnResidentRun;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span>运行中...</span>'; }
    try {
      const r = await fetch(`/api/residents/${currentResidentId}/run`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ trigger: 'manual', input: '' })
      }).then(r => r.json());
      if (r.status === 'completed') {
        await loadResidentDetail(currentResidentId);
      } else {
        alert('运行失败：' + (r.error || r.status));
      }
    } catch (e) {
      alert('运行失败：' + e);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>运行</span>';
      }
    }
  }

  
})();
