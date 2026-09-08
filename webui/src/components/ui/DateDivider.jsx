import React from 'react';

/**
 * Safely parse timestamps in various formats (ISO, Date, timestamp number, Postgres datetime string).
 */
export function parseTimestampSafe(timestamp) {
  if (!timestamp) return null;
  if (timestamp instanceof Date) return isNaN(timestamp.getTime()) ? null : timestamp;
  if (typeof timestamp === 'number') {
    const d = new Date(timestamp);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof timestamp === 'string') {
    let cleaned = timestamp.trim();
    if (cleaned.includes(' ') && !cleaned.includes('T')) {
      cleaned = cleaned.replace(' ', 'T');
    }
    const d = new Date(cleaned);
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

/**
 * Return local calendar day key formatted as 'YYYY-MM-DD'.
 */
export function getCalendarDayKey(timestamp) {
  const d = parseTimestampSafe(timestamp);
  if (!d) return null;
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format timestamp into standard human-readable full date string matching CAKRA style.
 * Example EN: "Monday, September 7, 2026"
 * Example ID: "Senin, 7 September 2026"
 */
export function formatDateDivider(timestamp, language = 'id') {
  const d = parseTimestampSafe(timestamp);
  if (!d) return '';
  try {
    return d.toLocaleDateString(language === 'en' ? 'en-US' : 'id-ID', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  } catch (e) {
    return '';
  }
}

/**
 * Deterministically check if current message should show a date divider relative to previous message.
 */
export function shouldShowDateDivider(currentMsg, prevMsg) {
  if (!currentMsg) return false;
  const currentKey = getCalendarDayKey(currentMsg.created_at || currentMsg.timestamp);
  if (!currentKey) return false;
  if (!prevMsg) return true;
  const prevKey = getCalendarDayKey(prevMsg.created_at || prevMsg.timestamp);
  return currentKey !== prevKey;
}

/**
 * DateDivider Component
 * Displays a sleek, centered date pill divider across day changes in both Collab and Main Chat.
 */
export const DateDivider = React.memo(function DateDivider({
  dateText,
  timestamp,
  language = 'id',
  darkMode = true,
  theme,
  style = {}
}) {
  const text = dateText || formatDateDivider(timestamp, language);
  if (!text) return null;

  const bg = theme?.headerBg || (darkMode ? '#1e1e20' : '#f3f4f6');
  const borderColor = theme?.borderColor || (darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)');
  const textColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  return (
    <div
      className="flex items-center justify-center my-6 select-none pointer-events-none w-full"
      style={{
        margin: '24px 0 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        ...style
      }}
    >
      <div
        className="px-3.5 py-1 rounded-full border text-[11px] font-medium shadow-sm backdrop-blur-sm transition-colors duration-200"
        style={{
          background: bg,
          borderColor: borderColor,
          color: textColor,
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
          letterSpacing: '0.01em'
        }}
      >
        {text}
      </div>
    </div>
  );
});

export default DateDivider;
