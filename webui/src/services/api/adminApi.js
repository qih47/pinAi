import apiClient from '../apiClient';

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
