// Module: skills
// Auto-extracted from app.js
(function() {
// ===== Skills management =====
  async function loadSkills() {
    if (!el.skillsList) return;
    try {
      const resp = await fetch('/api/skills');
      const data = await resp.json();
      const skills = data.skills || [];
      if (skills.length === 0) {
        el.skillsList.innerHTML = '<div class="rag-empty">还没有技能。点击右上角“+ 新建技能”创建一个。</div>';
        return;
      }
      el.skillsList.innerHTML = '';
      for (const s of skills) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const sizeKb = (s.size / 1024).toFixed(1);
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(s.name)}</span>
            <button class="skill-delete">删除</button>
          </div>
          <div class="skill-item-desc">${escapeHtml(s.description || '(无描述)')}</div>
          <div class="skill-item-meta">
            <span>📦 ${sizeKb} KB</span>
            <span>📝 ${s.size} 字符</span>
          </div>`;
        item.querySelector('.skill-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除技能 ${s.name}？`))) return;
          await fetch('/api/skills/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name: s.name }),
          });
          toast('已删除', 'success');
          loadSkills();
        });
        el.skillsList.appendChild(item);
      }
    } catch (e) {
      el.skillsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function createNewSkill() {
    const name = await uiPrompt('技能名称（小写字母、数字、短横线，如 web-search）：');
    if (!name) return;
    if (!/^[a-z0-9-]+$/.test(name)) {
      toast('名称只能包含小写字母、数字和短横线', 'error');
      return;
    }
    const description = await uiPrompt('技能描述（什么情况下 AI 应该使用这个技能？）：') || '';
    const body = await uiPrompt('技能内容（详细指令，可留空稍后编辑）：') || '';
    try {
      const resp = await fetch('/api/skills/create', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, description, body }),
      });
      const data = await resp.json();
      if (data.ok) {
        toast(`已创建技能: ${name}`, 'success');
        loadSkills();
      } else {
        toast(`创建失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('创建失败: ' + e.message, 'error');
    }
  }

  
})();
