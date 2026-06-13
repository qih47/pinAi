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
 * Handle SSE streaming chat using native fetch and ReadableStream
 * @param {Object} params - Chat parameters
 * @param {Object} callbacks - Handler callbacks for stream events
 */
export async function streamChat(
  { sessionUuid, messages, chatMode, isolatedDocId, attachmentPaths, npp },
  { onThinking, onSources, onChunk, onDone, onError }
) {
  try {
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
        temperature: 0.7,
        isolated_doc_id: isolatedDocId,
        attachment_paths: attachmentPaths
      })
    });

    if (!response.ok) {
      throw new Error('Gagal terhubung dengan server backend.');
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
          
          if (parsedData.thinking !== undefined && onThinking) {
            onThinking(parsedData.thinking);
          }
          
          if (parsedData.sources && Array.isArray(parsedData.sources) && onSources) {
            onSources(parsedData.sources);
          }
          
          if (parsedData.chunk !== undefined && onChunk) {
            onChunk(parsedData.chunk);
          }
          
          if (parsedData.done === true && onDone) {
            onDone();
          }
        } catch (jsonErr) {
          // Buffering incomplete JSON lines
        }
      }
    }
  } catch (error) {
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
