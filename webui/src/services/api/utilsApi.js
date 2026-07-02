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
  if (filePath.startsWith('accounts/')) {
    return `${getApiBase()}/${filePath}`;
  }
  const filename = filePath.includes('/') ? filePath.split('/').pop() : filePath;
  return `${getApiBase()}/uploads/${filename}`;
}

/**
 * Validate SSE event structure before processing
 * @param {Object} parsedData - Parsed JSON event
 * @returns {boolean} True if event is valid
 */
export function validateSSEEvent(parsedData) {
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
