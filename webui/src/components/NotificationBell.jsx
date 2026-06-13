import React, { useState } from "react";
import { useNotifications } from "../hooks/useNotifications";
import NotificationPanel from "./NotificationPanel";
import styles from "./notificationBell.module.css";

/**
 * Component: Notification Bell (W16)
 *
 * Displays bell icon with badge counter in top-right
 * Click to open/close notification panel
 * Shows connection status
 */
const NotificationBell = () => {
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const { unreadCount, isConnected, connectionError } = useNotifications();

  return (
    <div className={styles.container}>
      <button
        className={`${styles.bellButton} ${unreadCount > 0 ? styles.hasNotifications : ""}`}
        onClick={() => setIsPanelOpen(!isPanelOpen)}
        title={`${unreadCount} new notification${unreadCount !== 1 ? "s" : ""}`}
        aria-label="Notifications"
      >
        {/* Bell Icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={styles.bellIcon}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {/* Badge Counter */}
        {unreadCount > 0 && (
          <span className={styles.badge}>
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}

        {/* Connection Status Indicator */}
        <span
          className={`${styles.connectionDot} ${isConnected ? styles.connected : styles.disconnected}`}
          title={isConnected ? "Connected" : "Disconnected"}
        />
      </button>

      {/* Error Message */}
      {connectionError && (
        <div className={styles.errorToast}>
          <span className={styles.errorIcon}>⚠️</span>
          <span className={styles.errorText}>{connectionError}</span>
        </div>
      )}

      {/* Notification Panel */}
      {isPanelOpen && (
        <>
          {/* Backdrop to close panel on click outside */}
          <div
            className={styles.backdrop}
            onClick={() => setIsPanelOpen(false)}
          />
          <div className={styles.panelContainer}>
            <NotificationPanel onClose={() => setIsPanelOpen(false)} />
          </div>
        </>
      )}
    </div>
  );
};

export default NotificationBell;
