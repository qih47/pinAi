import React from "react";
import {
  useNotifications,
  getNotificationStyle,
  formatNotificationTime,
} from "../hooks/useNotifications";
import styles from "./notificationPanel.module.css";

/**
 * Component: Notification Panel (W16)
 *
 * Slide-out panel showing notification history
 * Color-coded by notification type
 * Shows read/unread status
 * Mark all as read, delete individual, or clear all
 */
const NotificationPanel = ({ onClose }) => {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearAll,
  } = useNotifications();

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <h2>Notifications</h2>
          {unreadCount > 0 && (
            <span className={styles.unreadBadge}>{unreadCount} new</span>
          )}
        </div>

        {/* Header Actions */}
        <div className={styles.headerActions}>
          {unreadCount > 0 && (
            <button
              className={styles.markAllButton}
              onClick={markAllAsRead}
              title="Mark all as read"
            >
              Mark all read
            </button>
          )}
          {notifications.length > 0 && (
            <button
              className={styles.clearButton}
              onClick={clearAll}
              title="Clear all notifications"
            >
              Clear all
            </button>
          )}
          <button
            className={styles.closeButton}
            onClick={onClose}
            title="Close panel"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Notifications List */}
      <div className={styles.list}>
        {notifications.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🔔</div>
            <p className={styles.emptyText}>No notifications yet</p>
            <p className={styles.emptySubtext}>
              Your notifications will appear here
            </p>
          </div>
        ) : (
          notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onRead={markAsRead}
              onDelete={deleteNotification}
            />
          ))
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className={styles.footer}>
          <p className={styles.footerText}>
            Showing {notifications.length} notification
            {notifications.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}
    </div>
  );
};

/**
 * Individual Notification Item
 */
const NotificationItem = ({ notification, onRead, onDelete }) => {
  const style = getNotificationStyle(notification.event_type);
  const timeAgo = formatNotificationTime(notification.created_at);

  return (
    <div
      className={`${styles.notificationItem} ${!notification.is_read ? styles.unread : styles.read}`}
      style={{
        borderLeftColor: style.color,
        backgroundColor: !notification.is_read ? style.bgColor : "#f9fafb",
      }}
    >
      {/* Icon */}
      <div className={styles.icon} style={{ color: style.color }}>
        {style.icon}
      </div>

      {/* Content */}
      <div className={styles.content}>
        <div className={styles.title}>
          {notification.title || notification.event_type}
        </div>
        {notification.message && (
          <p className={styles.message}>{notification.message}</p>
        )}
        <div className={styles.meta}>
          <span className={styles.time}>{timeAgo}</span>
          {notification.data && notification.data.details && (
            <span className={styles.details}>{notification.data.details}</span>
          )}
        </div>
      </div>

      {/* Unread Indicator */}
      {!notification.is_read && <div className={styles.unreadDot} />}

      {/* Actions */}
      <div className={styles.actions}>
        {!notification.is_read && (
          <button
            className={styles.actionButton}
            onClick={() => onRead(notification.id)}
            title="Mark as read"
            aria-label="Mark as read"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={styles.iconSmall}
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </button>
        )}
        <button
          className={styles.actionButton}
          onClick={() => onDelete(notification.id)}
          title="Delete notification"
          aria-label="Delete"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={styles.iconSmall}
          >
            <polyline points="3 6 5 4 21 4 23 6 23 20 2 20 2 6" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default NotificationPanel;
