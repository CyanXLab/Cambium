// Module: morning
// Auto-extracted from app.js
(function() {
// ===== Morning Letter =====
  async function loadMorningLetter(dateStr) {
    if (!el.morningLetterBody) return;
    try {
      const r = await fetch(`/api/mornings/${dateStr}`).then(r => r.ok ? r.json() : null);
      if (!r || !r.letter) {
        el.morningLetterBody.innerHTML = '<div class="today-empty">今天还没有信。点击"生成"让 Cambium 给你写一封。</div>';
        if (el.morningConcerns) el.morningConcerns.style.display = 'none';
        if (el.morningLetterMeta) el.morningLetterMeta.textContent = '今天的信（未生成）';
        return;
      }
      // Render letter (basic markdown: paragraphs, bold, italic)
      const html = r.letter
        .split(/\n\n+/)
        .map(p => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
        .join('');
      el.morningLetterBody.innerHTML = html;
      if (el.morningLetterMeta) {
        const time = new Date(r.generated_at * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        el.morningLetterMeta.textContent = `今天的信 · ${time} · 心情: ${r.mood || 'neutral'}`;
      }
      // Concerns
      if (r.concerns && r.concerns.length > 0) {
        if (el.morningConcerns) el.morningConcerns.style.display = '';
        if (el.morningConcernsList) {
          el.morningConcernsList.innerHTML = r.concerns.map(c => `
            <div class="morning-concern-item">
              <div class="concern-title">${escapeHtml(c.title || '')}</div>
              ${c.why ? `<div class="concern-why">${escapeHtml(c.why)}</div>` : ''}
            </div>`).join('');
        }
      } else {
        if (el.morningConcerns) el.morningConcerns.style.display = 'none';
      }
    } catch (e) {
      console.error('loadMorningLetter failed', e);
    }
  }

  async function generateMorningLetter() {
    if (!el.btnGenerateMorning) return;
    const btn = el.btnGenerateMorning;
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>生成中...</span>';
    try {
      const today = new Date();
      const dateStr = today.getFullYear() + '-' + String(today.getMonth()+1).padStart(2,'0') + '-' + String(today.getDate()).padStart(2,'0');
      const r = await fetch(`/api/mornings/${dateStr}/generate`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.text();
        alert('生成失败：' + err);
      } else {
        await loadMorningLetter(dateStr);
      }
    } catch (e) {
      alert('生成失败：' + e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }

  
})();
