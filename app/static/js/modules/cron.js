// Module: cron
// Auto-extracted from app.js
(function() {
// ===== Cron management =====
  async function loadCronJobs() {
    if (!el.cronJobsList) return;
    try {
      const resp = await fetch('/api/cron/jobs');
      const data = await resp.json();
      const jobs = data.jobs || [];
      if (jobs.length === 0) {
        el.cronJobsList.innerHTML = '<div class="rag-empty">还没有定时任务。点击右上角创建。</div>';
        return;
      }
      el.cronJobsList.innerHTML = '';
      for (const j of jobs) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const nextRun = j.next_run ? new Date(j.next_run * 1000).toLocaleString('zh-CN') : '-';
        const lastRun = j.last_run ? new Date(j.last_run * 1000).toLocaleString('zh-CN') : '从未';
        const enabled = j.enabled === 1 || j.enabled === true;
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(j.name || j.id)}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${enabled ? '#10a37f' : '#8e8e8e'};">${enabled ? '启用' : '禁用'}</span>
            <button class="ghost-btn" style="margin-left:auto; padding:4px 10px; font-size:12px;" data-act="toggle">${enabled ? '禁用' : '启用'}</button>
            <button class="ghost-btn" style="padding:4px 10px; font-size:12px;" data-act="run">立即运行</button>
            <button class="skill-delete">删除</button>
          </div>
          <div class="skill-item-desc" style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
            <b>调度:</b> ${escapeHtml(j.schedule)} (${j.kind}) · <b>下次:</b> ${nextRun} · <b>上次:</b> ${lastRun} · <b>已运行:</b> ${j.run_count || 0} 次
          </div>
          <div class="skill-item-desc" style="padding:6px 8px; background:rgba(255,255,255,0.03); border-radius:4px;">
            <b>Prompt:</b> ${escapeHtml((j.prompt || '').slice(0, 300))}
          </div>`;
        item.querySelector('[data-act="toggle"]').addEventListener('click', async () => {
          await fetch(`/api/cron/jobs/${j.id}/update`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ enabled: !enabled }),
          });
          toast(enabled ? '已禁用' : '已启用', 'success');
          loadCronJobs();
        });
        item.querySelector('[data-act="run"]').addEventListener('click', async () => {
          const r = await fetch(`/api/cron/jobs/${j.id}/run`, { method: 'POST' });
          const d = await r.json();
          if (d.session_id) {
            toast('已立即触发，可在后台会话页面查看结果', 'success');
          } else {
            toast('触发失败', 'error');
          }
        });
        item.querySelector('.skill-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除定时任务 ${j.name}？`))) return;
          await fetch(`/api/cron/jobs/${j.id}/delete`, { method: 'POST' });
          toast('已删除', 'success');
          loadCronJobs();
        });
        el.cronJobsList.appendChild(item);
      }
    } catch (e) {
      el.cronJobsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadCronRuns() {
    if (!el.cronRunsList) return;
    try {
      const resp = await fetch('/api/cron/runs?limit=20');
      const data = await resp.json();
      const runs = data.runs || [];
      if (runs.length === 0) {
        el.cronRunsList.innerHTML = '<div class="rag-empty">还没有执行记录</div>';
        return;
      }
      el.cronRunsList.innerHTML = '';
      for (const r of runs) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const started = r.started_at ? new Date(r.started_at * 1000).toLocaleString('zh-CN') : '-';
        const statusColor = r.status === 'completed' ? '#10a37f' : r.status === 'running' ? '#a8c7fa' : '#ef4444';
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name" style="font-size:13px;">${escapeHtml(r.session_id || r.id)}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${statusColor};">${r.status}</span>
          </div>
          <div class="skill-item-desc" style="font-size:12px; color:var(--text-muted);">
            ${started} · 任务: ${escapeHtml(r.job_id)}
          </div>`;
        el.cronRunsList.appendChild(item);
      }
    } catch (e) {
      el.cronRunsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function createCronJob() {
    const name = await uiPrompt('任务名称（如：每日简报）：');
    if (!name) return;
    const kind = await uiPrompt('类型（cron / one_time / fixed_rate，默认 cron）：') || 'cron';
    let schedule = '';
    if (kind === 'cron') {
      schedule = await uiPrompt('Cron 表达式（5 字段：分 时 日 月 周，如 "47 6 * * *" = 每天 6:47）：');
    } else if (kind === 'one_time') {
      schedule = await uiPrompt('执行时间（epoch 毫秒，如 1785048466000）：');
    } else {
      schedule = await uiPrompt('间隔秒数（如 3600 = 每小时）：');
    }
    if (!schedule) return;
    const prompt_text = await uiPrompt('要执行的 prompt（AI 会收到这段话作为任务）：');
    if (!prompt_text) return;
    try {
      const resp = await fetch('/api/cron/jobs/create', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, kind, schedule, prompt: prompt_text }),
      });
      const data = await resp.json();
      if (data.id) {
        toast(`已创建定时任务: ${name}`, 'success');
        loadCronJobs();
      } else {
        toast(`创建失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('创建失败: ' + e.message, 'error');
    }
  }

  
})();
