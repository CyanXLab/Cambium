// Module: views
// Auto-extracted from app.js
(function() {
// ===== View switcher (today / chat / library / skills / sessions / cron / dashboard / inbox / journal / residents / artifacts / philosophy) =====
  function switchView(view) {
    el.mainApp.style.display = (view === 'chat') ? '' : 'none';
    if (el.libraryView) el.libraryView.style.display = (view === 'library') ? '' : 'none';
    if (el.skillsView) el.skillsView.style.display = (view === 'skills') ? '' : 'none';
    if (el.sessionsView) el.sessionsView.style.display = (view === 'sessions') ? '' : 'none';
    if (el.cronView) el.cronView.style.display = (view === 'cron') ? '' : 'none';
    if (el.dashboardView) el.dashboardView.style.display = (view === 'dashboard') ? '' : 'none';
    if (el.todayView) el.todayView.style.display = (view === 'today') ? '' : 'none';
    if (el.inboxView) el.inboxView.style.display = (view === 'inbox') ? '' : 'none';
    if (el.journalView) el.journalView.style.display = (view === 'journal') ? '' : 'none';
    if (el.residentsView) el.residentsView.style.display = (view === 'residents') ? '' : 'none';
    if (el.artifactsView) el.artifactsView.style.display = (view === 'artifacts') ? '' : 'none';
    if (el.philosophyView) el.philosophyView.style.display = (view === 'philosophy') ? '' : 'none';
    // Update nav active state
    el.navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.view === view);
    });
    if (view === 'today') loadTodayBriefing();
    if (view === 'library') loadRagFiles();
    if (view === 'skills') loadSkills();
    if (view === 'sessions') loadSessions();
    if (view === 'cron') { loadCronJobs(); loadCronRuns(); }
    if (view === 'dashboard') loadDashboard();
    if (view === 'inbox') loadInboxList();
    if (view === 'journal') loadJournalView();
    if (view === 'residents') loadResidentsView();
    if (view === 'artifacts') loadArtifactsView();
    if (view === 'philosophy') loadPhilosophyView();
  }

  
})();
