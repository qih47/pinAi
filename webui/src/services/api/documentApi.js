import apiClient from '../apiClient';

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

/**
 * Fetch list of all regulatory documents from backend for Context Isolation (W7)
 */
export async function fetchAllDocuments({ offset = 0, limit = 15, search = '' } = {}) {
  const queryParams = new URLSearchParams();
  queryParams.append('offset', offset);
  queryParams.append('limit', limit);
  if (search) {
    queryParams.append('search', search);
  }
  
  const response = await apiClient.get(`/documents?${queryParams.toString()}`);
  return response.data;
}
