// Module: rag
// Auto-extracted from app.js
(function() {
// ===== RAG file management =====
  async function uploadRagFiles(files) {
    for (const file of files) {
      if (file.size > 20 * 1024 * 1024) {
        toast(`${file.name} 超过 20MB`, 'error');
        continue;
      }
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/rag/upload', { method: 'POST', body: fd });
        if (!resp.ok) {
          const e = await resp.json().catch(() => ({}));
          toast(`上传失败: ${e.detail || 'unknown'}`, 'error');
          continue;
        }
        const data = await resp.json();
        toast(`已上传: ${data.name}`, 'success');
      } catch (e) {
        toast(`上传失败: ${e.message}`, 'error');
      }
    }
    loadRagFiles();
  }

  async function loadRagFiles() {
    if (!el.ragFilesList) return;
    try {
      const resp = await fetch('/api/rag/list');
      const data = await resp.json();
      const files = data.files || [];
      if (files.length === 0) {
        el.ragFilesList.innerHTML = '<div class="rag-empty">还没有上传文件</div>';
        return;
      }
      el.ragFilesList.innerHTML = '';
      for (const f of files) {
        const item = document.createElement('div');
        item.className = 'rag-file-item';
        const sizeKb = (f.size / 1024).toFixed(1);
        const date = new Date(f.created_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
        item.innerHTML = `
          <div class="rag-file-icon">📄</div>
          <div class="rag-file-info">
            <div class="rag-file-name">${escapeHtml(f.name)}</div>
            <div class="rag-file-meta">${sizeKb} KB · ${f.chunks || 0} 个片段 · ${date}</div>
          </div>
          <button class="rag-file-delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>`;
        item.querySelector('.rag-file-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除 ${f.name}？`))) return;
          await fetch('/api/rag/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ id: f.id }),
          });
          toast('已删除', 'success');
          loadRagFiles();
        });
        el.ragFilesList.appendChild(item);
      }
    } catch (e) {
      el.ragFilesList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  
})();
