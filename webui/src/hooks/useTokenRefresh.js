import { useEffect } from 'react';
import { useChatAuthStore } from '../stores/authStore';
import * as endpoints from '../services/endpoints';

/**
 * Hook: Token Auto-Refresh Strategy (W18)
 * 
 * Automatically extends session token in three scenarios:
 * 1. Every 30 minutes (background refresh)
 * 2. On user activity (mouse move, keyboard, scroll)
 * 3. Emergency refresh: 5 minutes before expiry
 */
export const useTokenRefresh = () => {
  const { token, expiresAt } = useChatAuthStore();

  /**
   * Trigger session extension via backend
   */
  const refreshToken = async () => {
    if (!token) return false;

    try {
      const result = await endpoints.extendSession(8);
      
      if (result.success || result.expires_at) {
        // Update expiresAt in auth store
        useChatAuthStore.setState({
          expiresAt: new Date(result.expires_at)
        });
        console.log('✅ Token refreshed successfully');
        return true;
      }
    } catch (error) {
      console.error('❌ Token refresh failed:', error.message);
      return false;
    }
  };

  // 1️⃣ Background refresh every 30 minutes
  useEffect(() => {
    if (!token) return;

    const thirtyMinutesMs = 30 * 60 * 1000;
    const backgroundRefreshInterval = setInterval(() => {
      refreshToken();
    }, thirtyMinutesMs);

    return () => clearInterval(backgroundRefreshInterval);
  }, [token]);

  // 2️⃣ User activity refresh
  useEffect(() => {
    if (!token) return;

    let activityTimeout;
    let lastRefreshTime = Date.now();

    const handleUserActivity = () => {
      clearTimeout(activityTimeout);

      const now = Date.now();
      // Only refresh if at least 5 minutes have passed since last refresh
      if (now - lastRefreshTime >= 5 * 60 * 1000) {
        refreshToken();
        lastRefreshTime = now;
      }

      // Reset inactivity timeout
      activityTimeout = setTimeout(() => {
        // User has been inactive for 1 hour, could trigger logout if needed
        // For now, we just let the session expiry handler deal with it
      }, 60 * 60 * 1000);
    };

    // Listen to user activity
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
    events.forEach((event) => {
      document.addEventListener(event, handleUserActivity);
    });

    return () => {
      events.forEach((event) => {
        document.removeEventListener(event, handleUserActivity);
      });
      clearTimeout(activityTimeout);
    };
  }, [token]);

  // 3️⃣ Emergency refresh: 5 minutes before expiry
  useEffect(() => {
    if (!token || !expiresAt) return;

    const checkEmergencyRefresh = setInterval(() => {
      const now = Date.now();
      const expiryTime = new Date(expiresAt).getTime();
      const timeUntilExpiry = expiryTime - now;

      // If 5 minutes or less until expiry, do emergency refresh
      if (timeUntilExpiry > 0 && timeUntilExpiry <= 5 * 60 * 1000) {
        refreshToken();
        clearInterval(checkEmergencyRefresh);
      }
    }, 10000); // Check every 10 seconds

    return () => clearInterval(checkEmergencyRefresh);
  }, [token, expiresAt]);

  return { refreshToken };
};
