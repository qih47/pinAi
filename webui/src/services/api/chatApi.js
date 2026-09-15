import apiClient from '../apiClient';
import { validateSSEEvent } from './utilsApi';

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

/**
 * Fetch dynamic suggestions/hints for web search, documents, code, and focus modes
 * @param {string} mode - Mode: 'websearch' | 'documents' | 'code' | 'focus'
 * @param {string} query - Live typed query in the input bar
 * @param {number} limit - Max results
 */
export async function fetchChatSuggestions(mode = 'documents', query = '', limit = 6, docId = null) {
  try {
    const params = { mode, q: query, limit };
    if (docId) params.doc_id = docId;
    const response = await apiClient.get('/chat/suggestions', { params });
    return response.data?.data || [];
  } catch (error) {
    console.error('Error fetching chat suggestions:', error);
    return [];
  }
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
  { sessionUuid, messages, chatMode, thinking, isolatedDocId, attachmentPaths, npp, editIndex, signal, activeTopic, keySubject, forcedMode, bypassRouter, language, regeneratedFromId, parentId, isRegenerate, targetIndex, parentIndex },
  { onThinking, onStatus, onSources, onChunk, onFileStatus, onDone, onError, onTopicUpdate },
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
      'Accept': 'text/event-stream',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const cleanNpp = (npp || '').trim();
    const isPlaceholder = !cleanNpp || cleanNpp.startsWith('NPP');
    if (!isPlaceholder) {
      headers['X-NPP-Header'] = cleanNpp;
    }

    // 🌐 Client Ambient Context (Timezone & Geolocation cache)
    let clientContext = {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      client_time: new Date().toISOString(),
    };
    try {
      const cachedGeo = sessionStorage.getItem("cakra_client_geo");
      if (cachedGeo) {
        const geoObj = JSON.parse(cachedGeo);
        clientContext.lat = geoObj.lat;
        clientContext.lon = geoObj.lon;
      } else if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            sessionStorage.setItem("cakra_client_geo", JSON.stringify({
              lat: pos.coords.latitude,
              lon: pos.coords.longitude
            }));
          },
          () => {},
          { timeout: 4000, maximumAge: 600000 }
        );
      }
    } catch (e) {}

    const baseURL = apiClient.defaults.baseURL || '/api';
    const response = await fetch(`${baseURL}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_uuid: sessionUuid,
        messages: (messages || []).map(({ thought, thinking, ...rest }) => rest),
        mode: chatMode,
        thinking: thinking,
        temperature: 0.7,
        isolated_doc_id: isolatedDocId,
        attachment_paths: attachmentPaths,
        edit_index: editIndex,
        is_regenerate: Boolean(isRegenerate || regeneratedFromId),
        target_index: targetIndex !== undefined && targetIndex !== null ? targetIndex : undefined,
        parent_index: parentIndex !== undefined && parentIndex !== null ? parentIndex : undefined,
        regenerated_from_id: regeneratedFromId || undefined,
        parent_id: parentId || undefined,
        active_topic: activeTopic,
        key_subject: keySubject,
        language: language || localStorage.getItem("cakra_language") || 'id',
        client_context: {
          ...clientContext,
          language: language || localStorage.getItem("cakra_language") || 'id'
        },
        forced_mode: forcedMode || undefined,
        bypass_router: Boolean(bypassRouter)
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
        let cleanedLine = line.trim();
        if (!cleanedLine) continue;

        // 🛡️ Normalisasi format SSE standar: buang prefix "data:" jika ada
        if (cleanedLine.startsWith("data:")) {
          cleanedLine = cleanedLine.replace(/^data:\s*/, "").trim();
        }
        if (!cleanedLine) continue;

        // 🛡️ Intercept raw <sources_json> tags if emitted directly by LLM or handler
        if (cleanedLine.includes("<sources_json>")) {
          try {
            const start = cleanedLine.indexOf("<sources_json>") + "<sources_json>".length;
            const end = cleanedLine.indexOf("</sources_json>");
            const jsonStr = end !== -1 ? cleanedLine.substring(start, end) : cleanedLine.substring(start);
            const parsedSources = JSON.parse(jsonStr.trim());
            if (Array.isArray(parsedSources) && onSources) {
              onSources(parsedSources);
            }
          } catch (e) {
            console.debug("[SSE] Raw sources_json parse handled:", e);
          }
          continue;
        }

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
            const errCode = (typeof parsedData.error === 'object' && parsedData.error?.code) ? parsedData.error.code : 'STREAM_ERROR';
            const errMsg = (typeof parsedData.error === 'object' && parsedData.error?.message) ? parsedData.error.message : String(parsedData.error);
            console.error(
              `[SSE_ERROR_EVENT] ${errCode}: ${errMsg}`,
              parsedData.error
            );
            if (onError) {
              onError(new Error(errMsg));
            }
            continue;
          }


          // Handle regular events
          if (parsedData.thinking !== undefined && parsedData.thinking && onThinking) {
            onThinking(parsedData.thinking);
          }
          
          if (parsedData.status !== undefined && parsedData.status && onStatus) {
            onStatus(parsedData.status, parsedData.status_key);
          }
          
          if (parsedData.sources && Array.isArray(parsedData.sources) && parsedData.sources.length > 0 && onSources) {
            onSources(parsedData.sources);
          }
          
          if (parsedData.chunk !== undefined && parsedData.chunk && onChunk) {
            onChunk(parsedData.chunk);
          }

          // Handle topic & key subject update from Call 1 Router
          if (parsedData.event_type === 'topic_update' && parsedData.topic && onTopicUpdate) {
            onTopicUpdate(parsedData.topic, parsedData.key_subject);
          }

          // Handle file generation lifecycle (Interceptor-Analyst Pipeline)
          if (parsedData.event_type === 'file_status' && parsedData.file_status && onFileStatus) {
            onFileStatus(parsedData.file_status);
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
