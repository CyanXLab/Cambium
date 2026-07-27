// Module: chat
// Auto-extracted from app.js
(function() {
// ===== Conversation rendering =====
  function renderConversation() {
    const conv = currentConversation();
    el.conversationInner.innerHTML = '';
    if (!conv || conv.messages.length === 0) {
      el.conversationInner.appendChild(el.welcome);
      el.welcome.style.display = '';
      return;
    }
    conv.messages.forEach((m, idx) => {
      el.conversationInner.appendChild(buildMessageEl(m, idx));
    });
    // Auto-scroll on render
    setTimeout(() => scrollToBottom(true), 50);
    // Update right panel index
    if (typeof updateRightPanel === 'function') updateRightPanel();
  }

  function buildMessageEl(m, idx) {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg-' + m.role;
    wrap.dataset.idx = idx;

    if (m.role === 'user') {
      // Attachment thumbnails above the bubble
      if (m.attachments && m.attachments.length) {
        const atts = document.createElement('div');
        atts.className = 'msg-attachments';
        for (const a of m.attachments) {
          const att = document.createElement('div');
          att.className = 'msg-attachment';
          if (a.type === 'image') {
            att.innerHTML = `<img class="thumb" src="${a.path}" alt="${escapeHtml(a.name)}" /><span>${escapeHtml(a.name)}</span>`;
          } else {
            att.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>${escapeHtml(a.name)}</span>`;
          }
          atts.appendChild(att);
        }
        wrap.appendChild(atts);
      }
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = m.content;
      wrap.appendChild(bubble);

      // User message toolbar: copy / edit / delete
      const toolbar = document.createElement('div');
      toolbar.className = 'msg-toolbar';
      toolbar.innerHTML = `
        <button class="toolbar-btn" data-action="copy" title="复制"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
        <button class="toolbar-btn" data-action="edit" title="编辑"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
        <button class="toolbar-btn danger" data-action="delete" title="删除"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg></button>`;
      toolbar.querySelector('[data-action="copy"]').addEventListener('click', () => {
        navigator.clipboard.writeText(m.content || '');
        toast('已复制到剪贴板', 'success');
      });
      toolbar.querySelector('[data-action="edit"]').addEventListener('click', () => editUserMessage(idx, bubble));
      toolbar.querySelector('[data-action="delete"]').addEventListener('click', () => deleteUserMessage(idx));
      wrap.appendChild(toolbar);
      return wrap;
    }

    // assistant
    if (m.reasoning && m.reasoning.trim()) {
      const panel = document.createElement('div');
      panel.className = 'thinking-panel collapsed';
      panel.innerHTML = `
        <div class="thinking-header done">
          <span class="think-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span>
          <span class="think-label">思考过程</span>
          <span class="think-toggle">展开 ▾</span>
        </div>
        <div class="thinking-body">${escapeHtml(m.reasoning)}</div>`;
      panel.querySelector('.thinking-header').addEventListener('click', () => {
        panel.classList.toggle('collapsed');
        panel.querySelector('.think-toggle').textContent = panel.classList.contains('collapsed') ? '展开 ▾' : '收起 ▴';
      });
      wrap.appendChild(panel);
    }

    // Restore tool call history (if any)
    if (m.toolCalls && m.toolCalls.length > 0) {
      for (const tc of m.toolCalls) {
        const toolPanel = document.createElement('div');
        toolPanel.className = 'tool-panel collapsed';
        const toolMeta = getToolMeta(tc.name);
        const resultText = tc.result ? (typeof tc.result === 'string' ? tc.result : JSON.stringify(tc.result)) : '';
        const resultPreview = resultText.slice(0, 200);
        toolPanel.innerHTML = `
          <div class="tool-header" style="cursor:pointer;">
            <span class="tool-icon">${toolMeta.icon}</span>
            <span class="tool-name">${toolMeta.label}</span>
            <span class="tool-status" style="color:#10b981;">✓ 完成</span>
          </div>
          <div class="tool-args">${escapeHtml(JSON.stringify(tc.args, null, 2))}</div>
          <div class="tool-result">${escapeHtml(resultPreview)}${resultText.length > 200 ? '...' : ''}</div>`;
        toolPanel.querySelector('.tool-header').addEventListener('click', () => {
          toolPanel.classList.toggle('collapsed');
        });
        wrap.appendChild(toolPanel);
      }
    }

    const content = document.createElement('div');
    content.className = 'content';
    content.innerHTML = renderMarkdown(m.content || '');
    enhanceContent(content);
    wrap.appendChild(content);

    const toolbar = document.createElement('div');
    toolbar.className = 'msg-toolbar';
    toolbar.innerHTML = `
      <button class="toolbar-btn" data-action="copy" title="复制"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
      <button class="toolbar-btn" data-action="good" title="赞"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
      <button class="toolbar-btn" data-action="bad" title="踩"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
      <button class="toolbar-btn" data-action="regenerate" title="重新生成"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button>`;
    toolbar.querySelector('[data-action="copy"]').addEventListener('click', () => {
      navigator.clipboard.writeText(m.content || '');
      toast('已复制到剪贴板', 'success');
    });
    toolbar.querySelector('[data-action="good"]').addEventListener('click', (e) => {
      e.currentTarget.classList.toggle('active');
      toolbar.querySelector('[data-action="bad"]').classList.remove('active');
    });
    toolbar.querySelector('[data-action="bad"]').addEventListener('click', (e) => {
      e.currentTarget.classList.toggle('active');
      toolbar.querySelector('[data-action="good"]').classList.remove('active');
    });
    toolbar.querySelector('[data-action="regenerate"]').addEventListener('click', () => regenerateMessage(idx));
    wrap.appendChild(toolbar);
    return wrap;
  }

  
})();
