// Module: mcp
// Auto-extracted from app.js
(function() {
// ===== MCP server management =====
  async function refreshMcpServers() {
    if (!el.mcpServersList) return;
    try {
      const resp = await fetch('/api/mcp/servers');
      const data = await resp.json();
      const servers = data.servers || [];
      if (servers.length === 0) {
        el.mcpServersList.innerHTML = '<div class="rag-empty">还没有添加 MCP 服务器</div>';
        return;
      }
      el.mcpServersList.innerHTML = '';
      for (const s of servers) {
        const item = document.createElement('div');
        item.className = 'mcp-server-item';
        const status = s.connected ? 'connected' : 'unknown';
        const statusText = s.connected ? '已连接' : (s.error ? '错误' : '未连接');
        item.innerHTML = `
          <div class="mcp-server-info">
            <div class="mcp-server-name">${escapeHtml(s.name)} <span class="mcp-server-status ${status}">${statusText}</span></div>
            <div class="mcp-server-detail">${escapeHtml(s.command)}${s.tools && s.tools.length ? ' · ' + s.tools.length + ' 个工具' : ''}</div>
            ${s.error ? '<div class="mcp-server-detail" style="color:#ef4444;margin-top:4px;">' + escapeHtml(s.error) + '</div>' : ''}
          </div>
          <button class="rag-file-delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>`;
        item.querySelector('.rag-file-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除 MCP 服务器 ${s.name}？`))) return;
          await fetch('/api/mcp/servers/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name: s.name }),
          });
          toast('已删除', 'success');
          refreshMcpServers();
        });
        el.mcpServersList.appendChild(item);
      }
    } catch (e) {
      el.mcpServersList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function addMcpServer() {
    const name = (el.mcpAddName.value || '').trim();
    const command = (el.mcpAddCommand.value || '').trim();
    const envStr = (el.mcpAddEnv ? el.mcpAddEnv.value : '') || '';
    if (!name || !command) {
      toast('名称和命令不能为空', 'error');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(name)) {
      toast('名称只能包含小写字母、数字和短横线', 'error');
      return;
    }
    const env = {};
    if (envStr) {
      for (const pair of envStr.split(',')) {
        const [k, ...v] = pair.split('=');
        if (k) env[k.trim()] = v.join('=').trim();
      }
    }
    try {
      const resp = await fetch('/api/mcp/servers/add', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, command, env }),
      });
      const data = await resp.json();
      if (data.ok) {
        el.mcpAddName.value = '';
        el.mcpAddCommand.value = '';
        el.mcpAddEnv.value = '';
        toast(`已添加: ${name}`, 'success');
        refreshMcpServers();
      } else {
        toast(`添加失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('添加失败: ' + e.message, 'error');
    }
  }

  
})();
