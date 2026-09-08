import React, { memo, useState } from 'react';
import {
  Copy,
  Check,
  FileText,
  Image as ImageIcon,
  Pencil,
  Globe,
  Code2,
  Workflow,
  BarChart3,
  FilePlus,
  Mail,
  Target,
  ExternalLink
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CollabAvatar from './CollabAvatar';
import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl } from '../../../services/endpoints';

// 🏷️ Helper icon untuk context mode tag
const getModeIcon = (mode) => {
  switch (mode) {
    case 'code':
      return <Code2 size={13} className="text-indigo-400 shrink-0" />;
    case 'websearch':
      return <Globe size={13} className="text-blue-400 shrink-0" />;
    case 'documents':
      return <FileText size={13} className="text-amber-400 shrink-0" />;
    case 'diagram':
      return <Workflow size={13} className="text-purple-400 shrink-0" />;
    case 'chart':
      return <BarChart3 size={13} className="text-emerald-400 shrink-0" />;
    case 'create_file':
      return <FilePlus size={13} className="text-cyan-400 shrink-0" />;
    case 'smart_mail':
      return <Mail size={13} className="text-rose-400 shrink-0" />;
    case 'focus':
      return <Target size={13} className="text-red-400 shrink-0" />;
    default:
      return null;
  }
};

const getModeLabel = (mode, lang = 'id') => {
  const labels = {
    code: lang === 'en' ? 'Code & Script' : 'Koding & Skrip',
    websearch: lang === 'en' ? 'Web Search' : 'Berita Terkini',
    documents: lang === 'en' ? 'Document' : 'Regulasi & Dokumen',
    diagram: lang === 'en' ? 'Diagram' : 'Diagram & Bagan',
    chart: lang === 'en' ? 'Chart' : 'Grafik & Data',
    create_file: lang === 'en' ? 'Create File' : 'Buat Berkas',
    smart_mail: lang === 'en' ? 'Official Memo' : 'Draft Nota Dinas',
    focus: lang === 'en' ? 'Audit & Deep Focus' : 'Focus & Audit'
  };
  return labels[mode] || mode;
};

// 🕒 Helper format waktu pesan: AM/PM untuk Bahasa Inggris, WIB untuk Bahasa Indonesia
const formatMessageTime = (isoString, language = 'id') => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';

    if (language === 'en') {
      return d.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } else {
      const hours = String(d.getHours()).padStart(2, '0');
      const minutes = String(d.getMinutes()).padStart(2, '0');
      return `${hours}.${minutes} WIB`;
    }
  } catch (e) {
    return '';
  }
};

// 🎨 Palette warna bubble dinamis untuk membedakan pesan setiap rekan kerja
const MEMBER_PALETTES = [
  {
    nameColor: '#10b981',
    badgeBg: 'rgba(16, 185, 129, 0.12)',
    badgeBorder: 'rgba(16, 185, 129, 0.25)',
    badgeText: '#34d399',
    bubbleBgDark: '#162220',
    bubbleBgLight: '#f0fdf4',
    bubbleBorderDark: 'rgba(16, 185, 129, 0.25)',
    bubbleBorderLight: 'rgba(16, 185, 129, 0.22)'
  },
  {
    nameColor: '#818cf8',
    badgeBg: 'rgba(99, 102, 241, 0.12)',
    badgeBorder: 'rgba(99, 102, 241, 0.25)',
    badgeText: '#a5b4fc',
    bubbleBgDark: '#1b1e2c',
    bubbleBgLight: '#f5f7ff',
    bubbleBorderDark: 'rgba(99, 102, 241, 0.25)',
    bubbleBorderLight: 'rgba(99, 102, 241, 0.22)'
  },
  {
    nameColor: '#c084fc',
    badgeBg: 'rgba(168, 85, 247, 0.12)',
    badgeBorder: 'rgba(168, 85, 247, 0.25)',
    badgeText: '#d8b4fe',
    bubbleBgDark: '#221a2a',
    bubbleBgLight: '#faf5ff',
    bubbleBorderDark: 'rgba(168, 85, 247, 0.25)',
    bubbleBorderLight: 'rgba(168, 85, 247, 0.22)'
  },
  {
    nameColor: '#f59e0b',
    badgeBg: 'rgba(245, 158, 11, 0.12)',
    badgeBorder: 'rgba(245, 158, 11, 0.25)',
    badgeText: '#fbbf24',
    bubbleBgDark: '#251f15',
    bubbleBgLight: '#fffbeb',
    bubbleBorderDark: 'rgba(245, 158, 11, 0.25)',
    bubbleBorderLight: 'rgba(245, 158, 11, 0.22)'
  },
  {
    nameColor: '#fb7185',
    badgeBg: 'rgba(244, 63, 94, 0.12)',
    badgeBorder: 'rgba(244, 63, 94, 0.25)',
    badgeText: '#fda4af',
    bubbleBgDark: '#25181c',
    bubbleBgLight: '#fff1f2',
    bubbleBorderDark: 'rgba(244, 63, 94, 0.25)',
    bubbleBorderLight: 'rgba(244, 63, 94, 0.22)'
  },
  {
    nameColor: '#38bdf8',
    badgeBg: 'rgba(14, 165, 233, 0.12)',
    badgeBorder: 'rgba(14, 165, 233, 0.25)',
    badgeText: '#7dd3fc',
    bubbleBgDark: '#142129',
    bubbleBgLight: '#f0f9ff',
    bubbleBorderDark: 'rgba(14, 165, 233, 0.25)',
    bubbleBorderLight: 'rgba(14, 165, 233, 0.22)'
  }
];

const getMemberPalette = (str = '') => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return MEMBER_PALETTES[Math.abs(hash) % MEMBER_PALETTES.length];
};

const CollabUserBubble = memo(function CollabUserBubble({
  message,
  isMe = false,
  memberInfo = null,
  darkMode = true,
  theme = {},
  language = 'id',
  isAutoNoted = false,
  setPreviewImage,
  onEditMessage,
  onApplyToDocument
}) {
  const [isCopied, setIsCopied] = useState(false);
  const [isNotedManual, setIsNotedManual] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.message_text || message.content || '');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const senderName = message.sender_name || memberInfo?.name || (language === 'en' ? 'Team Member' : 'Rekan Tim');
  const senderNpp = message.sender_npp || memberInfo?.npp || senderName;
  const photoUrl = memberInfo?.profile_photo_url;
  const division = memberInfo?.divisi || 'PT Pindad';
  const timeStr = formatMessageTime(message.created_at, language);

  const rawContent = message.message_text || message.content || '';
  const attachments = Array.isArray(message.attachments) ? message.attachments : [];

  const textColor = theme?.textColor || (darkMode ? '#f1f5f9' : '#1e293b');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  const memberPalette = getMemberPalette(String(senderNpp));

  const executeCopy = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleEditSubmit = async () => {
    if (!editValue.trim() || isSubmitting) return;
    if (editValue.trim() === rawContent.trim()) {
      setIsEditing(false);
      return;
    }
    try {
      setIsSubmitting(true);
      if (onEditMessage) {
        await onEditMessage(message.id, editValue.trim());
      }
      setIsEditing(false);
    } catch (e) {
      console.error('Failed to edit message:', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditValue(rawContent);
  };

  // Render Lampiran File / Gambar / Konteks Rujukan Aktif (Tag Dokumen atau Mode)
  const renderAttachments = () => {
    if (!attachments || attachments.length === 0) return null;
    return (
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          marginBottom: rawContent ? '8px' : '0',
          justifyContent: isMe ? 'flex-end' : 'flex-start'
        }}
      >
        {attachments.map((att, attIdx) => {
          // 📄 Kartu Dokumen Terstruktur (Bukan sekadar badge)
          // Memungkinkan pengirim maupun seluruh rekan tim membuka dokumen di Document Interrogator
          if (att.type === 'context_doc') {
            const rawPath = att.file_path || (att.filename ? (att.filename.startsWith('file_peraturan/') ? att.filename : `file_peraturan/${att.filename}`) : null);
            const fileUrl = rawPath ? getUploadUrl(rawPath) : null;
            const docTitle = att.title || att.name || 'Dokumen Regulasi';
            const categoryLabel = att.category || 'Regulasi';
            const nomorLabel = att.nomor ? `No: ${att.nomor}` : null;
            const pagesLabel = att.total_pages ? `${att.total_pages} Halaman` : 'Dokumen PDF';

            const handleOpenDocument = (e) => {
              e.stopPropagation();
              if (fileUrl) {
                useChatStore.getState().setSplitScreen(true, fileUrl);
              } else if (att.doc_id && String(att.doc_id).match(/^\d+$/)) {
                window.open(`https://peraturan.pindad.com/content/detail/${att.doc_id}`, '_blank', 'noopener,noreferrer');
              } else {
                console.warn('[COLLAB_DOC] File URL not directly resolvable for:', att);
              }
            };

            return (
              <div
                key={attIdx}
                onClick={handleOpenDocument}
                className="group/doc cursor-pointer transition-all duration-200 hover:scale-[1.01]"
                style={{
                  width: '100%',
                  minWidth: '260px',
                  maxWidth: '350px',
                  borderRadius: '16px',
                  background: darkMode
                    ? 'linear-gradient(135deg, rgba(32, 33, 38, 0.95), rgba(24, 25, 29, 0.98))'
                    : '#ffffff',
                  border: darkMode
                    ? '1px solid rgba(245, 158, 11, 0.35)'
                    : '1px solid rgba(245, 158, 11, 0.3)',
                  boxShadow: darkMode
                    ? '0 4px 16px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
                    : '0 4px 14px rgba(245, 158, 11, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05)',
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  userSelect: 'none'
                }}
                title={language === 'en' ? "Click to open in Document Interrogator" : "Klik untuk membuka di Document Interrogator"}
              >
                {/* Header Kartu: Icon Dokumen + Badges */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div
                      className="shrink-0 flex items-center justify-center rounded-xl transition-transform group-hover/doc:scale-105"
                      style={{
                        width: '32px',
                        height: '32px',
                        background: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.35)',
                        color: '#fbbf24'
                      }}
                    >
                      <FileText size={16} />
                    </div>
                    <span
                      className="text-[10.5px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md"
                      style={{
                        background: darkMode ? 'rgba(245, 158, 11, 0.12)' : 'rgba(245, 158, 11, 0.1)',
                        color: darkMode ? '#fbbf24' : '#b45309',
                        border: `1px solid ${darkMode ? 'rgba(245, 158, 11, 0.25)' : 'rgba(245, 158, 11, 0.2)'}`
                      }}
                    >
                      {categoryLabel}
                    </span>
                  </div>

                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{
                      background: darkMode ? '#2a2b30' : '#f1f5f9',
                      color: secondaryTextColor,
                      border: `1px solid ${darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`
                    }}
                  >
                    {pagesLabel}
                  </span>
                </div>

                {/* Judul Dokumen */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <h4
                    className="text-xs sm:text-[13px] font-bold leading-snug line-clamp-2 group-hover/doc:text-amber-400 transition-colors"
                    style={{ color: textColor }}
                  >
                    {docTitle}
                  </h4>
                  {nomorLabel && (
                    <span className="text-[10.5px] font-medium" style={{ color: secondaryTextColor }}>
                      {nomorLabel}
                    </span>
                  )}
                </div>

                {/* Footer Action Bar: Buka di Document Interrogator */}
                <div
                  className="flex items-center justify-between pt-2 mt-0.5 border-t text-[11px] font-semibold"
                  style={{
                    borderColor: darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
                    color: darkMode ? '#fbbf24' : '#b45309'
                  }}
                >
                  <span className="flex items-center gap-1.5">
                    <ExternalLink size={12} />
                    <span>Buka di Document Interrogator</span>
                  </span>
                  <span className="text-[10px] opacity-70 group-hover/doc:translate-x-0.5 transition-transform">
                    Lihat Dokumen →
                  </span>
                </div>
              </div>
            );
          }

          // ⚡ Konteks Mode Aktif (Websearch, Koding, Diagram, dll.)
          if (att.type === 'context_mode') {
            return (
              <div
                key={attIdx}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl border shadow-sm select-none"
                style={{
                  background: darkMode ? 'rgba(99, 102, 241, 0.14)' : 'rgba(99, 102, 241, 0.09)',
                  borderColor: darkMode ? 'rgba(99, 102, 241, 0.35)' : 'rgba(99, 102, 241, 0.25)',
                  color: darkMode ? '#a5b4fc' : '#4f46e5',
                  maxWidth: '260px'
                }}
              >
                {getModeIcon(att.mode)}
                <span className="text-xs font-semibold">{getModeLabel(att.mode, language)}</span>
              </div>
            );
          }

          const fileName = att.name || att.filename || `Lampiran ${attIdx + 1}`;
          const isImg = att.type?.startsWith('image/') || att.preview;
          const isPdf = att.type === 'application/pdf' || fileName.toLowerCase().endsWith('.pdf');

          if (isImg && att.preview) {
            return (
              <div
                key={attIdx}
                onClick={() => setPreviewImage && setPreviewImage(att.preview)}
                className="rounded-xl overflow-hidden border shadow-sm cursor-pointer hover:opacity-95 transition-opacity"
                style={{
                  width: '120px',
                  height: '120px',
                  borderColor: darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'
                }}
                title={language === 'en' ? "Click to enlarge image" : "Klik untuk memperbesar gambar"}
              >
                <img src={att.preview} alt={fileName} className="w-full h-full object-cover" />
              </div>
            );
          }

          return (
            <div
              key={attIdx}
              onClick={() => {
                if (isPdf) {
                  const rawPath = att.file_path || (att.filename ? `file_peraturan/${att.filename}` : null) || (att.name ? `uploads/${att.name}` : null);
                  const fileUrl = rawPath ? getUploadUrl(rawPath) : null;
                  if (fileUrl) {
                    useChatStore.getState().setSplitScreen(true, fileUrl);
                  }
                }
              }}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl border shadow-sm ${isPdf ? 'cursor-pointer hover:border-amber-400/50 transition-colors' : ''}`}
              style={{
                background: darkMode ? '#1e1e21' : '#f1f5f9',
                borderColor: darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                maxWidth: '240px'
              }}
              title={isPdf ? 'Klik untuk membuka di Document Interrogator' : fileName}
            >
              {isPdf ? <FileText size={16} className="text-red-400 shrink-0" /> : <ImageIcon size={16} className="text-blue-400 shrink-0" />}
              <span className="text-xs truncate flex-1" style={{ color: textColor }}>{fileName}</span>
              {isPdf && <ExternalLink size={12} className="text-amber-400/70 shrink-0" />}
            </div>
          );
        })}
      </div>
    );
  };

  // ── SISI KANAN: Pesan Anda Sendiri (Jam kirim selalu tampil di kanan + Tools Copy/Edit muncul saat hover) ──
  if (isMe) {
    return (
      <div
        className="flex flex-col items-end group"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          animation: 'fadeInUp 0.15s ease-out forwards',
          marginBottom: '28px',
          width: '100%'
        }}
      >
        <div className="relative max-w-[78%] sm:max-w-[70%] flex flex-col items-end">
          {renderAttachments()}

          {isEditing ? (
            /* ✏️ MODE INLINE EDITING PESAN */
            <div
              style={{
                width: '100%',
                minWidth: '280px',
                maxWidth: '560px',
                padding: '12px 14px',
                borderRadius: 18,
                background: darkMode ? '#2d2d31' : '#ffffff',
                border: `1px solid ${darkMode ? 'rgba(255,255,255,0.15)' : '#cbd5e1'}`,
                boxShadow: darkMode ? '0 4px 16px rgba(0,0,0,0.3)' : '0 4px 12px rgba(0,0,0,0.06)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}
            >
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleEditSubmit();
                  }
                  if (e.key === 'Escape') {
                    handleCancelEdit();
                  }
                }}
                rows={3}
                style={{
                  width: '100%',
                  background: 'transparent',
                  color: textColor,
                  border: 'none',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                  outline: 'none',
                  lineHeight: 1.5
                }}
                autoFocus
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: secondaryTextColor,
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    padding: '5px 12px',
                    borderRadius: '16px'
                  }}
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleEditSubmit}
                  disabled={!editValue.trim() || isSubmitting}
                  style={{
                    background: '#6366f1',
                    color: '#ffffff',
                    border: 'none',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: editValue.trim() && !isSubmitting ? 'pointer' : 'not-allowed',
                    padding: '5px 16px',
                    borderRadius: '16px',
                    opacity: editValue.trim() && !isSubmitting ? 1 : 0.5,
                    boxShadow: '0 2px 6px rgba(99, 102, 241, 0.3)'
                  }}
                >
                  Kirim
                </button>
              </div>
            </div>
          ) : (
            rawContent && (
              <div
                style={{
                  padding: '13px 18px',
                  borderRadius: 22,
                  background: darkMode ? '#3a3a3f' : '#f3f4f6',
                  color: darkMode ? '#e2e8f0' : '#1f2937',
                  boxShadow: '0 2px 8px rgba(99, 102, 241, 0.12)',
                  border: `1px solid ${darkMode ? '#47474d' : '#e2e8f0'}`,
                  fontSize: '14.5px',
                  lineHeight: 1.6,
                  wordBreak: 'break-word'
                }}
              >
                <div className={`prose ${darkMode ? 'prose-invert' : ''} prose-sm max-w-none text-[14.5px]`}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {rawContent}
                  </ReactMarkdown>
                </div>
              </div>
            )
          )}

          {/* 🛰️ FOOTER BAWAH BUBBLE: Jam Kirim Selalu Tampil + Tools Copy & Edit Muncul Saat Hover */}
          {!isEditing && rawContent && (
            <div
              style={{
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
                justifyContent: 'flex-end',
                marginRight: '4px',
                marginTop: '4px',
                height: '20px'
              }}
            >
              {/* Tools Copy & Edit (Muncul saat hover bubble, berada di kiri jam) */}
              <div
                style={{
                  display: 'flex',
                  gap: '3px',
                  alignItems: 'center',
                  opacity: isHovered || isCopied ? 1 : 0,
                  pointerEvents: isHovered || isCopied ? 'auto' : 'none',
                  transition: 'opacity 0.15s ease'
                }}
              >
                <button
                  type="button"
                  onClick={() => executeCopy(rawContent)}
                  title={language === 'en' ? "Copy message" : "Salin pesan"}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: isCopied ? '#10b981' : secondaryTextColor,
                    cursor: 'pointer',
                    display: 'flex',
                    padding: '2px',
                    borderRadius: '4px',
                    transition: 'color 0.15s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = darkMode ? '#e2e8f0' : '#1f2937';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = isCopied ? '#10b981' : secondaryTextColor;
                  }}
                >
                  {isCopied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                </button>
                {onApplyToDocument && (
                  <button
                    type="button"
                    onClick={async () => {
                      setIsNotedManual(true);
                      await onApplyToDocument(rawContent, senderName);
                      setTimeout(() => setIsNotedManual(false), 2500);
                    }}
                    title={language === 'en' ? "Add to team notes" : "Salin ke Catatan Tim"}
                    style={{
                      background: (isAutoNoted || isNotedManual) ? (darkMode ? 'rgba(20, 184, 166, 0.15)' : 'rgba(20, 184, 166, 0.12)') : 'transparent',
                      border: (isAutoNoted || isNotedManual) ? `1px solid ${darkMode ? 'rgba(20, 184, 166, 0.3)' : 'rgba(20, 184, 166, 0.25)'}` : 'none',
                      color: (isAutoNoted || isNotedManual) ? '#14b8a6' : secondaryTextColor,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: (isAutoNoted || isNotedManual) ? '2px 8px' : '2px 4px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 500,
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = '#14b8a6';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = (isAutoNoted || isNotedManual) ? '#14b8a6' : secondaryTextColor;
                    }}
                  >
                    <FileText size={12} className="text-teal-400" />
                    <span className="hidden sm:inline">
                      {isNotedManual 
                        ? (language === 'en' ? "Recorded!" : "Tercatat!") 
                        : isAutoNoted 
                        ? (language === 'en' ? "📌 Auto-Noted" : "📌 Dicatat Otomatis") 
                        : (language === 'en' ? "To Notes" : "Ke Catatan")}
                    </span>
                  </button>
                )}
                {onEditMessage && (
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(true);
                      setEditValue(rawContent);
                    }}
                    title={language === 'en' ? "Edit message" : "Edit pesan"}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: secondaryTextColor,
                      cursor: 'pointer',
                      display: 'flex',
                      padding: '2px',
                      borderRadius: '4px',
                      transition: 'color 0.15s'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = darkMode ? '#e2e8f0' : '#1f2937';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = secondaryTextColor;
                    }}
                  >
                    <Pencil size={13} />
                  </button>
                )}
              </div>

              {/* Jam kirim pesan selalu tampil di paling pojok kanan */}
              <span
                className="text-[11px] font-medium select-none"
                style={{ color: secondaryTextColor }}
              >
                {timeStr}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── SISI KIRI: Pesan Rekan Kerja Lain (Foto Bulat, Sejajar dengan CAKRA & Warna Unik per Rekan) ──
  return (
    <div
      className="flex flex-col items-start w-full group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        animation: 'fadeInUp 0.15s ease-out forwards',
        marginBottom: '28px'
      }}
    >
      {/* ── HEADER USER LAIN (Foto Profil Bulat 26x26 & Sejajar Presisi dengan CAKRA) ── */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}>
          <CollabAvatar
            npp={senderNpp}
            name={senderName}
            photoUrl={photoUrl}
            size="w-[26px] h-[26px]"
            className="!w-[26px] !h-[26px] !rounded-full overflow-hidden text-[10px]"
            title={`${senderName} (${division})`}
          />
        </div>

        <div style={{ marginLeft: 8, display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: memberPalette.nameColor }}>
            {senderName}
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-full border font-medium"
            style={{
              background: memberPalette.badgeBg,
              borderColor: memberPalette.badgeBorder,
              color: memberPalette.badgeText
            }}
          >
            {division}
          </span>
          <span className="text-[11px]" style={{ color: secondaryTextColor }}>
            {timeStr}
          </span>
        </div>
      </div>

      {/* ── BUBBLE REKAN LAIN (Warna Berbeda Sesuai Anggota & Padding Indentasi Sejajar CAKRA) ── */}
      <div style={{ paddingLeft: '34px', maxWidth: '85%' }}>
        {renderAttachments()}

        {rawContent && (
          <div
            style={{
              padding: '12px 18px',
              borderRadius: 20,
              background: darkMode ? memberPalette.bubbleBgDark : memberPalette.bubbleBgLight,
              border: `1px solid ${darkMode ? memberPalette.bubbleBorderDark : memberPalette.bubbleBorderLight}`,
              color: textColor,
              fontSize: '14.5px',
              lineHeight: 1.6,
              wordBreak: 'break-word',
              boxShadow: darkMode ? '0 2px 10px rgba(0, 0, 0, 0.2)' : '0 2px 6px rgba(0, 0, 0, 0.03)'
            }}
          >
            <div className={`prose ${darkMode ? 'prose-invert' : ''} prose-sm max-w-none text-[14.5px]`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {rawContent}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* Action Copy Ringan di Bawah Bubble Rekan (Hanya muncul saat hover) */}
        {rawContent && (
          <div
            style={{
              display: 'flex',
              gap: '4px',
              alignItems: 'center',
              marginTop: '4px',
              marginLeft: '4px',
              opacity: isHovered || isCopied ? 1 : 0,
              pointerEvents: isHovered || isCopied ? 'auto' : 'none',
              transition: 'opacity 0.15s ease'
            }}
          >
            <button
              type="button"
              onClick={() => executeCopy(rawContent)}
              title={language === 'en' ? "Copy text" : "Salin teks"}
              style={{
                background: 'transparent',
                border: 'none',
                color: isCopied ? '#10b981' : secondaryTextColor,
                cursor: 'pointer',
                display: 'flex',
                padding: '2px 4px',
                borderRadius: '4px'
              }}
            >
              {isCopied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            </button>
            {onApplyToDocument && (
              <button
                type="button"
                onClick={async () => {
                  setIsNotedManual(true);
                  await onApplyToDocument(rawContent, senderName);
                  setTimeout(() => setIsNotedManual(false), 2500);
                }}
                title={language === 'en' ? "Add to team notes" : "Salin ke Catatan Tim"}
                style={{
                  background: (isAutoNoted || isNotedManual) ? (darkMode ? 'rgba(20, 184, 166, 0.15)' : 'rgba(20, 184, 166, 0.12)') : 'transparent',
                  border: (isAutoNoted || isNotedManual) ? `1px solid ${darkMode ? 'rgba(20, 184, 166, 0.3)' : 'rgba(20, 184, 166, 0.25)'}` : 'none',
                  color: (isAutoNoted || isNotedManual) ? '#14b8a6' : secondaryTextColor,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: (isAutoNoted || isNotedManual) ? '2px 8px' : '2px 4px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontWeight: 500,
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#14b8a6';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = (isAutoNoted || isNotedManual) ? '#14b8a6' : secondaryTextColor;
                }}
              >
                <FileText size={12} className="text-teal-400" />
                <span className="hidden sm:inline">
                  {isNotedManual 
                    ? (language === 'en' ? "Recorded!" : "Tercatat!") 
                    : isAutoNoted 
                    ? (language === 'en' ? "📌 Auto-Noted" : "📌 Dicatat Otomatis") 
                    : (language === 'en' ? "To Notes" : "Ke Catatan")}
                </span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

export default CollabUserBubble;
