import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ArrowUp, Bot, Sparkles, AtSign, Paperclip } from 'lucide-react';
import cakraLogo from '../../../assets/cakra.png';

const CollabInputArea = ({
  onSendMessage,
  onTypingChange,
  members = [],
  isSending = false,
  darkMode = true,
  theme
}) => {
  const [text, setText] = useState('');
  const [mentionQuery, setMentionQuery] = useState(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const textareaRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  const borderColor = theme?.borderColor || (darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)');
  const inputBg = darkMode ? '#1e1e21' : '#ffffff';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 160);
      textareaRef.current.style.height = `${Math.max(newHeight, 24)}px`;
    }
  }, [text]);

  // Handle typing broadcast throttled
  const notifyTyping = useCallback((isTyping) => {
    if (onTypingChange) {
      onTypingChange(isTyping);
    }
  }, [onTypingChange]);

  // Daftar opsi mention: CAKRA + anggota tim
  const mentionOptions = [
    {
      id: 'cakra',
      name: 'cakra',
      displayName: 'CAKRA (AI Teammate)',
      description: 'Panggil CAKRA untuk membantu diskusi tim',
      isAi: true
    },
    ...members.map((m) => ({
      id: m.npp,
      name: (m.name || m.npp).replace(/\s+/g, ''),
      displayName: `${m.name} (${m.divisi || 'PT Pindad'})`,
      description: `NPP: ${m.npp}`,
      isAi: false
    }))
  ];

  const filteredMentions = mentionQuery !== null
    ? mentionOptions.filter((opt) =>
        opt.name.toLowerCase().includes(mentionQuery.toLowerCase()) ||
        opt.displayName.toLowerCase().includes(mentionQuery.toLowerCase())
      )
    : [];

  const handleTextChange = (e) => {
    const val = e.target.value;
    setText(val);

    // Kirim sinyal typing
    if (val.trim()) {
      notifyTyping(true);
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = setTimeout(() => {
        notifyTyping(false);
      }, 2500);
    } else {
      notifyTyping(false);
    }

    // Deteksi karakter '@'
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf('@');

    if (lastAt !== -1) {
      const query = textBeforeCursor.slice(lastAt + 1);
      if (!/\s/.test(query)) {
        setMentionQuery(query);
        setMentionIndex(0);
        return;
      }
    }
    setMentionQuery(null);
  };

  const insertMention = (opt) => {
    if (!textareaRef.current) return;
    const cursorPos = textareaRef.current.selectionStart;
    const textBeforeCursor = text.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf('@');
    const textAfterCursor = text.slice(cursorPos);

    const mentionTag = `@${opt.name} `;
    const newText = text.slice(0, lastAt) + mentionTag + textAfterCursor;
    setText(newText);
    setMentionQuery(null);

    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const nextPos = lastAt + mentionTag.length;
        textareaRef.current.setSelectionRange(nextPos, nextPos);
      }
    }, 10);
  };

  const handleKeyDown = (e) => {
    if (mentionQuery !== null && filteredMentions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((prev) => (prev + 1) % filteredMentions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((prev) => (prev - 1 + filteredMentions.length) % filteredMentions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(filteredMentions[mentionIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setMentionQuery(null);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!text.trim() || isSending) return;
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    notifyTyping(false);
    onSendMessage(text.trim());
    setText('');
    setMentionQuery(null);
  };

  const quickMentionCakra = () => {
    if (text.includes('@cakra')) return;
    const separator = text.length > 0 && !text.endsWith(' ') ? ' ' : '';
    setText((prev) => `${prev}${separator}@cakra `);
    textareaRef.current?.focus();
  };

  return (
    <div className="w-full shrink-0 px-3 sm:px-6 pb-4 pt-1 flex flex-col items-center">
      {/* ── Wadah Terpusat Maksimal 816px (Identik dengan ChatInputArea Utama) ── */}
      <div
        className="w-full relative flex flex-col"
        style={{
          maxWidth: '816px',
          boxSizing: 'border-box'
        }}
      >
        {/* Pop-up Mention Suggestions */}
        {mentionQuery !== null && filteredMentions.length > 0 && (
          <div
            className="absolute bottom-full left-4 right-4 sm:left-6 sm:right-auto sm:w-80 mb-2 rounded-2xl border shadow-2xl overflow-hidden z-50 animate-fadeInUp"
            style={{
              background: darkMode ? '#1b1b1e' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div
              className="px-3.5 py-2 border-b text-[11px] font-semibold flex items-center gap-1.5"
              style={{
                background: darkMode ? '#151518' : '#f8fafc',
                borderColor: borderColor,
                color: secondaryTextColor
              }}
            >
              <AtSign size={12} className="text-teal-400" />
              <span>Pilih Anggota Tim atau CAKRA</span>
            </div>
            <div className="max-h-48 overflow-y-auto py-1 custom-scrollbar">
              {filteredMentions.map((opt, idx) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => insertMention(opt)}
                  className={`w-full text-left px-3.5 py-2 flex items-center gap-2.5 transition-colors ${
                    idx === mentionIndex
                      ? 'bg-teal-500/20 text-teal-300'
                      : 'hover:bg-white/5'
                  }`}
                  style={{ color: textColor }}
                >
                  {opt.isAi ? (
                    <div className="w-6 h-6 rounded-lg bg-teal-500/10 flex items-center justify-center p-0.5 shrink-0 border border-teal-500/20">
                      <img src={cakraLogo} alt="CAKRA" className="w-full h-full object-contain" />
                    </div>
                  ) : (
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 border border-white/10 bg-gradient-to-br from-teal-600 to-emerald-700 text-white"
                    >
                      {opt.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold truncate flex items-center gap-1.5">
                      <span>{opt.displayName}</span>
                      {opt.isAi && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-teal-950 text-teal-300 border border-teal-700/60 font-medium">
                          AI
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] truncate" style={{ color: secondaryTextColor }}>
                      {opt.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Kapsul Melayang Elevated Input (Kloning Bentuk ChatInputArea Utama) */}
        <div
          className="w-full rounded-3xl p-2 sm:p-2.5 transition-all flex flex-col shadow-xl"
          style={{
            background: inputBg,
            border: `1px solid ${borderColor}`,
            boxShadow: darkMode
              ? '0 8px 30px rgba(0, 0, 0, 0.35)'
              : '0 8px 24px rgba(0, 0, 0, 0.06)'
          }}
        >
          <div className="flex items-end gap-2 px-2">
            {/* Tombol Mention Cepat @cakra */}
            <button
              type="button"
              onClick={quickMentionCakra}
              className="mb-1 px-2.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all border shrink-0"
              style={{
                background: text.includes('@cakra') ? 'rgba(20, 184, 166, 0.15)' : 'transparent',
                borderColor: text.includes('@cakra') ? 'rgba(20, 184, 166, 0.4)' : borderColor,
                color: text.includes('@cakra') ? '#2dd4bf' : secondaryTextColor
              }}
              title="Panggil CAKRA AI Teammate"
            >
              <img src={cakraLogo} alt="CAKRA" className="w-3.5 h-3.5 object-contain" />
              <span>@cakra</span>
            </button>

            {/* Textarea Auto-Expanding */}
            <textarea
              ref={textareaRef}
              value={text}
              onChange={handleTextChange}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Ketik pesan diskusi... (Gunakan @cakra untuk bantuan AI)"
              className="flex-1 bg-transparent border-0 outline-none resize-none py-1.5 px-1 text-[14px] leading-relaxed custom-scrollbar placeholder:text-neutral-500"
              style={{
                color: textColor,
                maxHeight: '160px'
              }}
            />

            {/* Tombol Kirim (Send Button) */}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!text.trim() || isSending}
              className={`mb-0.5 w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-all ${
                text.trim() && !isSending
                  ? 'bg-teal-600 hover:bg-teal-500 text-white shadow-md shadow-teal-600/30'
                  : 'bg-neutral-800/40 text-neutral-500 cursor-not-allowed'
              }`}
              title="Kirim pesan (Enter)"
            >
              <ArrowUp size={18} strokeWidth={2.5} />
            </button>
          </div>
        </div>

        {/* Footer Info Keyboard Shortcut Tipis Bawah */}
        <div className="flex items-center justify-between px-3 mt-1.5 text-[11px]" style={{ color: secondaryTextColor }}>
          <span>Tekan <strong>Enter</strong> untuk kirim, <strong>Shift+Enter</strong> untuk baris baru</span>
          <span className="flex items-center gap-1 opacity-75 text-[10px]">
            <Sparkles size={10} className="text-teal-400" />
            CAKRA menyimak diskusi
          </span>
        </div>
      </div>
    </div>
  );
};

export default CollabInputArea;
