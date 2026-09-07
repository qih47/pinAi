import React, { memo } from 'react';
import { Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Helper warna avatar konsisten berdasarkan string nama/NPP
const getAvatarColor = (str = '') => {
  const colors = [
    'from-emerald-500 to-teal-700',
    'from-blue-500 to-indigo-700',
    'from-violet-500 to-purple-700',
    'from-amber-500 to-orange-700',
    'from-rose-500 to-pink-700',
    'from-cyan-500 to-blue-700',
  ];
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
};

const formatTime = (isoString) => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return '';
  }
};

const CollabUserBubble = ({ message, isMe, memberInfo, darkMode = true, theme }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    if (!message?.message_text) return;
    navigator.clipboard.writeText(message.message_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const senderName = message.sender_name || memberInfo?.name || 'Rekan Tim';
  const division = memberInfo?.divisi || 'PT Pindad';
  const timeStr = formatTime(message.created_at);
  const initials = senderName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('') || 'U';

  const avatarGradient = getAvatarColor(message.sender_npp || senderName);
  const textColor = theme?.textColor || (darkMode ? '#f1f5f9' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const bubbleBg = darkMode ? '#1e1e21' : '#f1f5f9';
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');

  if (isMe) {
    // Sisi KANAN: Pesan Saya Sendiri
    return (
      <div className="flex justify-end mb-4 px-4 group">
        <div className="max-w-[75%] sm:max-w-[65%] flex flex-col items-end">
          <div className="text-[11px] font-medium mb-1 px-1 flex items-center gap-1.5" style={{ color: secondaryTextColor }}>
            <span>Anda</span>
            <span>•</span>
            <span>{timeStr}</span>
          </div>

          <div className="relative bg-gradient-to-br from-emerald-600/90 to-teal-700/90 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-md shadow-emerald-950/20 border border-emerald-500/30 text-[14px] leading-relaxed break-words">
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.message_text}
              </ReactMarkdown>
            </div>

            <button
              onClick={handleCopy}
              className="absolute -left-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-white/5"
              style={{ color: secondaryTextColor }}
              title="Salin teks"
            >
              {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Sisi KIRI: Pesan Rekan Kerja Lain
  return (
    <div className="flex items-start gap-3 mb-4 px-4 group">
      {/* Avatar Inisial */}
      <div
        className={`w-9 h-9 rounded-full bg-gradient-to-br ${avatarGradient} flex items-center justify-center text-white text-xs font-bold shadow-sm shrink-0 border border-white/10`}
        title={`${senderName} (${division})`}
      >
        {initials}
      </div>

      <div className="max-w-[75%] sm:max-w-[65%] flex flex-col items-start">
        {/* Header: Nama + Badge Divisi + Waktu */}
        <div className="flex items-center gap-2 mb-1 px-1 flex-wrap">
          <span className="text-xs font-semibold" style={{ color: textColor }}>{senderName}</span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-full border font-medium"
            style={{
              background: darkMode ? '#1e1e20' : '#e5e7eb',
              borderColor: borderColor,
              color: secondaryTextColor
            }}
          >
            {division}
          </span>
          <span className="text-[11px]" style={{ color: secondaryTextColor }}>{timeStr}</span>
        </div>

        {/* Bubble Obrolan */}
        <div
          className="relative rounded-2xl rounded-tl-sm px-4 py-2.5 shadow-md border text-[14px] leading-relaxed break-words"
          style={{
            background: bubbleBg,
            borderColor: borderColor,
            color: textColor
          }}
        >
          <div className={`prose ${darkMode ? 'prose-invert' : ''} prose-sm max-w-none`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.message_text}
            </ReactMarkdown>
          </div>

          <button
            onClick={handleCopy}
            className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-white/5"
            style={{ color: secondaryTextColor }}
            title="Salin teks"
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
};

export default memo(CollabUserBubble);
