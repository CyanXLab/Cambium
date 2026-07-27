/* ============================================================
   Cambium — frontend logic (cognitive layer) (v2)
   Features: attachments, memory, multi-param settings, streaming
   ============================================================ */
(() => {
  'use strict';

  // ===== Tool label/icon lookup =====
  const TOOL_META = {
    // Time
    'get_current_time':  { icon: '🕐', label: '获取时间' },
    // Code execution
    'run_python':        { icon: '🐍', label: 'Python 执行' },
    'run_shell':         { icon: '⌨️', label: 'Shell 命令' },
    'install_package':   { icon: '📦', label: '安装包' },
    // File operations
    'read_file':         { icon: '📄', label: '读取文件' },
    'write_file':        { icon: '📝', label: '写入文件' },
    'edit_file':         { icon: '✏️', label: '修改文件' },
    'str_replace':       { icon: '🔁', label: '字符串替换' },
    'regex_replace':     { icon: '🔍', label: '正则替换' },
    'multi_edit':        { icon: '✨', label: '批量编辑' },
    'apply_patch':       { icon: '🩹', label: '应用补丁' },
    'file_append':       { icon: '➕', label: '追加内容' },
    'file_prepend':      { icon: '⬆️', label: '前置内容' },
    'insert_lines':      { icon: '📥', label: '插入行' },
    'delete_lines':      { icon: '🗑️', label: '删除行' },
    'file_move':         { icon: '🚚', label: '移动/重命名' },
    'file_copy':         { icon: '📋', label: '复制文件' },
    'delete_file':       { icon: '❌', label: '删除文件' },
    'make_directory':    { icon: '📁', label: '创建目录' },
    'file_stat':         { icon: '📊', label: '文件信息' },
    'file_tree':         { icon: '🌳', label: '目录树' },
    'list_directory':    { icon: '📂', label: '列出目录' },
    // Search
    'grep':              { icon: '🔎', label: '内容搜索' },
    'glob':              { icon: '🌐', label: '文件匹配' },
    // Web
    'web_search':        { icon: '🌐', label: '网络搜索' },
    'web_fetch':         { icon: '🌍', label: '抓取网页' },
    // Workflow
    'todo_write':        { icon: '✅', label: '更新待办' },
    'plan_write':        { icon: '📋', label: '保存计划' },
    // Skills self-evolution
    'skill_create':      { icon: '🧠', label: '创建技能' },
    'skill_update':      { icon: '🔄', label: '更新技能' },
    'skill_read':        { icon: '📖', label: '读取技能' },
    'skill_list':        { icon: '📚', label: '列出技能' },
    'save_custom_tool':  { icon: '🛠️', label: '保存工具' },
    'run_custom_tool':   { icon: '⚙️', label: '调用工具' },
    'list_custom_tools': { icon: '🧰', label: '列出工具' },
    // Sessions
    'sessions_list':     { icon: '🗂️', label: '会话列表' },
    'session_status':    { icon: '📈', label: '会话状态' },
    'sessions_history':  { icon: '📜', label: '会话历史' },
    'sessions_spawn':    { icon: '🚀', label: '启动子会话' },
    'sessions_send':     { icon: '💬', label: '会话通信' },
    // Memory
    'memory_search':     { icon: '💭', label: '检索记忆' },
    'memory_add':        { icon: '➕', label: '添加记忆' },
    // Default
    '_default':          { icon: '🔧', label: '工具调用' },
  };
  function getToolMeta(name) {
    return TOOL_META[name] || TOOL_META['_default'];
  }

  // ===== State =====
  const state = {
    conversations: [],
    currentId: null,
    streaming: false,
    abortCtrl: null,
    attachments: [],
    temporary: false,  // temporary chat mode
    settings: {
      system_prompt: '',
      temperature: 0.7,
      top_p: 0.95,
      top_k: 0,
      max_tokens: 4096,
      thinking_budget: 0,
      presence_penalty: 0,
      frequency_penalty: 0,
      enable_thinking: false,
      enable_memory: true,
      memory_auto_extract: true,
      memory_auto_summary: true,
      memory_inject_count: 5,
      stop_sequences: '',
      user_name: '',
      user_persona: '',
      user_occupation: '',
      user_details: '',
      personality: 'default',
      api_delay: 1,
      api_key: '',
      api_base_url: '',
      model_slots: ['Qwen/Qwen3.5-397B-A17B', 'Qwen/Qwen3.5-122B-A10B', '', '', ''],
      selected_model: '',
      theme_appearance: 'dark',
      theme_contrast: 'default',
      accent_color: 'default',
      language: 'auto',
      // RAG
      rag_enabled: true,
      rag_count: 3,
      // MCP
      mcp_enabled: true,
      // Skills
      skills_enabled: true,
      skills_mode: 'auto',
      // Multi-model division
      memory_api_key: '',
      memory_api_base_url: '',
      memory_api_model: '',
      subtask_api_key: '',
      subtask_api_base_url: '',
      subtask_api_model: '',
      max_subtasks: 3,
      rag_embedding_provider: 'local',
      rag_embedding_api_key: '',
      rag_embedding_api_base_url: '',
      rag_embedding_model: '',
      // Sessions / Cron
      sessions_enabled: true,
      cron_enabled: true,
      // Conversation enhancement
      compress_enabled: true,
      compress_threshold_tokens: 8000,
      compress_keep_recent: 6,
      chat_vectors_enabled: true,
      chat_vectors_search_top_k: 5,
      emotion_tracking_enabled: true,
      profile_auto_update: true,
      proactive_recall: true,
      emotional_resonance: true,
      // Backup API
      backup_api_enabled: false,
      backup_api_key: '',
      backup_api_base_url: 'http://127.0.0.1:8000/v1',
      backup_api_model: '',
    },
  };

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  // ===== Custom UI Modal (replaces alert/confirm/prompt) =====
  function uiAlert(message, title = '提示') {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.style.display = '';
      overlay.innerHTML = `
        <div class="modal" style="max-width:420px;">
          <div class="modal-header">
            <h2>${escapeHtml(title)}</h2>
            <button class="modal-close">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div style="white-space:pre-wrap; line-height:1.6; color:var(--text-primary);">${escapeHtml(message)}</div>
          </div>
          <div style="padding:0 20px 20px; text-align:right;">
            <button class="primary-btn ui-modal-ok">确定</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const close = () => { overlay.remove(); resolve(); };
      overlay.querySelector('.modal-close').addEventListener('click', close);
      overlay.querySelector('.ui-modal-ok').addEventListener('click', close);
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    });
  }

  function uiConfirm(message, title = '确认') {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.style.display = '';
      overlay.innerHTML = `
        <div class="modal" style="max-width:380px;">
          <div class="modal-header">
            <h2>${escapeHtml(title)}</h2>
            <button class="modal-close">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div style="white-space:pre-wrap; line-height:1.6; color:var(--text-primary);">${escapeHtml(message)}</div>
          </div>
          <div style="padding:0 20px 20px; display:flex; gap:8px; justify-content:flex-end;">
            <button class="ghost-btn ui-modal-cancel">取消</button>
            <button class="danger-btn ui-modal-ok">确认</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const close = (result) => { overlay.remove(); resolve(result); };
      overlay.querySelector('.modal-close').addEventListener('click', () => close(false));
      overlay.querySelector('.ui-modal-cancel').addEventListener('click', () => close(false));
      overlay.querySelector('.ui-modal-ok').addEventListener('click', () => close(true));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
    });
  }

  function uiPrompt(message, defaultValue = '', title = '输入') {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.style.display = '';
      overlay.innerHTML = `
        <div class="modal" style="max-width:380px;">
          <div class="modal-header">
            <h2>${escapeHtml(title)}</h2>
            <button class="modal-close">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div style="margin-bottom:12px; color:var(--text-primary); white-space:pre-wrap;">${escapeHtml(message)}</div>
            <input type="text" class="text-input ui-modal-input" value="${escapeHtml(defaultValue)}" style="width:100%;" />
          </div>
          <div style="padding:0 20px 20px; display:flex; gap:8px; justify-content:flex-end;">
            <button class="ghost-btn ui-modal-cancel">取消</button>
            <button class="primary-btn ui-modal-ok">确定</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const input = overlay.querySelector('.ui-modal-input');
      input.focus();
      input.select();
      const close = (result) => { overlay.remove(); resolve(result); };
      overlay.querySelector('.modal-close').addEventListener('click', () => close(null));
      overlay.querySelector('.ui-modal-cancel').addEventListener('click', () => close(null));
      overlay.querySelector('.ui-modal-ok').addEventListener('click', () => close(input.value));
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') close(input.value); if (e.key === 'Escape') close(null); });
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
    });
  }

  const el = {
    app: $('#app'),
    sidebar: $('#sidebar'),
    sidebarBackdrop: $('#sidebarBackdrop'),
    btnToggleSidebar: $('#btnToggleSidebar'),
    btnExpandSidebar: $('#btnExpandSidebar'),
    btnNewChatIcon: $('#btnNewChatIcon'),
    btnMobileSidebar: $('#btnMobileSidebar'),
    btnNewChat: $('#btnNewChat'),
    btnSearch: $('#btnSearch'),
    historyList: $('#historyList'),

    welcome: $('#welcome'),
    conversation: $('#conversation'),
    conversationInner: $('#conversationInner'),
    btnScrollDown: $('#btnScrollDown'),

    composerBox: $('#composerBox'),
    composerInput: $('#composerInput'),
    composerCounter: $('#composerCounter'),
    composerAttachments: $('#composerAttachments'),
    btnSend: $('#btnSend'),
    btnStop: $('#btnStop'),
    btnThink: $('#btnThink'),
    btnMic: $('#btnMic'),
    btnAttach: $('#btnAttach'),
    fileInput: $('#fileInput'),

    modelSelector: $('#modelSelector'),
    modelName: $('#modelName'),
    modelDropdown: $('#modelDropdown'),
    btnShare: $('#btnShare'),
    btnMore: $('#btnMore'),
    btnTemporary: $('#btnTemporary'),

    btnUserMenu: $('#btnUserMenu'),
    userMenu: $('#userMenu'),
    umSettings: $('#umSettings'),
    umMemory: $('#umMemory'),
    umHelp: $('#umHelp'),

    settingsModal: $('#settingsModal'),
    btnCloseSettings: $('#btnCloseSettings'),
    settingUserName: $('#settingUserName'),
    settingUserPersona: $('#settingUserPersona'),
    settingSystem: $('#settingSystem'),
    settingTemp: $('#settingTemp'),
    settingTempValue: $('#settingTempValue'),
    settingTopP: $('#settingTopP'),
    settingTopPValue: $('#settingTopPValue'),
    settingTopK: $('#settingTopK'),
    settingTopKValue: $('#settingTopKValue'),
    settingMaxTokens: $('#settingMaxTokens'),
    settingPresencePenalty: $('#settingPresencePenalty'),
    settingPresencePenaltyValue: $('#settingPresencePenaltyValue'),
    settingFrequencyPenalty: $('#settingFrequencyPenalty'),
    settingFrequencyPenaltyValue: $('#settingFrequencyPenaltyValue'),
    settingStop: $('#settingStop'),
    settingThinking: $('#settingThinking'),
    settingThinkingBudget: $('#settingThinkingBudget'),
    settingMemory: $('#settingMemory'),
    settingMemoryTab2: $('#settingMemoryTab2'),
    settingMemoryAuto: $('#settingMemoryAuto'),
    settingMemoryCount: $('#settingMemoryCount'),
    settingMemoryCountValue: $('#settingMemoryCountValue'),
    // btnOpenMemory handled via class selector below
    btnClearAll: $('#btnClearAll'),
    btnExport: $('#btnExport'),

    memoryModal: $('#memoryModal'),
    btnCloseMemory: $('#btnCloseMemory'),
    memoryAddInput: $('#memoryAddInput'),
    btnMemoryAdd: $('#btnMemoryAdd'),
    memoryList: $('#memoryList'),
    memoryStats: $('#memoryStats'),
    memorySummaryText: $('#memorySummaryText'),
    memorySummaryTime: $('#memorySummaryTime'),
    memorySummaryInput: $('#memorySummaryInput'),
    btnMemorySummaryUpdate: $('#btnMemorySummaryUpdate'),
    btnMemoryRegenerate: $('#btnMemoryRegenerate'),
    navMemory: $('#navMemory'),

    // New settings elements
    settingUserOccupation: $('#settingUserOccupation'),
    settingUserDetails: $('#settingUserDetails'),
    settingPersonality: $('#settingPersonality'),
    settingLanguage: $('#settingLanguage'),
    settingThemeAppearance: $('#settingThemeAppearance'),
    settingThemeContrast: $('#settingThemeContrast'),
    settingApiDelay: $('#settingApiDelay'),
    settingApiDelayValue: $('#settingApiDelayValue'),
    settingApiKey: $('#settingApiKey'),
    settingApiBaseUrl: $('#settingApiBaseUrl'),
    settingModelSlots: [
      $('#settingModelSlot1'),
      $('#settingModelSlot2'),
      $('#settingModelSlot3'),
      $('#settingModelSlot4'),
      $('#settingModelSlot5'),
    ],
    btnTestApi: $('#btnTestApi'),
    settingMemoryAutoSummary: $('#settingMemoryAutoSummary'),
    accentColorPicker: $('#accentColorPicker'),
    welcomeGreeting: $('#welcomeGreeting'),

    // Right panel (chat index)
    rightPanel: $('#rightPanel'),
    rightPanelList: $('#rightPanelList'),
    rightPanelBadge: $('#rightPanelBadge'),
    btnRightPanel: $('#btnRightPanel'),
    btnCloseRightPanel: $('#btnCloseRightPanel'),

    // Library view (RAG)
    libraryView: $('#libraryView'),
    ragUploadZone: $('#ragUploadZone'),
    ragFileInput: $('#ragFileInput'),
    ragFilesList: $('#ragFilesList'),
    btnLibBack: $('#btnLibBack'),
    btnOpenLibrary: $('#btnOpenLibrary'),
    settingRagEnabled: $('#settingRagEnabled'),
    settingRagCount: $('#settingRagCount'),
    settingRagCountValue: $('#settingRagCountValue'),

    // Today view
    todayView: $('#todayView'),
    todayGreeting: $('#todayGreeting'),
    todayDate: $('#todayDate'),
    yesterdayList: $('#yesterdayList'),
    yesterdayCount: $('#yesterdayCount'),
    reflectionBody: $('#reflectionBody'),
    todayGoalsList: $('#todayGoalsList'),
    todayGoalsCount: $('#todayGoalsCount'),
    journalPreview: $('#journalPreview'),
    journalStreakTag: $('#journalStreakTag'),
    inboxPendingList: $('#inboxPendingList'),
    inboxPendingCount: $('#inboxPendingCount'),
    coExpBody: $('#coExpBody'),
    recentActivityList: $('#recentActivityList'),
    btnTodayChat: $('#btnTodayChat'),
    btnTodayCapture: $('#btnTodayCapture'),
    btnTodayInbox: $('#btnTodayInbox'),
    btnJournalAiDraft: $('#btnJournalAiDraft'),
    btnJournalEdit: $('#btnJournalEdit'),
    btnInboxCapture: $('#btnInboxCapture'),
    inboxBadge: $('#inboxBadge'),

    // Inbox view
    inboxView: $('#inboxView'),
    btnInboxBack: $('#btnInboxBack'),
    btnInboxNew: $('#btnInboxNew'),
    btnInboxRefresh: $('#btnInboxRefresh'),
    inboxListContainer: $('#inboxListContainer'),

    // Journal view
    journalView: $('#journalView'),
    btnJournalBack: $('#btnJournalBack'),
    btnJournalToday: $('#btnJournalToday'),
    btnJournalSave: $('#btnJournalSave'),
    btnJournalAiDraftFull: $('#btnJournalAiDraftFull'),
    journalTitle: $('#journalTitle'),
    journalEditor: $('#journalEditor'),
    journalTone: $('#journalTone'),
    journalStreakInfo: $('#journalStreakInfo'),
    journalAiDraft: $('#journalAiDraft'),
    journalAiDraftText: $('#journalAiDraftText'),
    btnJournalAdoptDraft: $('#btnJournalAdoptDraft'),
    btnJournalDiscardDraft: $('#btnJournalDiscardDraft'),
    journalHighlights: $('#journalHighlights'),
    journalGrowth: $('#journalGrowth'),
    journalFailures: $('#journalFailures'),
    journalGratitude: $('#journalGratitude'),
    journalHistoryList: $('#journalHistoryList'),

    // Prompt engineering panel extras
    settingPromptJournalDraft: $('#settingPromptJournalDraft'),
    settingPromptJournalEmotion: $('#settingPromptJournalEmotion'),
    promptStatsDesc: $('#promptStatsDesc'),
    btnPromptsExport: $('#btnPromptsExport'),
    btnPromptsImport: $('#btnPromptsImport'),
    btnPromptsResetAll: $('#btnPromptsResetAll'),

    // Today view — Morning Letter + Discoveries
    morningLetterBody: $('#morningLetterBody'),
    morningLetterMeta: $('#morningLetterMeta'),
    morningConcerns: $('#morningConcerns'),
    morningConcernsList: $('#morningConcernsList'),
    btnGenerateMorning: $('#btnGenerateMorning'),
    todayDiscoveries: $('#todayDiscoveries'),
    todayDiscoveriesList: $('#todayDiscoveriesList'),

    // Residents view
    residentsView: $('#residentsView'),
    btnResidentsBack: $('#btnResidentsBack'),
    btnResidentNew: $('#btnResidentNew'),
    btnResidentRun: $('#btnResidentRun'),
    btnResidentEdit: $('#btnResidentEdit'),
    residentsListSidebar: $('#residentsListSidebar'),
    residentsViewContainer: $('#residentsViewContainer'),
    residentTitle: $('#residentTitle'),

    // Artifacts view
    artifactsView: $('#artifactsView'),
    btnArtifactsBack: $('#btnArtifactsBack'),
    btnArtifactNew: $('#btnArtifactNew'),
    btnArtifactSave: $('#btnArtifactSave'),
    btnArtifactNewVersion: $('#btnArtifactNewVersion'),
    artifactsViewContainer: $('#artifactsViewContainer'),
    artifactTitle: $('#artifactTitle'),

    // Philosophy view
    philosophyView: $('#philosophyView'),
    btnPhilosophyBack: $('#btnPhilosophyBack'),
    btnPhilosophyNew: $('#btnPhilosophyNew'),
    philosophyViewContainer: $('#philosophyViewContainer'),

    // Skills view
    skillsView: $('#skillsView'),
    skillsList: $('#skillsList'),
    btnInstallSkill: $('#btnInstallSkill'),
    btnSkillsBack: $('#btnSkillsBack'),
    btnOpenSkills: $('#btnOpenSkills'),
    settingSkillsEnabled: $('#settingSkillsEnabled'),
    settingSkillsMode: $('#settingSkillsMode'),

    // Sessions view
    sessionsView: $('#sessionsView'),
    sessionsList: $('#sessionsList'),
    btnSessionsBack: $('#btnSessionsBack'),
    btnSessionSpawn: $('#btnSessionSpawn'),
    btnOpenSessions: $('#btnOpenSessions'),
    settingSessionsEnabled: $('#settingSessionsEnabled'),
    settingMaxSubtasks: $('#settingMaxSubtasks'),
    settingMaxSubtasksValue: $('#settingMaxSubtasksValue'),
    settingMaxSubtasksTab2: $('#settingMaxSubtasksTab2'),
    settingMaxSubtasksTab2Value: $('#settingMaxSubtasksTab2Value'),

    // Cron view
    cronView: $('#cronView'),
    cronJobsList: $('#cronJobsList'),
    cronRunsList: $('#cronRunsList'),
    btnCronBack: $('#btnCronBack'),
    btnCronCreate: $('#btnCronCreate'),
    btnOpenCron: $('#btnOpenCron'),
    settingCronEnabled: $('#settingCronEnabled'),

    // Advanced conversation features
    settingCompressEnabled: $('#settingCompressEnabled'),
    settingCompressThreshold: $('#settingCompressThreshold'),
    settingCompressThresholdValue: $('#settingCompressThresholdValue'),
    settingCompressKeepRecent: $('#settingCompressKeepRecent'),
    settingCompressKeepRecentValue: $('#settingCompressKeepRecentValue'),
    settingChatVectorsEnabled: $('#settingChatVectorsEnabled'),
    settingChatVectorsTopK: $('#settingChatVectorsTopK'),
    settingChatVectorsTopKValue: $('#settingChatVectorsTopKValue'),
    btnRebuildChatVectors: $('#btnRebuildChatVectors'),
    settingEmotionTracking: $('#settingEmotionTracking'),
    settingProfileAutoUpdate: $('#settingProfileAutoUpdate'),
    settingProactiveRecall: $('#settingProactiveRecall'),
    settingEmotionalResonance: $('#settingEmotionalResonance'),
    btnViewProfile: $('#btnViewProfile'),

    // Backup API
    settingBackupApiEnabled: $('#settingBackupApiEnabled'),
    settingBackupApiBaseUrl: $('#settingBackupApiBaseUrl'),
    settingBackupApiKey: $('#settingBackupApiKey'),
    settingBackupApiModel: $('#settingBackupApiModel'),
    btnTestBackupApi: $('#btnTestBackupApi'),
    btnUseBackup: $('#btnUseBackup'),

    // Auto-fetch models
    btnAutoFetchModels: $('#btnAutoFetchModels'),
    autoFetchResultRow: $('#autoFetchResultRow'),
    autoFetchCount: $('#autoFetchCount'),
    autoFetchSelect: $('#autoFetchSelect'),
    btnApplyAutoFetch: $('#btnApplyAutoFetch'),

    // Memory Dashboard
    dashboardView: $('#dashboardView'),
    btnDashboardBack: $('#btnDashboardBack'),
    btnRefreshDashboard: $('#btnRefreshDashboard'),
    btnTriggerReflection: $('#btnTriggerReflection'),
    dashboardStats: $('#dashboardStats'),
    dashboardMemories: $('#dashboardMemories'),
    dashboardMemoryFilter: $('#dashboardMemoryFilter'),
    dashboardKG: $('#dashboardKG'),
    dashboardEpisodes: $('#dashboardEpisodes'),
    dashboardReflections: $('#dashboardReflections'),
    dashboardMetaCog: $('#dashboardMetaCog'),

    // Model division settings
    settingMemoryApiKey: $('#settingMemoryApiKey'),
    settingMemoryApiBaseUrl: $('#settingMemoryApiBaseUrl'),
    settingMemoryApiModel: $('#settingMemoryApiModel'),
    settingSubtaskApiKey: $('#settingSubtaskApiKey'),
    settingSubtaskApiBaseUrl: $('#settingSubtaskApiBaseUrl'),
    settingSubtaskApiModel: $('#settingSubtaskApiModel'),
    settingRagEmbeddingProvider: $('#settingRagEmbeddingProvider'),
    settingRagEmbeddingApiKey: $('#settingRagEmbeddingApiKey'),
    settingRagEmbeddingApiBaseUrl: $('#settingRagEmbeddingApiBaseUrl'),
    settingRagEmbeddingModel: $('#settingRagEmbeddingModel'),

    // Prompt engineering
    settingPromptSystem: $('#settingPromptSystem'),
    settingPromptMemoryEdit: $('#settingPromptMemoryEdit'),
    settingPromptMemoryExtract: $('#settingPromptMemoryExtract'),
    settingPromptCognitiveExtraction: $('#settingPromptCognitiveExtraction'),
    settingPromptReflection: $('#settingPromptReflection'),
    settingPromptProfileUpdate: $('#settingPromptProfileUpdate'),
    settingPromptMetaCognition: $('#settingPromptMetaCognition'),
    settingPromptIdentityAssessment: $('#settingPromptIdentityAssessment'),
    settingPromptCompress: $('#settingPromptCompress'),
    settingPromptClassifyImportance: $('#settingPromptClassifyImportance'),
    settingPromptReflectionTree: $('#settingPromptReflectionTree'),
    settingPromptTitle: $('#settingPromptTitle'),
    settingPromptMemorySummary: $('#settingPromptMemorySummary'),

    // MCP servers
    settingMcpEnabled: $('#settingMcpEnabled'),
    mcpAddName: $('#mcpAddName'),
    mcpAddCommand: $('#mcpAddCommand'),
    mcpAddEnv: $('#mcpAddEnv'),
    btnMcpAdd: $('#btnMcpAdd'),
    btnMcpRefresh: $('#btnMcpRefresh'),
    mcpServersList: $('#mcpServersList'),

    // Sidebar nav items
    navItems: $$('.sidebar-nav .nav-item'),
    mainApp: $('#app'),

    toastContainer: $('#toastContainer'),
  };

  // ===== Storage =====
  const STORAGE_KEY = 'my-ai-chat:v2';

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        state.conversations = parsed.conversations || [];
        state.currentId = parsed.currentId || null;
      }
    } catch (e) { console.warn('loadState failed', e); }
    // Temporary mode is NOT persisted — refresh destroys it
    state.temporary = false;
  }
  function saveState() {
    try {
      // Don't persist temporary conversations (they're destroyed on refresh)
      const convsToSave = state.temporary
        ? state.conversations.filter(c => !c.temporary)
        : state.conversations;
      const currentIdToSave = state.temporary ? null : state.currentId;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        conversations: convsToSave,
        currentId: currentIdToSave,
      }));
    } catch (e) {}
  }

  async function loadSettings() {
    try {
      const resp = await fetch('/api/settings');
      const s = await resp.json();
      state.settings.system_prompt = s.system_prompt || '';
      state.settings.temperature = parseFloat(s.temperature || '0.7');
      state.settings.top_p = parseFloat(s.top_p || '0.95');
      state.settings.top_k = parseInt(s.top_k || '0');
      state.settings.max_tokens = parseInt(s.max_tokens || '4096');
      state.settings.thinking_budget = parseInt(s.thinking_budget || '0');
      state.settings.presence_penalty = parseFloat(s.presence_penalty || '0');
      state.settings.frequency_penalty = parseFloat(s.frequency_penalty || '0');
      state.settings.enable_thinking = s.enable_thinking === 'true';
      state.settings.enable_memory = s.enable_memory !== 'false';
      state.settings.memory_auto_extract = s.memory_auto_extract !== 'false';
      state.settings.memory_auto_summary = s.memory_auto_summary !== 'false';
      state.settings.memory_inject_count = parseInt(s.memory_inject_count || '5');
      state.settings.stop_sequences = s.stop_sequences || '';
      state.settings.user_name = s.user_name || '';
      state.settings.user_persona = s.user_persona || '';
      state.settings.user_occupation = s.user_occupation || '';
      state.settings.user_details = s.user_details || '';
      state.settings.personality = s.personality || 'default';
      state.settings.theme_appearance = s.theme_appearance || 'dark';
      state.settings.theme_contrast = s.theme_contrast || 'default';
      state.settings.accent_color = s.accent_color || 'default';
      state.settings.language = s.language || 'auto';
      state.settings.api_delay = parseFloat(s.api_delay || '1');
      state.settings.api_key = s.api_key || '';
      state.settings.api_base_url = s.api_base_url || '';
      state.settings.model_slots = [
        s.model_slot_1 || '',
        s.model_slot_2 || '',
        s.model_slot_3 || '',
        s.model_slot_4 || '',
        s.model_slot_5 || '',
      ];
      state.settings.selected_model = s.selected_model || '';
      // New settings (persist properly)
      state.settings.rag_enabled = s.rag_enabled !== 'false';
      state.settings.rag_count = parseInt(s.rag_count || '3');
      state.settings.mcp_enabled = s.mcp_enabled !== 'false';
      state.settings.skills_enabled = s.skills_enabled !== 'false';
      state.settings.skills_mode = s.skills_mode || 'auto';
      state.settings.memory_api_key = s.memory_api_key || '';
      state.settings.memory_api_base_url = s.memory_api_base_url || '';
      state.settings.memory_api_model = s.memory_api_model || '';
      state.settings.subtask_api_key = s.subtask_api_key || '';
      state.settings.subtask_api_base_url = s.subtask_api_base_url || '';
      state.settings.subtask_api_model = s.subtask_api_model || '';
      state.settings.max_subtasks = parseInt(s.max_subtasks || '3');
      state.settings.rag_embedding_provider = s.rag_embedding_provider || 'local';
      state.settings.rag_embedding_api_key = s.rag_embedding_api_key || '';
      state.settings.rag_embedding_api_base_url = s.rag_embedding_api_base_url || '';
      state.settings.rag_embedding_model = s.rag_embedding_model || '';
      state.settings.sessions_enabled = s.sessions_enabled !== 'false';
      state.settings.cron_enabled = s.cron_enabled !== 'false';
      state.settings.compress_enabled = s.compress_enabled !== 'false';
      state.settings.compress_threshold_tokens = parseInt(s.compress_threshold_tokens || '80000');
      state.settings.compress_keep_recent = parseInt(s.compress_keep_recent || '6');
      state.settings.chat_vectors_enabled = s.chat_vectors_enabled !== 'false';
      state.settings.chat_vectors_search_top_k = parseInt(s.chat_vectors_search_top_k || '5');
      state.settings.emotion_tracking_enabled = s.emotion_tracking_enabled !== 'false';
      state.settings.profile_auto_update = s.profile_auto_update !== 'false';
      state.settings.proactive_recall = s.proactive_recall !== 'false';
      state.settings.emotional_resonance = s.emotional_resonance !== 'false';
      state.settings.backup_api_enabled = s.backup_api_enabled === 'true';
      state.settings.backup_api_key = s.backup_api_key || '';
      state.settings.backup_api_base_url = s.backup_api_base_url || 'http://127.0.0.1:8000/v1';
      state.settings.backup_api_model = s.backup_api_model || '';
      // Prompt engineering
      const promptKeys = ['prompt_system','prompt_memory_edit','prompt_memory_extract','prompt_memory_summary','prompt_title','prompt_compress','prompt_classify_importance','prompt_reflection','prompt_cognitive_extraction','prompt_profile_update','prompt_meta_cognition','prompt_identity_assessment','prompt_reflection_tree'];
      for (const k of promptKeys) {
        state.settings[k] = s[k] || '';
      }
      applyTheme();
      updateWelcomeGreeting();
    } catch (e) { console.warn('loadSettings failed', e); }
  }

  async function saveSettings() {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          system_prompt: state.settings.system_prompt,
          temperature: String(state.settings.temperature),
          top_p: String(state.settings.top_p),
          top_k: String(state.settings.top_k),
          max_tokens: String(state.settings.max_tokens),
          thinking_budget: String(state.settings.thinking_budget),
          presence_penalty: String(state.settings.presence_penalty),
          frequency_penalty: String(state.settings.frequency_penalty),
          enable_thinking: String(state.settings.enable_thinking),
          enable_memory: String(state.settings.enable_memory),
          memory_auto_extract: String(state.settings.memory_auto_extract),
          memory_auto_summary: String(state.settings.memory_auto_summary),
          memory_inject_count: String(state.settings.memory_inject_count),
          stop_sequences: state.settings.stop_sequences,
          user_name: state.settings.user_name,
          user_persona: state.settings.user_persona,
          user_occupation: state.settings.user_occupation,
          user_details: state.settings.user_details,
          personality: state.settings.personality,
          theme_appearance: state.settings.theme_appearance,
          theme_contrast: state.settings.theme_contrast,
          accent_color: state.settings.accent_color,
          language: state.settings.language,
          api_delay: String(state.settings.api_delay),
          api_key: state.settings.api_key,
          api_base_url: state.settings.api_base_url,
          model_slot_1: state.settings.model_slots[0] || '',
          model_slot_2: state.settings.model_slots[1] || '',
          model_slot_3: state.settings.model_slots[2] || '',
          model_slot_4: state.settings.model_slots[3] || '',
          model_slot_5: state.settings.model_slots[4] || '',
          selected_model: state.settings.selected_model,
          // New settings (persist to backend)
          rag_enabled: String(state.settings.rag_enabled),
          rag_count: String(state.settings.rag_count),
          mcp_enabled: String(state.settings.mcp_enabled),
          skills_enabled: String(state.settings.skills_enabled),
          skills_mode: state.settings.skills_mode,
          memory_api_key: state.settings.memory_api_key,
          memory_api_base_url: state.settings.memory_api_base_url,
          memory_api_model: state.settings.memory_api_model,
          subtask_api_key: state.settings.subtask_api_key,
          subtask_api_base_url: state.settings.subtask_api_base_url,
          subtask_api_model: state.settings.subtask_api_model,
          max_subtasks: String(state.settings.max_subtasks),
          rag_embedding_provider: state.settings.rag_embedding_provider,
          rag_embedding_api_key: state.settings.rag_embedding_api_key,
          rag_embedding_api_base_url: state.settings.rag_embedding_api_base_url,
          rag_embedding_model: state.settings.rag_embedding_model,
          sessions_enabled: String(state.settings.sessions_enabled),
          cron_enabled: String(state.settings.cron_enabled),
          compress_enabled: String(state.settings.compress_enabled),
          compress_threshold_tokens: String(state.settings.compress_threshold_tokens),
          compress_keep_recent: String(state.settings.compress_keep_recent),
          chat_vectors_enabled: String(state.settings.chat_vectors_enabled),
          chat_vectors_search_top_k: String(state.settings.chat_vectors_search_top_k),
          emotion_tracking_enabled: String(state.settings.emotion_tracking_enabled),
          profile_auto_update: String(state.settings.profile_auto_update),
          proactive_recall: String(state.settings.proactive_recall),
          emotional_resonance: String(state.settings.emotional_resonance),
          backup_api_enabled: String(state.settings.backup_api_enabled),
          backup_api_key: state.settings.backup_api_key,
          backup_api_base_url: state.settings.backup_api_base_url,
          backup_api_model: state.settings.backup_api_model,
          // Prompt engineering
          prompt_system: state.settings.prompt_system || '',
          prompt_memory_edit: state.settings.prompt_memory_edit || '',
          prompt_memory_extract: state.settings.prompt_memory_extract || '',
          prompt_memory_summary: state.settings.prompt_memory_summary || '',
          prompt_title: state.settings.prompt_title || '',
          prompt_compress: state.settings.prompt_compress || '',
          prompt_classify_importance: state.settings.prompt_classify_importance || '',
          prompt_reflection: state.settings.prompt_reflection || '',
          prompt_cognitive_extraction: state.settings.prompt_cognitive_extraction || '',
          prompt_profile_update: state.settings.prompt_profile_update || '',
          prompt_meta_cognition: state.settings.prompt_meta_cognition || '',
          prompt_identity_assessment: state.settings.prompt_identity_assessment || '',
          prompt_reflection_tree: state.settings.prompt_reflection_tree || '',
        }),
      });
    } catch (e) { console.warn('saveSettings failed', e); }
  }

  // ===== Theme application =====
  const ACCENT_COLORS = {
    default: { blue: '#4dabf7', accent: '#ececec' },
    blue: { blue: '#3b82f6', accent: '#3b82f6' },
    green: { blue: '#10b981', accent: '#10b981' },
    purple: { blue: '#8b5cf6', accent: '#8b5cf6' },
    orange: { blue: '#f59e0b', accent: '#f59e0b' },
    pink: { blue: '#ec4899', accent: '#ec4899' },
  };

  function applyTheme() {
    const root = document.documentElement;
    // Appearance
    const appearance = state.settings.theme_appearance;
    if (appearance === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
      root.setAttribute('data-theme', appearance);
    }
    // Accent color
    const accent = state.settings.accent_color;
    const colors = ACCENT_COLORS[accent] || ACCENT_COLORS.default;
    root.style.setProperty('--accent-blue', colors.blue);
    if (accent !== 'default') {
      root.style.setProperty('--accent', colors.accent);
    } else {
      root.style.setProperty('--accent', '#ececec');
    }
  }

  function updateWelcomeGreeting() {
    const name = state.settings.user_name;
    if (name) {
      el.welcomeGreeting.textContent = `${name}，准备好开始了吗？`;
    } else {
      el.welcomeGreeting.textContent = '今天能帮你做些什么？';
    }
  }

  // ===== Model selector (dynamic loading) =====
  async function loadModelSelector() {
    try {
      const resp = await fetch('/api/models');
      const data = await resp.json();
      const models = data.models || [];
      const selected = data.selected || (models[0] && models[0].id) || '';
      // Update model name display
      const selectedModel = models.find(m => m.id === selected) || models[0];
      if (selectedModel) {
        el.modelName.textContent = selectedModel.name;
      }
      // Populate dropdown
      el.modelDropdown.innerHTML = '';
      models.forEach(m => {
        const opt = document.createElement('div');
        opt.className = 'model-option' + (m.id === selected ? ' active' : '');
        opt.dataset.model = m.id;
        opt.innerHTML = `
          <div class="model-option-name">${escapeHtml(m.name)}</div>
          <div class="model-option-desc">${escapeHtml(m.id)}</div>`;
        opt.addEventListener('click', async (e) => {
          e.stopPropagation();
          // Select this model
          try {
            await fetch('/api/models/select', {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({model: m.id}),
            });
            state.settings.selected_model = m.id;
            el.modelName.textContent = m.name;
            el.modelDropdown.querySelectorAll('.model-option').forEach(o => o.classList.toggle('active', o === opt));
            el.modelSelector.classList.remove('open');
            toast(`已切换到 ${m.name}`, 'success');
          } catch (err) {
            toast('切换失败: ' + err.message, 'error');
          }
        });
        el.modelDropdown.appendChild(opt);
      });
    } catch (e) {
      console.warn('loadModelSelector failed', e);
    }
  }

  // ===== Utilities =====
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function toast(message, type = 'info') {
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = message;
    el.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3200);
  }
  function getConversation(id) { return state.conversations.find(c => c.id === id); }
  function currentConversation() { return getConversation(state.currentId); }

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

  // ===== History rendering =====
  function renderHistory() {
    el.historyList.innerHTML = '';
    // Update badge count
    const badge = document.getElementById('historyBadge');
    const convCount = state.conversations.filter(c => !c.temporary).length;
    if (badge) badge.textContent = convCount;
    if (state.conversations.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.textContent = '暂无历史对话';
      el.historyList.appendChild(empty);
      return;
    }
    // Don't show temporary conversations in sidebar
    const sorted = [...state.conversations].filter(c => !c.temporary).sort((a,b) => {
      // Pinned conversations first
      const aPinned = a.pinned ? 1 : 0;
      const bPinned = b.pinned ? 1 : 0;
      if (aPinned !== bPinned) return bPinned - aPinned;
      return b.updatedAt - a.updatedAt;
    });
    // Add pinned section
    const pinned = sorted.filter(c => c.pinned);
    if (pinned.length > 0) {
      const pt = document.createElement('div');
      pt.className = 'history-section-title history-pinned-label';
      pt.textContent = '📌 置顶';
      el.historyList.appendChild(pt);
      pinned.forEach(c => {
        const item = createHistoryItem(c, true);
        el.historyList.appendChild(item);
      });
    }
    const unpinned = sorted.filter(c => !c.pinned);
    const groups = { '今天': [], '昨天': [], '前 7 天': [], '更早': [] };
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;
    const weekStart = todayStart - 7 * 86400000;
    unpinned.forEach(c => {
      if (c.updatedAt >= todayStart) groups['今天'].push(c);
      else if (c.updatedAt >= yesterdayStart) groups['昨天'].push(c);
      else if (c.updatedAt >= weekStart) groups['前 7 天'].push(c);
      else groups['更早'].push(c);
    });
    for (const [title, convs] of Object.entries(groups)) {
      if (convs.length === 0) continue;
      const t = document.createElement('div');
      t.className = 'history-section-title';
      t.textContent = title;
      el.historyList.appendChild(t);
      convs.forEach(c => {
        const item = createHistoryItem(c, false);
        el.historyList.appendChild(item);
      });
    }
  }

  function createHistoryItem(c, isPinned) {
        const item = document.createElement('div');
        item.className = 'history-item' + (c.id === state.currentId ? ' active' : '') + (isPinned ? ' pinned' : '');
        item.dataset.id = c.id;
        item.innerHTML = `
          <span class="h-title">${escapeHtml(c.title || '新对话')}</span>
          <span class="h-actions">
            <button class="h-action" data-action="pin" title="${isPinned ? '取消置顶' : '置顶'}"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v6m0 0l3.5-3.5M12 8l-3.5-3.5M12 8v14"/></svg></button>
            <button class="h-action" data-action="rename" title="重命名"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
            <button class="h-action" data-action="delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>
          </span>`;
        item.addEventListener('click', (e) => {
          if (e.target.closest('.h-action')) return;
          switchConversation(c.id);
        });
        item.querySelector('[data-action="pin"]').addEventListener('click', (e) => {
          e.stopPropagation();
          c.pinned = !c.pinned;
          saveState();
          renderHistory();
        });
        item.querySelector('[data-action="rename"]').addEventListener('click', (e) => {
          e.stopPropagation();
          // Inline rename: replace title with input
          const titleEl = item.querySelector('.h-title');
          const oldTitle = c.title;
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'h-rename-input';
          input.value = oldTitle;
          input.style.cssText = 'flex:1;background:transparent;border:none;outline:none;color:var(--text-primary);font-size:14px;font-family:inherit;padding:0;min-width:0;';
          titleEl.replaceWith(input);
          input.focus();
          input.select();
          const finish = (save) => {
            const newTitle = input.value.trim();
            if (save && newTitle && newTitle !== oldTitle) {
              c.title = newTitle;
              saveState();
            }
            renderHistory();
          };
          input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
            else if (ev.key === 'Escape') { finish(false); }
          });
          input.addEventListener('blur', () => finish(true));
        });
        item.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
          e.stopPropagation();
          // Inline delete confirmation: replace item with confirm UI
          const origHTML = item.innerHTML;
          item.innerHTML = `
            <span class="h-title" style="color:var(--text-muted)">删除「${escapeHtml(c.title)}」？</span>
            <span class="h-actions" style="display:flex">
              <button class="h-action" data-action="confirm-delete" style="color:#ef4444" title="确认删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></button>
              <button class="h-action" data-action="cancel-delete" title="取消"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
            </span>`;
          item.querySelector('[data-action="confirm-delete"]').addEventListener('click', (ev) => {
            ev.stopPropagation();
            deleteConversation(c.id);
          });
          item.querySelector('[data-action="cancel-delete"]').addEventListener('click', (ev) => {
            ev.stopPropagation();
            renderHistory();
          });
        });
        el.historyList.appendChild(item);
      });
    }
  }

  function deleteConversation(id) {
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.currentId === id) state.currentId = null;
    saveState();
    renderHistory();
    renderConversation();
    // Cascade delete chat vectors on server
    if (state.settings.chat_vectors_enabled) {
      fetch('/api/conversations/delete', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id }),
      }).catch(e => console.warn('delete conv vectors failed', e));
    }
  }

  function switchConversation(id) {
    state.currentId = id;
    saveState();
    renderHistory();
    renderConversation();
    if (window.innerWidth < 769) toggleSidebarMobile(false);
  }

  function newConversation(initialPrompt) {
    // Just switch to a fresh empty state — DON'T create sidebar entry yet.
    // The conversation will be created and shown in sidebar only when first message is sent.
    // Preserve temporary mode (switching conversations doesn't exit temporary mode).
    state.currentId = null;
    renderHistory();
    renderConversation();
    if (initialPrompt) { el.composerInput.value = initialPrompt; autoResize(); }
    el.composerInput.focus();
    if (window.innerWidth < 769) toggleSidebarMobile(false);
  }

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

  // ===== Composer helpers =====
  function autoResize() {
    const ta = el.composerInput;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
    el.composerCounter.textContent = ta.value.length > 0 ? `${ta.value.length} 字` : '';
    el.btnSend.disabled = !ta.value.trim() && state.attachments.length === 0;
  }

  function scrollToBottom(force = false) {
    const c = el.conversation;
    if (!c) return;
    const nearBottom = (c.scrollHeight - c.scrollTop - c.clientHeight) < 100;
    if (force || nearBottom) c.scrollTop = c.scrollHeight;
  }

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

  // ===== Attachments =====
  async function handleFiles(files) {
    for (const file of files) {
      if (file.size > 20 * 1024 * 1024) {
        toast(`${file.name} 超过 20MB`, 'error');
        continue;
      }
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/upload', { method: 'POST', body: fd });
        if (!resp.ok) {
          const e = await resp.json();
          toast(`上传失败: ${e.detail || 'unknown'}`, 'error');
          continue;
        }
        const data = await resp.json();
        state.attachments.push(data);
        renderAttachments();
        autoResize();
      } catch (e) {
        toast(`上传失败: ${e.message}`, 'error');
      }
    }
  }

  function renderAttachments() {
    el.composerAttachments.innerHTML = '';
    if (state.attachments.length === 0) {
      el.composerAttachments.classList.remove('has-items');
      return;
    }
    el.composerAttachments.classList.add('has-items');
    state.attachments.forEach((a, i) => {
      const chip = document.createElement('div');
      chip.className = 'composer-attachment';
      if (a.type === 'image') {
        chip.innerHTML = `<img src="${a.path}" alt="" /><span class="ca-name">${escapeHtml(a.name)}</span><button class="ca-remove" data-i="${i}"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
      } else {
        chip.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span class="ca-name">${escapeHtml(a.name)}</span><button class="ca-remove" data-i="${i}"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
      }
      chip.querySelector('.ca-remove').addEventListener('click', () => {
        state.attachments.splice(i, 1);
        renderAttachments();
        autoResize();
      });
      el.composerAttachments.appendChild(chip);
    });
  }

  // ===== Memory management =====
  async function openMemoryModal() {
    el.memoryModal.style.display = '';
    await Promise.all([refreshMemoryList(), refreshMemorySummary()]);
  }

  async function refreshMemorySummary() {
    try {
      const resp = await fetch('/api/memory/summary');
      const data = await resp.json();
      if (data.summary) {
        el.memorySummaryText.textContent = data.summary;
        el.memorySummaryInput.value = '';
        const ago = formatTimeAgo(data.updated_at);
        el.memorySummaryTime.textContent = `更新于 ${ago}`;
      } else {
        el.memorySummaryText.textContent = '还没有记忆摘要。和 AI 多聊几句，它会自动总结你分享的关键信息。';
        el.memorySummaryTime.textContent = '尚未生成';
      }
    } catch (e) {
      el.memorySummaryText.textContent = '加载摘要失败: ' + e.message;
    }
  }

  function formatTimeAgo(timestamp) {
    if (!timestamp) return '未知';
    const diff = Date.now() / 1000 - timestamp;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`;
    return new Date(timestamp * 1000).toLocaleDateString('zh-CN');
  }

  async function refreshMemoryList() {
    try {
      const resp = await fetch('/api/memory');
      const data = await resp.json();
      const mems = data.memories || [];
      el.memoryStats.textContent = `${mems.length} 条`;
      el.memoryList.innerHTML = '';
      if (mems.length === 0) {
        el.memoryList.innerHTML = '<div class="memory-empty">还没有记忆片段。对话中的关键事实会自动保存到这里，也可以手动添加。</div>';
        return;
      }
      for (const m of mems) {
        const item = document.createElement('div');
        item.className = 'memory-item';
        const date = new Date(m.updated_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
        const source = m.source === 'auto' ? '自动' : '手动';
        item.innerHTML = `
          <div class="mi-content">${escapeHtml(m.content)}<div class="mi-meta">${date} · ${source} · 访问 ${m.access_count} 次</div></div>
          <button class="mi-delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>`;
        item.querySelector('.mi-delete').addEventListener('click', async () => {
          await fetch('/api/memory/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ id: m.id }),
          });
          refreshMemoryList();
          toast('已删除', 'success');
        });
        el.memoryList.appendChild(item);
      }
    } catch (e) {
      el.memoryList.innerHTML = `<div class="memory-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }
  async function addMemoryManual() {
    const text = el.memoryAddInput.value.trim();
    if (!text) return;
    try {
      const resp = await fetch('/api/memory/add', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: text, source: 'manual' }),
      });
      const data = await resp.json();
      if (data.action === 'add') {
        el.memoryAddInput.value = '';
        toast('已添加', 'success');
        refreshMemoryList();
      } else if (data.action === 'update') {
        toast('已合并到现有记忆', 'success');
        el.memoryAddInput.value = '';
        refreshMemoryList();
      } else {
        toast('已存在相似记忆', 'info');
      }
    } catch (e) {
      toast('添加失败: ' + e.message, 'error');
    }
  }

  async function updateMemorySummary() {
    const text = el.memorySummaryInput.value.trim();
    if (!text) return;
    try {
      await fetch('/api/memory/summary/update', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ summary: text }),
      });
      el.memorySummaryInput.value = '';
      toast('摘要已更新', 'success');
      await refreshMemorySummary();
    } catch (e) {
      toast('更新失败: ' + e.message, 'error');
    }
  }

  async function regenerateMemorySummary() {
    el.btnMemoryRegenerate.disabled = true;
    el.btnMemoryRegenerate.textContent = '生成中...';
    try {
      const resp = await fetch('/api/memory/summary/regenerate', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({}),
      });
      const data = await resp.json();
      if (data.summary) {
        toast('摘要已重新生成', 'success');
        await refreshMemorySummary();
      } else {
        toast('暂无记忆可生成摘要', 'info');
      }
    } catch (e) {
      toast('生成失败: ' + e.message, 'error');
    } finally {
      el.btnMemoryRegenerate.disabled = false;
      el.btnMemoryRegenerate.textContent = '刷新摘要';
    }
  }

  // ===== Settings UI =====
  function populateSettingsUI() {
    el.settingUserName.value = state.settings.user_name;
    el.settingUserPersona.value = state.settings.user_persona;
    el.settingUserOccupation.value = state.settings.user_occupation;
    el.settingUserDetails.value = state.settings.user_details;
    el.settingSystem.value = state.settings.system_prompt;
    el.settingTemp.value = state.settings.temperature;
    el.settingTempValue.textContent = state.settings.temperature;
    el.settingTopP.value = state.settings.top_p;
    el.settingTopPValue.textContent = state.settings.top_p;
    el.settingTopK.value = state.settings.top_k;
    el.settingTopKValue.textContent = state.settings.top_k;
    el.settingMaxTokens.value = state.settings.max_tokens;
    el.settingPresencePenalty.value = state.settings.presence_penalty;
    el.settingPresencePenaltyValue.textContent = state.settings.presence_penalty;
    el.settingFrequencyPenalty.value = state.settings.frequency_penalty;
    el.settingFrequencyPenaltyValue.textContent = state.settings.frequency_penalty;
    el.settingStop.value = state.settings.stop_sequences;
    el.settingThinking.checked = state.settings.enable_thinking;
    el.settingThinkingBudget.value = state.settings.thinking_budget;
    el.settingMemory.checked = state.settings.enable_memory;
    if (el.settingMemoryTab2) el.settingMemoryTab2.checked = state.settings.enable_memory;
    el.settingMemoryAuto.checked = state.settings.memory_auto_extract;
    el.settingMemoryAutoSummary.checked = state.settings.memory_auto_summary;
    el.settingMemoryCount.value = state.settings.memory_inject_count;
    el.settingMemoryCountValue.textContent = state.settings.memory_inject_count;
    // RAG
    if (el.settingRagEnabled) el.settingRagEnabled.checked = state.settings.rag_enabled;
    if (el.settingRagCount) {
      el.settingRagCount.value = state.settings.rag_count;
      el.settingRagCountValue.textContent = state.settings.rag_count;
    }
    // MCP
    if (el.settingMcpEnabled) el.settingMcpEnabled.checked = state.settings.mcp_enabled;
    // Skills
    if (el.settingSkillsEnabled) el.settingSkillsEnabled.checked = state.settings.skills_enabled;
    if (el.settingSkillsMode) el.settingSkillsMode.value = state.settings.skills_mode;
    // Multi-model division
    if (el.settingMemoryApiKey) el.settingMemoryApiKey.value = state.settings.memory_api_key || '';
    if (el.settingMemoryApiBaseUrl) el.settingMemoryApiBaseUrl.value = state.settings.memory_api_base_url || '';
    if (el.settingMemoryApiModel) el.settingMemoryApiModel.value = state.settings.memory_api_model || '';
    if (el.settingSubtaskApiKey) el.settingSubtaskApiKey.value = state.settings.subtask_api_key || '';
    if (el.settingSubtaskApiBaseUrl) el.settingSubtaskApiBaseUrl.value = state.settings.subtask_api_base_url || '';
    if (el.settingSubtaskApiModel) el.settingSubtaskApiModel.value = state.settings.subtask_api_model || '';
    if (el.settingMaxSubtasks) {
      el.settingMaxSubtasks.value = state.settings.max_subtasks;
      el.settingMaxSubtasksValue.textContent = state.settings.max_subtasks;
    }
    if (el.settingMaxSubtasksTab2) {
      el.settingMaxSubtasksTab2.value = state.settings.max_subtasks;
      el.settingMaxSubtasksTab2Value.textContent = state.settings.max_subtasks;
    }
    if (el.settingRagEmbeddingProvider) el.settingRagEmbeddingProvider.value = state.settings.rag_embedding_provider || 'local';
    if (el.settingRagEmbeddingApiKey) el.settingRagEmbeddingApiKey.value = state.settings.rag_embedding_api_key || '';
    if (el.settingRagEmbeddingApiBaseUrl) el.settingRagEmbeddingApiBaseUrl.value = state.settings.rag_embedding_api_base_url || '';
    if (el.settingRagEmbeddingModel) el.settingRagEmbeddingModel.value = state.settings.rag_embedding_model || '';
    // Sessions / Cron
    if (el.settingSessionsEnabled) el.settingSessionsEnabled.checked = state.settings.sessions_enabled;
    if (el.settingCronEnabled) el.settingCronEnabled.checked = state.settings.cron_enabled;
    // Advanced conversation features
    if (el.settingCompressEnabled) el.settingCompressEnabled.checked = state.settings.compress_enabled;
    if (el.settingCompressThreshold) {
      el.settingCompressThreshold.value = state.settings.compress_threshold_tokens;
      el.settingCompressThresholdValue.textContent = state.settings.compress_threshold_tokens;
    }
    if (el.settingCompressKeepRecent) {
      el.settingCompressKeepRecent.value = state.settings.compress_keep_recent;
      el.settingCompressKeepRecentValue.textContent = state.settings.compress_keep_recent;
    }
    if (el.settingChatVectorsEnabled) el.settingChatVectorsEnabled.checked = state.settings.chat_vectors_enabled;
    if (el.settingChatVectorsTopK) {
      el.settingChatVectorsTopK.value = state.settings.chat_vectors_search_top_k;
      el.settingChatVectorsTopKValue.textContent = state.settings.chat_vectors_search_top_k;
    }
    if (el.settingEmotionTracking) el.settingEmotionTracking.checked = state.settings.emotion_tracking_enabled;
    if (el.settingProfileAutoUpdate) el.settingProfileAutoUpdate.checked = state.settings.profile_auto_update;
    if (el.settingProactiveRecall) el.settingProactiveRecall.checked = state.settings.proactive_recall;
    if (el.settingEmotionalResonance) el.settingEmotionalResonance.checked = state.settings.emotional_resonance;
    // Backup API
    if (el.settingBackupApiEnabled) el.settingBackupApiEnabled.checked = state.settings.backup_api_enabled;
    if (el.settingBackupApiBaseUrl) el.settingBackupApiBaseUrl.value = state.settings.backup_api_base_url || 'http://127.0.0.1:8000/v1';
    if (el.settingBackupApiKey) el.settingBackupApiKey.value = state.settings.backup_api_key || '';
    if (el.settingBackupApiModel) el.settingBackupApiModel.value = state.settings.backup_api_model || '';
    // Prompt engineering — 加载默认 prompt 作为初始值
    const promptMap = {
      settingPromptSystem: 'prompt_system',
      settingPromptMemoryEdit: 'prompt_memory_edit',
      settingPromptMemoryExtract: 'prompt_memory_extract',
      settingPromptCognitiveExtraction: 'prompt_cognitive_extraction',
      settingPromptReflection: 'prompt_reflection',
      settingPromptProfileUpdate: 'prompt_profile_update',
      settingPromptMetaCognition: 'prompt_meta_cognition',
      settingPromptIdentityAssessment: 'prompt_identity_assessment',
      settingPromptCompress: 'prompt_compress',
      settingPromptClassifyImportance: 'prompt_classify_importance',
      settingPromptReflectionTree: 'prompt_reflection_tree',
      settingPromptTitle: 'prompt_title',
      settingPromptMemorySummary: 'prompt_memory_summary',
      settingPromptJournalDraft: 'prompt_journal_draft',
      settingPromptJournalEmotion: 'prompt_journal_emotion',
    };
    // 先用用户保存的值（如果有），否则从 API 加载默认值
    for (const [elKey, settingKey] of Object.entries(promptMap)) {
      if (el[elKey]) {
        const userVal = state.settings[settingKey] || '';
        if (userVal) {
          el[elKey].value = userVal;
        } else {
          // 从 API 加载默认值
          fetch(`/api/prompts/${encodeURIComponent(settingKey)}`)
            .then(r => r.ok ? r.json() : null)
            .then(d => {
              if (d && d.default) el[elKey].value = d.default;
            })
            .catch(() => {});
        }
      }
    }
    el.settingPersonality.value = state.settings.personality;
    el.settingLanguage.value = state.settings.language;
    el.settingThemeAppearance.value = state.settings.theme_appearance;
    el.settingThemeContrast.value = state.settings.theme_contrast;
    el.settingApiDelay.value = state.settings.api_delay;
    el.settingApiDelayValue.textContent = state.settings.api_delay;
    el.settingApiKey.value = state.settings.api_key;
    el.settingApiBaseUrl.value = state.settings.api_base_url;
    el.settingModelSlots.forEach((inp, i) => {
      if (inp) inp.value = state.settings.model_slots[i] || '';
    });
    // Accent color swatches
    if (el.accentColorPicker) {
      el.accentColorPicker.querySelectorAll('.accent-swatch').forEach(sw => {
        sw.classList.toggle('active', sw.dataset.color === state.settings.accent_color);
      });
    }
    el.btnThink.classList.toggle('active', state.settings.enable_thinking);
  }
  function applySettingsFromUI() {
    state.settings.user_name = el.settingUserName.value;
    state.settings.user_persona = el.settingUserPersona.value;
    state.settings.user_occupation = el.settingUserOccupation.value;
    state.settings.user_details = el.settingUserDetails.value;
    state.settings.system_prompt = el.settingSystem.value;
    state.settings.temperature = parseFloat(el.settingTemp.value);
    state.settings.top_p = parseFloat(el.settingTopP.value);
    state.settings.top_k = parseInt(el.settingTopK.value);
    state.settings.max_tokens = parseInt(el.settingMaxTokens.value);
    state.settings.presence_penalty = parseFloat(el.settingPresencePenalty.value);
    state.settings.frequency_penalty = parseFloat(el.settingFrequencyPenalty.value);
    state.settings.stop_sequences = el.settingStop.value;
    state.settings.enable_thinking = el.settingThinking.checked;
    state.settings.thinking_budget = parseInt(el.settingThinkingBudget.value || '0');
    el.settingMemory.checked = el.settingMemoryTab2 ? el.settingMemoryTab2.checked : el.settingMemory.checked;
    state.settings.enable_memory = el.settingMemory.checked;
    state.settings.memory_auto_extract = el.settingMemoryAuto.checked;
    state.settings.memory_auto_summary = el.settingMemoryAutoSummary.checked;
    state.settings.memory_inject_count = parseInt(el.settingMemoryCount.value);
    // RAG / MCP / Skills
    if (el.settingRagEnabled) state.settings.rag_enabled = el.settingRagEnabled.checked;
    if (el.settingRagCount) state.settings.rag_count = parseInt(el.settingRagCount.value);
    if (el.settingMcpEnabled) state.settings.mcp_enabled = el.settingMcpEnabled.checked;
    if (el.settingSkillsEnabled) state.settings.skills_enabled = el.settingSkillsEnabled.checked;
    if (el.settingSkillsMode) state.settings.skills_mode = el.settingSkillsMode.value;
    // Multi-model division
    if (el.settingMemoryApiKey) state.settings.memory_api_key = el.settingMemoryApiKey.value;
    if (el.settingMemoryApiBaseUrl) state.settings.memory_api_base_url = el.settingMemoryApiBaseUrl.value;
    if (el.settingMemoryApiModel) state.settings.memory_api_model = el.settingMemoryApiModel.value;
    if (el.settingSubtaskApiKey) state.settings.subtask_api_key = el.settingSubtaskApiKey.value;
    if (el.settingSubtaskApiBaseUrl) state.settings.subtask_api_base_url = el.settingSubtaskApiBaseUrl.value;
    if (el.settingSubtaskApiModel) state.settings.subtask_api_model = el.settingSubtaskApiModel.value;
    if (el.settingMaxSubtasks) state.settings.max_subtasks = parseInt(el.settingMaxSubtasks.value);
    if (el.settingRagEmbeddingProvider) state.settings.rag_embedding_provider = el.settingRagEmbeddingProvider.value;
    if (el.settingRagEmbeddingApiKey) state.settings.rag_embedding_api_key = el.settingRagEmbeddingApiKey.value;
    if (el.settingRagEmbeddingApiBaseUrl) state.settings.rag_embedding_api_base_url = el.settingRagEmbeddingApiBaseUrl.value;
    if (el.settingRagEmbeddingModel) state.settings.rag_embedding_model = el.settingRagEmbeddingModel.value;
    if (el.settingSessionsEnabled) state.settings.sessions_enabled = el.settingSessionsEnabled.checked;
    if (el.settingCronEnabled) state.settings.cron_enabled = el.settingCronEnabled.checked;
    // Advanced conversation features
    if (el.settingCompressEnabled) state.settings.compress_enabled = el.settingCompressEnabled.checked;
    if (el.settingCompressThreshold) state.settings.compress_threshold_tokens = parseInt(el.settingCompressThreshold.value);
    if (el.settingCompressKeepRecent) state.settings.compress_keep_recent = parseInt(el.settingCompressKeepRecent.value);
    if (el.settingChatVectorsEnabled) state.settings.chat_vectors_enabled = el.settingChatVectorsEnabled.checked;
    if (el.settingChatVectorsTopK) state.settings.chat_vectors_search_top_k = parseInt(el.settingChatVectorsTopK.value);
    if (el.settingEmotionTracking) state.settings.emotion_tracking_enabled = el.settingEmotionTracking.checked;
    if (el.settingProfileAutoUpdate) state.settings.profile_auto_update = el.settingProfileAutoUpdate.checked;
    if (el.settingProactiveRecall) state.settings.proactive_recall = el.settingProactiveRecall.checked;
    if (el.settingEmotionalResonance) state.settings.emotional_resonance = el.settingEmotionalResonance.checked;
    // Backup API
    if (el.settingBackupApiEnabled) state.settings.backup_api_enabled = el.settingBackupApiEnabled.checked;
    if (el.settingBackupApiBaseUrl) state.settings.backup_api_base_url = el.settingBackupApiBaseUrl.value;
    if (el.settingBackupApiKey) state.settings.backup_api_key = el.settingBackupApiKey.value;
    if (el.settingBackupApiModel) state.settings.backup_api_model = el.settingBackupApiModel.value;
    // Prompt engineering
    const promptApplyMap = {
      settingPromptSystem: 'prompt_system',
      settingPromptMemoryEdit: 'prompt_memory_edit',
      settingPromptMemoryExtract: 'prompt_memory_extract',
      settingPromptCognitiveExtraction: 'prompt_cognitive_extraction',
      settingPromptReflection: 'prompt_reflection',
      settingPromptProfileUpdate: 'prompt_profile_update',
      settingPromptMetaCognition: 'prompt_meta_cognition',
      settingPromptIdentityAssessment: 'prompt_identity_assessment',
      settingPromptCompress: 'prompt_compress',
      settingPromptClassifyImportance: 'prompt_classify_importance',
      settingPromptReflectionTree: 'prompt_reflection_tree',
      settingPromptTitle: 'prompt_title',
      settingPromptMemorySummary: 'prompt_memory_summary',
      settingPromptJournalDraft: 'prompt_journal_draft',
      settingPromptJournalEmotion: 'prompt_journal_emotion',
    };
    for (const [elKey, settingKey] of Object.entries(promptApplyMap)) {
      if (el[elKey]) state.settings[settingKey] = el[elKey].value;
    }
    state.settings.personality = el.settingPersonality.value;
    state.settings.language = el.settingLanguage.value;
    state.settings.theme_appearance = el.settingThemeAppearance.value;
    state.settings.theme_contrast = el.settingThemeContrast.value;
    state.settings.api_delay = parseFloat(el.settingApiDelay.value);
    state.settings.api_key = el.settingApiKey.value;
    state.settings.api_base_url = el.settingApiBaseUrl.value;
    el.settingModelSlots.forEach((inp, i) => {
      if (inp) state.settings.model_slots[i] = inp.value.trim();
    });
    saveSettings();
    applyTheme();
    updateWelcomeGreeting();
    // Reload model selector when settings change (model slots may have been updated)
    loadModelSelector();
    el.btnThink.classList.toggle('active', state.settings.enable_thinking);
  }

  // ===== Event wiring =====
  function wire() {
    el.btnNewChat.addEventListener('click', () => newConversation(''));
    el.btnToggleSidebar.addEventListener('click', () => toggleSidebarDesktop());
    if (el.btnExpandSidebar) {
      el.btnExpandSidebar.addEventListener('click', () => toggleSidebarDesktop());
    }
    el.btnNewChatIcon.addEventListener('click', () => newConversation(''));
    el.btnMobileSidebar.addEventListener('click', () => toggleSidebarMobile());
    el.sidebarBackdrop.addEventListener('click', () => toggleSidebarMobile(false));
    el.btnSearch.addEventListener('click', () => {
      // Inline search: show a search input at top of history list
      const existing = document.getElementById('searchBar');
      if (existing) { existing.remove(); return; }
      const searchBar = document.createElement('div');
      searchBar.id = 'searchBar';
      searchBar.style.cssText = 'padding:0 10px 8px;';
      searchBar.innerHTML = `<input type="text" class="text-input" placeholder="搜索对话..." style="width:100%;font-size:13px;padding:6px 10px;" />`;
      el.historyList.insertBefore(searchBar, el.historyList.firstChild);
      const input = searchBar.querySelector('input');
      input.focus();
      input.addEventListener('input', () => {
        const q = input.value.trim().toLowerCase();
        const items = el.historyList.querySelectorAll('.history-item');
        items.forEach(item => {
          const title = item.querySelector('.h-title')?.textContent.toLowerCase() || '';
          item.style.display = (!q || title.includes(q)) ? '' : 'none';
        });
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') searchBar.remove();
      });
    });

    // Composer
    el.composerInput.addEventListener('input', autoResize);
    el.composerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMessage();
      }
    });
    el.btnSend.addEventListener('click', sendMessage);
    el.btnStop.addEventListener('click', stopStreaming);
    el.btnThink.addEventListener('click', () => {
      state.settings.enable_thinking = !state.settings.enable_thinking;
      el.btnThink.classList.toggle('active', state.settings.enable_thinking);
      el.settingThinking.checked = state.settings.enable_thinking;
      saveSettings();
      toast(state.settings.enable_thinking ? '已开启深度思考' : '已关闭深度思考');
    });
    el.btnMic.addEventListener('click', () => {
      if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        toast('当前浏览器不支持语音识别', 'error'); return;
      }
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      const r = new SR();
      r.lang = 'zh-CN'; r.interimResults = false;
      r.onresult = (ev) => { el.composerInput.value += ev.results[0][0].transcript; autoResize(); };
      r.onerror = () => toast('语音识别失败', 'error');
      r.onend = () => el.btnMic.classList.remove('active');
      r.start();
      el.btnMic.classList.add('active');
    });

    // Attachments
    el.btnAttach.addEventListener('click', () => el.fileInput.click());
    el.fileInput.addEventListener('change', (e) => {
      handleFiles(e.target.files);
      el.fileInput.value = '';
    });
    // Drag-and-drop
    el.composerBox.addEventListener('dragover', (e) => {
      e.preventDefault();
      el.composerBox.classList.add('dragover');
    });
    el.composerBox.addEventListener('dragleave', () => el.composerBox.classList.remove('dragover'));
    el.composerBox.addEventListener('drop', (e) => {
      e.preventDefault();
      el.composerBox.classList.remove('dragover');
      if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
    });
    // Paste images
    el.composerInput.addEventListener('paste', (e) => {
      const items = e.clipboardData?.items || [];
      const files = [];
      for (const it of items) {
        if (it.kind === 'file') {
          const f = it.getAsFile();
          if (f) files.push(f);
        }
      }
      if (files.length) { e.preventDefault(); handleFiles(files); }
    });

    // Welcome suggestions
    $$('.suggest-card').forEach(card => {
      card.addEventListener('click', () => newConversation(card.dataset.prompt));
    });

    // Scroll
    el.conversation.addEventListener('scroll', () => {
      const c = el.conversation;
      const atBottom = (c.scrollHeight - c.scrollTop - c.clientHeight) < 60;
      el.btnScrollDown.classList.toggle('visible', !atBottom && c.scrollHeight > c.clientHeight + 200);
    });
    el.btnScrollDown.addEventListener('click', () => scrollToBottom(true));

    // Model selector
    el.modelSelector.addEventListener('click', (e) => {
      if (!e.target.closest('.model-option')) el.modelSelector.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!el.modelSelector.contains(e.target)) el.modelSelector.classList.remove('open');
    });

    // Share / settings
    el.btnShare.addEventListener('click', () => {
      const conv = currentConversation();
      if (!conv || conv.messages.length === 0) { toast('当前没有可分享的对话'); return; }
      const text = conv.messages.map(m => `**${m.role === 'user' ? '我' : 'Cambium'}：**\n${m.content}`).join('\n\n---\n\n');
      navigator.clipboard.writeText(text).then(() => toast('对话已复制到剪贴板', 'success'));
    });
    el.btnMore.addEventListener('click', () => {
      // Simple "more" menu — for now just open settings
      populateSettingsUI();
      el.settingsModal.style.display = '';
    });

    // User menu
    el.btnUserMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      el.userMenu.style.display = el.userMenu.style.display === 'none' ? '' : 'none';
    });
    // About button
    const btnAbout = $('#btnAbout');
    if (btnAbout) btnAbout.addEventListener('click', () => {
      uiAlert('Cambium — 持续存在的认知层\n\nModels change. Memories grow. Identity persists.\n\n模型会变，记忆会生长，身份得以延续。\n\nhttps://github.com/CyanXLab/Cambium');
    });
    // Debug mode toggle (in settings → general + data)
    const settingDebugMode = $('#settingDebugMode');
    const settingDebugModeGeneral = $('#settingDebugModeGeneral');
    function syncDebugToggle(checked) {
      if (settingDebugMode) settingDebugMode.checked = checked;
      if (settingDebugModeGeneral) settingDebugModeGeneral.checked = checked;
      const btn = $('#debugTabBtn');
      if (btn) btn.style.display = checked ? '' : 'none';
    }
    // Load current state
    fetch('/api/debug/status').then(r => r.json()).then(d => {
      syncDebugToggle(d.debug_mode);
    }).catch(() => {});
    async function toggleDebug() {
      const resp = await fetch('/api/debug/toggle', { method: 'POST' });
      const d = await resp.json();
      syncDebugToggle(d.debug_mode);
      if (d.debug_mode) toast('Debug 模式已开启', 'success');
      else toast('Debug 模式已关闭');
    }
    if (settingDebugMode) {
      settingDebugMode.addEventListener('change', toggleDebug);
    }
    if (settingDebugModeGeneral) {
      settingDebugModeGeneral.addEventListener('change', toggleDebug);
    }

    // Catch-up settings
    const catchupEnabled = $('#settingCatchupEnabled');

    // ===== API Providers =====
    async function loadProviders() {
      const list = $('#providersList');
      const assignDiv = $('#providerAssignments');
      if (!list || !assignDiv) return;
      try {
        const [providersResp, assignResp] = await Promise.all([
          fetch('/api/providers').then(r => r.json()),
          fetch('/api/providers/assignments').then(r => r.json()),
        ]);
        const providers = providersResp.providers || [];
        const assignments = assignResp.assignments || {};
        const tasks = assignResp.tasks || [];

        // Render provider list
        if (providers.length === 0) {
          list.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:8px;">还没有添加供应商。在下方添加第一个。</div>';
        } else {
          list.innerHTML = providers.map(p => `
            <div class="inbox-item" style="padding:8px 12px;">
              <div style="flex:1;">
                <div style="font-weight:600;font-size:13px;">${escapeHtml(p.name)}</div>
                <div style="font-size:11px;color:var(--text-muted);">${escapeHtml(p.base_url)} · ${p.models.length} 个模型</div>
              </div>
              <div class="inbox-item-actions">
                <button class="ghost-btn" data-action="fetch-models" data-id="${p.id}" style="font-size:11px;padding:2px 8px;">获取模型</button>
                <button class="danger" data-action="delete" data-id="${p.id}" style="font-size:11px;padding:2px 8px;">删除</button>
              </div>
            </div>`).join('');
          list.querySelectorAll('button[data-action]').forEach(btn => {
            btn.addEventListener('click', async () => {
              const id = btn.dataset.id;
              const action = btn.dataset.action;
              if (action === 'delete') {
                if (!confirm('删除这个供应商？')) return;
                await fetch(`/api/providers/${id}`, { method: 'DELETE' });
                loadProviders();
              } else if (action === 'fetch-models') {
                btn.textContent = '获取中...';
                try {
                  const r = await fetch(`/api/providers/${id}/fetch-models`, { method: 'POST' }).then(r => r.json());
                  if (r.models && r.models.length > 0) {
                    toast(`获取到 ${r.models.length} 个模型`, 'success');
                    loadProviders();
                  } else {
                    toast('获取失败: ' + (r.error || '无模型'), 'error');
                  }
                } catch (e) { toast('获取失败: ' + e, 'error'); }
                btn.textContent = '获取模型';
              }
            });
          });
        }

        // Render assignments
        const providerOptions = '<option value="">使用主 API</option>' +
          providers.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
        assignDiv.innerHTML = tasks.map(t => `
          <div style="display:flex;align-items:center;gap:8px;padding:4px 0;">
            <span style="flex:1;font-size:13px;">${escapeHtml(t.label)}</span>
            <select class="select-input" data-task="${t.key}" style="max-width:200px;">${providerOptions}</select>
          </div>`).join('');
        assignDiv.querySelectorAll('select[data-task]').forEach(sel => {
          sel.value = assignments[sel.dataset.task] || '';
          sel.addEventListener('change', async () => {
            await fetch('/api/providers/assignments', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ task: sel.dataset.task, provider_id: sel.value }),
            });
            toast('已保存', 'success');
          });
        });
      } catch (e) {
        console.error('loadProviders failed', e);
      }
    }
    const btnProviderAdd = $('#btnProviderAdd');
    if (btnProviderAdd) {
      btnProviderAdd.addEventListener('click', async () => {
        const name = ($('#providerAddName') || {}).value || '';
        const url = ($('#providerAddUrl') || {}).value || '';
        const key = ($('#providerAddKey') || {}).value || '';
        const modelsStr = ($('#providerAddModels') || {}).value || '';
        if (!name || !url) { toast('名称和地址不能为空', 'error'); return; }
        const models = modelsStr ? modelsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
        try {
          await fetch('/api/providers', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name, base_url: url, api_key: key, models }),
          });
          ($('#providerAddName') || {}).value = '';
          ($('#providerAddUrl') || {}).value = '';
          ($('#providerAddKey') || {}).value = '';
          ($('#providerAddModels') || {}).value = '';
          toast('供应商已添加', 'success');
          loadProviders();
        } catch (e) { toast('添加失败: ' + e, 'error'); }
      });
    }
    // Load providers when API tab is opened
    const apiTabBtn = document.querySelector('[data-tab="api"]');
    if (apiTabBtn) {
      apiTabBtn.addEventListener('click', () => setTimeout(loadProviders, 200));
    }

    const catchupStart = $('#settingCatchupStartHour');
    const catchupEnd = $('#settingCatchupEndHour');
    // Load current catchup settings
    fetch('/api/life-loop/status').then(r => r.json()).then(d => {
      const c = d.catchup || {};
      if (catchupEnabled) catchupEnabled.checked = c.enabled || false;
      if (catchupStart && c.start_hour !== undefined) catchupStart.value = c.start_hour;
      if (catchupEnd && c.end_hour !== undefined) catchupEnd.value = c.end_hour;
    }).catch(() => {});
    async function saveCatchupSettings() {
      const payload = {
        enabled: catchupEnabled ? catchupEnabled.checked : false,
        start_hour: catchupStart ? parseInt(catchupStart.value) : 0,
        end_hour: catchupEnd ? parseInt(catchupEnd.value) : 24,
      };
      try {
        await fetch('/api/life-loop/catchup-settings', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload),
        });
      } catch (e) {}
    }
    if (catchupEnabled) catchupEnabled.addEventListener('change', saveCatchupSettings);
    if (catchupStart) catchupStart.addEventListener('change', saveCatchupSettings);
    if (catchupEnd) catchupEnd.addEventListener('change', saveCatchupSettings);
    // Debug tab content loader
    const debugTabBtn = $('#debugTabBtn');
    if (debugTabBtn) {
      debugTabBtn.addEventListener('click', () => {
        setTimeout(loadDebugContent, 100);
      });
    }
    document.addEventListener('click', (e) => {
      if (!el.userMenu.contains(e.target) && !el.btnUserMenu.contains(e.target)) el.userMenu.style.display = 'none';
    });
    el.umSettings.addEventListener('click', () => { el.userMenu.style.display = 'none'; populateSettingsUI(); el.settingsModal.style.display = ''; });
    el.umMemory.addEventListener('click', () => { el.userMenu.style.display = 'none'; openMemoryModal(); });
    el.umHelp.addEventListener('click', () => { el.userMenu.style.display = 'none'; toast('在设置中可以调整所有参数', 'info'); });
    // navMemory is handled by the navItems.forEach loop below (avoids duplicate openMemoryModal)

    // Settings modal
    el.btnCloseSettings.addEventListener('click', () => { applySettingsFromUI(); el.settingsModal.style.display = 'none'; });
    el.settingsModal.addEventListener('click', (e) => { if (e.target === el.settingsModal) { applySettingsFromUI(); el.settingsModal.style.display = 'none'; } });
    // Settings tab navigation
    $$('.settings-nav-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        $$('.settings-nav-item').forEach(b => b.classList.toggle('active', b === btn));
        $$('.settings-tab').forEach(t => {
          t.style.display = t.dataset.tab === tab ? '' : 'none';
        });
      });
    });
    el.settingTemp.addEventListener('input', () => { el.settingTempValue.textContent = el.settingTemp.value; applySettingsFromUI(); });
    el.settingTopP.addEventListener('input', () => { el.settingTopPValue.textContent = el.settingTopP.value; applySettingsFromUI(); });
    el.settingTopK.addEventListener('input', () => { el.settingTopKValue.textContent = el.settingTopK.value; applySettingsFromUI(); });
    el.settingPresencePenalty.addEventListener('input', () => { el.settingPresencePenaltyValue.textContent = el.settingPresencePenalty.value; applySettingsFromUI(); });
    el.settingFrequencyPenalty.addEventListener('input', () => { el.settingFrequencyPenaltyValue.textContent = el.settingFrequencyPenalty.value; applySettingsFromUI(); });
    el.settingMemoryCount.addEventListener('input', () => { el.settingMemoryCountValue.textContent = el.settingMemoryCount.value; applySettingsFromUI(); });
    el.settingApiDelay.addEventListener('input', () => { el.settingApiDelayValue.textContent = el.settingApiDelay.value; applySettingsFromUI(); });
    ['change','blur'].forEach(ev => {
      el.settingApiKey.addEventListener(ev, applySettingsFromUI);
      el.settingApiBaseUrl.addEventListener(ev, applySettingsFromUI);
      el.settingModelSlots.forEach(inp => { if (inp) inp.addEventListener(ev, applySettingsFromUI); });
    });
    el.btnTestApi.addEventListener('click', async () => {
      applySettingsFromUI();
      el.btnTestApi.textContent = '测试中...';
      el.btnTestApi.disabled = true;
      try {
        const resp = await fetch('/api/test', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            api_key: state.settings.api_key,
            api_base_url: state.settings.api_base_url,
            api_model: state.settings.selected_model || state.settings.model_slots[0] || '',
          }),
        });
        const data = await resp.json();
        if (data.success) {
          toast(data.message, 'success');
        } else {
          toast('连接失败: ' + data.message, 'error');
        }
      } catch (e) {
        toast('测试失败: ' + e.message, 'error');
      } finally {
        el.btnTestApi.textContent = '测试连接';
        el.btnTestApi.disabled = false;
      }
    });
    ['change','blur'].forEach(ev => {
      el.settingUserName.addEventListener(ev, applySettingsFromUI);
      el.settingUserPersona.addEventListener(ev, applySettingsFromUI);
      el.settingSystem.addEventListener(ev, applySettingsFromUI);
      el.settingMaxTokens.addEventListener(ev, applySettingsFromUI);
      el.settingThinkingBudget.addEventListener(ev, applySettingsFromUI);
      el.settingStop.addEventListener(ev, applySettingsFromUI);
      el.settingThinking.addEventListener(ev, applySettingsFromUI);
      // settingMemory is handled separately below with sync logic (avoids duplicate applySettingsFromUI)
      el.settingMemoryAuto.addEventListener(ev, applySettingsFromUI);
    });
    // Memory management buttons (there are multiple in different tabs)
    $$('.btn-open-memory').forEach(btn => {
      btn.addEventListener('click', () => {
        applySettingsFromUI();
        el.settingsModal.style.display = 'none';
        openMemoryModal();
      });
    });
    el.btnClearAll.addEventListener('click', () => {
      // Inline confirm: change button text
      const btn = el.btnClearAll;
      if (btn.dataset.confirming === 'true') {
        state.conversations = []; state.currentId = null;
        saveState(); renderHistory(); renderConversation();
        el.settingsModal.style.display = 'none';
        toast('已清空所有对话', 'success');
        btn.dataset.confirming = 'false';
        btn.textContent = '清空对话';
      } else {
        btn.dataset.confirming = 'true';
        btn.textContent = '再次点击确认';
        setTimeout(() => {
          if (btn.dataset.confirming === 'true') {
            btn.dataset.confirming = 'false';
            btn.textContent = '清空对话';
          }
        }, 3000);
      }
    });
    el.btnExport.addEventListener('click', () => {
      const data = JSON.stringify(state.conversations, null, 2);
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `my-ai-conversations-${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast('已导出', 'success');
    });

    // Memory modal
    el.btnCloseMemory.addEventListener('click', () => el.memoryModal.style.display = 'none');
    el.memoryModal.addEventListener('click', (e) => { if (e.target === el.memoryModal) el.memoryModal.style.display = 'none'; });
    el.btnMemoryAdd.addEventListener('click', addMemoryManual);
    el.memoryAddInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addMemoryManual(); });
    el.btnMemorySummaryUpdate.addEventListener('click', updateMemorySummary);
    el.memorySummaryInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') updateMemorySummary(); });
    el.btnMemoryRegenerate.addEventListener('click', regenerateMemorySummary);

    // Temporary chat toggle
    el.btnTemporary.addEventListener('click', () => {
      if (state.streaming) { toast('请等待当前回复完成'); return; }
      state.temporary = !state.temporary;
      el.btnTemporary.classList.toggle('active', state.temporary);
      el.app.classList.toggle('temporary-mode', state.temporary);
      if (state.temporary) {
        // Start a fresh temporary conversation (not based on old one)
        state.currentId = null;
        renderConversation();
        el.composerInput.focus();
        toast('已开启临时对话（不记入历史，不使用记忆，刷新后销毁）');
      } else {
        toast('已关闭临时对话');
      }
    });

    // Accent color picker
    if (el.accentColorPicker) {
      el.accentColorPicker.querySelectorAll('.accent-swatch').forEach(sw => {
        sw.addEventListener('click', () => {
          state.settings.accent_color = sw.dataset.color;
          el.accentColorPicker.querySelectorAll('.accent-swatch').forEach(s => s.classList.toggle('active', s === sw));
          applyTheme();
          saveSettings();
        });
      });
    }
    // Theme/contrast/language change triggers immediate apply
    el.settingThemeAppearance.addEventListener('change', () => { applySettingsFromUI(); });
    el.settingThemeContrast.addEventListener('change', () => { applySettingsFromUI(); });
    el.settingPersonality.addEventListener('change', () => { applySettingsFromUI(); });
    el.settingLanguage.addEventListener('change', () => { applySettingsFromUI(); });
    el.settingUserOccupation.addEventListener('change', applySettingsFromUI);
    el.settingUserDetails.addEventListener('change', applySettingsFromUI);
    el.settingMemoryAutoSummary.addEventListener('change', applySettingsFromUI);

    // ===== Right panel toggle =====
    el.btnRightPanel.addEventListener('click', () => {
      const collapsed = el.mainApp.classList.toggle('right-collapsed');
      // When showing, refresh the list
      if (!collapsed) updateRightPanel();
    });
    el.btnCloseRightPanel.addEventListener('click', () => {
      el.mainApp.classList.add('right-collapsed');
    });

    // ===== Sidebar nav (view switcher) =====
    el.navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        if (view === 'memory') { openMemoryModal(); return; }
        switchView(view);
      });
    });

    // Nav group collapse/expand
    document.querySelectorAll('.nav-group-toggle').forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.preventDefault();
        const group = toggle.closest('.nav-group');
        if (group) group.classList.toggle('collapsed');
      });
    });

    // Resident selector — send resident with chat request
    const residentSelect = document.getElementById('residentSelect');
    if (residentSelect) {
      residentSelect.addEventListener('change', () => {
        state.resident = residentSelect.value || '';
        saveState();
      });
    }

    // History panel toggle
    const btnHistoryToggle = document.getElementById('btnHistoryToggle');
    const btnHistoryClose = document.getElementById('btnHistoryClose');
    const historyPanel = document.getElementById('historyPanel');
    if (btnHistoryToggle) {
      btnHistoryToggle.addEventListener('click', () => {
        if (historyPanel) historyPanel.classList.toggle('open');
      });
    }
    if (btnHistoryClose) {
      btnHistoryClose.addEventListener('click', () => {
        if (historyPanel) historyPanel.classList.remove('open');
      });
    }
    if (el.btnLibBack) el.btnLibBack.addEventListener('click', () => switchView('chat'));
    if (el.btnSkillsBack) el.btnSkillsBack.addEventListener('click', () => switchView('chat'));
    if (el.btnOpenLibrary) el.btnOpenLibrary.addEventListener('click', () => { el.settingsModal.style.display = 'none'; switchView('library'); });
    if (el.btnOpenSkills) el.btnOpenSkills.addEventListener('click', () => { el.settingsModal.style.display = 'none'; switchView('skills'); });
    if (el.btnSessionsBack) el.btnSessionsBack.addEventListener('click', () => switchView('chat'));
    if (el.btnSessionSpawn) el.btnSessionSpawn.addEventListener('click', spawnSessionManual);
    if (el.btnOpenSessions) el.btnOpenSessions.addEventListener('click', () => { el.settingsModal.style.display = 'none'; switchView('sessions'); });
    if (el.btnCronBack) el.btnCronBack.addEventListener('click', () => switchView('chat'));
    if (el.btnCronCreate) el.btnCronCreate.addEventListener('click', createCronJob);
    if (el.btnOpenCron) el.btnOpenCron.addEventListener('click', () => { el.settingsModal.style.display = 'none'; switchView('cron'); });
    if (el.btnDashboardBack) el.btnDashboardBack.addEventListener('click', () => switchView('today'));
    if (el.btnRefreshDashboard) el.btnRefreshDashboard.addEventListener('click', loadDashboard);
    if (el.dashboardMemoryFilter) el.dashboardMemoryFilter.addEventListener('change', loadDashboardMemories);

    // Today view wiring
    if (el.btnTodayChat) el.btnTodayChat.addEventListener('click', () => switchView('chat'));
    if (el.btnTodayCapture) el.btnTodayCapture.addEventListener('click', () => openInboxCaptureModal('text'));
    if (el.btnTodayInbox) el.btnTodayInbox.addEventListener('click', () => switchView('inbox'));
    if (el.btnJournalAiDraft) el.btnJournalAiDraft.addEventListener('click', async () => {
      if (el.btnJournalAiDraft) { el.btnJournalAiDraft.disabled = true; el.btnJournalAiDraft.textContent = 'AI 起草中...'; }
      try { await fetch('/api/daily/journal-draft', { method: 'POST' }); } catch (e) {}
      switchView('journal');
    });
    if (el.btnJournalEdit) el.btnJournalEdit.addEventListener('click', () => switchView('journal'));
    if (el.btnInboxCapture) el.btnInboxCapture.addEventListener('click', () => openInboxCaptureModal('text'));

    // Inbox view wiring
    if (el.btnInboxBack) el.btnInboxBack.addEventListener('click', () => switchView('today'));
    if (el.btnInboxNew) el.btnInboxNew.addEventListener('click', () => openInboxCaptureModal('text'));
    if (el.btnInboxRefresh) el.btnInboxRefresh.addEventListener('click', loadInboxList);
    document.querySelectorAll('[data-inbox-filter]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-inbox-filter]').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        inboxFilter = item.dataset.inboxFilter;
        loadInboxList();
      });
    });

    // Journal view wiring
    if (el.btnJournalBack) el.btnJournalBack.addEventListener('click', () => switchView('today'));
    if (el.btnJournalToday) el.btnJournalToday.addEventListener('click', () => loadJournalView());
    if (el.btnJournalSave) el.btnJournalSave.addEventListener('click', saveJournal);
    if (el.btnJournalAiDraftFull) el.btnJournalAiDraftFull.addEventListener('click', generateJournalAiDraft);
    if (el.btnJournalAdoptDraft) el.btnJournalAdoptDraft.addEventListener('click', () => {
      if (el.journalAiDraftText && el.journalEditor) {
        el.journalEditor.value = el.journalAiDraftText.textContent;
        if (el.journalAiDraft) el.journalAiDraft.style.display = 'none';
      }
    });
    if (el.btnJournalDiscardDraft) el.btnJournalDiscardDraft.addEventListener('click', () => {
      if (el.journalAiDraft) el.journalAiDraft.style.display = 'none';
    });

    // Prompt engineering panel extras
    if (el.btnPromptsExport) el.btnPromptsExport.addEventListener('click', exportPrompts);
    if (el.btnPromptsImport) el.btnPromptsImport.addEventListener('click', importPrompts);
    if (el.btnPromptsResetAll) el.btnPromptsResetAll.addEventListener('click', resetAllPrompts);

    // Morning letter
    if (el.btnGenerateMorning) el.btnGenerateMorning.addEventListener('click', generateMorningLetter);

    // Residents view
    if (el.btnResidentsBack) el.btnResidentsBack.addEventListener('click', () => switchView('today'));
    if (el.btnResidentNew) el.btnResidentNew.addEventListener('click', openResidentCreateModal);
    if (el.btnResidentRun) el.btnResidentRun.addEventListener('click', runResidentManually);
    if (el.btnResidentEdit) el.btnResidentEdit.addEventListener('click', () => {
      if (!currentResidentId) return;
      // Open a simple edit modal for the system prompt
      fetch(`/api/residents/${currentResidentId}`).then(r => r.json()).then(r => {
        const overlay = document.createElement('div');
        overlay.className = 'generic-modal-overlay';
        overlay.innerHTML = `
          <div class="generic-modal">
            <div class="generic-modal-title">编辑居民：${escapeHtml(r.name)}</div>
            <div class="generic-modal-field">
              <label>名字</label>
              <input type="text" id="editResName" value="${escapeHtml(r.name)}" />
            </div>
            <div class="generic-modal-field">
              <label>系统提示词</label>
              <textarea id="editResPrompt" style="min-height:160px;">${escapeHtml(r.system_prompt || '')}</textarea>
            </div>
            <div class="generic-modal-field">
              <label>状态</label>
              <select id="editResStatus">
                <option value="active" ${r.status==='active'?'selected':''}>active</option>
                <option value="paused" ${r.status==='paused'?'selected':''}>paused</option>
                <option value="disabled" ${r.status==='disabled'?'selected':''}>disabled</option>
              </select>
            </div>
            <div class="generic-modal-actions">
              <button class="today-btn" id="editResCancel">取消</button>
              <button class="today-btn primary" id="editResSubmit">保存</button>
            </div>
          </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#editResCancel').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        overlay.querySelector('#editResSubmit').addEventListener('click', async () => {
          await fetch(`/api/residents/${currentResidentId}`, {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
              name: overlay.querySelector('#editResName').value,
              system_prompt: overlay.querySelector('#editResPrompt').value,
              status: overlay.querySelector('#editResStatus').value,
            })
          });
          overlay.remove();
          await loadResidentsView();
          await loadResidentDetail(currentResidentId);
        });
      });
    });

    // Artifacts view
    if (el.btnArtifactsBack) el.btnArtifactsBack.addEventListener('click', () => switchView('today'));
    if (el.btnArtifactNew) el.btnArtifactNew.addEventListener('click', openArtifactCreateModal);
    if (el.btnArtifactSave) el.btnArtifactSave.addEventListener('click', saveCurrentArtifact);
    if (el.btnArtifactNewVersion) el.btnArtifactNewVersion.addEventListener('click', createNewArtifactVersion);
    document.querySelectorAll('[data-artifact-type]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-artifact-type]').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        currentArtifactTypeFilter = item.dataset.artifactType;
        currentArtifactId = null; // reset selection when filter changes
        loadArtifactsView();
      });
    });

    // Philosophy view
    if (el.btnPhilosophyBack) el.btnPhilosophyBack.addEventListener('click', () => switchView('today'));

    // Swarm view wiring
    const btnSwarmBack = document.getElementById('btnSwarmBack');
    const btnSwarmCreate = document.getElementById('btnSwarmCreate');
    const btnSwarmGenerateGoals = document.getElementById('btnSwarmGenerateGoals');
    if (btnSwarmBack) btnSwarmBack.addEventListener('click', () => switchView('today'));
    if (btnSwarmCreate) btnSwarmCreate.addEventListener('click', createSwarmTask);
    if (btnSwarmGenerateGoals) btnSwarmGenerateGoals.addEventListener('click', async () => {
      btnSwarmGenerateGoals.disabled = true;
      btnSwarmGenerateGoals.textContent = '生成中...';
      try {
        const r = await fetch('/api/self-goals/generate', { method: 'POST' }).then(r => r.json());
        if (r.generated > 0) toast(`生成了 ${r.generated} 个目标提案`, 'success');
        else toast('没有发现值得提议的目标', 'info');
        loadSelfGoals();
      } catch (e) { toast('生成失败: ' + e, 'error'); }
      btnSwarmGenerateGoals.disabled = false;
      btnSwarmGenerateGoals.textContent = '生成自主目标';
    });
    if (el.btnPhilosophyNew) el.btnPhilosophyNew.addEventListener('click', openPhilosophyCreateModal);
    document.querySelectorAll('[data-phil-type]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-phil-type]').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        currentPhilosophyTypeFilter = item.dataset.philType;
        loadPhilosophyView();
      });
    });

    // Global hotkeys: Ctrl+J = quick capture
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        openInboxCaptureModal('text');
      }
    });
    if (el.btnTriggerReflection) el.btnTriggerReflection.addEventListener('click', async () => {
      el.btnTriggerReflection.textContent = '反思中...';
      el.btnTriggerReflection.disabled = true;
      try {
        const resp = await fetch('/api/reflections/trigger', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
        const data = await resp.json();
        if (data.success) {
          toast(`反思完成：新增 ${data.new_memories_added} 条记忆`, 'success');
          loadDashboard();
        } else {
          toast('反思失败: ' + (data.error || 'unknown'), 'error');
        }
      } catch (e) {
        toast('反思失败: ' + e.message, 'error');
      } finally {
        el.btnTriggerReflection.textContent = '触发反思';
        el.btnTriggerReflection.disabled = false;
      }
    });

    // ===== RAG upload =====
    if (el.ragUploadZone) {
      el.ragUploadZone.addEventListener('click', () => el.ragFileInput.click());
      el.ragFileInput.addEventListener('change', (e) => {
        uploadRagFiles(e.target.files);
        el.ragFileInput.value = '';
      });
      el.ragUploadZone.addEventListener('dragover', (e) => { e.preventDefault(); el.ragUploadZone.classList.add('dragover'); });
      el.ragUploadZone.addEventListener('dragleave', () => el.ragUploadZone.classList.remove('dragover'));
      el.ragUploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        el.ragUploadZone.classList.remove('dragover');
        if (e.dataTransfer.files) uploadRagFiles(e.dataTransfer.files);
      });
    }

    // ===== Skills =====
    if (el.btnInstallSkill) el.btnInstallSkill.addEventListener('click', createNewSkill);

    // ===== MCP =====
    if (el.btnMcpAdd) el.btnMcpAdd.addEventListener('click', addMcpServer);
    if (el.btnMcpRefresh) el.btnMcpRefresh.addEventListener('click', refreshMcpServers);

    // ===== RAG / Skills settings listeners =====
    if (el.settingRagEnabled) el.settingRagEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingRagCount) el.settingRagCount.addEventListener('input', () => {
      el.settingRagCountValue.textContent = el.settingRagCount.value;
      applySettingsFromUI();
    });
    if (el.settingMcpEnabled) el.settingMcpEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingSkillsEnabled) el.settingSkillsEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingSkillsMode) el.settingSkillsMode.addEventListener('change', applySettingsFromUI);
    if (el.settingMaxSubtasks) el.settingMaxSubtasks.addEventListener('input', () => {
      el.settingMaxSubtasksValue.textContent = el.settingMaxSubtasks.value;
      if (el.settingMaxSubtasksTab2) el.settingMaxSubtasksTab2.value = el.settingMaxSubtasks.value;
      if (el.settingMaxSubtasksTab2Value) el.settingMaxSubtasksTab2Value.textContent = el.settingMaxSubtasks.value;
      applySettingsFromUI();
    });
    if (el.settingMaxSubtasksTab2) el.settingMaxSubtasksTab2.addEventListener('input', () => {
      el.settingMaxSubtasksTab2Value.textContent = el.settingMaxSubtasksTab2.value;
      if (el.settingMaxSubtasks) el.settingMaxSubtasks.value = el.settingMaxSubtasksTab2.value;
      if (el.settingMaxSubtasksValue) el.settingMaxSubtasksValue.textContent = el.settingMaxSubtasksTab2.value;
      applySettingsFromUI();
    });
    if (el.settingSessionsEnabled) el.settingSessionsEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingCronEnabled) el.settingCronEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingRagEmbeddingProvider) el.settingRagEmbeddingProvider.addEventListener('change', applySettingsFromUI);

    // ===== Advanced conversation features =====
    if (el.settingCompressEnabled) el.settingCompressEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingCompressThreshold) el.settingCompressThreshold.addEventListener('input', () => {
      el.settingCompressThresholdValue.textContent = el.settingCompressThreshold.value;
      applySettingsFromUI();
    });
    if (el.settingCompressKeepRecent) el.settingCompressKeepRecent.addEventListener('input', () => {
      el.settingCompressKeepRecentValue.textContent = el.settingCompressKeepRecent.value;
      applySettingsFromUI();
    });
    if (el.settingChatVectorsEnabled) el.settingChatVectorsEnabled.addEventListener('change', applySettingsFromUI);
    if (el.settingChatVectorsTopK) el.settingChatVectorsTopK.addEventListener('input', () => {
      el.settingChatVectorsTopKValue.textContent = el.settingChatVectorsTopK.value;
      applySettingsFromUI();
    });
    if (el.settingEmotionTracking) el.settingEmotionTracking.addEventListener('change', applySettingsFromUI);
    if (el.settingProfileAutoUpdate) el.settingProfileAutoUpdate.addEventListener('change', applySettingsFromUI);
    if (el.settingProactiveRecall) el.settingProactiveRecall.addEventListener('change', applySettingsFromUI);
    if (el.settingEmotionalResonance) el.settingEmotionalResonance.addEventListener('change', applySettingsFromUI);
    if (el.btnRebuildChatVectors) el.btnRebuildChatVectors.addEventListener('click', async () => {
      el.btnRebuildChatVectors.textContent = '重建中...';
      el.btnRebuildChatVectors.disabled = true;
      try {
        const resp = await fetch('/api/chat-vectors/rebuild', { method: 'POST' });
        const data = await resp.json();
        toast(`已重建 ${data.total_chunks} 个向量片段（${data.conversations} 个会话）`, 'success');
      } catch (e) {
        toast('重建失败: ' + e.message, 'error');
      } finally {
        el.btnRebuildChatVectors.textContent = '重建索引';
        el.btnRebuildChatVectors.disabled = false;
      }
    });
    if (el.btnViewProfile) el.btnViewProfile.addEventListener('click', async () => {
      try {
        const [profileResp, emotionResp] = await Promise.all([
          fetch('/api/profile').then(r => r.json()),
          fetch('/api/emotion/state').then(r => r.json()),
        ]);
        const lines = ['=== 用户画像 ==='];
        if (profileResp.auto_summary) lines.push(`总结: ${profileResp.auto_summary}`);
        if (profileResp.personality) lines.push(`性格: ${profileResp.personality}`);
        if (profileResp.interests) lines.push(`兴趣: ${profileResp.interests}`);
        if (profileResp.preferences) lines.push(`偏好: ${profileResp.preferences}`);
        if (profileResp.communication_style) lines.push(`沟通风格: ${profileResp.communication_style}`);
        if (profileResp.emotional_patterns) lines.push(`情绪模式: ${profileResp.emotional_patterns}`);
        if (profileResp.relationships) lines.push(`人际关系: ${profileResp.relationships}`);
        lines.push('', '=== 当前情绪 ===');
        lines.push(`主导情绪: ${emotionResp.current_emotion} (强度 ${Math.round((emotionResp.emotion_intensity || 0) * 100)}%)`);
        const recent = (emotionResp.recent_emotions || []).slice(-5).map(e => e.emotion).join(' → ');
        if (recent) lines.push(`近期轨迹: ${recent}`);
        if (lines.length <= 3) lines.push('（画像尚未建立，多聊几句就会逐渐积累）');
        uiAlert(lines.join('\n'));
      } catch (e) {
        toast('加载失败: ' + e.message, 'error');
      }
    });

    // ===== Backup API =====
    if (el.settingBackupApiEnabled) el.settingBackupApiEnabled.addEventListener('change', applySettingsFromUI);
    ['change','blur'].forEach(ev => {
      if (el.settingBackupApiBaseUrl) el.settingBackupApiBaseUrl.addEventListener(ev, applySettingsFromUI);
      if (el.settingBackupApiKey) el.settingBackupApiKey.addEventListener(ev, applySettingsFromUI);
      if (el.settingBackupApiModel) el.settingBackupApiModel.addEventListener(ev, applySettingsFromUI);
    });
    if (el.btnTestBackupApi) el.btnTestBackupApi.addEventListener('click', async () => {
      applySettingsFromUI();
      el.btnTestBackupApi.textContent = '测试中...';
      el.btnTestBackupApi.disabled = true;
      try {
        const resp = await fetch('/api/models/test-backup', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            api_key: state.settings.backup_api_key,
            base_url: state.settings.backup_api_base_url,
          }),
        });
        const data = await resp.json();
        if (data.success) {
          toast(`连接成功，找到 ${data.models.length} 个模型`, 'success');
          if (data.models.length > 0 && el.settingBackupApiModel && !el.settingBackupApiModel.value) {
            el.settingBackupApiModel.value = data.models[0];
            applySettingsFromUI();
          }
        } else {
          toast('连接失败: ' + data.error, 'error');
        }
      } catch (e) {
        toast('测试失败: ' + e.message, 'error');
      } finally {
        el.btnTestBackupApi.textContent = '测试连接';
        el.btnTestBackupApi.disabled = false;
      }
    });
    if (el.btnUseBackup) el.btnUseBackup.addEventListener('click', async () => {
      applySettingsFromUI();
      if (!state.settings.backup_api_enabled) {
        toast('请先启用备用 API', 'error');
        return;
      }
      if (!(await uiConfirm('确认切换主 API 到备用 API？当前主 API 配置将被覆盖。'))) return;
      try {
        const resp = await fetch('/api/models/use-backup', { method: 'POST' });
        const data = await resp.json();
        if (data.ok) {
          toast(`已切换到备用 API: ${data.api_model || '默认模型'}`, 'success');
          await loadSettings();
          populateSettingsUI();
        } else {
          toast('切换失败: ' + data.error, 'error');
        }
      } catch (e) {
        toast('切换失败: ' + e.message, 'error');
      }
    });

    // ===== Auto-fetch models =====
    if (el.btnAutoFetchModels) el.btnAutoFetchModels.addEventListener('click', async () => {
      applySettingsFromUI();
      el.btnAutoFetchModels.textContent = '获取中...';
      el.btnAutoFetchModels.disabled = true;
      try {
        const resp = await fetch('/api/models/auto', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            api_key: state.settings.api_key,
            base_url: state.settings.api_base_url,
          }),
        });
        const data = await resp.json();
        if (data.success && data.models.length > 0) {
          el.autoFetchResultRow.style.display = '';
          el.autoFetchCount.textContent = `找到 ${data.count} 个模型，选择一个填入模型槽：`;
          el.autoFetchSelect.innerHTML = data.models.map(m =>
            `<option value="${m.id}">${m.id}${m.owned_by ? ' (' + m.owned_by + ')' : ''}</option>`
          ).join('');
          toast(`找到 ${data.count} 个模型`, 'success');
        } else {
          toast('获取失败: ' + (data.error || '未找到模型'), 'error');
        }
      } catch (e) {
        toast('获取失败: ' + e.message, 'error');
      } finally {
        el.btnAutoFetchModels.textContent = '自动获取模型';
        el.btnAutoFetchModels.disabled = false;
      }
    });
    if (el.btnApplyAutoFetch) el.btnApplyAutoFetch.addEventListener('click', () => {
      const selected = el.autoFetchSelect.value;
      if (selected && el.settingModelSlots[0]) {
        el.settingModelSlots[0].value = selected;
        applySettingsFromUI();
        toast(`已填入槽 1: ${selected}`, 'success');
      }
    });
    ['change','blur'].forEach(ev => {
      if (el.settingMemoryApiKey) el.settingMemoryApiKey.addEventListener(ev, applySettingsFromUI);
      if (el.settingMemoryApiBaseUrl) el.settingMemoryApiBaseUrl.addEventListener(ev, applySettingsFromUI);
      if (el.settingMemoryApiModel) el.settingMemoryApiModel.addEventListener(ev, applySettingsFromUI);
      if (el.settingSubtaskApiKey) el.settingSubtaskApiKey.addEventListener(ev, applySettingsFromUI);
      if (el.settingSubtaskApiBaseUrl) el.settingSubtaskApiBaseUrl.addEventListener(ev, applySettingsFromUI);
      if (el.settingSubtaskApiModel) el.settingSubtaskApiModel.addEventListener(ev, applySettingsFromUI);
      if (el.settingRagEmbeddingApiKey) el.settingRagEmbeddingApiKey.addEventListener(ev, applySettingsFromUI);
      if (el.settingRagEmbeddingApiBaseUrl) el.settingRagEmbeddingApiBaseUrl.addEventListener(ev, applySettingsFromUI);
      if (el.settingRagEmbeddingModel) el.settingRagEmbeddingModel.addEventListener(ev, applySettingsFromUI);
      // Prompt engineering
      const promptElKeys = ['settingPromptSystem','settingPromptMemoryEdit','settingPromptMemoryExtract','settingPromptCognitiveExtraction','settingPromptReflection','settingPromptProfileUpdate','settingPromptMetaCognition','settingPromptIdentityAssessment','settingPromptCompress','settingPromptClassifyImportance','settingPromptReflectionTree','settingPromptTitle','settingPromptMemorySummary'];
      for (const k of promptElKeys) {
        if (el[k]) el[k].addEventListener(ev, applySettingsFromUI);
      }
    });

    // Sync two memory toggles
    if (el.settingMemory) el.settingMemory.addEventListener('change', () => {
      if (el.settingMemoryTab2) el.settingMemoryTab2.checked = el.settingMemory.checked;
      applySettingsFromUI();
    });
    if (el.settingMemoryTab2) el.settingMemoryTab2.addEventListener('change', () => {
      el.settingMemory.checked = el.settingMemoryTab2.checked;
      applySettingsFromUI();
    });
    // Make memory facts section collapsible
    const memFactsHeader = document.querySelector('.memory-facts-header');
    if (memFactsHeader) {
      memFactsHeader.addEventListener('click', () => {
        memFactsHeader.parentElement.classList.toggle('collapsed');
      });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); newConversation(''); }
      if ((e.ctrlKey || e.metaKey) && e.key === '/') { e.preventDefault(); el.composerInput.focus(); }
      if (e.key === 'Escape') {
        if (el.settingsModal.style.display !== 'none') { applySettingsFromUI(); el.settingsModal.style.display = 'none'; }
        else if (el.memoryModal.style.display !== 'none') el.memoryModal.style.display = 'none';
      }
    });

    // Save on unload
    window.addEventListener('beforeunload', () => saveState());
  }

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
    const swarmView = document.getElementById('swarmView');
    if (swarmView) swarmView.style.display = (view === 'swarm') ? '' : 'none';
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
    if (view === 'swarm') { loadSwarmTasks(); loadSelfGoals(); }
  }

  // ===== Right panel (chat index) =====
  function updateRightPanel() {
    if (!el.rightPanelList) return;
    const conv = currentConversation();
    if (!conv || conv.messages.length === 0) {
      el.rightPanelList.innerHTML = '<div class="right-panel-empty">当前对话没有用户问题。<br>发送一条消息后，这里会显示问题列表，方便快速跳转。</div>';
      if (el.rightPanelBadge) el.rightPanelBadge.style.display = 'none';
      return;
    }
    const userMsgs = [];
    conv.messages.forEach((m, i) => {
      if (m.role === 'user') userMsgs.push({ msg: m, idx: i });
    });
    if (userMsgs.length === 0) {
      el.rightPanelList.innerHTML = '<div class="right-panel-empty">当前对话没有用户问题。</div>';
      if (el.rightPanelBadge) el.rightPanelBadge.style.display = 'none';
      return;
    }
    if (el.rightPanelBadge) {
      el.rightPanelBadge.style.display = '';
      el.rightPanelBadge.textContent = String(userMsgs.length);
    }
    el.rightPanelList.innerHTML = '';
    userMsgs.forEach((u, i) => {
      const item = document.createElement('button');
      item.className = 'right-panel-item';
      const text = (u.msg.content || '').replace(/\n/g, ' ').slice(0, 80);
      item.textContent = text || '(空消息)';
      item.title = u.msg.content || '';
      item.addEventListener('click', () => {
        const msgEls = el.conversationInner.querySelectorAll('.msg');
        if (msgEls[u.idx]) {
          msgEls[u.idx].scrollIntoView({ behavior: 'smooth', block: 'start' });
          el.rightPanelList.querySelectorAll('.right-panel-item').forEach(x => x.classList.remove('active'));
          item.classList.add('active');
        }
      });
      el.rightPanelList.appendChild(item);
    });
  }

  // ===== RAG file management =====
  async function uploadRagFiles(files) {
    for (const file of files) {
      if (file.size > 20 * 1024 * 1024) {
        toast(`${file.name} 超过 20MB`, 'error');
        continue;
      }
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/rag/upload', { method: 'POST', body: fd });
        if (!resp.ok) {
          const e = await resp.json().catch(() => ({}));
          toast(`上传失败: ${e.detail || 'unknown'}`, 'error');
          continue;
        }
        const data = await resp.json();
        toast(`已上传: ${data.name}`, 'success');
      } catch (e) {
        toast(`上传失败: ${e.message}`, 'error');
      }
    }
    loadRagFiles();
  }

  async function loadRagFiles() {
    if (!el.ragFilesList) return;
    try {
      const resp = await fetch('/api/rag/list');
      const data = await resp.json();
      const files = data.files || [];
      if (files.length === 0) {
        el.ragFilesList.innerHTML = '<div class="rag-empty">还没有上传文件</div>';
        return;
      }
      el.ragFilesList.innerHTML = '';
      for (const f of files) {
        const item = document.createElement('div');
        item.className = 'rag-file-item';
        const sizeKb = (f.size / 1024).toFixed(1);
        const date = new Date(f.created_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
        item.innerHTML = `
          <div class="rag-file-icon">📄</div>
          <div class="rag-file-info">
            <div class="rag-file-name">${escapeHtml(f.name)}</div>
            <div class="rag-file-meta">${sizeKb} KB · ${f.chunks || 0} 个片段 · ${date}</div>
          </div>
          <button class="rag-file-delete" title="删除"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg></button>`;
        item.querySelector('.rag-file-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除 ${f.name}？`))) return;
          await fetch('/api/rag/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ id: f.id }),
          });
          toast('已删除', 'success');
          loadRagFiles();
        });
        el.ragFilesList.appendChild(item);
      }
    } catch (e) {
      el.ragFilesList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  // ===== Skills management =====
  async function loadSkills() {
    if (!el.skillsList) return;
    try {
      const resp = await fetch('/api/skills');
      const data = await resp.json();
      const skills = data.skills || [];
      if (skills.length === 0) {
        el.skillsList.innerHTML = '<div class="rag-empty">还没有技能。点击右上角“+ 新建技能”创建一个。</div>';
        return;
      }
      el.skillsList.innerHTML = '';
      for (const s of skills) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const sizeKb = (s.size / 1024).toFixed(1);
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(s.name)}</span>
            <button class="skill-delete">删除</button>
          </div>
          <div class="skill-item-desc">${escapeHtml(s.description || '(无描述)')}</div>
          <div class="skill-item-meta">
            <span>📦 ${sizeKb} KB</span>
            <span>📝 ${s.size} 字符</span>
          </div>`;
        item.querySelector('.skill-delete').addEventListener('click', async () => {
          if (!(await uiConfirm(`确认删除技能 ${s.name}？`))) return;
          await fetch('/api/skills/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name: s.name }),
          });
          toast('已删除', 'success');
          loadSkills();
        });
        el.skillsList.appendChild(item);
      }
    } catch (e) {
      el.skillsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function createNewSkill() {
    const name = await uiPrompt('技能名称（小写字母、数字、短横线，如 web-search）：');
    if (!name) return;
    if (!/^[a-z0-9-]+$/.test(name)) {
      toast('名称只能包含小写字母、数字和短横线', 'error');
      return;
    }
    const description = await uiPrompt('技能描述（什么情况下 AI 应该使用这个技能？）：') || '';
    const body = await uiPrompt('技能内容（详细指令，可留空稍后编辑）：') || '';
    try {
      const resp = await fetch('/api/skills/create', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, description, body }),
      });
      const data = await resp.json();
      if (data.ok) {
        toast(`已创建技能: ${name}`, 'success');
        loadSkills();
      } else {
        toast(`创建失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('创建失败: ' + e.message, 'error');
    }
  }

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

  // ===== Sessions management =====
  async function loadSessions() {
    if (!el.sessionsList) return;
    try {
      const resp = await fetch('/api/sessions');
      const data = await resp.json();
      const sessions = data.sessions || [];
      if (sessions.length === 0) {
        el.sessionsList.innerHTML = '<div class="rag-empty">还没有后台会话。可以让 AI 通过 sessions_spawn 工具启动，或点击右上角手动启动。</div>';
        return;
      }
      el.sessionsList.innerHTML = '';
      for (const s of sessions) {
        const item = document.createElement('div');
        item.className = 'skill-item';
        const date = s.created_at ? new Date(s.created_at * 1000).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }) : '';
        const statusColor = s.status === 'completed' ? '#10a37f' : s.status === 'running' ? '#a8c7fa' : s.status === 'failed' ? '#ef4444' : '#8e8e8e';
        const result = s.assistant_result ? s.assistant_result.slice(0, 200) + (s.assistant_result.length > 200 ? '...' : '') : '';
        item.innerHTML = `
          <div class="skill-item-header">
            <span class="skill-item-name">${escapeHtml(s.title || s.id)}</span>
            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.06); color:${statusColor};">${s.status}</span>
            <button class="skill-delete">删除</button>
          </div>
          <div class="skill-item-desc" style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
            ${date} · ${s.model || ''} · ${s.id}
          </div>
          ${result ? `<div class="skill-item-desc">${escapeHtml(result)}</div>` : ''}
          ${s.user_message ? `<div class="skill-item-desc" style="margin-top:6px; padding:6px 8px; background:rgba(255,255,255,0.03); border-radius:4px; font-size:12px;"><b>任务:</b> ${escapeHtml(s.user_message.slice(0, 300))}</div>` : ''}`;
        item.style.cursor = 'pointer';
        item.addEventListener('click', (e) => {
          if (e.target.classList.contains('skill-delete')) return;
          openSessionDetail(s.id, s);
        });
        item.querySelector('.skill-delete').addEventListener('click', async (e) => {
          e.stopPropagation();
          if (!(await uiConfirm(`确认删除会话 ${s.title || s.id}？`))) return;
          await fetch(`/api/sessions/${s.id}`, { method: 'DELETE' });
          toast('已删除', 'success');
          loadSessions();
        });
        el.sessionsList.appendChild(item);
      }
    } catch (e) {
      el.sessionsList.innerHTML = `<div class="rag-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function openSessionDetail(sessionId, sessionData) {
    try {
      const resp = await fetch(`/api/sessions/${sessionId}`);
      const s = resp.ok ? await resp.json() : sessionData;
      const overlay = document.createElement('div');
      overlay.className = 'generic-modal-overlay';
      overlay.innerHTML = `
        <div class="generic-modal" style="max-width:700px;max-height:80vh;overflow-y:auto;">
          <div class="generic-modal-title">${escapeHtml(s.title || s.id || '会话详情')}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">
            ${s.status || ''} · ${s.model || ''} · ${s.id || sessionId}
          </div>
          ${s.user_message ? `<div style="margin-bottom:12px;"><b>任务:</b><br>${escapeHtml(s.user_message)}</div>` : ''}
          ${s.assistant_result ? `<div style="margin-bottom:12px;"><b>结果:</b><br><div style="white-space:pre-wrap;">${escapeHtml(s.assistant_result)}</div></div>` : ''}
          <div class="generic-modal-actions">
            <button class="today-btn" id="closeSessionDetail">关闭</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.querySelector('#closeSessionDetail').addEventListener('click', () => overlay.remove());
      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    } catch (e) {
      toast('加载会话详情失败: ' + e, 'error');
    }
  }

  async function spawnSessionManual() {
    const title = await uiPrompt('会话标题（如：研究旅行计划）：');
    if (!title) return;
    const message = await uiPrompt('任务描述（AI 要做什么）：');
    if (!message) return;
    try {
      const resp = await fetch('/api/sessions/spawn', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title, message }),
      });
      const data = await resp.json();
      if (data.session_id) {
        toast(`已启动会话: ${title}`, 'success');
        loadSessions();
      } else {
        toast(`启动失败: ${data.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      toast('启动失败: ' + e.message, 'error');
    }
  }

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
      const resp = await fetch('/api/memory-dashboard');
      const data = await resp.json();
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


  // ===== Debug Content Loader (inside settings) =====
  async function loadDebugContent() {
    try {
      const [dataResp, healthResp] = await Promise.all([
        fetch('/api/debug/all-data').then(r => r.json()),
        fetch('/api/debug/health').then(r => r.json()),
      ]);

      // System Health
      const healthGrid = $('#debugHealthGrid');
      if (healthGrid) {
        let html = '';
        for (const [k, v] of Object.entries(healthResp)) {
          if (k.startsWith('_')) continue;
          const color = v === 0 ? 'var(--text-muted)' : v === -1 ? '#ef4444' : 'var(--text-primary)';
          html += `<div style="background:var(--bg-elevated); padding:6px 10px; border-radius:6px; font-size:12px;"><span style="color:var(--text-muted);">${k}:</span> <span style="color:${color}; font-weight:600;">${v === -1 ? 'N/A' : v}</span></div>`;
        }
        healthGrid.innerHTML = html;
      }

      // AI Data Stats
      const dataGrid = $('#debugDataGrid');
      if (dataGrid) {
        const stats = dataResp.stats || {};
        let html = '';
        for (const [k, v] of Object.entries(stats)) {
          html += `<div style="background:var(--bg-elevated); padding:6px 10px; border-radius:6px; font-size:12px;"><span style="color:var(--text-muted);">${k}:</span> <span style="font-weight:600;">${v}</span></div>`;
        }
        dataGrid.innerHTML = html;
      }

      // Identity
      const identityBox = $('#debugIdentityBox');
      if (identityBox) {
        if (dataResp.identity) {
          identityBox.textContent = `名字: ${dataResp.identity.name || 'Cambium'}\n阶段: ${dataResp.identity.current_phase || 'forming'}\n\n${dataResp.identity.self_narrative || '(无叙事)'}`;
        } else {
          identityBox.textContent = '(尚未初始化)';
        }
      }

      // Memory Summary
      const summaryBox = $('#debugSummaryBox');
      if (summaryBox) {
        summaryBox.textContent = (dataResp.memory_summary && dataResp.memory_summary.summary) || '(无摘要)';
      }

      // Memories
      const memList = $('#debugMemoriesList');
      if (memList) {
        if (dataResp.memories && dataResp.memories.length > 0) {
          memList.innerHTML = dataResp.memories.slice(0, 15).map(m =>
            `<div style="background:var(--bg-elevated); padding:6px 10px; border-radius:6px; font-size:12px; margin-bottom:4px;"><span style="color:var(--text-muted);">[${m.layer}] imp=${m.importance}</span> ${escapeHtml(m.content.slice(0, 120))}</div>`
          ).join('');
        } else {
          memList.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">(无记忆)</div>';
        }
      }

      // Reflections
      const refList = $('#debugReflectionsList');
      if (refList) {
        if (dataResp.reflections && dataResp.reflections.length > 0) {
          refList.innerHTML = dataResp.reflections.slice(0, 5).map(r =>
            `<div style="background:var(--bg-elevated); padding:6px 10px; border-radius:6px; font-size:12px; margin-bottom:4px;"><span style="color:var(--text-muted);">[${r.trigger}]</span> ${escapeHtml((r.summary || '').slice(0, 150))}</div>`
          ).join('');
        } else {
          refList.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">(无反思)</div>';
        }
      }

      // Life Loop
      const llBox = $('#debugLifeLoopBox');
      if (llBox) {
        if (dataResp.life_loop) {
          let html = '';
          for (const [k, v] of Object.entries(dataResp.life_loop)) {
            const ago = v.seconds_ago ? Math.round(v.seconds_ago / 60) + ' 分钟前' : '从未';
            html += `<div>${k}: ${ago}</div>`;
          }
          llBox.innerHTML = html;
        } else {
          llBox.textContent = '(无数据)';
        }
      }

      // Wire debug buttons (they may have been added before content was loaded)
      document.querySelectorAll('.debug-accelerate').forEach(btn => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = 'true';
        btn.addEventListener('click', async () => {
          const secs = parseInt(btn.dataset.secs);
          const orig = btn.textContent;
          btn.textContent = '加速中...';
          await fetch('/api/debug/accelerate-time', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ seconds: secs }),
          });
          btn.textContent = '✓';
          toast(`时间加速 ${secs / 3600}h`, 'success');
          setTimeout(() => { btn.textContent = orig; }, 1500);
        });
      });

      document.querySelectorAll('.debug-trigger').forEach(btn => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = 'true';
        btn.addEventListener('click', async () => {
          const cycle = btn.dataset.cycle;
          const orig = btn.textContent;
          btn.textContent = '执行中...';
          btn.disabled = true;
          try {
            const resp = await fetch('/api/debug/trigger-cycle', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ cycle }),
            });
            const d = await resp.json();
            if (d.ok) toast(`${cycle} 触发成功`, 'success');
            else toast(`失败: ${d.error}`, 'error');
          } catch (e) { toast('失败: ' + e.message, 'error'); }
          btn.disabled = false;
          btn.textContent = orig;
        });
      });

      document.querySelectorAll('.debug-clear').forEach(btn => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = 'true';
        btn.addEventListener('click', async () => {
          const store = btn.dataset.store;
          if (!(await uiConfirm(`确认清空 ${store}？`))) return;
          const resp = await fetch('/api/debug/clear', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ store }),
          });
          const d = await resp.json();
          toast(`已清空 ${d.deleted} 条`, 'success');
          loadDebugContent();
        });
      });

    } catch (e) {
      console.error('debug content load failed', e);
    }
  }

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

  // ===== Inbox view =====
  let inboxFilter = 'all';
  async function loadInboxList() {
    if (!el.inboxListContainer) return;
    try {
      const params = new URLSearchParams();
      if (inboxFilter !== 'all') params.set('status', inboxFilter);
      params.set('limit', '100');
      const resp = await fetch('/api/inbox/items?' + params.toString());
      const data = await resp.json();
      const items = data.items || [];
      if (items.length === 0) {
        el.inboxListContainer.innerHTML = '<div class="inbox-empty">Inbox 是空的。点击 "新建捕获" 添加任何东西。</div>';
        return;
      }
      el.inboxListContainer.innerHTML = items.map(it => {
        const ts = new Date(it.created_at * 1000).toLocaleString('zh-CN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
        const statusLabel = it.status === 'pending' ? '待处理' : (it.status === 'processed' ? '已处理→' + (it.destination || '') : (it.status === 'archived' ? '已归档' : it.status));
        return `<div class="inbox-item" data-id="${it.id}">
          <span class="inbox-item-type">${it.type}</span>
          <div class="inbox-item-body">
            ${it.title ? `<div class="inbox-item-title">${escapeHtml(it.title)}</div>` : ''}
            <div class="inbox-item-content">${escapeHtml(it.content.slice(0, 300))}${it.content.length > 300 ? '…' : ''}</div>
            <div class="inbox-item-meta">
              <span class="inbox-item-status ${it.status}">${statusLabel}</span>
              <span>${ts}</span>
              ${it.suggested_destination ? `<span class="inbox-item-suggested">建议: ${it.suggested_destination}</span>` : ''}
            </div>
          </div>
          <div class="inbox-item-actions">
            ${it.status === 'pending' ? `<button data-action="process" data-id="${it.id}" data-dest="${it.suggested_destination || 'note'}">处理</button>` : ''}
            ${it.status !== 'archived' ? `<button data-action="archive" data-id="${it.id}">归档</button>` : ''}
            <button data-action="delete" data-id="${it.id}" class="danger">删除</button>
          </div>
        </div>`;
      }).join('');
      // Wire action buttons
      el.inboxListContainer.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          if (action === 'delete') {
            if (!confirm('删除这个 Inbox 项？')) return;
            await fetch(`/api/inbox/items/${id}`, { method: 'DELETE' });
          } else if (action === 'archive') {
            await fetch(`/api/inbox/items/${id}/archive`, { method: 'POST' });
          } else if (action === 'process') {
            const dest = btn.dataset.dest || 'note';
            await fetch(`/api/inbox/items/${id}/process`, {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ destination: dest })
            });
          }
          loadInboxList();
        });
      });
    } catch (e) {
      el.inboxListContainer.innerHTML = '<div class="inbox-empty">加载失败：' + escapeHtml(String(e)) + '</div>';
    }
  }

  function openInboxCaptureModal(prefillType = 'text', prefillContent = '') {
    // Remove existing
    const existing = document.querySelector('.inbox-capture-overlay');
    if (existing) existing.remove();
    let currentType = prefillType;
    const overlay = document.createElement('div');
    overlay.className = 'inbox-capture-overlay';
    overlay.innerHTML = `
      <div class="inbox-capture-modal">
        <div class="inbox-capture-title">捕获到 Inbox</div>
        <div class="inbox-capture-types">
          ${['text','url','todo','idea','note'].map(t => `
            <button class="inbox-capture-type-btn ${t === currentType ? 'active' : ''}" data-type="${t}">${t}</button>
          `).join('')}
        </div>
        <textarea class="inbox-capture-input" placeholder="输入任何东西... 想法、链接、待办、灵感。Life Loop 会自动归类。">${escapeHtml(prefillContent)}</textarea>
        <div class="inbox-capture-suggested">建议归类：<span id="captureSuggested">...</span></div>
        <div class="inbox-capture-actions">
          <button class="today-btn" id="captureCancel">取消</button>
          <button class="today-btn primary" id="captureSubmit">保存</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const ta = overlay.querySelector('.inbox-capture-input');
    const suggestedEl = overlay.querySelector('#captureSuggested');
    const updateSuggested = async () => {
      try {
        const r = await fetch('/api/inbox/route-suggest', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ content: ta.value, type: currentType })
        });
        const d = await r.json();
        suggestedEl.textContent = d.destination;
      } catch (e) { suggestedEl.textContent = '...'; }
    };
    overlay.querySelectorAll('.inbox-capture-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        currentType = btn.dataset.type;
        overlay.querySelectorAll('.inbox-capture-type-btn').forEach(b => b.classList.toggle('active', b === btn));
        updateSuggested();
      });
    });
    ta.addEventListener('input', () => { if (ta.value.length % 10 === 0) updateSuggested(); });
    overlay.querySelector('#captureCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#captureSubmit').addEventListener('click', async () => {
      const content = ta.value.trim();
      if (!content) { ta.focus(); return; }
      try {
        await fetch('/api/inbox/items', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ type: currentType, content, source: 'manual' })
        });
        overlay.remove();
        if (el.inboxView && el.inboxView.style.display !== 'none') loadInboxList();
        // Refresh badge
        try {
          const stats = await fetch('/api/inbox/stats').then(r => r.json());
          if (el.inboxBadge) {
            if (stats.pending > 0) { el.inboxBadge.style.display = ''; el.inboxBadge.textContent = stats.pending; }
            else { el.inboxBadge.style.display = 'none'; }
          }
        } catch (e) {}
      } catch (e) {
        alert('保存失败：' + e);
      }
    });
    ta.focus();
    updateSuggested();
  }

  // ===== Journal view =====
  let currentJournalDate = null;
  async function loadJournalView(dateStr) {
    if (!el.journalView) return;
    if (!dateStr) {
      // Default to today
      const d = new Date();
      dateStr = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    }
    currentJournalDate = dateStr;
    if (el.journalTitle) el.journalTitle.textContent = `日志 · ${dateStr}`;
    try {
      // Get journal entry
      let j;
      try {
        const r = await fetch(`/api/journal/${dateStr}`);
        if (r.ok) j = await r.json();
        else j = await fetch('/api/journal/today').then(r => r.json());
      } catch (e) {
        j = await fetch('/api/journal/today').then(r => r.json());
      }
      if (el.journalEditor) el.journalEditor.value = j.content || '';
      if (el.journalHighlights) el.journalHighlights.value = (j.highlights || []).join(' / ');
      if (el.journalGrowth) el.journalGrowth.value = j.growth_notes || '';
      if (el.journalFailures) el.journalFailures.value = j.failures || '';
      if (el.journalGratitude) el.journalGratitude.value = j.gratitude || '';
      // Tone
      if (el.journalTone) {
        if (j.emotional_tone) {
          el.journalTone.style.display = '';
          el.journalTone.textContent = '情绪：' + j.emotional_tone;
        } else {
          el.journalTone.style.display = 'none';
        }
      }
      // AI draft
      if (el.journalAiDraft) {
        if (j.ai_draft && j.ai_draft !== '（今日暂无活动记录）' && j.ai_draft.length > 10) {
          el.journalAiDraft.style.display = '';
          if (el.journalAiDraftText) el.journalAiDraftText.textContent = j.ai_draft;
        } else {
          el.journalAiDraft.style.display = 'none';
        }
      }
      // Streak
      try {
        const sr = await fetch('/api/journal/streak').then(r => r.json());
        if (el.journalStreakInfo) {
          el.journalStreakInfo.textContent = `连续 ${sr.current_streak} 天 · 累计 ${sr.total_entries} 篇 · 最长 ${sr.longest_streak} 天`;
        }
      } catch (e) {}
      // History list
      try {
        const lr = await fetch('/api/journal/list?days=60').then(r => r.json());
        if (el.journalHistoryList) {
          const items = (lr.items || []).filter(x => x.content);
          if (items.length === 0) {
            el.journalHistoryList.innerHTML = '<div class="history-empty">暂无历史日志</div>';
          } else {
            el.journalHistoryList.innerHTML = items.map(j => {
              const d = new Date(j.date + 'T00:00:00');
              const month = d.getMonth() + 1, day = d.getDate();
              const preview = (j.content || '').slice(0, 40).replace(/\n/g, ' ');
              return `<div class="history-item" data-date="${j.date}">
                <div class="history-item-title">${month}月${day}日</div>
                <div class="history-item-preview">${escapeHtml(preview)}</div>
              </div>`;
            }).join('');
            el.journalHistoryList.querySelectorAll('.history-item').forEach(item => {
              item.addEventListener('click', () => loadJournalView(item.dataset.date));
            });
          }
        }
      } catch (e) {}
    } catch (e) {
      console.error('loadJournalView failed', e);
    }
  }

  async function saveJournal() {
    if (!currentJournalDate) return;
    const payload = {
      content: el.journalEditor ? el.journalEditor.value : '',
      highlights: el.journalHighlights ? el.journalHighlights.value.split('/').map(s => s.trim()).filter(Boolean) : [],
      growth_notes: el.journalGrowth ? el.journalGrowth.value : '',
      failures: el.journalFailures ? el.journalFailures.value : '',
      gratitude: el.journalGratitude ? el.journalGratitude.value : '',
    };
    try {
      await fetch(`/api/journal/${currentJournalDate}/content`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: payload.content })
      });
      await fetch(`/api/journal/${currentJournalDate}/fields`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          highlights: payload.highlights,
          growth_notes: payload.growth_notes,
          failures: payload.failures,
          gratitude: payload.gratitude,
        })
      });
      // Tiny toast
      const t = document.createElement('div');
      t.textContent = '✓ 已保存';
      t.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;z-index:99999;';
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 1500);
    } catch (e) {
      alert('保存失败：' + e);
    }
  }

  async function generateJournalAiDraft() {
    if (!currentJournalDate) return;
    const btn = el.btnJournalAiDraftFull;
    if (btn) { btn.disabled = true; btn.textContent = 'AI 起草中...'; }
    try {
      const r = await fetch(`/api/journal/${currentJournalDate}/ai-draft`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.text();
        alert('AI 起草失败：' + err);
      } else {
        await loadJournalView(currentJournalDate);
      }
    } catch (e) {
      alert('AI 起草失败：' + e);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'AI 起草'; }
    }
  }

  // ===== Morning Letter =====
  async function loadMorningLetter(dateStr) {
    if (!el.morningLetterBody) return;
    try {
      const r = await fetch(`/api/mornings/${dateStr}`).then(r => r.ok ? r.json() : null);
      if (!r || !r.letter) {
        el.morningLetterBody.innerHTML = '<div class="today-empty">今天还没有信。点击"生成"让 Cambium 给你写一封。</div>';
        if (el.morningConcerns) el.morningConcerns.style.display = 'none';
        if (el.morningLetterMeta) el.morningLetterMeta.textContent = '今天的信（未生成）';
        return;
      }
      // Render letter (basic markdown: paragraphs, bold, italic)
      const html = r.letter
        .split(/\n\n+/)
        .map(p => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
        .join('');
      el.morningLetterBody.innerHTML = html;
      if (el.morningLetterMeta) {
        const time = new Date(r.generated_at * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        el.morningLetterMeta.textContent = `今天的信 · ${time} · 心情: ${r.mood || 'neutral'}`;
      }
      // Concerns
      if (r.concerns && r.concerns.length > 0) {
        if (el.morningConcerns) el.morningConcerns.style.display = '';
        if (el.morningConcernsList) {
          el.morningConcernsList.innerHTML = r.concerns.map(c => `
            <div class="morning-concern-item">
              <div class="concern-title">${escapeHtml(c.title || '')}</div>
              ${c.why ? `<div class="concern-why">${escapeHtml(c.why)}</div>` : ''}
            </div>`).join('');
        }
      } else {
        if (el.morningConcerns) el.morningConcerns.style.display = 'none';
      }
    } catch (e) {
      console.error('loadMorningLetter failed', e);
    }
  }

  async function generateMorningLetter() {
    if (!el.btnGenerateMorning) return;
    const btn = el.btnGenerateMorning;
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>生成中...</span>';
    try {
      const today = new Date();
      const dateStr = today.getFullYear() + '-' + String(today.getMonth()+1).padStart(2,'0') + '-' + String(today.getDate()).padStart(2,'0');
      const r = await fetch(`/api/mornings/${dateStr}/generate`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.text();
        alert('生成失败：' + err);
      } else {
        await loadMorningLetter(dateStr);
      }
    } catch (e) {
      alert('生成失败：' + e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }

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

  // ===== Residents view =====
  let currentResidentId = null;
  async function loadResidentsView() {
    if (!el.residentsView) return;
    try {
      const r = await fetch('/api/residents').then(r => r.json());
      const items = r.items || [];
      if (el.residentsListSidebar) {
        if (items.length === 0) {
          el.residentsListSidebar.innerHTML = '<div class="history-empty">还没有居民</div>';
        } else {
          el.residentsListSidebar.innerHTML = items.map(res => `
            <div class="history-item ${res.id === currentResidentId ? 'active' : ''}" data-resident-id="${res.id}">
              <div class="history-item-title">${escapeHtml(res.name)}</div>
              <div class="history-item-preview">${res.role} · ${res.status}</div>
            </div>`).join('');
          el.residentsListSidebar.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
              currentResidentId = item.dataset.residentId;
              loadResidentDetail(currentResidentId);
              loadResidentsView(); // refresh active state
            });
          });
        }
      }
      // Auto-select first if none selected
      if (!currentResidentId && items.length > 0) {
        currentResidentId = items[0].id;
        loadResidentDetail(currentResidentId);
      }
    } catch (e) {
      console.error('loadResidentsView failed', e);
    }
  }

  async function loadResidentDetail(residentId) {
    if (!el.residentsViewContainer) return;
    try {
      const r = await fetch(`/api/residents/${residentId}`).then(r => r.json());
      const runsR = await fetch(`/api/residents/${residentId}/runs?limit=5`).then(r => r.json());
      const runs = runsR.items || [];
      if (el.residentTitle) el.residentTitle.textContent = r.name;
      const traits = r.personality_traits || {};
      const traitLabels = { rigor: '严谨', curiosity: '好奇', pushback: '反驳', patience: '耐心' };
      const traitsHtml = Object.keys(traitLabels).map(k => {
        const v = traits[k] || 0;
        return `<div class="resident-trait">
          <div class="resident-trait-label">${traitLabels[k]} (${(v*100).toFixed(0)}%)</div>
          <div class="resident-trait-bar"><div class="resident-trait-fill" style="width:${v*100}%"></div></div>
        </div>`;
      }).join('');

      const concerns = r.current_concerns || [];
      const concernsHtml = concerns.length > 0
        ? concerns.map(c => `<div class="resident-concern">${escapeHtml(c.title || c)}</div>`).join('')
        : '<div style="color:var(--text-muted); font-style:italic; font-size:13px;">暂无当前关注</div>';

      const runsHtml = runs.length > 0
        ? runs.map(run => `<div class="resident-run">
            <span class="resident-run-status ${run.status}">${run.status}</span>
            <span class="resident-run-trigger">${escapeHtml(run.trigger)}</span>
            <span class="resident-run-time">${new Date(run.created_at * 1000).toLocaleString('zh-CN')}</span>
          </div>`).join('')
        : '<div style="color:var(--text-muted); font-style:italic; font-size:13px;">还没有运行记录</div>';

      el.residentsViewContainer.innerHTML = `
        <div class="resident-detail">
          <div class="resident-detail-header">
            <div class="resident-avatar">${escapeHtml(r.name.charAt(0).toUpperCase())}</div>
            <div>
              <div class="resident-name">${escapeHtml(r.name)}
                <span class="resident-status ${r.status}">${r.status}</span>
              </div>
              <div class="resident-role">${r.role} · 运行 ${r.run_count} 次</div>
            </div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">人格设定</div>
            <div class="resident-system-prompt">${escapeHtml(r.system_prompt || '(空)')}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">个性特征</div>
            <div class="resident-traits">${traitsHtml}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">当前在想的事</div>
            <div class="resident-concerns-list">${concernsHtml}</div>
          </div>
          <div class="resident-section">
            <div class="resident-section-label">最近运行</div>
            <div class="resident-runs">${runsHtml}</div>
          </div>
        </div>`;
    } catch (e) {
      console.error('loadResidentDetail failed', e);
      el.residentsViewContainer.innerHTML = '<div class="residents-empty">加载失败</div>';
    }
  }

  function openResidentCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">创建新居民</div>
        <div class="generic-modal-field">
          <label>名字</label>
          <input type="text" id="newResName" placeholder="例如：Debugger" />
        </div>
        <div class="generic-modal-field">
          <label>角色</label>
          <select id="newResRole">
            <option value="custom">自定义</option>
            <option value="architect">Architect (架构师)</option>
            <option value="researcher">Researcher (研究员)</option>
            <option value="writer">Writer (作家)</option>
            <option value="planner">Planner (规划师)</option>
            <option value="historian">Historian (史官)</option>
            <option value="designer">Designer (设计师)</option>
            <option value="critic">Critic (批评者)</option>
            <option value="debugger">Debugger (调试员)</option>
            <option value="explorer">Explorer (探索者)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>系统提示词 (人格设定)</label>
          <textarea id="newResPrompt" placeholder="描述这个居民的性格、专长、说话方式..."></textarea>
        </div>
        <div class="generic-modal-field">
          <label>运行模式</label>
          <select id="newResMode">
            <option value="async">异步 (后台排队)</option>
            <option value="sync">同步 (内联)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>最大重试次数</label>
          <input type="number" id="newResRetries" value="3" min="0" max="10" />
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newResCancel">取消</button>
          <button class="today-btn primary" id="newResSubmit">创建</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newResCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newResSubmit').addEventListener('click', async () => {
      const name = overlay.querySelector('#newResName').value.trim();
      if (!name) { overlay.querySelector('#newResName').focus(); return; }
      const payload = {
        name,
        role: overlay.querySelector('#newResRole').value,
        system_prompt: overlay.querySelector('#newResPrompt').value,
        mode: overlay.querySelector('#newResMode').value,
        max_retries: parseInt(overlay.querySelector('#newResRetries').value) || 3,
        personality_traits: { rigor: 0.7, curiosity: 0.7, pushback: 0.5, patience: 0.7 },
      };
      try {
        const r = await fetch('/api/residents', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        }).then(r => r.json());
        overlay.remove();
        currentResidentId = r.id;
        await loadResidentsView();
        await loadResidentDetail(r.id);
      } catch (e) {
        alert('创建失败：' + e);
      }
    });
  }

  async function runResidentManually() {
    if (!currentResidentId) return;
    const btn = el.btnResidentRun;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span>运行中...</span>'; }
    try {
      const r = await fetch(`/api/residents/${currentResidentId}/run`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ trigger: 'manual', input: '' })
      }).then(r => r.json());
      if (r.status === 'completed') {
        await loadResidentDetail(currentResidentId);
      } else {
        alert('运行失败：' + (r.error || r.status));
      }
    } catch (e) {
      alert('运行失败：' + e);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>运行</span>';
      }
    }
  }

  // ===== Artifacts view =====
  let currentArtifactId = null;
  let currentArtifactTypeFilter = 'all';
  async function loadArtifactsView() {
    if (!el.artifactsView) return;
    try {
      const params = new URLSearchParams();
      if (currentArtifactTypeFilter !== 'all') params.set('type', currentArtifactTypeFilter);
      params.set('limit', '100');
      const r = await fetch('/api/artifacts?' + params.toString()).then(r => r.json());
      const items = r.items || [];
      // Populate sidebar with artifacts (reuse residentsListSidebar pattern but we need separate)
      // For simplicity, render list inside the main container as a list view
      if (items.length === 0) {
        el.artifactsViewContainer.innerHTML = '<div class="artifacts-empty">还没有作品。点击"新建作品"创建第一个。</div>';
        return;
      }
      // If no current artifact selected, show list view
      if (!currentArtifactId) {
        el.artifactsViewContainer.innerHTML = `
          <div class="artifact-list" style="max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:8px;">
            ${items.map(a => `
              <div class="inbox-item" data-artifact-id="${a.id}" style="cursor:pointer;">
                <span class="inbox-item-type">${a.type}</span>
                <div class="inbox-item-body">
                  <div class="inbox-item-title">${escapeHtml(a.title)} <span style="color:var(--text-muted);font-size:11px;">v${a.version}</span></div>
                  <div class="inbox-item-content">${escapeHtml((a.content || '').slice(0, 100))}${a.content && a.content.length > 100 ? '…' : ''}</div>
                  <div class="inbox-item-meta">
                    <span>${new Date(a.updated_at * 1000).toLocaleString('zh-CN')}</span>
                    <span>by ${a.created_by}</span>
                    ${a.tags && a.tags.length > 0 ? `<span>#${a.tags.join(' #')}</span>` : ''}
                  </div>
                </div>
              </div>`).join('')}
          </div>`;
        el.artifactsViewContainer.querySelectorAll('[data-artifact-id]').forEach(item => {
          item.addEventListener('click', () => {
            currentArtifactId = item.dataset.artifactId;
            loadArtifactDetail(currentArtifactId);
          });
        });
      } else {
        await loadArtifactDetail(currentArtifactId);
      }
    } catch (e) {
      console.error('loadArtifactsView failed', e);
    }
  }

  async function loadArtifactDetail(artifactId) {
    if (!el.artifactsViewContainer) return;
    try {
      const a = await fetch(`/api/artifacts/${artifactId}`).then(r => r.json());
      if (el.artifactTitle) el.artifactTitle.textContent = a.title;
      el.artifactsViewContainer.innerHTML = `
        <div class="artifact-detail">
          <div class="artifact-header">
            <input class="artifact-title-input" id="artifactTitleInput" value="${escapeHtml(a.title)}" />
            <div class="artifact-meta-row">
              <span class="artifact-type-badge">${a.type}</span>
              <span class="artifact-version">v${a.version}</span>
              <span>${new Date(a.updated_at * 1000).toLocaleString('zh-CN')}</span>
              <span>by ${a.created_by}</span>
              ${a.created_with_resident ? `<span>with ${escapeHtml(a.created_with_resident)}</span>` : ''}
            </div>
          </div>
          <textarea class="artifact-editor" id="artifactEditor">${escapeHtml(a.content || '')}</textarea>
          <div class="artifact-tags-row">
            ${(a.tags || []).map(t => `<span class="artifact-tag">#${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>`;
      currentArtifactId = artifactId;
    } catch (e) {
      console.error('loadArtifactDetail failed', e);
    }
  }

  async function saveCurrentArtifact() {
    if (!currentArtifactId) return;
    const titleInput = document.getElementById('artifactTitleInput');
    const editor = document.getElementById('artifactEditor');
    if (!titleInput || !editor) return;
    try {
      await fetch(`/api/artifacts/${currentArtifactId}`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title: titleInput.value, content: editor.value })
      });
      const t = document.createElement('div');
      t.textContent = '✓ 已保存';
      t.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;z-index:99999;';
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 1500);
    } catch (e) {
      alert('保存失败：' + e);
    }
  }

  function openArtifactCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">新建作品</div>
        <div class="generic-modal-field">
          <label>标题</label>
          <input type="text" id="newArtTitle" placeholder="例如：README v3" />
        </div>
        <div class="generic-modal-field">
          <label>类型</label>
          <select id="newArtType">
            <option value="readme">README</option>
            <option value="design">设计文档</option>
            <option value="paper">论文</option>
            <option value="prompt">Prompt</option>
            <option value="code">代码</option>
            <option value="note">笔记</option>
            <option value="project">项目</option>
            <option value="plan">计划</option>
            <option value="research">研究</option>
            <option value="essay">文章</option>
            <option value="outline">大纲</option>
            <option value="draft">草稿</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>内容 (可留空，稍后编辑)</label>
          <textarea id="newArtContent" placeholder="开始写..."></textarea>
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newArtCancel">取消</button>
          <button class="today-btn primary" id="newArtSubmit">创建</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newArtCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newArtSubmit').addEventListener('click', async () => {
      const title = overlay.querySelector('#newArtTitle').value.trim();
      if (!title) { overlay.querySelector('#newArtTitle').focus(); return; }
      const payload = {
        title,
        type: overlay.querySelector('#newArtType').value,
        content: overlay.querySelector('#newArtContent').value,
        created_by: 'user',
      };
      try {
        const r = await fetch('/api/artifacts', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        }).then(r => r.json());
        overlay.remove();
        currentArtifactId = r.id;
        await loadArtifactDetail(r.id);
      } catch (e) {
        alert('创建失败：' + e);
      }
    });
  }

  async function createNewArtifactVersion() {
    if (!currentArtifactId) return;
    const editor = document.getElementById('artifactEditor');
    if (!editor) return;
    try {
      const r = await fetch(`/api/artifacts/${currentArtifactId}/new-version`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ content: editor.value })
      }).then(r => r.json());
      currentArtifactId = r.id;
      await loadArtifactDetail(r.id);
    } catch (e) {
      alert('创建新版本失败：' + e);
    }
  }

  // ===== Philosophy view =====
  let currentPhilosophyTypeFilter = 'all';
  async function loadPhilosophyView() {
    if (!el.philosophyViewContainer) return;
    try {
      const url = currentPhilosophyTypeFilter === 'all'
        ? '/api/philosophy'
        : `/api/philosophy?type=${currentPhilosophyTypeFilter}`;
      const r = await fetch(url).then(r => r.json());
      const items = r.items || [];
      if (items.length === 0) {
        el.philosophyViewContainer.innerHTML = '<div class="philosophy-empty">还没有原则。点击"新增"添加第一条。</div>';
        return;
      }
      el.philosophyViewContainer.innerHTML = `
        <div class="philosophy-grid">
          ${items.map(p => `
            <div class="philosophy-card type-${p.type}">
              <div class="philosophy-card-head">
                <span class="philosophy-card-type">${p.type}</span>
                <span class="philosophy-card-confidence">${(p.confidence * 100).toFixed(0)}%</span>
              </div>
              <div class="philosophy-card-content">${escapeHtml(p.content)}</div>
              ${p.rationale ? `<div class="philosophy-card-rationale">${escapeHtml(p.rationale)}</div>` : ''}
              <div class="philosophy-card-actions">
                <button data-action="retire" data-id="${p.id}">退役</button>
                <button data-action="delete" data-id="${p.id}" class="danger">删除</button>
              </div>
            </div>`).join('')}
        </div>`;
      el.philosophyViewContainer.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          if (action === 'retire') {
            await fetch(`/api/philosophy/${id}/retire`, { method: 'POST' });
          } else if (action === 'delete') {
            if (!confirm('删除这条原则？')) return;
            await fetch(`/api/philosophy/${id}`, { method: 'DELETE' });
          }
          loadPhilosophyView();
        });
      });
    } catch (e) {
      console.error('loadPhilosophyView failed', e);
    }
  }

  function openPhilosophyCreateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'generic-modal-overlay';
    overlay.innerHTML = `
      <div class="generic-modal">
        <div class="generic-modal-title">新增原则</div>
        <div class="generic-modal-field">
          <label>类型</label>
          <select id="newPhilType">
            <option value="principle">原则 (做事的规则)</option>
            <option value="value">价值观 (什么重要)</option>
            <option value="belief">信念 (相信什么)</option>
            <option value="anti_goal">反目标 (要避免什么)</option>
          </select>
        </div>
        <div class="generic-modal-field">
          <label>内容</label>
          <input type="text" id="newPhilContent" placeholder="例如：Simple > Complex" />
        </div>
        <div class="generic-modal-field">
          <label>理由 (为什么)</label>
          <textarea id="newPhilRationale" placeholder="为什么这条重要？"></textarea>
        </div>
        <div class="generic-modal-field">
          <label>信心度 (0-1)</label>
          <input type="number" id="newPhilConfidence" value="0.8" min="0" max="1" step="0.1" />
        </div>
        <div class="generic-modal-actions">
          <button class="today-btn" id="newPhilCancel">取消</button>
          <button class="today-btn primary" id="newPhilSubmit">添加</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#newPhilCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#newPhilSubmit').addEventListener('click', async () => {
      const content = overlay.querySelector('#newPhilContent').value.trim();
      if (!content) { overlay.querySelector('#newPhilContent').focus(); return; }
      const payload = {
        type: overlay.querySelector('#newPhilType').value,
        content,
        rationale: overlay.querySelector('#newPhilRationale').value,
        confidence: parseFloat(overlay.querySelector('#newPhilConfidence').value) || 0.8,
        source: 'user',
      };
      try {
        await fetch('/api/philosophy', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        overlay.remove();
        loadPhilosophyView();
      } catch (e) {
        alert('添加失败：' + e);
      }
    });
  }

  // ===== Prompt engineering panel extras =====
  async function loadPromptStats() {
    if (!el.promptStatsDesc) return;
    try {
      const r = await fetch('/api/prompts/stats').then(r => r.json());
      el.promptStatsDesc.textContent = `共 ${r.total} 个 Prompt，${r.customized} 个已自定义，${r.default} 个使用默认值。`;
    } catch (e) {
      el.promptStatsDesc.textContent = '加载统计失败';
    }
  }

  async function exportPrompts() {
    try {
      const r = await fetch('/api/prompts').then(r => r.json());
      const customized = r.prompts.filter(p => !p.is_default);
      const blob = new Blob([JSON.stringify(customized, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'cambium-prompts.json';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { alert('导出失败：' + e); }
  }

  async function importPrompts() {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json,application/json';
    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        if (!Array.isArray(data)) { alert('JSON 格式错误：应为数组'); return; }
        for (const p of data) {
          if (p.key && p.content) {
            await fetch(`/api/prompts/${encodeURIComponent(p.key)}`, {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ content: p.content })
            });
          }
        }
        alert(`已导入 ${data.length} 个 Prompt`);
        await loadSettings();
        populateSettingsUI();
        loadPromptStats();
      } catch (e) {
        alert('导入失败：' + e);
      }
    };
    input.click();
  }

  async function resetAllPrompts() {
    if (!confirm('把所有 Prompt 重置为默认值？此操作不可撤销。')) return;
    try {
      const r = await fetch('/api/prompts').then(r => r.json());
      for (const p of r.prompts) {
        await fetch(`/api/prompts/${encodeURIComponent(p.key)}/reset`, { method: 'POST' });
      }
      alert('已重置');
      await loadSettings();
      populateSettingsUI();
      loadPromptStats();
    } catch (e) { alert('重置失败：' + e); }
  }

  // ===== AI Greeting — Cambium speaks first =====
  async function loadAiGreeting() {
    const block = document.getElementById('aiGreetingBlock');
    const textEl = document.getElementById('aiGreetingText');
    const hintEl = document.getElementById('aiGreetingHint');
    if (!block || !textEl) return;
    try {
      const r = await fetch('/api/greeting').then(r => r.json());
      if (r.greeting && r.greeting.length > 5) {
        textEl.textContent = r.greeting;
        block.style.display = '';
        // Hide hint after 10 seconds
        if (hintEl) {
          setTimeout(() => { hintEl.style.opacity = '0'; }, 10000);
        }
      }
    } catch (e) {
      console.error('loadAiGreeting failed', e);
    }
  }

  // ===== Onboarding (first-run) =====
  const onboardingSlides = [
    {
      icon: '🌱',
      title: '欢迎来到 Cambium',
      text: '这不是普通的聊天机器人。这是一个你和 AI 共同生活、共同创造、共同成长的世界。',
      features: [
        { icon: '🌅', text: 'AI 每天早上给你写一封信' },
        { icon: '👥', text: '7 个 AI 居民住在这里' },
        { icon: '📜', text: 'AI 会引用你们共同的原则' },
      ],
    },
    {
      icon: '💬',
      title: '聊天只是入口之一',
      text: '聊天不是 Cambium 的全部。打开"今天"看 AI 写给你的信，打开"居民"看谁住在里面，打开"作品"看你们一起创造了什么。',
      features: [
        { icon: '📂', text: '消息会消失，作品会留下' },
        { icon: '🤝', text: 'AI 是居民，不是工具' },
      ],
    },
    {
      icon: '🧠',
      title: 'AI 越用越懂你',
      text: '第一次对话它什么都不记得。第十次它会引用你说过的话。第三十次它会主动提你之前的想法。给它时间，它会成为真正认识你的存在。',
      features: [
        { icon: '⏰', text: '需要时间才会真正"活起来"' },
        { icon: '🎯', text: '每次对话后告诉它"记住了什么"' },
      ],
    },
    {
      icon: '🚀',
      title: '开始吧',
      text: '点击任意一个发现卡片，或直接开始聊天。没有错误的方式——慢慢探索就好。',
      features: [
        { icon: '1️⃣', text: '去"今天"看晨报' },
        { icon: '2️⃣', text: '在"原则"里加一条你的信念' },
        { icon: '3️⃣', text: '和 Cambium 聊天，看它怎么"认识"你' },
      ],
    },
  ];
  let onboardingCurrentSlide = 0;

  function showOnboardingSlide(idx) {
    const content = document.getElementById('onboardingContent');
    if (!content) return;
    onboardingCurrentSlide = idx;
    const slide = onboardingSlides[idx];
    content.innerHTML = `
      <div class="onboarding-slide active">
        <div class="onboarding-slide-icon">${slide.icon}</div>
        <div class="onboarding-slide-title">${slide.title}</div>
        <div class="onboarding-slide-text">${slide.text}</div>
        <div class="onboarding-slide-features">
          ${slide.features.map(f => `
            <div class="onboarding-feature">
              <span class="onboarding-feature-icon">${f.icon}</span>
              <span>${f.text}</span>
            </div>`).join('')}
        </div>
        <div class="onboarding-dots">
          ${onboardingSlides.map((_, i) => `<div class="onboarding-dot ${i === idx ? 'active' : ''}"></div>`).join('')}
        </div>
      </div>`;
    const nextBtn = document.getElementById('btnOnboardingNext');
    if (nextBtn) {
      nextBtn.textContent = idx === onboardingSlides.length - 1 ? '开始使用' : '下一步';
    }
  }

  function openOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (!modal) return;
    modal.style.display = '';
    showOnboardingSlide(0);
  }

  function closeOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (modal) modal.style.display = 'none';
    try { localStorage.setItem('cambium_onboarding_done', '1'); } catch (e) {}
  }

  function wireOnboarding() {
    const nextBtn = document.getElementById('btnOnboardingNext');
    const skipBtn = document.getElementById('btnOnboardingSkip');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (onboardingCurrentSlide < onboardingSlides.length - 1) {
          showOnboardingSlide(onboardingCurrentSlide + 1);
        } else {
          closeOnboarding();
        }
      });
    }
    if (skipBtn) skipBtn.addEventListener('click', closeOnboarding);
  }

  // Wire discovery cards in welcome screen
  function wireWelcomeDiscovery() {
    document.querySelectorAll('.discovery-card[data-view]').forEach(card => {
      card.addEventListener('click', (e) => {
        e.preventDefault();
        switchView(card.dataset.view);
      });
    });
  }

  // ===== Init =====
  async function init() {
    loadState();
    await loadSettings();
    configureMarked();
    wire();
    autoResize();
    populateSettingsUI();
    loadModelSelector();
    renderHistory();
    renderConversation();
    renderAttachments();
    updateRightPanel();
    refreshMcpServers();
    // Load prompt stats in background
    loadPromptStats();
    // Wire onboarding + welcome discovery
    wireOnboarding();
    wireWelcomeDiscovery();
    // Show onboarding for first-time users
    try {
      const done = localStorage.getItem('cambium_onboarding_done');
      if (!done) {
        setTimeout(() => openOnboarding(), 800);
      }
    } catch (e) {}
    // Load AI greeting in chat view (Cambium speaks first)
    setTimeout(() => loadAiGreeting(), 500);
    // Default view: Today (life-first). User can switch to chat by clicking "聊天".
    // But if we're loading a specific conversation (via state), go to chat.
    if (state.conversations && state.conversations.length > 0 && state.currentConversationId) {
      switchView('chat');
      el.composerInput.focus();
    } else {
      switchView('today');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
