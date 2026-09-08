import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useChatStore } from '../../../stores/chatStore';

/**
 * 🧭 CollabChatNavigator
 * Navigasi Mini-Map User Messages (Pill Kanan) yang melayang di sebelah KANAN chat area Collab Space.
 * Memudahkan navigasi cepat antar-topik atau pesan yang dikirim oleh rekan-rekan kerja tim.
 */
export default function CollabChatNavigator({
  messages = [],
  onNavigate,
  darkMode = true,
  theme = {},
  language = 'id',
  scrollContainerRef
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [trueVisibleIndex, setTrueVisibleIndex] = useState(0);
  const [clickedIndex, setClickedIndex] = useState(null);
  const scrollTimeout = useRef(null);
  const clickTimeout = useRef(null);

  const isSplitScreen = useChatStore(state => state.isSplitScreen);

  // ── 1. Ekstrak Hanya Pesan User/Rekan Kerja Tim ──
  const userMessages = useMemo(() => {
    if (!Array.isArray(messages)) return [];
    return messages
      .map((msg, index) => ({ ...msg, originalIndex: index }))
      .filter(msg => msg.sender_type === 'USER' || msg.role === 'user');
  }, [messages]);

  // ── 2. Tentukan Pesan User yang Sedang Aktif di Viewport ──
  const activeUserMessageIndex = useMemo(() => {
    if (clickedIndex !== null) return clickedIndex;
    if (userMessages.length === 0) return -1;

    let activeIdx = userMessages[0].originalIndex;
    for (let i = 0; i < userMessages.length; i++) {
      if (userMessages[i].originalIndex <= trueVisibleIndex) {
        activeIdx = userMessages[i].originalIndex;
      }
    }
    return activeIdx;
  }, [userMessages, trueVisibleIndex, clickedIndex]);

  // ── 3. Pantau Scroll untuk Update Posisi Aktif ──
  useEffect(() => {
    if (!scrollContainerRef?.current) return;
    const container = scrollContainerRef.current;

    const handleScroll = () => {
      if (scrollTimeout.current) return;
      scrollTimeout.current = requestAnimationFrame(() => {
        scrollTimeout.current = null;

        const elements = container.querySelectorAll('[data-msg-index]');
        if (!elements || elements.length === 0) return;

        const containerRect = container.getBoundingClientRect();
        for (let i = 0; i < elements.length; i++) {
          const rect = elements[i].getBoundingClientRect();
          if (rect.bottom > containerRect.top + 100) {
            const index = parseInt(elements[i].getAttribute('data-msg-index'), 10);
            if (!isNaN(index)) {
              setTrueVisibleIndex(index);
            }
            break;
          }
        }
      });
    };

    container.addEventListener('scroll', handleScroll, { passive: true, capture: true });
    setTimeout(() => handleScroll(), 120);

    return () => {
      container.removeEventListener('scroll', handleScroll, { capture: true });
      if (scrollTimeout.current) cancelAnimationFrame(scrollTimeout.current);
    };
  }, [scrollContainerRef]);

  // ── 4. Gap Dinamis Mini-Map (Harus dipanggil sebelum early return sesuai aturan hooks React) ──
  const unhoveredGap = useMemo(() => {
    if (userMessages.length <= 15) return 4;
    if (userMessages.length <= 25) return 3;
    return 2;
  }, [userMessages.length]);

  const handleDotClick = (originalIndex) => {
    setClickedIndex(originalIndex);
    if (clickTimeout.current) clearTimeout(clickTimeout.current);
    clickTimeout.current = setTimeout(() => {
      setClickedIndex(null);
    }, 800);

    if (typeof onNavigate === 'function') {
      onNavigate(originalIndex);
    }
  };

  if (userMessages.length < 3 || isSplitScreen) return null;

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'absolute',
        right: '16px',
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 40,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        padding: '8px 0',
      }}
    >
      <div
        className="no-scrollbar"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: isHovered ? '6px' : `${unhoveredGap}px`,
          padding: isHovered ? '10px 12px' : '8px 6px',
          borderRadius: isHovered ? '16px' : '999px',
          background: darkMode
            ? isHovered ? 'rgba(24, 24, 27, 0.92)' : 'rgba(24, 24, 27, 0.55)'
            : isHovered ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.65)',
          backdropFilter: 'blur(12px)',
          border: `1px solid ${darkMode ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.8)'}`,
          boxShadow: isHovered
            ? (darkMode ? '0 12px 30px rgba(0, 0, 0, 0.45)' : '0 12px 30px rgba(0, 0, 0, 0.1)')
            : '0 4px 12px rgba(0, 0, 0, 0.08)',
          maxHeight: '440px',
          overflowY: isHovered ? 'auto' : 'hidden',
          scrollbarWidth: 'none',
          msOverflowStyle: 'none',
          transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {userMessages.map((msg) => {
          const isActive = msg.originalIndex === activeUserMessageIndex;
          const senderName = msg.sender_name || 'Rekan';
          const textPreview = (msg.message_text || msg.content || '').trim().replace(/\s+/g, ' ');

          return (
            <button
              key={msg.id || msg.originalIndex}
              type="button"
              onClick={() => handleDotClick(msg.originalIndex)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: isHovered ? '4px 6px' : '2px',
                borderRadius: '8px',
                transition: 'all 0.15s ease',
                width: isHovered ? '240px' : 'auto',
                justifyContent: isHovered ? 'flex-start' : 'flex-end',
                textAlign: 'left'
              }}
              onMouseEnter={(e) => {
                if (isHovered) {
                  e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';
                }
              }}
              onMouseLeave={(e) => {
                if (isHovered) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
              title={!isHovered ? `${senderName}: ${textPreview}` : undefined}
            >
              {/* Dot Indicator */}
              <span
                style={{
                  width: isActive ? (isHovered ? '8px' : '8px') : '6px',
                  height: isActive ? (isHovered ? '8px' : '8px') : '6px',
                  borderRadius: '999px',
                  background: isActive ? '#6366f1' : (darkMode ? '#71717a' : '#9ca3af'),
                  boxShadow: isActive ? '0 0 8px rgba(99, 102, 241, 0.7)' : 'none',
                  transition: 'all 0.15s ease',
                  flexShrink: 0
                }}
              />

              {/* Teks Cuplikan Pesan saat Dihover */}
              {isHovered && (
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span
                      className="text-[10px] font-bold truncate"
                      style={{ color: isActive ? '#818cf8' : (darkMode ? '#e2e8f0' : '#1e293b') }}
                    >
                      {senderName}
                    </span>
                  </div>
                  <div
                    className="text-[11px] truncate leading-tight"
                    style={{ color: darkMode ? '#a1a1aa' : '#64748b' }}
                  >
                    {textPreview || (language === 'en' ? '(Document/attachment message)' : '(Pesan dokumen/lampiran)')}
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
