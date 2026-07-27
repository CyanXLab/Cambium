// Module: prompts
// Auto-extracted from app.js
(function() {
// ===== Prompt engineering panel extras =====
  async function loadPromptStats() {
    if (!el.promptStatsDesc) return;
    try {
      const r = await fetch('/api/prompts/stats').then(r => r.json());
      el.promptStatsDesc.textContent = `共 ${r.total} 个 Prompt，${r.customized} 个已自定义，${r.default} 个使用默认值。`;
    } catch (e) {
      el.promptStatsDesc.textContent = '加载统计失败';
    }
  }

  async function exportPrompts() {
    try {
      const r = await fetch('/api/prompts').then(r => r.json());
      const customized = r.prompts.filter(p => !p.is_default);
      const blob = new Blob([JSON.stringify(customized, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'cambium-prompts.json';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { alert('导出失败：' + e); }
  }

  async function importPrompts() {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json,application/json';
    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        if (!Array.isArray(data)) { alert('JSON 格式错误：应为数组'); return; }
        for (const p of data) {
          if (p.key && p.content) {
            await fetch(`/api/prompts/${encodeURIComponent(p.key)}`, {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ content: p.content })
            });
          }
        }
        alert(`已导入 ${data.length} 个 Prompt`);
        await loadSettings();
        populateSettingsUI();
        loadPromptStats();
      } catch (e) {
        alert('导入失败：' + e);
      }
    };
    input.click();
  }

  async function resetAllPrompts() {
    if (!confirm('把所有 Prompt 重置为默认值？此操作不可撤销。')) return;
    try {
      const r = await fetch('/api/prompts').then(r => r.json());
      for (const p of r.prompts) {
        await fetch(`/api/prompts/${encodeURIComponent(p.key)}/reset`, { method: 'POST' });
      }
      alert('已重置');
      await loadSettings();
      populateSettingsUI();
      loadPromptStats();
    } catch (e) { alert('重置失败：' + e); }
  }

  
})();
