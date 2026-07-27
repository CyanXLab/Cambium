// Module: today
// Auto-extracted from app.js
(function() {
// ===== Today view (life-first homepage) =====
  async function loadTodayBriefing() {
    try {
      const resp = await fetch('/api/daily/briefing');
      const b = await resp.json();
      if (el.todayGreeting) el.todayGreeting.textContent = b.greeting || '你好';
      if (el.todayDate) {
        const d = new Date(b.date + 'T00:00:00');
        const weekday = ['日','一','二','三','四','五','六'][d.getDay()];
        el.todayDate.textContent = `${b.date} 星期${weekday}`;
      }

      // Load AI Morning Letter
      await loadMorningLetter(b.date);

      // Load Discoveries
      await loadTodayDiscoveries();
      // Yesterday done
      if (el.yesterdayList) {
        if (!b.yesterday_done || b.yesterday_done.length === 0) {
          el.yesterdayList.innerHTML = '<div class="today-empty">昨天没有完成的事项</div>';
        } else {
          el.yesterdayList.innerHTML = b.yesterday_done.map(item => {
            const icon = item.type === 'task' ? '✓' : (item.type === 'conversation' ? '💬' : '📥');
            return `<div class="today-yesterday-item">
              <span class="today-yesterday-icon">${icon}</span>
              <span class="today-yesterday-title">${escapeHtml(item.title)}</span>
              <span class="today-yesterday-type">${item.type}</span>
            </div>`;
          }).join('');
        }
      }
      if (el.yesterdayCount) el.yesterdayCount.textContent = b.yesterday_count || 0;
      // Reflection
      if (el.reflectionBody) {
        if (b.reflection) {
          const text = b.reflection.insight || b.reflection.observation || '';
          el.reflectionBody.innerHTML = `<div class="today-reflection-text">${escapeHtml(text)}</div>
            <div class="today-reflection-meta">${new Date(b.reflection.created_at * 1000).toLocaleString('zh-CN')}</div>`;
        } else {
          el.reflectionBody.innerHTML = '<div class="today-empty">还没有生成反思。Life Loop 会在每天结束时自动生成。</div>';
        }
      }
      // Today goals
      if (el.todayGoalsList) {
        if (!b.today_goals || b.today_goals.length === 0) {
          el.todayGoalsList.innerHTML = '<div class="today-empty">暂无目标。在 Inbox 添加 todo，或让 AI 帮你规划。</div>';
        } else {
          el.todayGoalsList.innerHTML = b.today_goals.map(g => `
            <div class="today-goal-item">
              <span class="today-goal-bullet"></span>
              <span class="today-goal-text">${escapeHtml(g.title)}</span>
              <span class="today-goal-source">${g.source}</span>
            </div>`).join('');
        }
      }
      if (el.todayGoalsCount) el.todayGoalsCount.textContent = b.today_goals_count || 0;
      // Journal preview
      if (el.journalPreview) {
        const j = b.journal;
        if (j && j.content) {
          el.journalPreview.innerHTML = `<div class="today-reflection-text">${escapeHtml(j.content.slice(0,200))}${j.content.length > 200 ? '…' : ''}</div>
            <div class="today-journal-actions">
              <button class="today-btn" id="btnJournalEdit2">继续编辑</button>
            </div>`;
          const b2 = document.getElementById('btnJournalEdit2');
          if (b2) b2.addEventListener('click', () => switchView('journal'));
        } else if (j && j.ai_draft) {
          el.journalPreview.innerHTML = `<div class="today-empty">AI 已起草今日日志，点击查看</div>
            <div class="today-journal-actions">
              <button class="today-btn primary" id="btnJournalEdit3">查看 AI 草稿</button>
            </div>`;
          const b3 = document.getElementById('btnJournalEdit3');
          if (b3) b3.addEventListener('click', () => switchView('journal'));
        } else {
          el.journalPreview.innerHTML = `<div class="today-empty">今天还没有写日志。</div>
            <div class="today-journal-actions">
              <button class="today-btn primary" id="btnJournalAiDraft2">让 AI 起草</button>
              <button class="today-btn" id="btnJournalEdit4">写日志</button>
            </div>`;
          const b4 = document.getElementById('btnJournalAiDraft2');
          if (b4) b4.addEventListener('click', async () => {
            b4.disabled = true; b4.textContent = 'AI 起草中...';
            try { await fetch('/api/daily/journal-draft', { method: 'POST' }); } catch (e) {}
            switchView('journal');
          });
          const b5 = document.getElementById('btnJournalEdit4');
          if (b5) b5.addEventListener('click', () => switchView('journal'));
        }
      }
      if (el.journalStreakTag) {
        try {
          const sr = await fetch('/api/journal/streak').then(r => r.json());
          if (sr.current_streak > 0) {
            el.journalStreakTag.style.display = '';
            el.journalStreakTag.textContent = `连续 ${sr.current_streak} 天`;
          } else {
            el.journalStreakTag.style.display = 'none';
          }
        } catch (e) {}
      }
      // Inbox pending
      if (el.inboxPendingList) {
        try {
          const ir = await fetch('/api/inbox/items?status=pending&limit=5').then(r => r.json());
          if (ir.items && ir.items.length > 0) {
            el.inboxPendingList.innerHTML = ir.items.map(it => `
              <div class="today-yesterday-item">
                <span class="today-yesterday-icon">📥</span>
                <span class="today-yesterday-title">${escapeHtml(it.title || it.content.slice(0,40))}</span>
                <span class="today-yesterday-type">${it.type}</span>
              </div>`).join('');
          } else {
            el.inboxPendingList.innerHTML = '<div class="today-empty">Inbox 是空的。捕获任何想法、链接、待办，让 Life Loop 帮你归类。</div>';
          }
          if (el.inboxPendingCount) el.inboxPendingCount.textContent = ir.items ? ir.items.length : 0;
        } catch (e) {
          el.inboxPendingList.innerHTML = '<div class="today-empty">加载失败</div>';
        }
      }
      // Update inbox badge in sidebar
      try {
        const stats = await fetch('/api/inbox/stats').then(r => r.json());
        if (el.inboxBadge) {
          if (stats.pending > 0) {
            el.inboxBadge.style.display = '';
            el.inboxBadge.textContent = stats.pending;
          } else {
            el.inboxBadge.style.display = 'none';
          }
        }
      } catch (e) {}
      // Co-experience moment
      if (el.coExpBody) {
        if (b.co_experience_moment) {
          const m = b.co_experience_moment;
          const daysAgo = Math.floor((Date.now() / 1000 - m.occurred_at) / 86400);
          el.coExpBody.innerHTML = `<div class="today-coexp-text">"${escapeHtml(m.title)}"</div>
            <div class="today-coexp-meta">${daysAgo === 0 ? '今天' : daysAgo + ' 天前'} · ${m.moment_type}</div>`;
        } else {
          el.coExpBody.innerHTML = '<div class="today-empty">还没有共同回忆。重要的时刻会被自动收集到这里。</div>';
        }
      }
      // Recent activity
      if (el.recentActivityList) {
        if (b.recent_activity && b.recent_activity.length > 0) {
          el.recentActivityList.innerHTML = b.recent_activity.map(a => `
            <div class="today-activity-item">
              <span class="today-activity-type">${a.type}</span>
              <span class="today-activity-title">${escapeHtml(a.title)}</span>
            </div>`).join('');
        } else {
          el.recentActivityList.innerHTML = '<div class="today-empty">暂无活动</div>';
        }
      }
    } catch (e) {
      console.error('loadTodayBriefing failed', e);
    }
  }

  
})();
