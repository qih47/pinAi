import React, { useEffect, useRef, useCallback, useState } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ChatBubble from './ChatBubble';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';

// 🚦 W6: Helper untuk memetakan pesan pipeline ke nama fase yang lebih rapi
function formatThinkingPhase(thought) {
  if (!thought) return "CAKRA sedang berpikir...";
  if (thought.includes("jalur") || thought.includes("Gateway")) {
    return "🚦 Layer 0: Menganalisis intent & jalur...";
  }
  if (thought.includes("dokumen") || thought.includes("RAG")) {
    return "📚 RAG: Mencari regulasi internal Pindad...";
  }
  if (thought.includes("cepat") || thought.includes("respons") || thought.includes("Gemma")) {
    return "✍️ Layer 2: Menyusun formulasi respons...";
  }
  if (thought.includes("PDF")) {
    return "📄 Membaca lampiran PDF...";
  }
  if (thought.includes("visual")) {
    return "🖼️ Menganalisis visual...";
  }
  return thought;
}

// 🟡 W2: Shimmer Skeleton loading bubble placeholder
const SkeletonChat = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '100%', padding: '12px 0' }}>
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div className="skeleton-shimmer" style={{ width: '45%', height: '42px', borderRadius: '22px' }} />
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-start' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div className="skeleton-shimmer" style={{ width: '25px', height: '25px', borderRadius: '8px' }} />
        <div className="skeleton-shimmer" style={{ width: '80px', height: '16px', borderRadius: '4px' }} />
      </div>
      <div className="skeleton-shimmer" style={{ width: '75%', height: '100px', borderRadius: '22px', marginLeft: '33px' }} />
    </div>
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div className="skeleton-shimmer" style={{ width: '30%', height: '42px', borderRadius: '22px' }} />
    </div>
  </div>
);

export default function ChatArea({
  messages,
  isStreaming,
  theme,
  darkMode,
  messagesContainerRef,
  setInput,
  isThinking,
  currentThinking,
  isStreamingText,
  lastAssistantIndex,
  sendMessage,
  searchQuery = '',
  isLoading = false
}) {
  const virtuosoRef = useRef(null);
  const prevMessagesLengthRef = useRef(messages.length);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  useEffect(() => {
    if (messages.length > prevMessagesLengthRef.current) {
      requestAnimationFrame(() => {
        if (virtuosoRef.current) {
          virtuosoRef.current.scrollTo({
            top: 9999999,
            behavior: 'smooth'
          });
        }
      });
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages.length]);

  const itemContent = useCallback((idx, msg) => (
    <ChatBubble
      idx={idx}
      msg={msg}
      darkMode={darkMode}
      theme={theme}
      isThinking={isThinking}
      isStreamingText={isStreamingText}
      sendMessage={sendMessage}
      searchQuery={searchQuery}
    />
  ), [darkMode, theme, isThinking, isStreamingText, sendMessage, searchQuery]);

  const FooterComponent = useCallback(() => (
    <>
      {isStreaming && lastAssistantIndex === -1 && (
        <div style={{ ...styles.assistantRow, padding: '12px 0' }}>
          <div style={styles.assistantMessageWrapper}>
            <div style={styles.assistantHeader}>
              <div style={styles.avatarWrap}>
                <img src={cakraLogo} alt="CAKRA" style={{ width: 25, height: 25, borderRadius: 8, objectFit: 'cover', background: 'transparent', animation: 'cakraSpin 1.2s linear infinite' }} />
                <span style={{ ...styles.statusDot, background: '#ef4444', borderColor: theme.mainBg }} />
              </div>
              <span style={{ ...styles.thinkingInline, color: theme.secondaryText, marginLeft: 10 }}>
                {formatThinkingPhase(currentThinking)}
              </span>
            </div>
            <div style={styles.assistantContent}></div>
          </div>
        </div>
      )}
      <div style={{ height: '60px', width: '100%', flexShrink: 0 }} />
    </>
  ), [isStreaming, lastAssistantIndex, currentThinking, theme.mainBg, theme.secondaryText]);

  return (
    <div
      ref={messagesContainerRef}
      style={{ ...styles.scrollArea, overflowY: 'auto', position: 'relative' }}
      className="custom-scroll-gemini"
    >
      <div style={styles.chatInner}>
        {isLoading ? (
          <SkeletonChat />
        ) : messages.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyLogoWrap}>
              <img src={cakraLogo} alt="CAKRA" style={styles.emptyLogo} />
            </div>
            <h1 style={{ ...styles.emptyTitle, color: theme.textColor }}>Halo, saya CAKRA</h1>
            <p style={{ ...styles.emptySubtitle, color: theme.secondaryText }}>Ada yang bisa saya bantu hari ini?</p>
          </div>
        ) : (
          // 🔥 KUNCI SAKTI: Masukin class container ke pembungkus luar ini biar warning DOM murni hilang, dan Virtuoso ga re-render pas ngetik
          <div className="assistant-content-container" style={{ position: 'relative' }}>
            <Virtuoso
              ref={virtuosoRef}
              data={messages}
              customScrollParent={messagesContainerRef?.current || undefined}
              useWindowScroll={false}
              itemContent={itemContent}
              atBottomStateChange={(atBottom) => {
                setShowScrollBottom(!atBottom);
              }}
              followOutput={(isAtBottom) => {
                if (isAtBottom) {
                  return isStreamingText ? 'auto' : 'smooth';
                }
                return false;
              }}
              increaseViewportBy={{ top: 800, bottom: 800 }}
              initialTopMostItemIndex={Math.max(0, messages.length - 1)}
              components={{
                Footer: FooterComponent
              }}
            />
          </div>
        )}
      </div>

      {/* 🔴 W1: Scroll-to-Bottom Floating Button */}
      {showScrollBottom && messages.length > 0 && (
        <button
          onClick={() => {
            if (virtuosoRef.current) {
              virtuosoRef.current.scrollTo({
                top: 9999999,
                behavior: 'smooth'
              });
            }
          }}
          style={{
            ...styles.scrollBottomBtn,
            background: darkMode ? '#3b82f6' : '#2563eb',
            color: '#ffffff'
          }}
          title="Kembali ke Bawah"
        >
          ↓
        </button>
      )}
    </div>
  );
}