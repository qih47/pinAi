import React from "react";
import { useSessionExpiry } from "../hooks/useSessionExpiry";
import { useChatAuthStore } from "../stores/authStore";
import styles from "./sessionExpiryStatus.module.css";

/**
 * Component: Session Expiry Status Display (W11)
 *
 * Shows countdown timer above the sidebar
 * - Normal: "Session expires in: 7h 45m"
 * - Warning (< 5 min): "Session expiring in: 4m 32s" (red background)
 * - "Keep me signed in" button to extend
 */
const SessionExpiryStatus = () => {
  const { isAuthenticated } = useChatAuthStore();
  const { expiresIn, isExpiring, extendSession } = useSessionExpiry();

  if (!isAuthenticated || !expiresIn) {
    return null;
  }

  return (
    <div
      className={`${styles.container} ${isExpiring ? styles.warning : styles.normal}`}
    >
      <div className={styles.content}>
        <span className={styles.label}>
          {isExpiring ? "⏰ Session expiring in:" : "⏱️ Session expires in:"}
        </span>
        <span className={styles.time}>{expiresIn}</span>
      </div>

      {isExpiring && (
        <button
          className={styles.keepSignedInBtn}
          onClick={() => extendSession(8)}
          title="Extend your session for another 8 hours"
        >
          Keep Me Signed In
        </button>
      )}
    </div>
  );
};

export default SessionExpiryStatus;
