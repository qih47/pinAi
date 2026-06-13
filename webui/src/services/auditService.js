import apiClient from './apiClient';

/**
 * W17 — Audit Log Service
 *
 * Handles all API calls to the backend audit log endpoints.
 * These are admin-only endpoints that require elevated privileges.
 */

/**
 * Fetch paginated audit logs with optional filters
 * @param {Object} params - Filter parameters
 * @param {string} [params.event_type] - Filter by event type (LOGIN, LOGOUT, CHAT, etc.)
 * @param {string} [params.npp] - Filter by employee NPP
 * @param {number} [params.days] - Filter by number of days back (default: 7)
 * @param {number} [params.limit] - Page size (default: 100)
 * @param {number} [params.offset] - Page offset (default: 0)
 * @returns {Promise<Object>} Paginated list of audit logs
 */
export async function fetchAuditLogs({ event_type, npp, days = 7, limit = 100, offset = 0 } = {}) {
  const params = { days, limit, offset };
  if (event_type && event_type !== 'ALL') params.event_type = event_type;
  if (npp && npp.trim()) params.npp = npp.trim();

  const response = await apiClient.get('/admin/audit-logs', { params });
  return response.data;
}

/**
 * Fetch audit log dashboard statistics
 * @returns {Promise<Object>} Stats: total_logins, unique_users, failed_attempts, top_ips
 */
export async function fetchAuditStats() {
  const response = await apiClient.get('/admin/audit-logs/stats');
  return response.data;
}

/**
 * Export audit logs as CSV or JSON
 * @param {string} format - 'csv' or 'json'
 * @param {Object} filters - Same filters as fetchAuditLogs
 * @returns {Promise<Blob>} File blob for download
 */
export async function exportAuditLogs(format = 'csv', filters = {}) {
  const params = { format, ...filters };
  const response = await apiClient.post('/admin/audit-logs/export', null, {
    params,
    responseType: 'blob'
  });
  return response.data;
}

/**
 * Trigger download of audit log export blob
 * @param {Blob} blob - File blob
 * @param {string} format - 'csv' or 'json'
 */
export function downloadAuditExport(blob, format = 'csv') {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `cakra_audit_log_${new Date().toISOString().slice(0, 10)}.${format}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
