/**
 * WebLLM Chat Provider — browser-side LLM for low-stakes tasks.
 *
 * Uses @mlc-ai/web-llm to run small LLMs (0.5B-1.5B) entirely in the browser.
 * No API key needed, no server round-trip, works offline after model download.
 *
 * Recommended models (Chinese-capable, small):
 *   - Qwen2.5-0.5B-Instruct (~1GB, basic Chinese)
 *   - Qwen2.5-1.5B-Instruct (~2GB, decent Chinese)
 *   - SmolLM2-360M-Instruct (~700MB, English-focused)
 *   - Llama-3.2-1B-Instruct (~2GB, multilingual)
 *
 * This is registered as a special "provider" in the API providers system.
 * When a task is assigned to the "webllm" provider, the frontend:
 *   1. Loads the model via WebLLM
 *   2. Runs inference locally
 *   3. Returns the result
 *
 * The backend's /api/sessions/{sid}/send and other LLM endpoints detect
 * the "webllm" provider and return a special response that the frontend
 * handles by running inference locally.
 *
 * For now, this is used for: title generation, emotion analysis, simple Q&A.
 * Complex tasks (chat, cognitive extraction) should use server-side LLMs.
 */

// ============================================================
// State
// ============================================================

let _engine = null;
let _loadingPromise = null;
let _currentModel = '';

// Default model — small, Chinese-capable
const DEFAULT_WEBLLM_CHAT_MODEL = 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC';

// ============================================================
// Model loading
// ============================================================

/**
 * Load the WebLLM engine (singleton).
 * Loads from CDN: https://esm.run/@mlc-ai/web-llm
 *
 * @param {string} [model] - Model name (default: Qwen2.5-0.5B-Instruct)
 * @returns {Promise<Engine>} The WebLLM engine
 */
async function _getEngine(model = DEFAULT_WEBLLM_CHAT_MODEL) {
  if (_engine && _currentModel === model) return _engine;
  if (_loadingPromise) return _loadingPromise;

  _loadingPromise = (async () => {
    // Load WebLLM from CDN
    if (!window.webllm) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.type = 'module';
        script.textContent = `
          import * as webllm from 'https://esm.run/@mlc-ai/web-llm';
          window.webllm = webllm;
          window.dispatchEvent(new Event('webllm-loaded'));
        `;
        document.head.appendChild(script);
        if (window.webllm) {
          resolve();
        } else {
          window.addEventListener('webllm-loaded', resolve, { once: true });
          setTimeout(() => reject(new Error('WebLLM load timeout')), 30000);
        }
      });
    }

    const { CreateMLCEngine } = window.webllm;
    console.log(`[webllm-chat] loading model: ${model} (first time: ~1GB download)`);
    _engine = await CreateMLCEngine(model, {
      initProgressCallback: (info) => {
        console.log(`[webllm-chat] ${info.text || ''} ${info.progress ? Math.round(info.progress * 100) + '%' : ''}`);
      },
    });
    _currentModel = model;
    console.log(`[webllm-chat] model ready: ${model}`);
    return _engine;
  })();

  try {
    return await _loadingPromise;
  } finally {
    _loadingPromise = null;
  }
}

// ============================================================
// Public API
// ============================================================

/**
 * Check if WebLLM chat is available.
 */
export function isWebLLMChatAvailable() {
  return _engine !== null;
}

/**
 * Get available WebLLM models.
 */
export function getAvailableModels() {
  return [
    { id: 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC', name: 'Qwen2.5-0.5B (~1GB, 中文)', size: '~1GB' },
    { id: 'Qwen2.5-1.5B-Instruct-q4f16_1-MLC', name: 'Qwen2.5-1.5B (~2GB, 中文)', size: '~2GB' },
    { id: 'SmolLM2-360M-Instruct-q4f16_1-MLC', name: 'SmolLM2-360M (~700MB, English)', size: '~700MB' },
    { id: 'Llama-3.2-1B-Instruct-q4f16_1-MLC', name: 'Llama-3.2-1B (~2GB, multilingual)', size: '~2GB' },
  ];
}

/**
 * Run a chat completion using WebLLM (browser-side).
 *
 * @param {Array} messages - [{role, content}, ...]
 * @param {object} [options] - {temperature, max_tokens, model}
 * @returns {Promise<string>} The assistant's response text
 */
export async function webllmChat(messages, options = {}) {
  try {
    const model = options.model || DEFAULT_WEBLLM_CHAT_MODEL;
    const engine = await _getEngine(model);
    const completion = await engine.chat.completions.create({
      messages,
      temperature: options.temperature ?? 0.7,
      max_tokens: options.max_tokens ?? 512,
    });
    return completion.choices[0]?.message?.content || '';
  } catch (e) {
    console.error('[webllm-chat] inference failed:', e);
    throw e;
  }
}

/**
 * Generate a title for a conversation using WebLLM.
 * This is a low-stakes task perfect for a small browser-side model.
 *
 * @param {string} userMessage - The user's message
 * @param {string} assistantMessage - The assistant's reply
 * @returns {Promise<string>} A short title (≤20 chars)
 */
export async function webllmGenerateTitle(userMessage, assistantMessage) {
  const prompt = `Generate a very short title (max 15 characters, Chinese if the input is Chinese) for this conversation. Output only the title, no quotes, no explanation.

User: ${userMessage.slice(0, 200)}
Assistant: ${assistantMessage.slice(0, 200)}

Title:`;
  try {
    const title = await webllmChat(
      [{ role: 'user', content: prompt }],
      { temperature: 0.3, max_tokens: 30 }
    );
    return title.trim().replace(/^["']|["']$/g, '').slice(0, 20);
  } catch (e) {
    console.warn('[webllm-chat] title generation failed:', e);
    return null;
  }
}

/**
 * Analyze emotion of a message using WebLLM.
 * Another low-stakes task suitable for browser-side inference.
 *
 * @param {string} message - The user's message
 * @returns {Promise<string>} Emotion label: positive/negative/neutral/angry/sad/happy
 */
export async function webllmAnalyzeEmotion(message) {
  const prompt = `Analyze the emotion of this message. Output only one word: positive, negative, neutral, angry, sad, happy, anxious, or excited.

Message: ${message.slice(0, 500)}

Emotion:`;
  try {
    const result = await webllmChat(
      [{ role: 'user', content: prompt }],
      { temperature: 0.1, max_tokens: 10 }
    );
    return result.trim().toLowerCase().split(/\s+/)[0];
  } catch (e) {
    console.warn('[webllm-chat] emotion analysis failed:', e);
    return 'neutral';
  }
}

// Expose to window for non-module scripts
if (typeof window !== 'undefined') {
  window.WebLLMChat = {
    isWebLLMChatAvailable,
    getAvailableModels,
    webllmChat,
    webllmGenerateTitle,
    webllmAnalyzeEmotion,
    DEFAULT_MODEL: DEFAULT_WEBLLM_CHAT_MODEL,
  };
}
