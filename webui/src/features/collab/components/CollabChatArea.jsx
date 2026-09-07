import React, { useRef, useEffect, useCallback } from 'react';
import CollabUserBubble from './CollabUserBubble';
import CollabChatBubble from './CollabChatBubble';
import CollabAvatar from './CollabAvatar';
import CollabDocumentMinimapPill from './CollabDocumentMinimapPill';
import CollabChatNavigator from './CollabChatNavigator';
import cakraLogo from '../../../assets/cakra.png';

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
  streamingCakra = null,
  cakraThinkingPhase = '',
  darkMode = true,
  theme,
  language = 'id',
  onApplyToDocument,
  onFileClick,
  setPreviewImage,
  onOpenArtifact,
  handleDownloadArtifact,
  handleDownloadAllArtifacts,
  onEditMessage
}) => {
  const bottomRef = useRef(null);
  const scrollContainerRef = useRef(null);

  const handleNavigate = useCallback((index) => {
    const targetMsg = messages[index];
    const targetId = targetMsg?.id || index;
    const el = document.getElementById(`collab-msg-${targetId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (scrollContainerRef.current) {
      const ratio = index / Math.max(messages.length - 1, 1);
      scrollContainerRef.current.scrollTo({
        top: ratio * scrollContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typingStatus, streamingCakra]);

  let lastDate = '';

  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');

  return (
    <div className="flex-1 overflow-hidden relative flex flex-col">
      {/* 🌟 TOP FADE OVERLAY: Efek transparan memudar halus di bagian atas batas chat */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '75px',
          background: `linear-gradient(to bottom, ${theme?.mainBg || (darkMode ? '#151517' : '#ffffff')} 0%, ${darkMode ? 'rgba(21,21,23,0.92)' : 'rgba(255,255,255,0.92)'} 25%, ${darkMode ? 'rgba(21,21,23,0.55)' : 'rgba(255,255,255,0.55)'} 55%, ${darkMode ? 'rgba(21,21,23,0.15)' : 'rgba(255,255,255,0.15)'} 80%, transparent 100%)`,
          pointerEvents: 'none',
          zIndex: 20,
          transition: 'background 0.2s ease',
        }}
      />

      {/* 🌟 BOTTOM FADE OVERLAY: Efek transparan memudar halus di bagian bawah batas chat */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '80px',
          background: `linear-gradient(to top, ${theme?.mainBg || (darkMode ? '#151517' : '#ffffff')} 0%, ${darkMode ? 'rgba(21,21,23,0.92)' : 'rgba(255,255,255,0.92)'} 25%, ${darkMode ? 'rgba(21,21,23,0.55)' : 'rgba(255,255,255,0.55)'} 55%, ${darkMode ? 'rgba(21,21,23,0.15)' : 'rgba(255,255,255,0.15)'} 80%, transparent 100%)`,
          pointerEvents: 'none',
          zIndex: 20,
          transition: 'background 0.2s ease',
        }}
      />

      {/* 💊 Navigasi Dokumen Rujukan Tim (Pill Kiri) */}
      <CollabDocumentMinimapPill
        messages={messages}
        darkMode={darkMode}
        language={language}
        onNavigate={handleNavigate}
        scrollContainerRef={scrollContainerRef}
      />

      {/* 🧭 Navigasi Mini-Map User Messages (Pill Kanan) */}
      <CollabChatNavigator
        messages={messages}
        darkMode={darkMode}
        theme={theme}
        onNavigate={handleNavigate}
        scrollContainerRef={scrollContainerRef}
      />

      <div className="flex-1 overflow-y-auto custom-scrollbar bg-transparent" ref={scrollContainerRef}>
        {/* ── Wadah Terpusat Maksimal 865px (Identik dengan styles.chatInner ChatPage Utama) ── */}
        <div
          className="w-full flex flex-col justify-start min-h-full"
          style={{
            maxWidth: '865px',
            margin: '0 auto',
            padding: '36px 16px 24px',
            boxSizing: 'border-box'
          }}
        >
          {messages.length === 0 && !streamingCakra ? (
            <div
              className="flex-1 flex flex-col items-center justify-center text-center p-8 min-h-[300px]"
              style={{ color: secondaryTextColor }}
            >
              <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center mb-3 p-2 shadow-lg shadow-teal-500/5">
                <img src={cakraLogo} alt="CAKRA" className="w-full h-full object-contain" />
              </div>
              <h3 className="text-base font-semibold mb-1" style={{ color: textColor }}>
                Ruang Diskusi Tim
              </h3>
              <p className="text-xs max-w-md leading-relaxed" style={{ color: secondaryTextColor }}>
                Mulai obrolan bersama tim Anda. CAKRA siap mendampingi diskusi, koordinasi kerja, dan membantu memberikan masukan terbaik saat dipanggil dengan mention <strong>@cakra</strong>.
              </p>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => {
                const msgDate = formatDateDivider(msg.created_at);
                const showDateDivider = msgDate && msgDate !== lastDate;
                if (showDateDivider) {
                  lastDate = msgDate;
                }

                const isMe =
                  msg.sender_type === 'USER' &&
                  String(msg.sender_npp).trim() === String(currentNpp).trim();
                const memberInfo = membersMap[msg.sender_npp];

                return (
                  <div key={msg.id || idx} data-msg-index={idx} id={`collab-msg-${msg.id || idx}`} className="w-full">
                    {showDateDivider && (
                      <div className="flex items-center justify-center my-6">
                        <div
                          className="px-3.5 py-1 rounded-full border text-[11px] font-medium shadow-sm"
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
                      <CollabChatBubble
                        msg={msg}
                        idx={idx}
                        isStreaming={false}
                        darkMode={darkMode}
                        theme={theme}
                        language={language}
                        isLastMessage={idx === messages.length - 1}
                        onApplyToDocument={onApplyToDocument}
                        onFileClick={onFileClick}
                        setPreviewImage={setPreviewImage}
                        onOpenArtifact={onOpenArtifact}
                        handleDownloadArtifact={handleDownloadArtifact}
                        handleDownloadAllArtifacts={handleDownloadAllArtifacts}
                      />
                    ) : (
                      <CollabUserBubble
                        message={msg}
                        isMe={isMe}
                        memberInfo={memberInfo}
                        darkMode={darkMode}
                        theme={theme}
                        language={language}
                        setPreviewImage={setPreviewImage}
                        onEditMessage={onEditMessage}
                      />
                    )}
                  </div>
                );
              })}

            {/* Bubble Streaming Real-time CAKRA (Saat sedang menjawab) */}
            {streamingCakra && (
              <CollabChatBubble
                msg={streamingCakra}
                idx={messages.length}
                isStreaming={true}
                thinkingPhase={cakraThinkingPhase}
                darkMode={darkMode}
                theme={theme}
                language={language}
                isLastMessage={true}
                onApplyToDocument={onApplyToDocument}
                onFileClick={onFileClick}
                setPreviewImage={setPreviewImage}
                onOpenArtifact={onOpenArtifact}
                handleDownloadArtifact={handleDownloadArtifact}
                handleDownloadAllArtifacts={handleDownloadAllArtifacts}
              />
            )}
          </>
        )}

        {/* Indikator Mengetik Rekan Kerja / CAKRA (Typing Indicator) */}
        {typingStatus?.is_typing && !streamingCakra && String(typingStatus?.sender_npp) !== String(currentNpp) && (() => {
          const nppKey = typingStatus.sender_npp ? String(typingStatus.sender_npp).trim() : '';
          const senderKey = typingStatus.sender ? String(typingStatus.sender).trim().toLowerCase() : '';
          const isCakra = nppKey === 'CAKRA' || senderKey.includes('cakra');
          const typingMember = isCakra
            ? { name: 'CAKRA', photo_url: cakraLogo }
            : (membersMap[nppKey] || membersMap[senderKey] || membersMap[typingStatus.sender] || {});
          const senderName = isCakra ? 'CAKRA' : (typingStatus.sender || typingMember.name || typingMember.nama || 'Rekan');
          const senderPhoto = isCakra ? cakraLogo : (typingStatus.photo_url || typingStatus.profile_photo_url || typingMember.profile_photo_url || typingMember.photo_url || null);
          return (
            <div className="flex items-center gap-2.5 px-3 py-2 mb-2 animate-fadeInUp">
              {isCakra ? (
                <div className="w-[24px] h-[24px] rounded-full overflow-hidden flex items-center justify-center p-0.5 bg-teal-500/10 border border-teal-500/20 shrink-0">
                  <img src={cakraLogo} alt="CAKRA" className="w-full h-full object-contain" />
                </div>
              ) : (
                <CollabAvatar
                  npp={typingStatus.sender_npp || typingMember.npp}
                  name={senderName}
                  photoUrl={senderPhoto}
                  size="w-[24px] h-[24px]"
                  className="!w-[24px] !h-[24px] !rounded-full shadow-sm shrink-0 overflow-hidden text-[9px]"
                />
              )}
              <div className="flex items-center gap-2 text-xs" style={{ color: secondaryTextColor }}>
                <span>
                  <strong style={{ color: textColor }}>{senderName}</strong> sedang mengetik
                </span>
                <div className="inline-flex gap-1 items-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          );
        })()}

        {/* Spacer bawah agar bubble terakhir mengambang mulus di atas gradient */}
        <div style={{ height: '40px', width: '100%', flexShrink: 0 }} />
        <div ref={bottomRef} />
      </div>
      </div>
    </div>
  );
};

export default CollabChatArea;
