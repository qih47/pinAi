import React, { useState, useEffect } from 'react';

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
 * Format timestamp menjadi relative time string (ID / EN)
 * @param {string|number|Date} timestamp 
 * @param {string} language 'id' | 'en'
 * @returns {string}
 */
export function getRelativeTimeString(timestamp, language = 'id') {
    const messageDate = parseTimestampSafe(timestamp);
    if (!messageDate) {
        return language === 'en' ? 'Just now' : 'Baru saja';
    }

    const now = new Date();
    const diffSeconds = Math.max(0, Math.floor((now.getTime() - messageDate.getTime()) / 1000));

    // Kurang dari 60 detik -> "Baru saja" / "Just now"
    if (diffSeconds < 60) {
        return language === 'en' ? 'Just now' : 'Baru saja';
    }

    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) {
        if (language === 'en') {
            return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
        } else {
            return `${diffMinutes} menit lalu`;
        }
    }

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
        if (language === 'en') {
            return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
        } else {
            return `${diffHours} jam lalu`;
        }
    }

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) {
        if (language === 'en') {
            return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
        } else {
            return diffDays === 1 ? 'Kemarin' : `${diffDays} hari lalu`;
        }
    }

    // Format tanggal untuk pesan lama (> 7 hari)
    try {
        if (language === 'en') {
            return messageDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } else {
            return messageDate.toLocaleDateString('id-ID', { month: 'short', day: 'numeric' });
        }
    } catch {
        return language === 'en' ? 'Just now' : 'Baru saja';
    }
}

/**
 * MessageTimer Component
 * Menampilkan label timer relatif di samping tombol aksi bubble chat.
 */
export const MessageTimer = React.memo(function MessageTimer({
    timestamp,
    language = 'id',
    darkMode = false,
    style = {}
}) {
    const [timeStr, setTimeStr] = useState(() => getRelativeTimeString(timestamp, language));

    useEffect(() => {
        setTimeStr(getRelativeTimeString(timestamp, language));

        // Auto update setiap 30 detik agar transisi dari 'Baru saja' ke '1 menit lalu' berjalan otomatis
        const intervalId = setInterval(() => {
            setTimeStr(getRelativeTimeString(timestamp, language));
        }, 30000);

        return () => clearInterval(intervalId);
    }, [timestamp, language]);

    const messageDate = parseTimestampSafe(timestamp);
    const formattedFullTime = messageDate
        ? (() => {
            try {
                return messageDate.toLocaleString(language === 'en' ? 'en-US' : 'id-ID', {
                    dateStyle: 'medium',
                    timeStyle: 'short'
                });
            } catch {
                return '';
            }
        })()
        : '';

    return (
        <span
            style={{
                fontSize: '11px',
                fontWeight: 450,
                color: darkMode ? '#94a3b8' : '#9ca3af',
                userSelect: 'none',
                lineHeight: 1,
                padding: '0 4px',
                opacity: 0.8,
                letterSpacing: '-0.01em',
                display: 'inline-flex',
                alignItems: 'center',
                whiteSpace: 'nowrap',
                ...style
            }}
            title={formattedFullTime}
        >
            {timeStr}
        </span>
    );
});

export default MessageTimer;
