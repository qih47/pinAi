import apiClient from '../apiClient';

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
