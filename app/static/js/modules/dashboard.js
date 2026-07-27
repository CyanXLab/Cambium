// Module: dashboard
// Auto-extracted from app.js
(function() {
// ===== Memory Dashboard =====
  async function loadDashboard() {
    await Promise.all([
      loadDashboardStats(),
      loadDashboardMemories(),
      loadDashboardKG(),
      loadDashboardEpisodes(),
      loadDashboardReflections(),
      loadDashboardMetaCog(),
    ]);
  }

  async function loadDashboardStats() {
    if (!el.dashboardStats) return;
    try {
      const [memResp, vsResp] = await Promise.all([
        fetch('/api/memory-dashboard'),
        fetch('/api/v2/vector-store/status').catch(() => null),
      ]);
      const data = await memResp.json();
      const vs = vsResp ? await vsResp.json() : {};
      const o = data.orchestrator || {};
      const kg = data.knowledge_graph || {};
      const ep = data.episodes || {};
      const mc = data.meta_cognition || {};
      const cv = data.chat_vectors || {};
      const cards = [
        { label: '总记忆数', value: o.total_memories || 0, color: '#a8c7fa' },
        { label: '永久记忆', value: (o.by_layer || {}).permanent?.count || 0, color: '#10a37f' },
        { label: '长期记忆', value: (o.by_layer || {}).long_term?.count || 0, color: '#10b981' },
        { label: '短期记忆', value: (o.by_layer || {}).short_term?.count || 0, color: '#f59e0b' },
        { label: '知识图谱实体', value: kg.entities || 0, color: '#8b5cf6' },
        { label: '知识图谱关系', value: kg.relations || 0, color: '#8b5cf6' },
        { label: '事件记忆', value: ep.total || 0, color: '#ec4899' },
        { label: '反思次数', value: o.reflections_count || 0, color: '#06b6d4' },
        { label: '元认知检查', value: mc.total_evaluations || 0, color: '#a8c7fa' },
        { label: '平均信心度', value: Math.round((mc.avg_confidence || 0) * 100) + '%', color: '#10a37f' },
        { label: '聊天向量片段', value: cv.total_chunks || 0, color: '#f59e0b' },
        { label: '活跃目标', value: o.active_goals || 0, color: '#a8c7fa' },
      ];
      el.dashboardStats.innerHTML = cards.map(c => `
        <div style="background:var(--bg-elevated); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:14px;">
          <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em;">${c.label}</div>
          <div style="font-size:24px; font-weight:600; color:${c.color}; margin-top:4px;">${c.value}</div>
        </div>
      `).join('');

      // Vector store status banner
      if (vs.current_backend) {
        const statusColor = vs.has_real_embeddings ? '#10a37f' : '#f59e0b';
        const statusText = vs.has_real_embeddings
          ? `向量模型已加载: ${vs.loaded_model || 'unknown'}`
          : `使用 ${vs.current_backend} (未加载真实向量模型)`;
        const hint = vs.has_real_embeddings ? '' : ` · ${vs.install_hint || ''}`;
        const banner = document.createElement('div');
        banner.style.cssText = 'margin-top:12px; padding:10px 14px; background:var(--bg-elevated); border:1px solid var(--border-subtle); border-radius:var(--radius-md); font-size:13px;';
        banner.innerHTML = `<span style="color:${statusColor};">●</span> <strong>向量检索后端:</strong> ${vs.current_backend} · <span style="color:${statusColor};">${statusText}</span>${hint}`;
        el.dashboardStats.appendChild(banner);
      }
    } catch (e) {
      el.dashboardStats.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadDashboardMemories() {
    if (!el.dashboardMemories) return;
    try {
      const filter = el.dashboardMemoryFilter ? el.dashboardMemoryFilter.value : '';
      const url = '/api/memory/list?limit=50' + (filter ? `&layer=${filter}` : '');
      const resp = await fetch(url);
      const data = await resp.json();
      const mems = data.memories || [];
      if (mems.length === 0) {
        el.dashboardMemories.innerHTML = '<div class="rag-empty">还没有分层记忆。多聊几句，AI 会自动评估重要度并分层存储。</div>';
        return;
      }
      const layerNames = { permanent: '永久', long_term: '长期', short_term: '短期', working: '工作' };
      const layerColors = { permanent: '#10a37f', long_term: '#10b981', short_term: '#f59e0b', working: '#8e8e8e' };
      el.dashboardMemories.innerHTML = mems.map(m => `
        <div class="skill-item">
          <div class="skill-item-header">
            <span class="skill-item-name" style="font-size:13px;">${escapeHtml(m.content.slice(0, 100))}${m.content.length > 100 ? '...' : ''}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${layerColors[m.layer] || '#8e8e8e'};">${layerNames[m.layer] || m.layer}</span>
            <span style="font-size:11px; color:var(--text-muted);">重要度 ${m.importance}</span>
            <span style="font-size:11px; color:var(--text-muted);">${m.category}</span>
            <span style="font-size:11px; color:var(--text-muted);">衰减 ${m.decay_weight.toFixed(2)}</span>
            <button class="skill-delete" data-mid="${m.id}">删除</button>
          </div>
        </div>
      `).join('');
      el.dashboardMemories.querySelectorAll('.skill-delete').forEach(btn => {
        btn.addEventListener('click', async () => {
          const mid = btn.dataset.mid;
          await fetch(`/api/memory/${mid}/delete`, { method: 'POST' });
          toast('已删除', 'success');
          loadDashboardMemories();
          loadDashboardStats();
        });
      });
    } catch (e) {
      el.dashboardMemories.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadDashboardKG() {
    if (!el.dashboardKG) return;
    try {
      const resp = await fetch('/api/kg/triples?limit=100');
      const data = await resp.json();
      const triples = data.triples || [];
      if (triples.length === 0) {
        el.dashboardKG.innerHTML = '<div class="rag-empty">还没有知识图谱三元组。后台反思时会自动从对话提取。</div>';
        return;
      }
      el.dashboardKG.innerHTML = triples.map(t => `
        <div class="skill-item">
          <div class="skill-item-header">
            <span class="skill-item-name" style="font-size:13px;">${escapeHtml(t.subject)} <span style="color:#8b5cf6;">—${escapeHtml(t.predicate)}→</span> ${escapeHtml(t.object)}</span>
            <span style="font-size:11px; color:var(--text-muted);">权重 ${t.weight.toFixed(1)}</span>
          </div>
        </div>
      `).join('');
    } catch (e) {
      el.dashboardKG.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadDashboardEpisodes() {
    if (!el.dashboardEpisodes) return;
    try {
      const resp = await fetch('/api/episodes?limit=50');
      const data = await resp.json();
      const eps = data.episodes || [];
      if (eps.length === 0) {
        el.dashboardEpisodes.innerHTML = '<div class="rag-empty">还没有事件记忆。后台反思时会自动从对话提取事件。</div>';
        return;
      }
      const statusColors = { completed: '#10a37f', ongoing: '#a8c7fa', planned: '#f59e0b', abandoned: '#8e8e8e' };
      el.dashboardEpisodes.innerHTML = eps.map(ep => `
        <div class="skill-item">
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(ep.title)}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${statusColors[ep.status] || '#8e8e8e'};">${ep.status}</span>
            <span style="font-size:11px; color:var(--text-muted);">重要度 ${ep.importance}</span>
            ${ep.occurred_at ? `<span style="font-size:11px; color:var(--text-muted);">${escapeHtml(ep.occurred_at)}</span>` : ''}
            <button class="skill-delete" data-eid="${ep.id}">删除</button>
          </div>
          ${ep.description ? `<div class="skill-item-desc" style="font-size:13px;">${escapeHtml(ep.description)}</div>` : ''}
          ${ep.tags ? `<div class="skill-item-desc" style="font-size:11px; color:var(--text-muted);">标签: ${escapeHtml(ep.tags)}</div>` : ''}
        </div>
      `).join('');
      el.dashboardEpisodes.querySelectorAll('.skill-delete').forEach(btn => {
        btn.addEventListener('click', async () => {
          const eid = btn.dataset.eid;
          await fetch(`/api/episodes/${eid}/delete`, { method: 'POST' });
          toast('已删除', 'success');
          loadDashboardEpisodes();
          loadDashboardStats();
        });
      });
    } catch (e) {
      el.dashboardEpisodes.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadDashboardReflections() {
    if (!el.dashboardReflections) return;
    try {
      const resp = await fetch('/api/reflections?limit=20');
      const data = await resp.json();
      const refs = data.reflections || [];
      if (refs.length === 0) {
        el.dashboardReflections.innerHTML = '<div class="rag-empty">还没有反思记录。每 30 条新消息后自动触发，或点上方"触发反思"手动运行。</div>';
        return;
      }
      el.dashboardReflections.innerHTML = refs.map(r => {
        const date = new Date(r.created_at * 1000).toLocaleString('zh-CN');
        const insights = r.insights ? r.insights.split('\n').filter(x => x.trim()).map(x => `<div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">• ${escapeHtml(x)}</div>`).join('') : '';
        return `
          <div class="skill-item">
            <div class="skill-item-header">
              <span class="skill-item-name" style="font-size:13px;">${escapeHtml(r.trigger)} 反思</span>
              <span style="font-size:11px; color:var(--text-muted);">${date}</span>
              <span style="font-size:11px; color:var(--text-muted);">${r.message_count_at_trigger} 条消息</span>
            </div>
            <div class="skill-item-desc">${escapeHtml(r.summary || '(无摘要)')}</div>
            ${insights}
          </div>
        `;
      }).join('');
    } catch (e) {
      el.dashboardReflections.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function loadDashboardMetaCog() {
    if (!el.dashboardMetaCog) return;
    try {
      const resp = await fetch('/api/meta-cognition/logs?limit=20');
      const data = await resp.json();
      const logs = data.logs || [];
      if (logs.length === 0) {
        el.dashboardMetaCog.innerHTML = '<div class="rag-empty">还没有元认知检查记录。每次 AI 回复后会自动自检。</div>';
        return;
      }
      el.dashboardMetaCog.innerHTML = logs.map(l => {
        const date = new Date(l.created_at * 1000).toLocaleString('zh-CN');
        const confPct = Math.round((l.confidence || 0) * 100);
        const confColor = confPct >= 70 ? '#10a37f' : confPct >= 40 ? '#f59e0b' : '#ef4444';
        return `
          <div class="skill-item">
            <div class="skill-item-header">
              <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${confColor};">信心 ${confPct}%</span>
              ${l.has_contradiction ? '<span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(239,68,68,0.15); color:#ef4444;">有矛盾</span>' : ''}
              ${l.needs_clarification ? '<span style="font-size:11px; color:#f59e0b;">需澄清</span>' : ''}
              ${l.needs_search ? '<span style="font-size:11px; color:#a8c7fa;">需搜索</span>' : ''}
              <span style="font-size:11px; color:var(--text-muted); margin-left:auto;">${date}</span>
            </div>
            <div class="skill-item-desc" style="font-size:12px;"><b>问:</b> ${escapeHtml((l.user_query || '').slice(0, 80))}</div>
            <div class="skill-item-desc" style="font-size:12px;"><b>自检:</b> ${escapeHtml(l.self_check || '')}</div>
            ${l.correction ? `<div class="skill-item-desc" style="font-size:12px; color:#f59e0b;"><b>修正:</b> ${escapeHtml(l.correction)}</div>` : ''}
          </div>
        `;
      }).join('');
    } catch (e) {
      el.dashboardMetaCog.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }


  
})();
