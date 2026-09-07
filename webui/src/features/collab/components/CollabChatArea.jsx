import React, { useRef, useEffect } from 'react';
import CollabUserBubble from './CollabUserBubble';
import CollabCakraBubble from './CollabCakraBubble';
import { Bot } from 'lucide-react';

const formatDateDivider = (isoString) => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('id-ID', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  } catch (e) {
    return '';
  }
};

const CollabChatArea = ({
  messages = [],
  currentNpp,
  membersMap = {},
  typingStatus = null,
  onApplyToDocument,
  darkMode = true,
  theme
}) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typingStatus]);

  let lastDate = '';

  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const bubbleBg = darkMode ? '#1e1e20' : '#f3f4f6';

  return (
    <div className="flex-1 overflow-y-auto py-4 px-2 sm:px-6 custom-scrollbar space-y-1 bg-transparent">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center p-8" style={{ color: secondaryTextColor }}>
          <div className="w-12 h-12 rounded-2xl bg-teal-500/10 text-teal-400 border border-teal-500/20 flex items-center justify-center mb-3">
            <Bot size={24} />
          </div>
          <h3 className="text-sm font-semibold mb-1" style={{ color: textColor }}>
            Ruang Diskusi Masih Kosong
          </h3>
          <p className="text-xs max-w-sm" style={{ color: secondaryTextColor }}>
            Mulai obrolan bersama tim Anda. CAKRA siap mendampingi pembahasan regulasi dan penyusunan draf dokumen kerja.
          </p>
        </div>
      ) : (
        messages.map((msg, idx) => {
          const msgDate = formatDateDivider(msg.created_at);
          const showDateDivider = msgDate && msgDate !== lastDate;
          if (showDateDivider) {
            lastDate = msgDate;
          }

          const isMe = msg.sender_type === 'USER' && String(msg.sender_npp).trim() === String(currentNpp).trim();
          const memberInfo = membersMap[msg.sender_npp];

          return (
            <React.Fragment key={msg.id || idx}>
              {showDateDivider && (
                <div className="flex items-center justify-center my-4">
                  <div
                    className="px-3 py-1 rounded-full border text-[11px] font-medium"
                    style={{
                      background: darkMode ? '#1e1e20' : '#f3f4f6',
                      borderColor: borderColor,
                      color: secondaryTextColor
                    }}
                  >
                    {msgDate}
                  </div>
                </div>
              )}

              {msg.sender_type === 'CAKRA' ? (
                <CollabCakraBubble
                  message={msg}
                  onApplyToDocument={onApplyToDocument}
                  darkMode={darkMode}
                  theme={theme}
                />
              ) : (
                <CollabUserBubble
                  message={msg}
                  isMe={isMe}
                  memberInfo={memberInfo}
                  darkMode={darkMode}
                  theme={theme}
                />
              )}
            </React.Fragment>
          );
        })
      )}

      {/* Typing Indicator */}
      {typingStatus?.is_typing && (
        <div className="flex items-center gap-3 px-4 py-2 mb-2 animate-in fade-in">
          <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30 flex items-center justify-center shrink-0">
            <Bot size={16} className="animate-pulse" />
          </div>
          <div
            className="rounded-2xl rounded-tl-sm px-3.5 py-2 flex items-center gap-2 text-xs border"
            style={{
              background: bubbleBg,
              borderColor: borderColor,
              color: textColor
            }}
          >
            <span>{typingStatus.sender || 'CAKRA'} sedang mengetik</span>
            <div className="flex gap-1 items-center">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

export default CollabChatArea;
