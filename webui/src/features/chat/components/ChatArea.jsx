import React, { useEffect, useRef, useCallback, useState } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ChatBubble from './ChatBubble';
import ChatNavigator from './ChatNavigator';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
import { translations } from '../../../utils/translations';
import { useChatStore } from '../../../stores/chatStore';

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
  isLoading = false,
  onAtBottomChange,
  onFileClick,
  setPreviewImage,
  onOpenArtifact,
  handleDownloadAllArtifacts,
  handleDownloadArtifact,
  language
}) {
  const virtuosoRef = useRef(null);

  // scrollParent via useState — set saat isLoading=true (Virtuoso belum ada)
  // sehingga ketika isLoading=false, Virtuoso mount langsung dengan scrollParent yang benar.
  const [scrollParent, setScrollParent] = useState(null);
  const [visibleRange, setVisibleRange] = useState({ startIndex: 0, endIndex: 0 });

  useEffect(() => {
    if (messagesContainerRef?.current && !scrollParent) {
      setScrollParent(messagesContainerRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // AUTO SCROLL SAAT STREAMING SELESAI
  const prevIsStreamingRef = useRef(isStreaming);
  useEffect(() => {
    if (prevIsStreamingRef.current === true && isStreaming === false) {
      const isEditRegenerating = useChatStore.getState().isEditRegenerating;
      if (!isEditRegenerating && virtuosoRef.current && messages.length > 0) {
        const forceScroll = (behavior) => {
          if (virtuosoRef.current) {
            virtuosoRef.current.scrollTo({ top: 9999999, behavior });
          }
        };
        // Scroll pertama (animasi)
        setTimeout(() => forceScroll('smooth'), 150);
        // Scroll kedua (sapu bersih jika ada layout shift dari markdown)
        setTimeout(() => forceScroll('auto'), 500);
      }
    }
    prevIsStreamingRef.current = isStreaming;
  }, [isStreaming, messages.length]);

  // SCROLL TO BOTTOM SAAT SESSION DI-LOAD
  // Sama seperti ScrollBottomButton: scrollTo({ top: 9999999 }).
  // Dua attempt: rAF (setelah DOM commit) + 200ms (setelah Virtuoso setup virtual padding).
  const prevIsLoadingRef = useRef(isLoading);
  const prevMsgLenRef = useRef(messages.length);
  useEffect(() => {
    const wasLoading = prevIsLoadingRef.current;
    const appeared = prevMsgLenRef.current === 0 && messages.length > 0;

    if ((wasLoading && !isLoading && messages.length > 0) || appeared) {
      const scrollToBottom = () => {
        if (virtuosoRef.current) {
          virtuosoRef.current.scrollTo({
            top: 9999999,
            behavior: 'auto'
          });
        }
      };
      requestAnimationFrame(scrollToBottom);
      setTimeout(scrollToBottom, 200);
      setTimeout(scrollToBottom, 500); // Safeguard buat nunggu gambar/markdown
    }

    prevIsLoadingRef.current = isLoading;
    prevMsgLenRef.current = messages.length;
  }, [isLoading, messages.length, messagesContainerRef]);

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
      isLastMessage={idx === messages.length - 1}
      onFileClick={onFileClick}
      setPreviewImage={setPreviewImage}
      onOpenArtifact={onOpenArtifact}
      handleDownloadAllArtifacts={handleDownloadAllArtifacts}
      handleDownloadArtifact={handleDownloadArtifact}
      language={language}
    />
  ), [darkMode, theme, isThinking, isStreamingText, sendMessage, searchQuery, messages.length, onFileClick, setPreviewImage, onOpenArtifact, handleDownloadAllArtifacts, handleDownloadArtifact, language]);

  const t = translations[language]?.chatArea || translations.id.chatArea;

  const FooterComponent = useCallback(() => (
    <>
      {isStreaming && lastAssistantIndex === -1 && (
        <div style={{ ...styles.assistantRow, padding: '12px 0' }}>
          <div style={styles.assistantMessageWrapper}>
            <div style={styles.assistantHeader}>
              <div style={styles.avatarWrap}>
                <img
                  src={cakraLogo}
                  alt="CAKRA"
                  style={{ width: 25, height: 25, borderRadius: 8, objectFit: 'cover', background: 'transparent', animation: 'cakraSpin 1.2s linear infinite' }}
                />
                <span style={{ ...styles.statusDot, background: '#ef4444', borderColor: theme.mainBg }} />
              </div>
              <span style={{ ...styles.thinkingInline, color: theme.secondaryText, marginLeft: 10 }}>
                {currentThinking || t.thinking}
              </span>
            </div>
            <div style={styles.assistantContent} />
          </div>
        </div>
      )}
      {/* Spacer bawah yang sudah di-adjust (tidak terlalu tinggi, tidak terlalu mepet) */}
      <div style={{ height: '90px', width: '100%', flexShrink: 0 }} />
    </>
  ), [isStreaming, lastAssistantIndex, currentThinking, theme.mainBg, theme.secondaryText]);

  return (
    <div style={{ flex: 1, minHeight: 0, position: 'relative', display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div
        ref={messagesContainerRef}
        style={{ ...styles.scrollArea, overflowY: 'auto', position: 'relative', flex: 1 }}
        className="custom-scrollbar chat-main-scroll"
      >
      <div style={styles.chatInner}>
        {isLoading ? (
          <div style={{ animation: 'fadeSlideIn 0.2s ease-out' }}>
            <SkeletonChat />
          </div>
        ) : messages.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
              <div style={styles.emptyLogoWrap}>
                <img src={cakraLogo} alt="CAKRA" style={styles.emptyLogo} />
              </div>
              <h1 style={{ ...styles.emptyTitle, color: theme.textColor }}>{t.welcomeTitle}</h1>
            </div>
            <p style={{ ...styles.emptySubtitle, color: theme.secondaryText }}>{t.welcomeSubtitle}</p>
          </div>
        ) : (
          <div
            className="assistant-content-container"
            style={{ flex: 1, minHeight: 0, position: 'relative', animation: 'fadeSlideIn 0.15s ease-out' }}
          >
            <Virtuoso
              ref={virtuosoRef}
              style={{ height: '100%' }}
              data={messages}
              customScrollParent={scrollParent}
              useWindowScroll={false}
              itemContent={itemContent}
              language={language}
              atBottomStateChange={(atBottom) => {
                if (onAtBottomChange) onAtBottomChange(atBottom);
              }}
              alignToBottom={true}
              followOutput={(isAtBottom) => {
                if (isStreamingText) return 'auto';
                if (isAtBottom) return 'auto';
                return false;
              }}
              rangeChanged={(range) => {
                setVisibleRange(range);
              }}
              increaseViewportBy={{ top: 800, bottom: 800 }}
              components={{ Footer: FooterComponent }}
            />
          </div>
        )}
      </div>
    </div>
      
      {/* Navigasi Mini-Map User Messages - Sekarang absolute terhadap parent yang tidak scroll */}
      <ChatNavigator 
        messages={messages} 
        darkMode={darkMode} 
        theme={theme}
        scrollContainerRef={messagesContainerRef}
        onNavigate={(index) => {
          if (virtuosoRef.current) {
            virtuosoRef.current.scrollToIndex({ index, align: 'start', behavior: 'smooth' });
          }
        }} 
      />
    </div>
  );
}