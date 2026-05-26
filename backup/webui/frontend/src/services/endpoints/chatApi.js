import { API_BASE, API_PREFIX, apiGet, apiPost, apiPostStream } from "../apiClient";

export async function checkHealth() {
  return fetch(`${API_BASE}/health`);
}

export async function fetchAvailableModels() {
  return apiGet("/api/available-models");
}

export async function fetchDocuments() {
  return apiGet("/api/documents");
}

export async function fetchChatMessages(sessionUuid) {
  return apiGet(`/api/chat-messages/${sessionUuid}`);
}

export async function fetchChatHistory(npp) {
  return apiGet(`/api/chat-history/${npp}`);
}

export async function sendChatMessage(payload) {
  return apiPostStream("/api/chat", payload);
}

export async function pinChat(sessionUuid) {
  return apiPost(`/api/chat/pin/${sessionUuid}`, {});
}

export async function renameChat(sessionUuid, judul) {
  return apiPost(`/api/chat/rename/${sessionUuid}`, { judul });
}

export async function deleteChat(sessionUuid) {
  return apiPost(`/api/chat/delete/${sessionUuid}`, {});
}
