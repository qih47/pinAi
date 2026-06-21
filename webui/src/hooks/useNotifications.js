import { useEffect, useState, useCallback } from 'react';
import { useChatAuthStore } from '../stores/authStore';
import { getApiBase } from '../services/endpoints';

/**
 * Hook: Real-time Notification Manager (W16)
 *
 * Handles SSE connection to backend `/api/notifications/subscribe`
 * Maintains notification history in state
 * Auto-reconnect on disconnect
 */
export const useNotifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);

  const { user } = useChatAuthStore();

  /**
   * Mark a notification as read
   */
  const markAsRead = useCallback((notificationId) => {
    setNotifications((prev) =>
      prev.map((notif) =>
        notif.id === notificationId ? { ...notif, is_read: true } : notif
      )
    );
    updateUnreadCount();
  }, []);

  /**
   * Mark all notifications as read
   */
  const markAllAsRead = useCallback(() => {
    setNotifications((prev) =>
      prev.map((notif) => ({ ...notif, is_read: true }))
    );
    setUnreadCount(0);
  }, []);

  /**
   * Delete a notification
   */
  const deleteNotification = useCallback((notificationId) => {
    setNotifications((prev) =>
      prev.filter((notif) => notif.id !== notificationId)
    );
    updateUnreadCount();
  }, []);

  /**
   * Clear all notifications
   */
  const clearAll = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  /**
   * Update unread count
   */
  const updateUnreadCount = useCallback(() => {
    setNotifications((prev) => {
      const count = prev.filter((n) => !n.is_read).length;
      setUnreadCount(count);
      return prev;
    });
  }, []);

  // SSE Connection Effect
  useEffect(() => {
    if (!user || !user.npp) {
      setIsConnected(false);
      return;
    }

    let eventSource;
    let reconnectTimeout;
    const maxReconnectAttempts = 5;
    let reconnectAttempts = 0;

    const connectToNotifications = () => {
      try {
        // ── 🛠️ FIX MUTLAK: Ambil URL absolut dari core service agar menembak port IP backend asli ──
        const apiBaseUrl = getApiBase(); 
        const url = `${apiBaseUrl}/api/notifications/subscribe?npp=${encodeURIComponent(user.npp)}`;
        
        eventSource = new EventSource(url);
        
        // Connection opened
        eventSource.onopen = () => {
          console.log('✅ Notification connection established');
          setIsConnected(true);
          setConnectionError(null);
          reconnectAttempts = 0;
        };

        // Message received
        eventSource.onmessage = (event) => {
          try {
            const notification = JSON.parse(event.data);
            
            // Add timestamp if not present
            if (!notification.created_at) {
              notification.created_at = new Date().toISOString();
            }
            
            // Set is_read to false by default
            if (notification.is_read === undefined) {
              notification.is_read = false;
            }

            setNotifications((prev) => {
              // Avoid duplicates
              const isDuplicate = prev.some((n) => n.id === notification.id);
              if (isDuplicate) return prev;

              // Keep only last 50 notifications
              const updated = [notification, ...prev].slice(0, 50);
              return updated;
            });

            // Update unread count
            setNotifications((prev) => {
              const count = prev.filter((n) => !n.is_read).length;
              setUnreadCount(count);
              return prev;
            });
          } catch (parseErr) {
            console.error('Failed to parse notification:', parseErr);
          }
        };

        // Error handling
        eventSource.onerror = (error) => {
          console.error('❌ Notification connection error:', error);
          setIsConnected(false);
          eventSource.close();

          // Attempt to reconnect with exponential backoff
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            const backoffTime = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
            console.log(`⏳ Reconnecting in ${backoffTime}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
            
            reconnectTimeout = setTimeout(() => {
              connectToNotifications();
            }, backoffTime);
            
            setConnectionError(`Connection lost. Retrying...`);
          } else {
            setConnectionError('Failed to connect to notifications after multiple attempts');
          }
        };
      } catch (err) {
        console.error('Failed to create EventSource:', err);
        setConnectionError(err.message);
        setIsConnected(false);
      }
    };

    connectToNotifications();

    // Cleanup
    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [user]);

  return {
    notifications,           // array of notifications
    unreadCount,            // number of unread notifications
    isConnected,            // boolean: is SSE connected?
    connectionError,        // string: error message if any
    markAsRead,             // function(notificationId)
    markAllAsRead,          // function()
    deleteNotification,     // function(notificationId)
    clearAll                // function()
  };
};

/**
 * Helper: Get notification styling based on type
 */
export const getNotificationStyle = (notificationType) => {
  const styles = {
    SESSION_CREATED: {
      icon: '💬',
      color: '#3b82f6',    // blue
      bgColor: '#dbeafe',
      borderColor: '#93c5fd'
    },
    MEMORY_CONSOLIDATED: {
      icon: '🧠',
      color: '#9333ea',    // purple
      bgColor: '#f3e8ff',
      borderColor: '#e9d5ff'
    },
    DOCUMENT_INDEXED: {
      icon: '📄',
      color: '#22c55e',    // green
      bgColor: '#dcfce7',
      borderColor: '#bbf7d0'
    },
    ADMIN_ALERT: {
      icon: '🚨',
      color: '#ef4444',    // red
      bgColor: '#fee2e2',
      borderColor: '#fecaca'
    },
    DEFAULT: {
      icon: '📢',
      color: '#6366f1',    // indigo
      bgColor: '#e0e7ff',
      borderColor: '#c7d2fe'
    }
  };

  return styles[notificationType] || styles.DEFAULT;
};

/**
 * Helper: Format notification timestamp
 */
export const formatNotificationTime = (timestamp) => {
  const now = new Date();
  const notifTime = new Date(timestamp);
  const diffMs = now.getTime() - notifTime.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return notifTime.toLocaleDateString();
};