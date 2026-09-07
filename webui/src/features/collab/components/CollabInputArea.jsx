import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, AtSign, Sparkles } from 'lucide-react';

const CollabInputArea = ({ onSendMessage, members = [], isSending, darkMode = true, theme }) => {
  const [text, setText] = useState('');
  const [mentionQuery, setMentionQuery] = useState(null); // null if not mentioning, or string after @
  const [mentionIndex, setMentionIndex] = useState(0);
  const textareaRef = useRef(null);

  const pageBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const inputBg = darkMode ? '#1e1e20' : '#f3f4f6';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  // Daftar opsi mention: Cakra + anggota tim
  const mentionOptions = [
    {
      id: 'cakra',
      name: 'cakra',
      displayName: 'CAKRA (AI Teammate)',
      description: 'Panggil CAKRA untuk klarifikasi regulasi atau draf SE',
      isAi: true
    },
    ...members.map((m) => ({
      id: m.npp,
      name: m.name.replace(/\s+/g, ''),
      displayName: `${m.name} (${m.divisi || 'Pindad'})`,
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

  // Handle perubahan text dan deteksi '@'
  const handleTextChange = (e) => {
    const val = e.target.value;
    setText(val);

    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf('@');

    if (lastAt !== -1) {
      const query = textBeforeCursor.slice(lastAt + 1);
      // Hanya aktif jika query tidak mengandung spasi
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
    onSendMessage(text.trim());
    setText('');
    setMentionQuery(null);
  };

  return (
    <div
      className="relative p-3 sm:p-4 border-t"
      style={{
        background: pageBg,
        borderColor: borderColor
      }}
    >
      {/* Pop-up Mention Suggestions */}
      {mentionQuery !== null && filteredMentions.length > 0 && (
        <div
          className="absolute bottom-full left-4 right-4 sm:left-6 sm:right-auto sm:w-80 mb-2 rounded-xl border shadow-2xl overflow-hidden z-50"
          style={{
            background: darkMode ? '#1c1c1f' : '#ffffff',
            borderColor: borderColor
          }}
        >
          <div
            className="px-3 py-2 border-b text-[11px] font-semibold flex items-center gap-1.5"
            style={{
              background: pageBg,
              borderColor: borderColor,
              color: secondaryTextColor
            }}
          >
            <AtSign size={12} className="text-teal-400" />
            <span>Sebut Anggota Tim atau CAKRA</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            {filteredMentions.map((opt, idx) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => insertMention(opt)}
                className={`w-full text-left px-3 py-2 flex items-center gap-2.5 transition-colors ${
                  idx === mentionIndex ? 'bg-teal-500/20 text-white' : 'hover:bg-white/5'
                }`}
                style={{ color: textColor }}
              >
                {opt.isAi ? (
                  <div className="w-6 h-6 rounded-md bg-teal-500/20 text-teal-300 border border-teal-500/40 flex items-center justify-center shrink-0">
                    <Bot size={14} />
                  </div>
                ) : (
                  <div
                    className="w-6 h-6 rounded-md border flex items-center justify-center text-xs font-bold shrink-0"
                    style={{
                      background: inputBg,
                      borderColor: borderColor,
                      color: textColor
                    }}
                  >
                    {opt.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium truncate flex items-center gap-1.5">
                    <span>{opt.displayName}</span>
                    {opt.isAi && (
                      <span className="text-[9px] px-1 rounded bg-teal-950 text-teal-400 border border-teal-800">
                        AI
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] truncate" style={{ color: secondaryTextColor }}>{opt.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Box */}
      <div
        className="flex items-end gap-2 border rounded-2xl px-3.5 py-2.5 transition-all shadow-inner focus-within:border-teal-500/60 focus-within:ring-1 focus-within:ring-teal-500/30"
        style={{
          background: inputBg,
          borderColor: borderColor
        }}
      >
        <button
          type="button"
          onClick={() => {
            setText((prev) => prev + '@cakra ');
            if (textareaRef.current) textareaRef.current.focus();
          }}
          className="p-1.5 text-teal-400 hover:text-teal-300 rounded-lg hover:bg-teal-500/10 transition-colors shrink-0 mb-0.5"
          title="Panggil @cakra"
        >
          <Bot size={18} />
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder="Ketik pesan diskusi... (Gunakan @cakra untuk meminta tanggapan AI)"
          rows={1}
          className="flex-1 bg-transparent border-0 text-sm focus:outline-none focus:ring-0 resize-none max-h-32 py-1 leading-relaxed"
          style={{
            minHeight: '24px',
            color: textColor
          }}
        />

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!text.trim() || isSending}
          className={`p-2 rounded-lg transition-all shrink-0 mb-0.5 ${
            text.trim() && !isSending
              ? 'bg-gradient-to-r from-teal-500 to-emerald-600 text-white shadow-md shadow-teal-950/40 hover:brightness-110'
              : 'opacity-50 cursor-not-allowed border'
          }`}
          style={(!text.trim() || isSending) ? { background: pageBg, borderColor: borderColor, color: secondaryTextColor } : {}}
          title="Kirim pesan"
        >
          <Send size={16} />
        </button>
      </div>

      <div className="flex items-center justify-between mt-1.5 px-1 text-[11px]" style={{ color: secondaryTextColor }}>
        <span>Tekan <b>Enter</b> untuk kirim, <b>Shift+Enter</b> untuk baris baru</span>
        <span className="flex items-center gap-1 text-teal-500/80">
          <Sparkles size={11} />
          CAKRA menyimak otomatis
        </span>
      </div>
    </div>
  );
};

export default CollabInputArea;
