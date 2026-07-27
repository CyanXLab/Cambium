// Module: memory
// Auto-extracted from app.js
(function() {
// ===== Memory management =====
  async function openMemoryModal() {
    el.memoryModal.style.display = '';
    await Promise.all([refreshMemoryList(), refreshMemorySummary()]);
  }

  async function refreshMemorySummary() {
    try {
      const resp = await fetch('/api/memory/summary');
      const data = await resp.json();
      if (data.summary) {
        el.memorySummaryText.textContent = data.summary;
        el.memorySummaryInput.value = '';
        const ago = formatTimeAgo(data.updated_at);
        el.memorySummaryTime.textContent = `更新于 ${ago}`;
      } else {
        el.memorySummaryText.textContent = '还没有记忆摘要。和 AI 多聊几句，它会自动总结你分享的关键信息。';
        el.memorySummaryTime.textContent = '尚未生成';
      }
    } catch (e) {
      el.memorySummaryText.textContent = '加载摘要失败: ' + e.message;
    }
  }

  function formatTimeAgo(timestamp) {
    if (!timestamp) return '未知';
    const diff = Date.now() / 1000 - timestamp;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`;
    return new Date(timestamp * 1000).toLocaleDateString('zh-CN');
  }

  async function refreshMemoryList() {
    try {
      const resp = await fetch('/api/memory');
      const data = await resp.json();
      const mems = data.memories || [];
      el.memoryStats.textContent = `${mems.length} 条`;
      el.memoryList.innerHTML = '';
      if (mems.length === 0) {
        el.memoryList.innerHTML = '<div class="memory-empty">还没有记忆片段。对话中的关键事实会自动保存到这里，也可以手动添加。</div>';
        return;
      }
      for (const m of mems) {
        const item = document.createElement('div');
        item.className = 'memory-item';
        const date = new Date(m.updated_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
        const source = m.source === 'auto' ? '自动' : '手动';
        item.innerHTML = `
          <div class="mi-content">${escapeHtml(m.content)}<div class="mi-meta">${date} · ${source} · 访问 ${m.access_count} 次</div></div>
          <button class="mi-delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>`;
        item.querySelector('.mi-delete').addEventListener('click', async () => {
          await fetch('/api/memory/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ id: m.id }),
          });
          refreshMemoryList();
          toast('已删除', 'success');
        });
        el.memoryList.appendChild(item);
      }
    } catch (e) {
      el.memoryList.innerHTML = `<div class="memory-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }
  async function addMemoryManual() {
    const text = el.memoryAddInput.value.trim();
    if (!text) return;
    try {
      const resp = await fetch('/api/memory/add', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: text, source: 'manual' }),
      });
      const data = await resp.json();
      if (data.action === 'add') {
        el.memoryAddInput.value = '';
        toast('已添加', 'success');
        refreshMemoryList();
      } else if (data.action === 'update') {
        toast('已合并到现有记忆', 'success');
        el.memoryAddInput.value = '';
        refreshMemoryList();
      } else {
        toast('已存在相似记忆', 'info');
      }
    } catch (e) {
      toast('添加失败: ' + e.message, 'error');
    }
  }

  async function updateMemorySummary() {
    const text = el.memorySummaryInput.value.trim();
    if (!text) return;
    try {
      await fetch('/api/memory/summary/update', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ summary: text }),
      });
      el.memorySummaryInput.value = '';
      toast('摘要已更新', 'success');
      await refreshMemorySummary();
    } catch (e) {
      toast('更新失败: ' + e.message, 'error');
    }
  }

  async function regenerateMemorySummary() {
    el.btnMemoryRegenerate.disabled = true;
    el.btnMemoryRegenerate.textContent = '生成中...';
    try {
      const resp = await fetch('/api/memory/summary/regenerate', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({}),
      });
      const data = await resp.json();
      if (data.summary) {
        toast('摘要已重新生成', 'success');
        await refreshMemorySummary();
      } else {
        toast('暂无记忆可生成摘要', 'info');
      }
    } catch (e) {
      toast('生成失败: ' + e.message, 'error');
    } finally {
      el.btnMemoryRegenerate.disabled = false;
      el.btnMemoryRegenerate.textContent = '刷新摘要';
    }
  }

  
})();
