// Module: discoveries
// Auto-extracted from app.js
(function() {
// ===== Today Discoveries =====
  async function loadTodayDiscoveries() {
    if (!el.todayDiscoveries) return;
    try {
      const r = await fetch('/api/discoveries/today').then(r => r.json());
      const items = r.items || [];
      if (items.length === 0) {
        el.todayDiscoveries.style.display = 'none';
        return;
      }
      el.todayDiscoveries.style.display = '';
      if (el.todayDiscoveriesList) {
        el.todayDiscoveriesList.innerHTML = items.slice(0, 5).map(d => `
          <div class="discovery-item">
            <span class="discovery-type-badge ${d.type}">${d.type}</span>
            <div class="discovery-content">
              <div class="discovery-title">${escapeHtml(d.title)}</div>
              <div class="discovery-text">${escapeHtml(d.content.slice(0, 200))}${d.content.length > 200 ? '…' : ''}</div>
            </div>
          </div>`).join('');
      }
    } catch (e) {
      console.error('loadTodayDiscoveries failed', e);
    }
  }

  
})();
