import React, { memo, useState } from 'react';
import { Sparkles, Copy, Check } from 'lucide-react';
import CakraResponseRenderer from '../../chat/components/CakraResponseRenderer';
import cakraLogo from '../../../assets/cakra.png';

const formatTime = (isoString) => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return '';
  }
};

const CollabCakraBubble = ({
  message,
  isActive = false,
  thinkingPhase = '',
  darkMode = true,
  theme
}) => {
  const [copied, setCopied] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const timeStr = formatTime(message.created_at);

  const handleCopy = () => {
    if (!message?.message_text) return;
    navigator.clipboard.writeText(message.message_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isProactive = message.interjection_type === 'PROACTIVE_SUGGESTION';
  const isMention = message.is_mention || message.interjection_type === 'EXPLICIT_MENTION';
  const isWelcome = message.interjection_type === 'WELCOME';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  const displayThought = thinkingPhase || "CAKRA sedang berpikir";

  return (
    <div
      className="assistant-chat-row flex flex-col mb-7 group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        padding: '0 4px',
        animation: 'fadeInUp 0.3s ease-out'
      }}
    >
      {/* ── Header CAKRA (Identik dengan ChatBubble ChatPage Utama) ── */}
      <div className="flex items-center gap-2 mb-2">
        <div className="relative shrink-0 flex items-center justify-center">
          <img
            src={cakraLogo}
            alt="CAKRA"
            style={{
              width: 25,
              height: 25,
              borderRadius: 8,
              objectFit: 'cover',
              background: 'transparent',
              animation: isActive ? 'cakraSpin 0.7s linear infinite' : 'none',
              transform: isActive ? undefined : 'rotate(0deg)',
            }}
          />
          {isActive && (
            <span
              className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full border"
              style={{
                background: '#10b981',
                borderColor: darkMode ? '#151517' : '#ffffff'
              }}
            />
          )}
        </div>

        {/* Status Shimmer Saat Streaming atau Nama CAKRA */}
        {isActive ? (
          <div className="flex items-center gap-1.5 ml-1">
            <span
              className="text-[13px] italic font-medium"
              style={{
                background: 'linear-gradient(90deg, #94a3b8 0%, #38bdf8 50%, #94a3b8 100%)',
                backgroundSize: '200% 100%',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                animation: 'shimmerFlow 1.2s linear infinite'
              }}
            >
              {displayThought}
            </span>
            <span className="flex items-center gap-0.5 text-sky-400 font-bold animate-pulse text-xs">
              ...
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 ml-1">
            <span
              className="text-[13.5px] font-semibold tracking-wide"
              style={{ color: textColor }}
            >
              CAKRA
            </span>

            {isProactive && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                💡 Masukan Proaktif
              </span>
            )}

            {isMention && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 font-medium">
                🎯 Respons @cakra
              </span>
            )}

            {isWelcome && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                👋 Tim Kolaborasi
              </span>
            )}

            <span className="text-[11px]" style={{ color: secondaryTextColor }}>
              {timeStr}
            </span>
          </div>
        )}
      </div>

      {/* ── Konten Jawaban Mengalir Natural (Tanpa Kotak Border Kaku) ── */}
      <div
        className="assistant-content-container"
        style={{
          paddingLeft: 33,
          paddingRight: 10,
          wordBreak: 'break-word',
          color: textColor
        }}
      >
        <div className="text-[15px] leading-relaxed">
          <CakraResponseRenderer
            rawContent={message.message_text || ''}
            isStreaming={isActive}
            darkMode={darkMode}
            theme={theme}
          />
        </div>

        {/* Tombol Aksi Minimalis Bawah (Copy) */}
        {!isActive && message.message_text && (
          <div className="mt-2.5 flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-opacity hover:opacity-100"
              style={{
                color: secondaryTextColor,
                background: darkMode ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
                opacity: isHovered || copied ? 1 : 0.6
              }}
              title="Salin jawaban"
            >
              {copied ? (
                <>
                  <Check size={12} className="text-emerald-400" />
                  <span className="text-emerald-400 text-[11px] font-medium">Tersalin</span>
                </>
              ) : (
                <>
                  <Copy size={12} />
                  <span className="text-[11px]">Salin</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default memo(CollabCakraBubble);
