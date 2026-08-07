import React, { useState, useMemo, useEffect, useRef } from 'react';

export default function ChatNavigator({ messages, onNavigate, darkMode, theme, scrollContainerRef }) {
  const [isHovered, setIsHovered] = useState(false);
  const [trueVisibleIndex, setTrueVisibleIndex] = useState(0);
  const [clickedIndex, setClickedIndex] = useState(null);
  const scrollTimeout = useRef(null);
  const clickTimeout = useRef(null);

  // Extract only user messages with their original indices
  const userMessages = useMemo(() => {
    return messages
      .map((msg, index) => ({ ...msg, originalIndex: index }))
      .filter(msg => msg.role === 'user');
  }, [messages]);

  // Tentukan indeks pesan user mana yang sedang "aktif" di layar
  const activeUserMessageIndex = useMemo(() => {
    if (clickedIndex !== null) return clickedIndex;
    if (userMessages.length === 0) return -1;

    let activeIdx = userMessages[0].originalIndex; // fallback pertama

    // Cari pesan user terakhir yang posisinya sudah dilewati oleh bagian atas layar
    for (let i = 0; i < userMessages.length; i++) {
      if (userMessages[i].originalIndex <= trueVisibleIndex) {
        activeIdx = userMessages[i].originalIndex;
      }
    }

    return activeIdx;
  }, [userMessages, trueVisibleIndex, clickedIndex]);

  // Pantau scroll secara real-time untuk mendapatkan item yang benar-benar ada di viewport
  // (Mengabaikan item yang di-overscan / di-render di luar layar oleh Virtuoso)
  useEffect(() => {
    if (!scrollContainerRef?.current) return;
    const container = scrollContainerRef.current;

    const handleScroll = () => {
      if (scrollTimeout.current) return;
      scrollTimeout.current = requestAnimationFrame(() => {
        scrollTimeout.current = null;

        const elements = container.querySelectorAll('[data-index]');
        if (!elements || elements.length === 0) return;

        const containerRect = container.getBoundingClientRect();

        // Cari elemen pertama yang setidaknya sebagian besar tampil di layar (melewati batas atas + 150px)
        // Hal ini mencegah pesan AI di atasnya yang hanya terlihat sedikit terdeteksi sebagai elemen teratas.
        for (let i = 0; i < elements.length; i++) {
          const rect = elements[i].getBoundingClientRect();
          if (rect.bottom > containerRect.top + 150) {
            const index = parseInt(elements[i].getAttribute('data-index'), 10);
            if (!isNaN(index)) {
              setTrueVisibleIndex(index);
            }
            break;
          }
        }
      });
    };

    container.addEventListener('scroll', handleScroll, { passive: true, capture: true });

    // Initial check (delay sedikit agar DOM siap)
    setTimeout(() => {
      handleScroll();
    }, 100);

    return () => {
      container.removeEventListener('scroll', handleScroll, { capture: true });
      if (scrollTimeout.current) cancelAnimationFrame(scrollTimeout.current);
    };
  }, [scrollContainerRef]);

  if (userMessages.length < 5) return null;

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'absolute',
        right: '16px',
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        padding: '10px 0', // larger hover target
      }}
    >
      <div
        className="premium-scroll custom-scrollbar"
        style={{
          background: isHovered ? (darkMode ? '#1E1E22' : '#ffffff') : 'transparent',
          boxShadow: isHovered ? (darkMode ? '0 8px 30px rgba(0,0,0,0.5)' : '0 8px 30px rgba(0,0,0,0.15)') : 'none',
          borderRadius: '12px',
          padding: isHovered ? '8px' : '0px',
          display: 'flex',
          flexDirection: 'column',
          gap: isHovered ? '2px' : '6px',
          maxHeight: '60vh',
          overflowY: isHovered ? 'auto' : 'hidden',
          border: isHovered ? `1px solid ${darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}` : 'none',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          width: isHovered ? '320px' : '16px'
        }}>
        {userMessages.map((msg, i) => {
          const isActive = msg.originalIndex === activeUserMessageIndex;

          return (
            <div
              key={i}
              onClick={() => {
                setClickedIndex(msg.originalIndex);
                if (clickTimeout.current) clearTimeout(clickTimeout.current);
                clickTimeout.current = setTimeout(() => {
                  setClickedIndex(null);
                }, 1000);
                onNavigate(msg.originalIndex);
              }}
              style={{
                cursor: 'pointer',
                width: '100%',
                height: isHovered ? 'auto' : '2px',
                minHeight: isHovered ? '34px' : '2px',
                padding: isHovered ? '8px 12px' : '0px',
                background: isHovered
                  ? (isActive ? (darkMode ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)') : 'transparent')
                  : (isActive ? (darkMode ? '#ffffff' : '#000000') : (darkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)')),
                borderRadius: isHovered ? '6px' : '0px',
                display: 'flex',
                alignItems: 'center',
                fontSize: '13px',
                color: darkMode ? '#e2e8f0' : '#1e293b',
                fontWeight: isActive ? 600 : 400,
                transition: 'background 0.1s',
                flexShrink: 0
              }}
              onMouseEnter={(e) => {
                if (isHovered) {
                  e.currentTarget.style.background = isActive
                    ? (darkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.2)')
                    : (darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)');
                } else {
                  e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.6)';
                }
              }}
              onMouseLeave={(e) => {
                if (isHovered) {
                  e.currentTarget.style.background = isActive
                    ? (darkMode ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)')
                    : 'transparent';
                } else {
                  e.currentTarget.style.background = isActive
                    ? (darkMode ? '#ffffff' : '#000000')
                    : (darkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)');
                }
              }}
              title={isHovered ? '' : (msg.content || 'Attachment...')}
            >
              {isHovered ? (
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%', pointerEvents: 'none' }}>
                  {msg.content || '[File Attachment]'}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
