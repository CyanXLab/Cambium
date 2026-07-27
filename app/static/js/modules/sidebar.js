// Module: sidebar
// Auto-extracted from app.js
(function() {
// ===== Sidebar =====
  function toggleSidebarDesktop() {
    const collapsed = el.app.classList.toggle('sidebar-collapsed');
    // Clear any mobile state to avoid conflicts
    if (collapsed) el.app.classList.remove('sidebar-open');
    // Show/hide the expand button in topbar
    if (el.btnExpandSidebar) {
      el.btnExpandSidebar.style.display = collapsed ? 'flex' : 'none';
    }
  }
  function toggleSidebarMobile(open) {
    if (open === undefined) open = !el.app.classList.contains('sidebar-open');
    // Clear desktop collapsed state so it doesn't override mobile open
    el.app.classList.remove('sidebar-collapsed');
    el.app.classList.toggle('sidebar-open', open);
  }

  
})();
