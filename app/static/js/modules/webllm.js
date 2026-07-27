/**
 * WebLLM Embedding Service — browser-side embeddings via Transformers.js.
 *
 * Default embedding backend for Cambium. Runs entirely in the browser,
 * no server install needed. Uses Xenova/multilingual-e5-small (~200MB,
 * Chinese + English, 384-dim).
 *
 * The model is loaded once and cached in the browser. Subsequent calls
 * are fast (~10ms per embedding after warmup).
 *
 * Embeddings are sent to the backend for storage in ChromaDB via:
 *   POST /api/v2/vector-store/webllm/add
 *   POST /api/v2/vector-store/webllm/query
 *
 * Library: Transformers.js (@xenova/transformers) loaded via CDN.
 * Model: Xenova/multilingual-e5-small (384-dim, multilingual)
 *
 * Usage:
 *   import { webllmEmbed, webllmAddToStore, webllmQueryStore } from './webllm.js';
 *   const vec = await webllmEmbed('你好世界');
 *   await webllmAddToStore('memories_default', 'mem_123', '你好世界', vec);
 *   const results = await webllmQueryStore('memories_default', vec);
 */

// ============================================================
// State
// ============================================================

let _pipeline = null;
let _loadingPromise = null;
const WEBLLM_MODEL = 'Xenova/multilingual-e5-small';
const WEBLLM_DIM = 384; // multilingual-e5-small output dim

// ============================================================
// Model loading
// ============================================================

/**
 * Load the Transformers.js pipeline (singleton).
 * Loads from CDN: https://cdn.jsdelivr.net/npm/@xenova/transformers
 *
 * @returns {Promise<Pipeline>} The embedding pipeline
 */
async function _getPipeline() {
  if (_pipeline) return _pipeline;
  if (_loadingPromise) return _loadingPromise;

  _loadingPromise = (async () => {
    // Load Transformers.js from CDN if not already loaded
    if (!window.transformers) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2';
        script.onload = resolve;
        script.onerror = () => reject(new Error('Failed to load Transformers.js from CDN'));
        document.head.appendChild(script);
      });
    }

    const { pipeline } = window.transformers;
    console.log(`[webllm] loading model: ${WEBLLM_MODEL} (~200MB, first time only)`);
    _pipeline = await pipeline('feature-extraction', WEBLLM_MODEL, {
      quantized: true, // Use quantized version (~120MB instead of 480MB)
    });
    console.log(`[webllm] model ready: ${WEBLLM_MODEL}, dim=${WEBLLM_DIM}`);
    return _pipeline;
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
 * Check if WebLLM embedding is available (Transformers.js loaded).
 * @returns {boolean}
 */
export function isWebLLMAvailable() {
  return _pipeline !== null || _loadingPromise !== null;
}

/**
 * Get the model name and dimension.
 */
export function getWebLLMInfo() {
  return { model: WEBLLM_MODEL, dim: WEBLLM_DIM };
}

/**
 * Embed a text using WebLLM (browser-side).
 *
 * @param {string} text - The text to embed (max 8000 chars)
 * @returns {Promise<number[]>} The embedding vector (384-dim, L2-normalized)
 */
export async function webllmEmbed(text) {
  if (!text || !text.trim()) return null;
  try {
    const extractor = await _getPipeline();
    // e5 models need a prefix: "query: " or "passage: "
    // For general embedding, use "passage: " (for documents to be searched)
    const prefixed = text.length > 8000 ? text.slice(0, 8000) : text;
    const output = await extractor(prefixed, {
      pooling: 'mean',
      normalize: true,
    });
    return Array.from(output.data);
  } catch (e) {
    console.error('[webllm] embed failed:', e);
    return null;
  }
}

/**
 * Embed a query text using WebLLM (with "query: " prefix for e5 models).
 *
 * @param {string} query - The query text
 * @returns {Promise<number[]>} The embedding vector
 */
export async function webllmEmbedQuery(query) {
  if (!query || !query.trim()) return null;
  try {
    const extractor = await _getPipeline();
    // e5 models: queries use "query: " prefix
    const prefixed = `query: ${query.slice(0, 8000)}`;
    const output = await extractor(prefixed, {
      pooling: 'mean',
      normalize: true,
    });
    return Array.from(output.data);
  } catch (e) {
    console.error('[webllm] embed query failed:', e);
    return null;
  }
}

/**
 * Add an item to the vector store with a pre-computed WebLLM embedding.
 *
 * @param {string} collection - Collection name (e.g. "memories_default")
 * @param {string} id - Unique item ID
 * @param {string} text - The text content
 * @param {number[]} [embedding] - Pre-computed embedding (if null, will compute)
 * @param {object} [metadata] - Additional metadata
 * @returns {Promise<object>} Result
 */
export async function webllmAddToStore(collection, id, text, embedding, metadata = {}) {
  let vec = embedding;
  if (!vec) {
    vec = await webllmEmbed(text);
  }
  if (!vec) {
    console.warn('[webllm] no embedding, skipping add');
    return { status: 'skipped' };
  }
  try {
    const resp = await fetch('/api/v2/vector-store/webllm/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection,
        id,
        text,
        embedding: vec,
        metadata,
      }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('[webllm] addToStore failed:', e);
    return { status: 'error', error: e.message };
  }
}

/**
 * Query the vector store with a pre-computed WebLLM embedding.
 *
 * @param {string} collection - Collection name
 * @param {string} query - The query text
 * @param {number} [topK=5] - Number of results
 * @returns {Promise<object[]>} Search results
 */
export async function webllmQueryStore(collection, query, topK = 5) {
  const vec = await webllmEmbedQuery(query);
  if (!vec) {
    console.warn('[webllm] no query embedding, returning empty');
    return [];
  }
  try {
    const resp = await fetch('/api/v2/vector-store/webllm/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection,
        embedding: vec,
        top_k: topK,
      }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    return data.results || [];
  } catch (e) {
    console.error('[webllm] queryStore failed:', e);
    return [];
  }
}

// Expose to window for non-module scripts
if (typeof window !== 'undefined') {
  window.WebLLM = {
    isWebLLMAvailable,
    getWebLLMInfo,
    webllmEmbed,
    webllmEmbedQuery,
    webllmAddToStore,
    webllmQueryStore,
  };
}
