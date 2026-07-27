// Module: artifacts
// Auto-extracted from app.js
(function() {
// ===== Artifacts view =====
  let currentArtifactId = null;
  let currentArtifactTypeFilter = 'all';
  async function loadArtifactsView() {
    if (!el.artifactsView) return;
    try {
      const params = new URLSearchParams();
      if (currentArtifactTypeFilter !== 'all') params.set('type', currentArtifactTypeFilter);
      params.set('limit', '100');
      const r = await fetch('/api/artifacts?' + params.toString()).then(r => r.json());
      const items = r.items || [];
      // Populate sidebar with artifacts (reuse residentsListSidebar pattern but we need separate)
      // For simplicity, render list inside the main container as a list view
      if (items.length === 0) {
        el.artifactsViewContainer.innerHTML = '<div class="artifacts-empty">还没有作品。点击"新建作品"创建第一个。</div>';
        return;
      }
      // If no current artifact selected, show list view
      if (!currentArtifactId) {
        el.artifactsViewContainer.innerHTML = `
          <div class="artifact-list" style="max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:8px;">
            ${items.map(a => `
              <div class="inbox-item" data-artifact-id="${a.id}" style="cursor:pointer;">
                <span class="inbox-item-type">${a.type}</span>
                <div class="inbox-item-body">
                  <div class="inbox-item-title">${escapeHtml(a.title)} <span style="color:var(--text-muted);font-size:11px;">v${a.version}</span></div>
                  <div class="inbox-item-content">${escapeHtml((a.content || '').slice(0, 100))}${a.content && a.content.length > 100 ? '…' : ''}</div>
                  <div class="inbox-item-meta">
                    <span>${new Date(a.updated_at * 1000).toLocaleString('zh-CN')}</span>
                    <span>by ${a.created_by}</span>
                    ${a.tags && a.tags.length > 0 ? `<span>#${a.tags.join(' #')}</span>` : ''}
                  </div>
                </div>
              </div>`).join('')}
          </div>`;
        el.artifactsViewContainer.querySelectorAll('[data-artifact-id]').forEach(item => {
          item.addEventListener('click', () => {
            currentArtifactId = item.dataset.artifactId;
            loadArtifactDetail(currentArtifactId);
          });
        });
      } else {
        await loadArtifactDetail(currentArtifactId);
      }
    } catch (e) {
      console.error('loadArtifactsView failed', e);
    }
  }

  async function loadArtifactDetail(artifactId) {
    if (!el.artifactsViewContainer) return;
    try {
      const a = await fetch(`/api/artifacts/${artifactId}`).then(r => r.json());
      if (el.artifactTitle) el.artifactTitle.textContent = a.title;
      el.artifactsViewContainer.innerHTML = `
        <div class="artifact-detail">
          <div class="artifact-header">
            <input class="artifact-title-input" id="artifactTitleInput" value="${escapeHtml(a.title)}" />
            <div class="artifact-meta-row">
              <span class="artifact-type-badge">${a.type}</span>
              <span class="artifact-version">v${a.version}</span>
              <span>${new Date(a.updated_at * 1000).toLocaleString('zh-CN')}</span>
              <span>by ${a.created_by}</span>
              ${a.created_with_resident ? `<span>with ${escapeHtml(a.created_with_resident)}</span>` : ''}
            </div>
          </div>
          <textarea class="artifact-editor" id="artifactEditor">${escapeHtml(a.content || '')}</textarea>
          <div class="artifact-tags-row">
            ${(a.tags || []).map(t => `<span class="artifact-tag">#${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>`;
      currentArtifactId = artifactId;
    } catch (e) {
      console.error('loadArtifactDetail failed', e);
    }
  }

  async function saveCurrentArtifact() {
    if (!currentArtifactId) return;
    const titleInput = document.getElementById('artifactTitleInput');
    const editor = document.getElementById('artifactEditor');
    if (!titleInput || !editor) return;
    try {
      await fetch(`/api/artifacts/${currentArtifactId}`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title: titleInput.value, content: editor.value })
      });
      const t = document.createElement('div');
      t.textContent = '✓ 已保存';
      t.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;z-index:99999;';
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 1500);
    } catch (e) {
      alert('保存失败：' + e);
    }
  }

  function openArtifactCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">新建作品</div>
        <div class="generic-modal-field">
          <label>标题</label>
          <input type="text" id="newArtTitle" placeholder="例如：README v3" />
        </div>
        <div class="generic-modal-field">
          <label>类型</label>
          <select id="newArtType">
            <option value="readme">README</option>
            <option value="design">设计文档</option>
            <option value="paper">论文</option>
            <option value="prompt">Prompt</option>
            <option value="code">代码</option>
            <option value="note">笔记</option>
            <option value="project">项目</option>
            <option value="plan">计划</option>
            <option value="research">研究</option>
            <option value="essay">文章</option>
            <option value="outline">大纲</option>
            <option value="draft">草稿</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>内容 (可留空，稍后编辑)</label>
          <textarea id="newArtContent" placeholder="开始写..."></textarea>
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newArtCancel">取消</button>
          <button class="today-btn primary" id="newArtSubmit">创建</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newArtCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newArtSubmit').addEventListener('click', async () => {
      const title = overlay.querySelector('#newArtTitle').value.trim();
      if (!title) { overlay.querySelector('#newArtTitle').focus(); return; }
      const payload = {
        title,
        type: overlay.querySelector('#newArtType').value,
        content: overlay.querySelector('#newArtContent').value,
        created_by: 'user',
      };
      try {
        const r = await fetch('/api/artifacts', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        }).then(r => r.json());
        overlay.remove();
        currentArtifactId = r.id;
        await loadArtifactDetail(r.id);
      } catch (e) {
        alert('创建失败：' + e);
      }
    });
  }

  async function createNewArtifactVersion() {
    if (!currentArtifactId) return;
    const editor = document.getElementById('artifactEditor');
    if (!editor) return;
    try {
      const r = await fetch(`/api/artifacts/${currentArtifactId}/new-version`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: editor.value })
      }).then(r => r.json());
      currentArtifactId = r.id;
      await loadArtifactDetail(r.id);
    } catch (e) {
      alert('创建新版本失败：' + e);
    }
  }

  
})();
