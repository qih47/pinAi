import apiClient from './apiClient';

/**
 * CAKRA AI — Service Layer API Terpusat
 *
 * Seluruh panggilan REST dan SSE streaming ke backend dikelola di sini.
 * REST menggunakan Axios (`apiClient`), sedangkan SSE streaming menggunakan
 * browser native `fetch` dengan `ReadableStream` agar terhindar dari keterbatasan Axios
 * pada browser environment untuk streaming.
 */

// Helper to get API_BASE (removes '/api' suffix if present on apiClient baseURL)
export const getApiBase = () => {
  const base = apiClient.defaults.baseURL || '';
  return base.endsWith('/api') ? base.slice(0, -4) : base;
};

/**
 * Get the full URL for uploaded files
 * @param {string} filePath - Path of the file
 * @returns {string} Absolute URL to the file
 */
export function getUploadUrl(filePath) {
  if (!filePath) return '';
  const filename = filePath.includes('/') ? filePath.split('/').pop() : filePath;
  return `${getApiBase()}/uploads/${filename}`;
}

// =========================================================================
// ENDPOINTS: CHAT SESSIONS (REST via Axios)
// =========================================================================

/**
 * Fetch list of chat sessions for the user
 * @param {string} npp - User identity NPP
 */
export async function fetchChatSessions(npp) {
  const response = await apiClient.get('/chat/sessions', {
    headers: npp ? { 'X-NPP-Header': npp } : {}
  });
  return response.data;
}

/**
 * Create a new chat session
 * @param {string} judul - Session title
 * @param {string} npp - User identity NPP
 */
export async function createChatSession(judul, npp) {
  const params = judul ? { judul } : {};
  const response = await apiClient.post('/chat/sessions/create', null, {
    params,
    headers: npp ? { 'X-NPP-Header': npp } : {}
  });
  return response.data;
}

/**
 * Get messages inside a chat session
 * @param {string} sessionUuid - UUID of the session
 * @param {string} npp - User identity NPP
 */
export async function fetchSessionMessages(sessionUuid, npp) {
  const response = await apiClient.get(`/chat/sessions/${sessionUuid}/messages`, {
    headers: npp ? { 'X-NPP-Header': npp } : {}
  });
  return response.data;
}

/**
 * Toggle pin/unpin status of a session
 * @param {string} sessionUuid - UUID of the session
 * @param {boolean} nextPinState - Target pin status
 */
export async function pinSession(sessionUuid, nextPinState) {
  const response = await apiClient.put(`/chat/sessions/${sessionUuid}/pin`, null, {
    params: { is_pinned: nextPinState }
  });
  return response.data;
}

/**
 * Rename session title
 * @param {string} sessionUuid - UUID of the session
 * @param {string} title - New title
 */
export async function renameSession(sessionUuid, title) {
  const response = await apiClient.put(`/chat/sessions/${sessionUuid}/title`, {
    judul: title
  });
  return response.data;
}

/**
 * Delete a session
 * @param {string} sessionUuid - UUID of the session
 * @param {string} npp - User identity NPP
 */
export async function deleteSession(sessionUuid, npp) {
  const response = await apiClient.delete(`/chat/sessions/${sessionUuid}`, {
    headers: npp ? { 'X-NPP-Header': npp } : {}
  });
  return response.data;
}

/**
 * Assign an existing session to the currently logged in user
 * @param {string} sessionUuid - UUID of the session
 */
export async function assignSession(sessionUuid) {
  const response = await apiClient.put(`/chat/sessions/${sessionUuid}/assign`);
  return response.data;
}

// =========================================================================
// ENDPOINT: DOCUMENTS / UPLOAD (REST via Axios)
// =========================================================================

/**
 * Upload multiple files to a chat session
 * @param {FormData} formData - Form data containing files and session_uuid
 */
export async function uploadDocuments(formData) {
  const response = await apiClient.post('/chat/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
}

// =========================================================================
// ENDPOINT: SSE STREAMING (Native fetch + ReadableStream)
// =========================================================================

/**
 * Validate SSE event structure before processing
 * @param {Object} parsedData - Parsed JSON event
 * @returns {boolean} True if event is valid
 */
function validateSSEEvent(parsedData) {
  // ✅ Validate event has at least one field
  const hasValidFields =
    parsedData.thinking !== undefined ||
    parsedData.chunk !== undefined ||
    parsedData.sources !== undefined ||
    parsedData.done === true;

  if (!hasValidFields) {
    console.warn('[SSE_VALIDATION] Empty event, all fields undefined', parsedData);
    return false;
  }

  // ✅ Validate sources format if present
  if (parsedData.sources !== null && parsedData.sources !== undefined) {
    if (!Array.isArray(parsedData.sources)) {
      console.warn('[SSE_VALIDATION] Sources not array:', parsedData.sources);
      return false;
    }

    // Validate each source has required identification fields
    for (const source of parsedData.sources) {
      // FIX: Cukup validasi keberadaan id atau dokumen_id saja, hapus kewajiban field content
      const hasValidId = source.id !== undefined || source.dokumen_id !== undefined;
      if (!hasValidId) {
        console.warn('[SSE_VALIDATION] Source missing identification (id/dokumen_id):', source);
        return false;
      }
    }
  }

  return true;
}

/**
 * Handle SSE streaming chat using native fetch and ReadableStream
 * 
 * Features:
 * - Request timeout support (default 5 minutes)
 * - SSE event validation
 * - Rich error responses with error codes
 * - Proper cleanup on completion/error
 * 
 * @param {Object} params - Chat parameters
 * @param {Object} callbacks - Handler callbacks for stream events
 * @param {Object} options - Configuration options (timeoutMs, etc)
 */
export async function streamChat(
  { sessionUuid, messages, chatMode, thinking, isolatedDocId, attachmentPaths, npp, editIndex, signal },
  { onThinking, onStatus, onSources, onChunk, onDone, onError },
  options = {}
) {
  const { timeoutMs = 5 * 60 * 1000 } = options;  // 5 minute default timeout
  let timeoutId = null;

  try {
    // ✅ ADD: Timeout support with AbortController
    const controller = new AbortController();
    
    // Bind external abort signal to internal controller
    if (signal) {
      signal.addEventListener('abort', () => controller.abort());
    }

    timeoutId = setTimeout(() => {
      console.warn(`[SSE_TIMEOUT] Request timeout after ${timeoutMs}ms`);
      controller.abort();
    }, timeoutMs);

    const token = localStorage.getItem('cakra_token');
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const cleanNpp = (npp || '').trim();
    const isPlaceholder = !cleanNpp || cleanNpp.startsWith('NPP');
    if (!isPlaceholder) {
      headers['X-NPP-Header'] = cleanNpp;
    }

    const baseURL = apiClient.defaults.baseURL || '/api';
    const response = await fetch(`${baseURL}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_uuid: sessionUuid,
        messages: messages,
        mode: chatMode,
        thinking: thinking,
        temperature: 0.7,
        isolated_doc_id: isolatedDocId,
        attachment_paths: attachmentPaths,
        edit_index: editIndex
      }),
      signal: controller.signal,  // ✅ ADD: Abort signal for timeout
    });

    clearTimeout(timeoutId);  // ✅ ADD: Clear timeout on success

    if (!response.ok) {
      // ✅ Extract rich error info
      let errorData = {};
      try {
        errorData = await response.json();
      } catch (e) {
        errorData = { message: 'Unknown error' };
      }

      const errorCode = errorData.code || 'UNKNOWN_ERROR';
      const errorMessage = errorData.message || `HTTP ${response.status}`;
      const requestId = errorData.request_id;

      console.error(`[SSE_ERROR] ${errorCode}: ${errorMessage}`, { requestId });

      throw new Error(JSON.stringify({
        code: errorCode,
        message: errorMessage,
        requestId,
      }));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let streamBuffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      streamBuffer += decoder.decode(value, { stream: true });
      const lines = streamBuffer.split('\n');
      streamBuffer = lines.pop();

      for (const line of lines) {
        const cleanedLine = line.trim();
        if (!cleanedLine) continue;

        try {
          const parsedData = JSON.parse(cleanedLine);
          
          // ✅ ADD: Validate event structure
          if (!validateSSEEvent(parsedData)) {
            console.debug('[SSE] Skipping invalid event:', parsedData);
            continue;
          }

          // ✅ ADD: Log event for debugging
          console.debug(
            `[SSE_EVENT] ${parsedData.event_type || '?'} @ ${parsedData.timestamp}`
          );

          // ✅ Handle error events
          if (parsedData.error) {
            console.error(
              `[SSE_ERROR_EVENT] ${parsedData.error.code}: ${parsedData.error.message}`,
              parsedData.error
            );
            if (onError) {
              onError(new Error(JSON.stringify(parsedData.error)));
            }
            continue;
          }

          // Handle regular events
          if (parsedData.thinking !== undefined && parsedData.thinking && onThinking) {
            onThinking(parsedData.thinking);
          }
          
          if (parsedData.status !== undefined && parsedData.status && onStatus) {
            onStatus(parsedData.status);
          }
          
          if (parsedData.sources && Array.isArray(parsedData.sources) && parsedData.sources.length > 0 && onSources) {
            onSources(parsedData.sources);
          }
          
          if (parsedData.chunk !== undefined && parsedData.chunk && onChunk) {
            onChunk(parsedData.chunk);
          }
          
          if (parsedData.done === true && onDone) {
            onDone(parsedData);
          }
        } catch (jsonErr) {
          console.warn(`[SSE_PARSE_ERROR] ${jsonErr.message}`);
          // Continue on parse errors (might be incomplete line)
        }
      }
    }
    
    // GUARANTEE UI UNLOCK: If the transport stream ends, trigger onDone.
    if (onDone) {
      onDone();
    }
  } catch (error) {
    clearTimeout(timeoutId);  // ✅ Cleanup

    // ✅ Handle abort error (timeout or manual stop)
    if (error.name === 'AbortError') {
      if (onError) onError(error);
      throw error;
    }

    if (onError) {
      onError(error);
    } else {
      throw error;
    }
  }
}

/**
 * Fetch list of all regulatory documents from backend for Context Isolation (W7)
 */
export async function fetchAllDocuments() {
  const response = await apiClient.get('/documents');
  return response.data;
}

// =========================================================================
// ENDPOINTS: AUTH — Session Management (B10 Sync — Token Expiry)
// =========================================================================

/**
 * Extend current session expiry time (W11 + W18)
 * @param {number} hoursToAdd - Number of hours to extend (default: 8)
 * @returns {Promise<Object>} Extended session info with new expires_at timestamp
 */
export async function extendSession(hoursToAdd = 8) {
  try {
    const response = await apiClient.post('/auth/extend-session', {
      hours_to_add: hoursToAdd
    });
    return {
      success: true,
      ...response.data
    };
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to extend session');
  }
}

/**
 * Fetch embedding cache statistics (W13)
 * @returns {Promise<Object>} Statistics containing total entries, hits, misses, etc.
 */
export async function fetchCacheStats() {
  try {
    const response = await apiClient.get('/admin/cache-stats');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to fetch cache statistics');
  }
}

/**
 * Clear embedding cache (W13)
 * @returns {Promise<Object>} Response status and message
 */
export async function clearEmbeddingCache() {
  try {
    const response = await apiClient.post('/admin/clear-embedding-cache');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to clear embedding cache');
  }
}

/**
 * Fetch vector HNSW index status (W15)
 * @returns {Promise<Object>} Index status, counts, size metrics
 */
export async function fetchVectorIndexStatus() {
  try {
    const response = await apiClient.get('/admin/vector-index-status');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to fetch vector index status');
  }
}

/**
 * Optimize vector index via VACUUM ANALYZE (W15)
 * @returns {Promise<Object>} Response status and metrics
 */
export async function optimizeVectorIndex() {
  try {
    const response = await apiClient.post('/admin/optimize-vector-index');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to optimize vector index');
  }
}

/**
 * Trim session messages history for edit/regenerate
 * @param {string} sessionUuid - The UUID of the session
 * @param {number} keepCount - Number of messages to keep from the beginning
 */
export async function trimSessionMessages(sessionUuid, keepCount) {
  try {
    const response = await apiClient.delete(`/chat/sessions/${sessionUuid}/messages/trim`, {
      params: { keep_count: keepCount }
    });
    return response.data;
  } catch (error) {
    console.error('Error trimming session messages:', error);
    throw new Error(error.response?.data?.detail || 'Failed to trim session messages');
  }
}

/**
 * Fetch toggle settings (chatMode, isThinkingMode) for a session
 */
export async function fetchSessionSettings(sessionUuid) {
  try {
    const response = await apiClient.get(`/chat/sessions/${sessionUuid}/settings`);
    return response.data;
  } catch (error) {
    console.error('Error fetching session settings:', error);
    return null;
  }
}

/**
 * Update toggle settings (chatMode, isThinkingMode) for a session
 */
export async function updateSessionSettings(sessionUuid, settings) {
  try {
    const response = await apiClient.patch(`/chat/sessions/${sessionUuid}/settings`, {
      settings: settings
    });
    return response.data;
  } catch (error) {
    console.error('Error updating session settings:', error);
    return null;
  }
}
