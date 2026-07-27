// Module: markdown
// Auto-extracted from app.js
(function() {
// ===== Markdown =====
  function configureMarked() {
    if (!window.marked) return;
    marked.setOptions({ breaks: true, gfm: true });
  }

  function renderMarkdown(text) {
    if (!window.marked) return escapeHtml(text).replace(/\n/g, '<br>');
    let processed = text || '';
    // Handle incomplete code blocks during streaming
    const codeFenceCount = (processed.match(/```/g) || []).length;
    if (codeFenceCount % 2 === 1) {
      processed += '\n```';
    }
    // Handle incomplete tables during streaming — if there's a | without closing newline
    // marked.js needs complete table rows to render tables
    // If the text ends mid-table-row (has | but no trailing newline), add one
    if (processed.includes('|') && !processed.endsWith('\n') && processed.lastIndexOf('|') > processed.lastIndexOf('\n')) {
      processed += '\n';
    }
    let raw = marked.parse(processed);
    if (window.DOMPurify) {
      // Allow all standard HTML elements that marked.js produces
      raw = DOMPurify.sanitize(raw, {
        ADD_ATTR: ['target', 'colspan', 'rowspan', 'align'],
        ADD_TAGS: ['table', 'thead', 'tbody', 'tr', 'th', 'td', 'pre', 'code', 'blockquote', 'hr', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'br', 'span', 'div', 'del', 's', 'sub', 'sup'],
      });
    }
    return raw;
  }

  function enhanceContent(container) {
    // Wrap <pre><code> with our code-block component
    container.querySelectorAll('pre > code').forEach((code) => {
      const pre = code.parentElement;
      if (pre.parentElement && pre.parentElement.classList.contains('code-block')) return;
      let lang = '';
      const classes = (code.className || '').split(/\s+/);
      for (const c of classes) { if (c.startsWith('language-')) { lang = c.slice(9); break; } }
      const wrap = document.createElement('div');
      wrap.className = 'code-block';
      const header = document.createElement('div');
      header.className = 'code-block-header';
      const langLabel = document.createElement('span');
      langLabel.textContent = lang || 'code';
      const copyBtn = document.createElement('button');
      copyBtn.className = 'code-block-copy';
      copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>复制</span>`;
      copyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        navigator.clipboard.writeText(code.textContent || '');
        copyBtn.querySelector('span').textContent = '已复制';
        setTimeout(() => copyBtn.querySelector('span').textContent = '复制', 1500);
      });
      header.appendChild(langLabel);
      header.appendChild(copyBtn);
      pre.parentElement.insertBefore(wrap, pre);
      wrap.appendChild(header);
      wrap.appendChild(pre);
      if (window.hljs) { try { hljs.highlightElement(code); } catch (e) {} }
    });
    // Make links open in new tab
    container.querySelectorAll('a[href]').forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
    // KaTeX
    if (window.renderMathInElement) {
      try {
        renderMathInElement(container, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '\\[', right: '\\]', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\(', right: '\\)', display: false},
          ],
          throwOnError: false,
        });
      } catch (e) {}
    }
  }

  
})();
