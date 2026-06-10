import React, { useEffect, useRef, useCallback } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ChatBubble from './ChatBubble';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';

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
  sendMessage
}) {
  const virtuosoRef = useRef(null);
  const prevMessagesLengthRef = useRef(messages.length);

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
      msg={{ ...msg, totalMessages: messages.length }}
      darkMode={darkMode}
      theme={theme}
      isThinking={isThinking}
      isStreamingText={isStreamingText}
      sendMessage={sendMessage}
    />
  ), [darkMode, theme, isThinking, isStreamingText, messages.length, sendMessage]);

  return (
    <div
      ref={messagesContainerRef}
      style={{ ...styles.scrollArea, overflowY: 'auto' }}
      className="custom-scroll-gemini"
    >
      <div style={styles.chatInner}>
        {messages.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyLogoWrap}>
              <img src={cakraLogo} alt="CAKRA" style={styles.emptyLogo} />
            </div>
            <h1 style={{ ...styles.emptyTitle, color: theme.textColor }}>Halo, saya CAKRA</h1>
            <p style={{ ...styles.emptySubtitle, color: theme.secondaryText }}>Ada yang bisa saya bantu hari ini?</p>
          </div>
        ) : (
          // 🔥 KUNCI SAKTI: Masukin class container ke pembungkus luar ini biar warning DOM murni hilang, dan Virtuoso ga re-render pas ngetik
          <div className="assistant-content-container">
            <Virtuoso
              ref={virtuosoRef}
              data={messages}
              customScrollParent={messagesContainerRef?.current || undefined}
              useWindowScroll={false}
              itemContent={itemContent}
              followOutput={(isAtBottom) => {
                if (isAtBottom) {
                  return isStreamingText ? 'auto' : 'smooth';
                }
                return false;
              }}
              increaseViewportBy={{ top: 800, bottom: 800 }}
              initialTopMostItemIndex={Math.max(0, messages.length - 1)}
              components={{
                Footer: () => (
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
                              {currentThinking || 'CAKRA sedang berpikir...'}
                            </span>
                          </div>
                          <div style={styles.assistantContent}></div>
                        </div>
                      </div>
                    )}
                    <div style={{ height: '60px', width: '100%', flexShrink: 0 }} />
                  </>
                )
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}