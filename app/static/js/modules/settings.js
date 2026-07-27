// Module: settings
// Auto-extracted from app.js
(function() {
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

  
})();
