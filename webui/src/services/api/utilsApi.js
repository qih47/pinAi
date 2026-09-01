import apiClient from '../apiClient';

/**
 * Helper to get API_BASE (removes '/api' suffix if present on apiClient baseURL)
 */
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
  
  let npp = '';
  try {
    const authStorage = localStorage.getItem('auth-storage');
    if (authStorage) {
      const parsed = JSON.parse(authStorage);
      npp = parsed?.state?.authUser?.npp || '';
    }
  } catch(e) {}
  
  const tokenQuery = npp ? `?npp=${encodeURIComponent(npp)}` : '';
  
  if (filePath.startsWith('accounts/')) {
    return `${getApiBase()}/${filePath}${tokenQuery}`;
  }
  if (filePath.includes('file_peraturan/')) {
    const filename = filePath.split('file_peraturan/').pop();
    return `${getApiBase()}/file_peraturan/${filename}${tokenQuery}`;
  }
  const filename = filePath.includes('/') ? filePath.split('/').pop() : filePath;
  return `${getApiBase()}/uploads/${filename}${tokenQuery}`;
}

/**
 * Validate SSE event structure before processing
 * @param {Object} parsedData - Parsed JSON event
 * @returns {boolean} True if event is valid
 */
export function validateSSEEvent(parsedData) {
  if (!parsedData || typeof parsedData !== 'object') {
    console.warn('[SSE_VALIDATION] Non-object event data:', parsedData);
    return false;
  }

  // ✅ Validate event has at least one valid semantic field
  const hasValidFields =
    parsedData.thinking !== undefined ||
    parsedData.chunk !== undefined ||
    parsedData.status !== undefined ||
    parsedData.status_key !== undefined ||
    parsedData.event_type !== undefined ||
    parsedData.sources !== undefined ||
    parsedData.topic !== undefined ||
    parsedData.active_topic !== undefined ||
    parsedData.key_subject !== undefined ||
    parsedData.wizard !== undefined ||
    parsedData.radar !== undefined ||
    parsedData.file_process !== undefined ||
    parsedData.title !== undefined ||
    parsedData.error !== undefined ||
    parsedData.metrics !== undefined ||
    parsedData.suggestions !== undefined ||
    parsedData.done !== undefined;

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
