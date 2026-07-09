import React, { useEffect, useRef, useCallback, useState } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ChatBubble from './ChatBubble';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';

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
}) {
  const virtuosoRef = useRef(null);

  // scrollParent via useState — set saat isLoading=true (Virtuoso belum ada)
  // sehingga ketika isLoading=false, Virtuoso mount langsung dengan scrollParent yang benar.
  const [scrollParent, setScrollParent] = useState(null);
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
      if (messagesContainerRef?.current) {
        setTimeout(() => {
          if (messagesContainerRef.current) {
            messagesContainerRef.current.scrollTo({
              top: messagesContainerRef.current.scrollHeight,
              behavior: 'smooth',
            });
          }
        }, 150);
      }
    }
    prevIsStreamingRef.current = isStreaming;
  }, [isStreaming, messagesContainerRef]);

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
        if (messagesContainerRef?.current) {
          messagesContainerRef.current.scrollTo({ top: 9999999, behavior: 'instant' });
        }
      };
      requestAnimationFrame(scrollToBottom);
      setTimeout(scrollToBottom, 200);
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
    />
  ), [darkMode, theme, isThinking, isStreamingText, sendMessage, searchQuery, messages.length, onFileClick, setPreviewImage, onOpenArtifact, handleDownloadAllArtifacts, handleDownloadArtifact]);

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
                {currentThinking || 'CAKRA sedang berpikir'}
              </span>
            </div>
            <div style={styles.assistantContent} />
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
          <div style={{ animation: 'fadeSlideIn 0.2s ease-out' }}>
            <SkeletonChat />
          </div>
        ) : messages.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
              <div style={styles.emptyLogoWrap}>
                <img src={cakraLogo} alt="CAKRA" style={styles.emptyLogo} />
              </div>
              <h1 style={{ ...styles.emptyTitle, color: theme.textColor }}>Halo, saya CAKRA</h1>
            </div>
            <p style={{ ...styles.emptySubtitle, color: theme.secondaryText }}>Ada yang bisa saya bantu hari ini?</p>
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
              initialTopMostItemIndex={messages.length > 0 ? messages.length - 1 : 0}
              atBottomStateChange={(atBottom) => {
                if (onAtBottomChange) onAtBottomChange(atBottom);
              }}
              followOutput={(isAtBottom) => {
                if (isAtBottom) return isStreamingText ? 'auto' : 'smooth';
                return false;
              }}
              increaseViewportBy={{ top: 800, bottom: 800 }}
              components={{ Footer: FooterComponent }}
            />
          </div>
        )}
      </div>
    </div>
  );
}