// Module: journal
// Auto-extracted from app.js
(function() {
// ===== Journal view =====
  let currentJournalDate = null;
  async function loadJournalView(dateStr) {
    if (!el.journalView) return;
    if (!dateStr) {
      // Default to today
      const d = new Date();
      dateStr = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    }
    currentJournalDate = dateStr;
    if (el.journalTitle) el.journalTitle.textContent = `日志 · ${dateStr}`;
    try {
      // Get journal entry
      let j;
      try {
        const r = await fetch(`/api/journal/${dateStr}`);
        if (r.ok) j = await r.json();
        else j = await fetch('/api/journal/today').then(r => r.json());
      } catch (e) {
        j = await fetch('/api/journal/today').then(r => r.json());
      }
      if (el.journalEditor) el.journalEditor.value = j.content || '';
      if (el.journalHighlights) el.journalHighlights.value = (j.highlights || []).join(' / ');
      if (el.journalGrowth) el.journalGrowth.value = j.growth_notes || '';
      if (el.journalFailures) el.journalFailures.value = j.failures || '';
      if (el.journalGratitude) el.journalGratitude.value = j.gratitude || '';
      // Tone
      if (el.journalTone) {
        if (j.emotional_tone) {
          el.journalTone.style.display = '';
          el.journalTone.textContent = '情绪：' + j.emotional_tone;
        } else {
          el.journalTone.style.display = 'none';
        }
      }
      // AI draft
      if (el.journalAiDraft) {
        if (j.ai_draft && j.ai_draft !== '（今日暂无活动记录）' && j.ai_draft.length > 10) {
          el.journalAiDraft.style.display = '';
          if (el.journalAiDraftText) el.journalAiDraftText.textContent = j.ai_draft;
        } else {
          el.journalAiDraft.style.display = 'none';
        }
      }
      // Streak
      try {
        const sr = await fetch('/api/journal/streak').then(r => r.json());
        if (el.journalStreakInfo) {
          el.journalStreakInfo.textContent = `连续 ${sr.current_streak} 天 · 累计 ${sr.total_entries} 篇 · 最长 ${sr.longest_streak} 天`;
        }
      } catch (e) {}
      // History list
      try {
        const lr = await fetch('/api/journal/list?days=60').then(r => r.json());
        if (el.journalHistoryList) {
          const items = (lr.items || []).filter(x => x.content);
          if (items.length === 0) {
            el.journalHistoryList.innerHTML = '<div class="history-empty">暂无历史日志</div>';
          } else {
            el.journalHistoryList.innerHTML = items.map(j => {
              const d = new Date(j.date + 'T00:00:00');
              const month = d.getMonth() + 1, day = d.getDate();
              const preview = (j.content || '').slice(0, 40).replace(/\n/g, ' ');
              return `<div class="history-item" data-date="${j.date}">
                <div class="history-item-title">${month}月${day}日</div>
                <div class="history-item-preview">${escapeHtml(preview)}</div>
              </div>`;
            }).join('');
            el.journalHistoryList.querySelectorAll('.history-item').forEach(item => {
              item.addEventListener('click', () => loadJournalView(item.dataset.date));
            });
          }
        }
      } catch (e) {}
    } catch (e) {
      console.error('loadJournalView failed', e);
    }
  }

  async function saveJournal() {
    if (!currentJournalDate) return;
    const payload = {
      content: el.journalEditor ? el.journalEditor.value : '',
      highlights: el.journalHighlights ? el.journalHighlights.value.split('/').map(s => s.trim()).filter(Boolean) : [],
      growth_notes: el.journalGrowth ? el.journalGrowth.value : '',
      failures: el.journalFailures ? el.journalFailures.value : '',
      gratitude: el.journalGratitude ? el.journalGratitude.value : '',
    };
    try {
      await fetch(`/api/journal/${currentJournalDate}/content`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: payload.content })
      });
      await fetch(`/api/journal/${currentJournalDate}/fields`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          highlights: payload.highlights,
          growth_notes: payload.growth_notes,
          failures: payload.failures,
          gratitude: payload.gratitude,
        })
      });
      // Tiny toast
      const t = document.createElement('div');
      t.textContent = '✓ 已保存';
      t.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;z-index:99999;';
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 1500);
    } catch (e) {
      alert('保存失败：' + e);
    }
  }

  async function generateJournalAiDraft() {
    if (!currentJournalDate) return;
    const btn = el.btnJournalAiDraftFull;
    if (btn) { btn.disabled = true; btn.textContent = 'AI 起草中...'; }
    try {
      const r = await fetch(`/api/journal/${currentJournalDate}/ai-draft`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.text();
        alert('AI 起草失败：' + err);
      } else {
        await loadJournalView(currentJournalDate);
      }
    } catch (e) {
      alert('AI 起草失败：' + e);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'AI 起草'; }
    }
  }

  
})();
