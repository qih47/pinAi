import apiClient from '../apiClient';

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
