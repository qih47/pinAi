import { useEffect, useState } from 'react';
import { useChatAuthStore } from '../stores/authStore';
import * as endpoints from '../services/endpoints';
import { useToast } from './useToast';

/**
 * Hook: Session Expiry Countdown Manager (W11)
 * 
 * Handles:
 * - Real-time countdown display of remaining session time
 * - Warning toast 5 minutes before expiry
 * - Graceful logout on token expiry
 * - Manual "Keep Me Signed In" button trigger
 */
export const useSessionExpiry = () => {
  const [timeRemaining, setTimeRemaining] = useState(null); // in milliseconds
  const [expiresIn, setExpiresIn] = useState(''); // formatted string: "7h 45m"
  const [warningShown, setWarningShown] = useState(false);
  const [isExpiring, setIsExpiring] = useState(false);

  const { user, token } = useChatAuthStore();
  const toast = useToast();

  /**
   * Format milliseconds to human readable string (e.g., "7h 45m" or "23m 30s")
   */
  const formatTimeRemaining = (ms) => {
    if (ms <= 0) return '0m';

    const hours = Math.floor(ms / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((ms % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
  };

  /**
   * Extend session expiry by calling backend endpoint
   */
  const extendSession = async (hoursToAdd = 8) => {
    try {
      const result = await endpoints.extendSession(hoursToAdd);
      
      if (result.success || result.expires_at) {
        // Update expiresAt in auth store
        useChatAuthStore.setState({
          expiresAt: new Date(result.expires_at)
        });
        
        toast.success(`✅ Session extended! You're signed in for another ${hoursToAdd} hours.`);
        setWarningShown(false); // Reset warning
        return true;
      }
    } catch (error) {
      toast.error(`❌ Failed to extend session: ${error.message}`);
      return false;
    }
  };

  /**
   * Manual logout function
   */
  const handleExpiredLogout = async () => {
    const { logout } = useChatAuthStore.getState();
    await logout();
    toast.warning('⏰ Your session has expired. Please log in again.');
  };

  // Main countdown effect
  useEffect(() => {
    if (!token || !user) {
      setTimeRemaining(null);
      setExpiresIn('');
      return;
    }

    // Check if expiresAt is set in authStore
    const expiresAt = useChatAuthStore.getState().expiresAt;
    
    if (!expiresAt) {
      // If expiresAt not set (old token without expiry), assume 8 hours from now
      const newExpiresAt = new Date(Date.now() + 8 * 60 * 60 * 1000);
      useChatAuthStore.setState({ expiresAt: newExpiresAt });
      return;
    }

    const countdownInterval = setInterval(() => {
      const now = Date.now();
      const expiryTime = new Date(expiresAt).getTime();
      const remaining = expiryTime - now;

      // Token expired
      if (remaining <= 0) {
        setTimeRemaining(0);
        setExpiresIn('0m');
        setIsExpiring(true);
        clearInterval(countdownInterval);
        handleExpiredLogout();
        return;
      }

      setTimeRemaining(remaining);
      setExpiresIn(formatTimeRemaining(remaining));

      // Show warning at 5 minutes before expiry
      if (remaining <= 5 * 60 * 1000 && !warningShown) {
        setIsExpiring(true);
        setWarningShown(true);
        toast.warning(
          '⏰ Your session is expiring in 5 minutes!',
          {
            action: {
              label: 'Keep Signed In',
              onClick: () => extendSession(8)
            }
          }
        );
      }

      // Reset warning state if expiry is more than 5 minutes away
      if (remaining > 5 * 60 * 1000 && warningShown) {
        setWarningShown(false);
        setIsExpiring(false);
      }
    }, 1000); // Update every second for smooth countdown

    return () => clearInterval(countdownInterval);
  }, [token, user, warningShown]);

  return {
    timeRemaining,           // milliseconds
    expiresIn,              // formatted string "7h 45m"
    isExpiring,             // boolean: is session about to expire?
    extendSession,          // function to extend session
    handleExpiredLogout     // function to handle expiry logout
  };
};
