// Module: stream
// Auto-extracted from app.js
(function() {
// ===== Send / stream =====
  function buildApiMessages(conv) {
    const msgs = [];
    for (const m of conv.messages) {
      if (m.role === 'user' || m.role === 'assistant') {
        if (m.content && m.content.trim()) {
          msgs.push({ role: m.role, content: m.content });
        }
      }
    }
    return msgs;
  }

  async function sendMessage() {
    const text = el.composerInput.value.trim();
    if ((!text && state.attachments.length === 0) || state.streaming) return;

    let conv = currentConversation();
    if (!conv) {
      conv = { id: uid(), title: '新对话', messages: [], createdAt: Date.now(), updatedAt: Date.now(), temporary: state.temporary };
      state.conversations.unshift(conv);
      state.currentId = conv.id;
    }

    // === Auto-compress check: if conversation is too long, compress older messages ===
    if (state.settings.compress_enabled && conv.messages.length >= 12 && !state.temporary) {
      try {
        const checkResp = await fetch('/api/conversations/auto-compress-check', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ messages: conv.messages.map(m => ({role: m.role, content: m.content})) }),
        });
        const checkData = await checkResp.json();
        if (checkData.should_compress) {
          // Compress and replace older messages with summary
          const compressResp = await fetch('/api/conversations/compress', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
              messages: conv.messages.map(m => ({role: m.role, content: m.content})),
              keep_recent: checkData.keep_recent,
            }),
          });
          const compressData = await compressResp.json();
          if (compressData.summary && compressData.kept_messages) {
            // Replace conversation: summary message + kept recent messages
            conv.messages = [
              { id: uid(), role: 'system', content: `[对话摘要] ${compressData.summary}`, createdAt: Date.now() },
              ...compressData.kept_messages.map(m => ({ id: uid(), role: m.role, content: m.content, createdAt: Date.now() })),
            ];
            toast(`已自动压缩对话（${compressData.compressed_count} 条 → 摘要）`, 'success');
            renderConversation();
          }
        }
      } catch (e) {
        console.warn('compress check failed', e);
      }
    }

    // Parse attachments into message-friendly format
    const msgAttachments = [...state.attachments];
    let userContent = text;

    // For text files, append content inline so the LLM can read it
    if (msgAttachments.length > 0) {
      const parsedTexts = [];
      for (const a of msgAttachments) {
        if (a.type === 'file') {
          try {
            const r = await fetch('/api/attachments/parse', {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ path: a.path, name: a.name, mime: a.mime }),
            });
            const parsed = await r.json();
            if (parsed.kind === 'text' && parsed.content) {
              parsedTexts.push(`\n\n--- 附件 ${a.name} ---\n${parsed.content}\n--- 附件结束 ---`);
            }
          } catch (e) { console.warn('parse attachment failed', e); }
        }
      }
      userContent = text + parsedTexts.join('');
    }

    conv.messages.push({
      role: 'user',
      content: userContent,
      attachments: msgAttachments,
      createdAt: Date.now(),
    });
    if (conv.title === '新对话') {
      conv.title = text.slice(0, 28) + (text.length > 28 ? '…' : '');
    }
    conv.updatedAt = Date.now();
    saveState();
    renderHistory();

    // Clear input + attachments
    el.composerInput.value = '';
    state.attachments = [];
    renderAttachments();
    autoResize();

    renderConversation();
    await streamAssistant(conv);
  }

  async function regenerateMessage(idx) {
    if (state.streaming) return;
    const conv = currentConversation();
    if (!conv) return;
    if (conv.messages[idx].role !== 'assistant') return;
    conv.messages.splice(idx, 1);
    conv.updatedAt = Date.now();
    saveState();
    renderConversation();
    await streamAssistant(conv);
  }

  function editUserMessage(idx, bubbleEl) {
    if (state.streaming) { toast('请等待当前回复完成'); return; }
    const conv = currentConversation();
    if (!conv) return;
    const m = conv.messages[idx];
    if (m.role !== 'user') return;
    // Already in edit mode? Skip
    if (bubbleEl.classList.contains('editing')) return;
    // Remove any existing edit action row
    const wrap = bubbleEl.parentElement;
    const existingRow = wrap.querySelector('.edit-action-row');
    if (existingRow) existingRow.remove();
    // Enter edit mode
    bubbleEl.classList.add('editing');
    bubbleEl.setAttribute('contenteditable', 'true');
    bubbleEl.focus();
    // Select all
    const range = document.createRange();
    range.selectNodeContents(bubbleEl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    // Add a small action row below
    const actionRow = document.createElement('div');
    actionRow.className = 'msg-toolbar edit-action-row';
    actionRow.style.opacity = '1';
    actionRow.style.justifyContent = 'flex-end';
    actionRow.innerHTML = `
      <button class="toolbar-btn" data-action="cancel" title="取消" style="width:auto;padding:0 10px;font-size:13px;">取消</button>
      <button class="toolbar-btn" data-action="save" title="保存并发送" style="width:auto;padding:0 10px;font-size:13px;color:var(--accent-blue);">保存并发送</button>`;
    wrap.appendChild(actionRow);

    function exitEdit() {
      bubbleEl.classList.remove('editing');
      bubbleEl.setAttribute('contenteditable', 'false');
      bubbleEl.textContent = m.content;
      actionRow.remove();
    }

    actionRow.querySelector('[data-action="cancel"]').addEventListener('click', exitEdit);
    actionRow.querySelector('[data-action="save"]').addEventListener('click', async () => {
      const newText = bubbleEl.textContent.trim();
      if (!newText || newText === m.content) { exitEdit(); return; }
      // Update message, remove all messages after this one, re-stream
      m.content = newText;
      // Truncate conversation to this user message
      conv.messages = conv.messages.slice(0, idx + 1);
      conv.updatedAt = Date.now();
      saveState();
      renderConversation();
      await streamAssistant(conv);
    });

    bubbleEl.addEventListener('keydown', function handler(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        actionRow.querySelector('[data-action="save"]').click();
        bubbleEl.removeEventListener('keydown', handler);
      } else if (e.key === 'Escape') {
        exitEdit();
        bubbleEl.removeEventListener('keydown', handler);
      }
    });
  }

  function deleteUserMessage(idx) {
    if (state.streaming) { toast('请等待当前回复完成'); return; }
    const conv = currentConversation();
    if (!conv) return;
    const m = conv.messages[idx];
    if (m.role !== 'user') return;
    // Delete this user message and any following messages until next user message
    let endIdx = idx + 1;
    while (endIdx < conv.messages.length && conv.messages[endIdx].role !== 'user') endIdx++;
    conv.messages.splice(idx, endIdx - idx);
    conv.updatedAt = Date.now();
    saveState();
    renderHistory();
    renderConversation();
    toast('已删除', 'success');
  }

  async function streamAssistant(conv) {
    const assistantMsg = { role: 'assistant', content: '', reasoning: '' };
    conv.messages.push(assistantMsg);
    conv.updatedAt = Date.now();

    el.welcome.style.display = 'none';

    const msgEl = document.createElement('div');
    msgEl.className = 'msg msg-assistant streaming';
    const contentEl = document.createElement('div');
    contentEl.className = 'content stream-caret';
    contentEl.innerHTML = '<span style="color:var(--text-muted)">思考中…</span>';
    msgEl.appendChild(contentEl);
    el.conversationInner.appendChild(msgEl);

    // Thinking panel
    let thinkPanel = null, thinkBody = null, thinkHeader = null;
    if (state.settings.enable_thinking) {
      thinkPanel = document.createElement('div');
      thinkPanel.className = 'thinking-panel';
      thinkPanel.innerHTML = `
        <div class="thinking-header">
          <span class="think-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span>
          <span class="think-label">思考中…</span>
          <span class="think-toggle">收起 ▴</span>
        </div>
        <div class="thinking-body"></div>`;
      thinkHeader = thinkPanel.querySelector('.thinking-header');
      thinkBody = thinkPanel.querySelector('.thinking-body');
      thinkHeader.addEventListener('click', () => {
        thinkPanel.classList.toggle('collapsed');
        thinkPanel.querySelector('.think-toggle').textContent = thinkPanel.classList.contains('collapsed') ? '展开 ▾' : '收起 ▴';
      });
      msgEl.insertBefore(thinkPanel, contentEl);
    }

    scrollToBottom(true);

    state.streaming = true;
    state.abortCtrl = new AbortController();
    el.btnSend.style.display = 'none';
    el.btnStop.style.display = 'flex';

    const apiMessages = buildApiMessages(conv);
    const stopSeqs = state.settings.stop_sequences
      ? state.settings.stop_sequences.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const payload = {
      messages: apiMessages,
      attachments: conv.messages[conv.messages.length - 2]?.attachments || [],
      temperature: state.settings.temperature,
      top_p: state.settings.top_p,
      top_k: state.settings.top_k,
      max_tokens: state.settings.max_tokens,
      thinking_budget: state.settings.thinking_budget,
      presence_penalty: state.settings.presence_penalty,
      frequency_penalty: state.settings.frequency_penalty,
      enable_thinking: state.settings.enable_thinking,
      stop: stopSeqs,
      system_prompt: state.settings.system_prompt,
      enable_memory: state.settings.enable_memory,
      temporary: state.temporary,
      personality: state.settings.personality,
      enable_tools: !state.temporary,  // enable tools in normal mode
      conversation_id: state.temporary ? null : conv.id,  // for title generation
      resident: state.resident || null,  // 指定回复的居民（null=自动选择）
    };

    let thinkingStart = null;
    let renderRAF = null;
    let lastEnhanceTime = 0;
    function scheduleRender() {
      if (renderRAF) return;
      renderRAF = requestAnimationFrame(() => {
        renderRAF = null;
        if (thinkBody) thinkBody.scrollTop = thinkBody.scrollHeight;
        contentEl.innerHTML = renderMarkdown(assistantMsg.content || '');
        // Only run enhanceContent (code blocks, KaTeX) every 500ms during streaming
        // to avoid performance issues with long content
        const now = Date.now();
        if (now - lastEnhanceTime > 500) {
          enhanceContent(contentEl);
          lastEnhanceTime = now;
        }
        scrollToBottom();
      });
    }

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload),
        signal: state.abortCtrl.signal,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (!resp.body) throw new Error('No response body');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let firstDelta = true;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          let evType = 'message';
          let dataStr = '';
          chunk.split('\n').forEach(line => {
            if (line.startsWith('event:')) evType = line.slice(6).trim();
            else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
          });
          if (!dataStr) continue;
          let data;
          try { data = JSON.parse(dataStr); } catch { continue; }

          if (evType === 'resident') {
            // Resident info — store prefix to display at start of message
            assistantMsg.resident = data;
            if (data.prefix) {
              contentEl.innerHTML = `<span class="resident-prefix">${escapeHtml(data.prefix)}</span>`;
            }
          } else if (evType === 'discussion') {
            // Multi-resident discussion — show each resident's message
            const messages = data.messages || [];
            if (messages.length > 0) {
              contentEl.innerHTML = '<div class="discussion-panel"><div class="discussion-label">🗣️ 居民讨论</div></div>';
              const panel = contentEl.querySelector('.discussion-panel');
              for (const msg of messages) {
                const msgEl = document.createElement('div');
                msgEl.className = 'discussion-message';
                msgEl.innerHTML = escapeHtml(msg).replace(/\n/g, '<br>');
                panel.appendChild(msgEl);
              }
              const summaryEl = document.createElement('div');
              summaryEl.className = 'discussion-summary';
              summaryEl.textContent = '正在综合讨论结果...';
              panel.appendChild(summaryEl);
              scrollToBottom();
            }
          } else if (evType === 'thinking' && thinkBody) {
            if (!thinkingStart) thinkingStart = Date.now();
            assistantMsg.reasoning += data.text || '';
            thinkBody.textContent = assistantMsg.reasoning;
            thinkBody.scrollTop = thinkBody.scrollHeight;
            scrollToBottom();
          } else if (evType === 'tool_start') {
            // Show tool call panel
            if (firstDelta) {
              firstDelta = false;
              contentEl.innerHTML = assistantMsg.resident?.prefix ? `<span class="resident-prefix">${escapeHtml(assistantMsg.resident.prefix)}</span>` : '';
              if (thinkHeader) {
                thinkHeader.classList.add('done');
                thinkPanel.classList.add('collapsed');
                thinkPanel.querySelector('.think-toggle').textContent = '展开 ▾';
              }
            }
            // Save tool call to message for persistence
            if (!assistantMsg.toolCalls) assistantMsg.toolCalls = [];
            assistantMsg.toolCalls.push({ id: data.id, name: data.name, args: data.args, result: null });

            const toolPanel = document.createElement('div');
            toolPanel.className = 'tool-panel';
            toolPanel.dataset.toolId = data.id;
            const toolMeta = getToolMeta(data.name);
            toolPanel.innerHTML = `
              <div class="tool-header">
                <span class="tool-icon">${toolMeta.icon}</span>
                <span class="tool-name">${toolMeta.label}</span>
                <span class="tool-status">执行中…</span>
              </div>
              <div class="tool-args">${escapeHtml(JSON.stringify(data.args, null, 2))}</div>
              <div class="tool-result" style="display:none"></div>`;
            msgEl.insertBefore(toolPanel, contentEl);
            scrollToBottom();
          } else if (evType === 'tool_end') {
            // Save result to message for persistence
            if (assistantMsg.toolCalls && assistantMsg.toolCalls.length > 0) {
              const last = assistantMsg.toolCalls[assistantMsg.toolCalls.length - 1];
              if (last.id === data.id) {
                last.result = data.result;
              }
            }
            const toolPanel = msgEl.querySelector(`.tool-panel[data-tool-id="${data.id}"]`);
            if (toolPanel) {
              const result = data.result;
              const statusEl = toolPanel.querySelector('.tool-status');
              const resultEl = toolPanel.querySelector('.tool-result');
              if (result.success) {
                statusEl.textContent = '✓ 完成';
                statusEl.style.color = '#10b981';
              } else {
                statusEl.textContent = '✗ 失败';
                statusEl.style.color = '#ef4444';
              }
              resultEl.style.display = 'block';
              resultEl.textContent = result.result || result.error || '(no output)';
              // Make panel collapsible after execution
              const header = toolPanel.querySelector('.tool-header');
              header.style.cursor = 'pointer';
              header.addEventListener('click', () => {
                toolPanel.classList.toggle('collapsed');
              });
              // Auto-collapse after showing
              setTimeout(() => toolPanel.classList.add('collapsed'), 100);
            }
            scrollToBottom();
          } else if (evType === 'title') {
            // Update conversation title
            if (data.conversation_id && data.title) {
              const c = state.conversations.find(c => c.id === data.conversation_id);
              if (c) {
                c.title = data.title;
                saveState();
                renderHistory();
              }
            }
          } else if (evType === 'delta') {
            if (firstDelta) {
              firstDelta = false;
              contentEl.innerHTML = assistantMsg.resident?.prefix ? `<span class="resident-prefix">${escapeHtml(assistantMsg.resident.prefix)}</span>` : '';
              if (thinkHeader) {
                thinkHeader.classList.add('done');
                const dur = thinkingStart ? ((Date.now() - thinkingStart) / 1000).toFixed(1) : null;
                thinkHeader.querySelector('.think-label').textContent = dur ? `思考了 ${dur} 秒` : '思考过程';
                thinkPanel.classList.add('collapsed');
                thinkPanel.querySelector('.think-toggle').textContent = '展开 ▾';
              }
            }
            assistantMsg.content += data.text || '';
            scheduleRender();
          } else if (evType === 'error') {
            throw new Error(data.message || 'Stream error');
          } else if (evType === 'done') {
            break;
          }
        }
      }

      // Final render
      contentEl.classList.remove('stream-caret');
      contentEl.innerHTML = renderMarkdown(assistantMsg.content || '');
      enhanceContent(contentEl);

      if (thinkHeader) {
        thinkHeader.classList.add('done');
        const dur = thinkingStart ? ((Date.now() - thinkingStart) / 1000).toFixed(1) : null;
        thinkHeader.querySelector('.think-label').textContent = dur ? `思考了 ${dur} 秒` : '思考过程';
      }
      msgEl.classList.remove('streaming');
      appendToolbar(msgEl, assistantMsg, conv.messages.length - 1);

      // Memory update: accumulate and batch — NOT every turn.
      // Only trigger memory edit after every 5 turns or 10 minutes since last update.
      if (state.settings.enable_memory && !state.temporary && assistantMsg.content) {
        const lastUser = conv.messages[conv.messages.length - 2];
        if (lastUser && lastUser.role === 'user') {
          // Track turn count and last memory update time
          if (!state._memoryTurnCount) state._memoryTurnCount = 0;
          if (!state._lastMemoryUpdate) state._lastMemoryUpdate = 0;
          state._memoryTurnCount++;
          const now = Date.now();
          const turnsSinceLast = state._memoryTurnCount;
          const timeSinceLast = (now - state._lastMemoryUpdate) / 1000; // seconds
          // Trigger: every 5 turns OR every 10 minutes (600s)
          const shouldUpdate = turnsSinceLast >= 5 || timeSinceLast >= 600;
          if (shouldUpdate) {
            // Gather recent conversation text (last 5 turns)
            const recentMsgs = conv.messages.slice(-10);
            const convText = recentMsgs.map(m =>
              `${m.role === 'user' ? '用户' : '助手'}: ${m.content.slice(0, 500)}`
            ).join('\n\n');
            const useEdit = state.settings.memory_auto_summary !== false;
            const endpoint = useEdit ? '/api/memory/edit' : '/api/memory/extract';
            fetch(endpoint, {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ text: convText }),
            }).then(r => r.json()).then(d => {
              state._memoryTurnCount = 0;
              state._lastMemoryUpdate = Date.now();
            }).catch(e => console.warn('memory update failed', e));
          }
        }
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        contentEl.classList.remove('stream-caret');
        contentEl.innerHTML = renderMarkdown(assistantMsg.content || '');
        if (thinkHeader) thinkHeader.classList.add('done');
        msgEl.classList.remove('streaming');
        if (assistantMsg.content) appendToolbar(msgEl, assistantMsg, conv.messages.length - 1);
        else conv.messages.pop();
      } else {
        console.error(err);
        contentEl.classList.remove('stream-caret');
        contentEl.innerHTML = `<div style="color:#c62828">⚠ 出错了：${escapeHtml(err.message)}</div>`;
        if (!assistantMsg.content) conv.messages.pop();
        toast('生成失败：' + err.message, 'error');
      }
    } finally {
      state.streaming = false;
      state.abortCtrl = null;
      el.btnSend.style.display = '';
      el.btnStop.style.display = 'none';
      saveState();
      renderHistory();
    }
  }

  function appendToolbar(msgEl, m, idx) {
    const toolbar = document.createElement('div');
    toolbar.className = 'msg-toolbar';
    toolbar.style.opacity = '1';
    toolbar.innerHTML = `
      <button class="toolbar-btn" data-action="copy"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
      <button class="toolbar-btn" data-action="good"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
      <button class="toolbar-btn" data-action="bad"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
      <button class="toolbar-btn" data-action="regenerate"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button>`;
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
    msgEl.appendChild(toolbar);
  }

  function stopStreaming() {
    if (state.abortCtrl) { state.abortCtrl.abort(); state.abortCtrl = null; }
  }

  
})();
