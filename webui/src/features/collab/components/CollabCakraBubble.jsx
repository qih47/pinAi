import React, { memo, useState } from 'react';
import { Bot, Sparkles, Copy, Check, FileText, ArrowRight } from 'lucide-react';
import CakraResponseRenderer from '../../chat/components/CakraResponseRenderer';

const formatTime = (isoString) => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return '';
  }
};

const CollabCakraBubble = ({ message, onApplyToDocument, darkMode = true, theme }) => {
  const [copied, setCopied] = useState(false);
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
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const bubbleBg = darkMode ? '#18181b' : '#ffffff';
  const buttonBg = darkMode ? '#222226' : '#f3f4f6';

  return (
    <div className="flex items-start gap-3 mb-5 px-4 group">
      {/* Avatar CAKRA */}
      <div className="relative shrink-0">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 via-cyan-600 to-emerald-700 flex items-center justify-center text-white shadow-lg shadow-teal-500/20 border border-teal-400/40">
          <Bot size={20} className="text-white animate-pulse" />
        </div>
        <span
          className="absolute -bottom-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full border"
          style={{ background: darkMode ? '#151517' : '#ffffff', borderColor: borderColor }}
        >
          <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
        </span>
      </div>

      <div className="max-w-[85%] sm:max-w-[75%] flex flex-col items-start w-full">
        {/* Header Badges */}
        <div className="flex items-center gap-2 mb-1.5 px-1 flex-wrap">
          <span className="text-xs font-bold text-teal-400 tracking-wide">CAKRA</span>
          
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-700/60 font-medium flex items-center gap-1">
            <Sparkles size={10} className="text-teal-300" />
            AI Teammate
          </span>

          {isProactive && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-950/70 text-amber-300 border border-amber-700/50 font-medium">
              💡 Masukan Proaktif
            </span>
          )}

          {isMention && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/70 text-cyan-300 border border-cyan-700/50 font-medium">
              🎯 Respons @cakra
            </span>
          )}

          {isWelcome && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-950/70 text-indigo-300 border border-indigo-700/50 font-medium">
              👋 Selamat Datang
            </span>
          )}

          <span className="text-[11px]" style={{ color: secondaryTextColor }}>{timeStr}</span>
        </div>

        {/* Bubble Box */}
        <div
          className="w-full rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-xl border relative"
          style={{
            background: bubbleBg,
            borderColor: darkMode ? 'rgba(20, 184, 166, 0.3)' : 'rgba(13, 148, 136, 0.4)',
            color: theme?.textColor || (darkMode ? '#f1f5f9' : '#1f2937')
          }}
        >
          <div className="text-[14.5px] leading-relaxed">
            <CakraResponseRenderer
              content={message.message_text}
              isStreaming={false}
              darkMode={darkMode}
              theme={theme}
            />
          </div>

          {/* Action Footer */}
          <div
            className="mt-3 pt-2.5 border-t flex items-center justify-between text-xs flex-wrap gap-2"
            style={{ borderColor: borderColor }}
          >
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors border"
                style={{
                  background: buttonBg,
                  borderColor: borderColor,
                  color: theme?.textColor || (darkMode ? '#cbd5e1' : '#334155')
                }}
              >
                {copied ? (
                  <>
                    <Check size={13} className="text-emerald-400" />
                    <span className="text-emerald-400 font-medium">Tersalin</span>
                  </>
                ) : (
                  <>
                    <Copy size={13} />
                    <span>Salin</span>
                  </>
                )}
              </button>

              {onApplyToDocument && (
                <button
                  onClick={() => onApplyToDocument(message.message_text)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-teal-950/80 hover:bg-teal-900/90 text-teal-300 hover:text-teal-200 transition-colors border border-teal-700/60"
                  title="Salin dan terapkan ke Document Pad"
                >
                  <FileText size={13} />
                  <span>Kirim ke Dokumen</span>
                  <ArrowRight size={12} />
                </button>
              )}
            </div>

            <span className="text-[11px] italic" style={{ color: secondaryTextColor }}>
              Didukung model regulasi Pindad
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(CollabCakraBubble);
