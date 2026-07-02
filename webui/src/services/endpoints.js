// This is a barrel file to preserve backward compatibility for existing imports
export { 
  getApiBase, 
  getUploadUrl, 
  validateSSEEvent 
} from './api/utilsApi';

export {
  fetchChatSessions,
  createChatSession,
  fetchSessionMessages,
  pinSession,
  renameSession,
  deleteSession,
  assignSession
} from './api/sessionApi';

export {
  uploadDocuments,
  fetchAllDocuments
} from './api/documentApi';

export {
  streamChat,
  trimSessionMessages,
  fetchSessionSettings,
  updateSessionSettings
} from './api/chatApi';

export {
  fetchCacheStats,
  clearEmbeddingCache,
  fetchVectorIndexStatus,
  optimizeVectorIndex
} from './api/adminApi';

export {
  extendSession
} from './api/authApi';
