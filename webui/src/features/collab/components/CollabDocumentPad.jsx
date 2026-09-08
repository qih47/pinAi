import React, { useState, useEffect, useRef } from 'react';
import { 
  FileText, 
  Save, 
  Check, 
  Copy, 
  Download, 
  X, 
  Sparkles, 
  RefreshCw, 
  Edit3, 
  Eye,
  Trash2,
  Loader2 
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { translations } from '../../../utils/translations';

const DISCUSSION_TEMPLATE = `# Catatan Diskusi Tim
**Topik:** [Topik Bahasan]  
**Tanggal:** [Hari, DD Bulan YYYY]  

---

## 1. Poin Pembahasan
- Pembahasan mengenai penyesuaian klausul aturan kerja
- Evaluasi draf dan masukan dari anggota tim

## 2. Kesimpulan & Keputusan Bersama
- **Keputusan 1:** Menyetujui revisi pada pasal operasional
- **Keputusan 2:** Meminta verifikasi rujukan regulasi dari CAKRA AI

## 3. Tindak Lanjut (Action Items)
- [ ] Finalisasi draf naskah (PIC: Mas Hendra)
- [ ] Verifikasi kepatuhan PKB & SE (PIC: Qisthi)
`;

const formatDocContent = (text) => {
  if (!text) return '';
  let res = text;
  // Perbaiki simbol LaTeX arrow mentah atau terpotong ($ ightarrow$ atau $\rightarrow$)
  res = res.replace(/\$\s*\\?ightarrow\s*\$/gi, ' → ');
  res = res.replace(/\$\s*\\rightarrow\s*\$/gi, ' → ');
  res = res.replace(/\\rightarrow\b/gi, ' → ');
  res = res.replace(/\$\\([a-zA-Z]+)\$/g, (_, sym) => {
    const map = { rightarrow: '→', leftarrow: '←', Rightarrow: '⇒', times: '×', leq: '≤', geq: '≥' };
    return map[sym] || `\\${sym}`;
  });

  // Perbaiki format aneh seperti ". 5." atau "```\n. 6."
  res = res.replace(/(?:^|\n|\s)\.\s*(\d+\.\s+)/g, '\n\n$1');

  // Format poin bernomor (1., 2., 3., dst) yang ditulis menyatu dalam paragraf
  // otomatis dipecah menjadi baris list markdown baru
  // Contoh: "...meliputi: 1. " -> "...meliputi:\n\n1. "
  res = res.replace(/([:：])\s*(1\.\s+)/g, '$1\n\n$2');

  // Pecah butir berikutnya (2., 3., dst) setelah tanda baca penutup atau blok kode
  // Contoh: "... /layouts ). 2. Coding..." -> "... /layouts ).\n\n2. Coding..."
  // Contoh: "... Prettier. 4. Struktur..." -> "... Prettier.\n\n4. Struktur..."
  res = res.replace(/([.!?;)]|```)\s*(\d+\.\s+[A-Za-z0-9_*])/g, '$1\n\n$2');

  return res;
};

const CollabDocumentPad = ({
  documentContent,
  onSave,
  onSummarize,
  onClose,
  isSaving,
  roomTopic,
  darkMode = true,
  theme,
  language = 'id'
}) => {
  const t = translations[language]?.collab || translations.id.collab;
  const [content, setContent] = useState(documentContent || '');
  const [isDirty, setIsDirty] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  // Default to preview mode if there is content, otherwise edit mode
  const [viewMode, setViewMode] = useState(documentContent && documentContent.trim() ? 'preview' : 'edit');

  const pageBg = theme?.mainBg || (darkMode ? '#131315' : '#ffffff');
  const editorBg = theme?.mainBg || (darkMode ? '#131315' : '#ffffff');
  const textColor = theme?.textColor || (darkMode ? '#e4e4e7' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#a1a1aa' : '#6b7280');
  
  // Pembatas halus & seamless tanpa garis putih tebal/mencolok
  const subtleBorder = darkMode ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.08)';

  useEffect(() => {
    setContent(documentContent || '');
    setIsDirty(false);
    if (documentContent && documentContent.trim() && viewMode !== 'edit') {
      setViewMode('preview');
    }
  }, [documentContent]);

  const handleChange = (e) => {
    setContent(e.target.value);
    setIsDirty(true);
  };

  const handleSave = async () => {
    if (onSave) {
      await onSave(content);
      setIsDirty(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleInsertTemplate = () => {
    if (content.trim() && !window.confirm(t.docPadConfirmTemplate || 'Gunakan format Template Notulen & Poin Diskusi?')) {
      return;
    }
    setContent(DISCUSSION_TEMPLATE);
    setIsDirty(true);
    setViewMode('preview');
  };

  // Kosongkan seluruh catatan
  const handleClear = () => {
    if (!content.trim()) return;
    if (window.confirm(t.docPadConfirmClear || 'Kosongkan seluruh isi Catatan Tim untuk memulai draf baru?')) {
      setContent('');
      setIsDirty(true);
      if (onSave) onSave('');
    }
  };

  // Rangkum otomatis obrolan menjadi Notulensi Resmi via CAKRA AI
  const handleSummarize = async () => {
    if (!onSummarize) return;
    try {
      setIsSummarizing(true);
      await onSummarize();
      setViewMode('preview');
    } catch (err) {
      console.error('Failed to summarize:', err);
    } finally {
      setIsSummarizing(false);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Catatan_Diskusi_Tim_${Date.now()}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div
      className="h-full flex flex-col shadow-2xl overflow-hidden select-text"
      style={{
        background: editorBg,
        color: textColor
      }}
    >
      {/* Header Pad */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: pageBg,
          borderBottom: `1px solid ${subtleBorder}`
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-teal-500/15 text-teal-400 border border-teal-500/25 shrink-0">
            <FileText size={16} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold flex items-center gap-2 truncate" style={{ color: textColor }}>
              <span>{t.docPadTitle}</span>
              {isDirty && (
                <span className="h-2 w-2 rounded-full bg-amber-400 shrink-0" title={t.docPadUnsaved} />
              )}
            </h3>
            <p className="text-[11px] truncate" style={{ color: secondaryTextColor }}>
              {t.docPadSubtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              isDirty
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/40'
                : 'opacity-40 cursor-not-allowed bg-white/[0.03] text-zinc-400'
            }`}
          >
            {isSaving ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span>{t.docPadSaving}</span>
              </>
            ) : (
              <>
                <Save size={13} />
                <span>{t.docPadSave}</span>
              </>
            )}
          </button>

          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-zinc-400 hover:text-zinc-200"
              title={t.docPadClose}
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div
        className="px-4 py-2 flex items-center justify-between text-xs flex-wrap gap-2"
        style={{
          background: pageBg,
          borderBottom: `1px solid ${subtleBorder}`,
          color: secondaryTextColor
        }}
      >
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Switch Edit / Preview Mode */}
          <div className="flex items-center p-0.5 rounded-lg bg-black/30 border border-white/[0.06]">
            <button
              type="button"
              onClick={() => setViewMode('edit')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                viewMode === 'edit'
                  ? 'bg-teal-500/20 text-teal-300 shadow-sm border border-teal-500/30'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Edit teks catatan secara langsung"
            >
              <Edit3 size={12} />
              <span>{t.docPadEdit}</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('preview')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                viewMode === 'preview'
                  ? 'bg-teal-500/20 text-teal-300 shadow-sm border border-teal-500/30'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Lihat hasil format Markdown"
            >
              <Eye size={12} />
              <span>{t.docPadPreview}</span>
            </button>
          </div>

          {/* Tombol Buat Notulensi Otomatis via AI */}
          {onSummarize && (
            <button
              type="button"
              onClick={handleSummarize}
              disabled={isSummarizing}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-teal-500/30 bg-teal-500/15 hover:bg-teal-500/25 text-teal-300 transition-all text-[11px] font-medium disabled:opacity-50 shadow-sm"
              title="Rangkum seluruh obrolan tim di ruangan ini menjadi Notulensi Resmi via CAKRA AI"
            >
              {isSummarizing ? (
                <Loader2 size={12} className="animate-spin text-teal-400" />
              ) : (
                <Sparkles size={12} className="text-teal-400" />
              )}
              <span>{isSummarizing ? t.docPadAiSummarizing : t.docPadAiSummarize}</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleInsertTemplate}
            className="flex items-center gap-1 px-2 py-1 rounded-lg border border-white/10 hover:bg-white/5 text-zinc-300 transition-colors text-[11px] font-medium"
            title="Gunakan format template notulen standar"
          >
            <span>{t.docPadTemplate}</span>
          </button>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-white/5 transition-colors text-zinc-300"
            title="Salin seluruh isi catatan"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            <span className="text-[11px]">{copied ? (t.copied || 'Tersalin') : t.docPadCopy}</span>
          </button>

          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-white/5 transition-colors text-zinc-300"
            title="Unduh catatan (.md)"
          >
            <Download size={13} />
            <span className="text-[11px]">{t.docPadDownload}</span>
          </button>

          {/* Kosongkan Catatan */}
          {content.trim() && (
            <button
              type="button"
              onClick={handleClear}
              className="flex items-center gap-1 px-1.5 py-1 rounded-lg hover:bg-rose-500/10 text-zinc-400 hover:text-rose-400 transition-colors"
              title="Kosongkan seluruh isi catatan untuk membuat draf baru"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Konten Catatan: Edit Mode vs Preview Mode */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden" style={{ background: editorBg }}>
        {viewMode === 'edit' ? (
          <div className="flex-1 p-4 flex flex-col min-h-0">
            <textarea
              value={content}
              onChange={handleChange}
              placeholder={t.docPadPlaceholder}
              className="w-full h-full resize-none bg-transparent border-0 text-sm font-sans leading-relaxed focus:outline-none focus:ring-0 custom-scrollbar placeholder:text-zinc-600"
              style={{ color: textColor }}
              spellCheck={false}
              autoFocus
            />
          </div>
        ) : (
          <div 
            className="flex-1 p-5 overflow-y-auto custom-scrollbar select-text text-sm leading-relaxed"
            onDoubleClick={() => setViewMode('edit')}
            title="Klik ganda di area ini untuk beralih ke mode edit"
          >
            {content.trim() ? (
              <div className="prose prose-invert max-w-none space-y-3">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ node, ...props }) => (
                      <h1 className="text-lg font-bold text-teal-400 pb-2 mb-3 border-b border-white/[0.08]" {...props} />
                    ),
                    h2: ({ node, ...props }) => (
                      <h2 className="text-base font-semibold text-zinc-100 mt-4 mb-2 flex items-center gap-2" {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3 className="text-sm font-semibold text-zinc-200 mt-3 mb-1" {...props} />
                    ),
                    p: ({ node, ...props }) => (
                      <p className="mb-2.5 text-zinc-300 leading-relaxed text-sm" {...props} />
                    ),
                    ul: ({ node, ...props }) => (
                      <ul className="list-disc pl-5 my-2.5 space-y-1.5 text-zinc-300 text-sm marker:text-teal-400" {...props} />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol className="list-decimal pl-5 my-2.5 space-y-2 text-zinc-300 text-sm marker:text-teal-400 marker:font-semibold" {...props} />
                    ),
                    li: ({ node, ...props }) => (
                      <li className="text-zinc-300 leading-relaxed pl-1" {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                      <strong className="font-semibold text-teal-300" {...props} />
                    ),
                    em: ({ node, ...props }) => (
                      <em className="italic text-zinc-200" {...props} />
                    ),
                    pre: ({ children }) => <>{children}</>,
                    code: ({ node, inline, className, children, ...props }) => {
                      const match = /language-(\w+)/.exec(className || '');
                      const codeStr = String(children || '').replace(/\n$/, '');
                      const isMultiLine = codeStr.includes('\n');
                      const isBlock = !inline && (Boolean(match) || isMultiLine);

                      if (isBlock) {
                        return (
                          <div className="my-2.5 rounded-xl bg-black/60 border border-white/[0.08] overflow-hidden shadow-inner">
                            {match && (
                              <div className="px-3.5 py-1.5 bg-white/[0.04] border-b border-white/[0.06] text-[11px] font-mono text-teal-400 font-semibold uppercase tracking-wider">
                                {match[1]}
                              </div>
                            )}
                            <pre className="p-3.5 overflow-x-auto text-xs font-mono text-zinc-200 leading-relaxed custom-scrollbar">
                              <code>{codeStr}</code>
                            </pre>
                          </div>
                        );
                      }

                      return (
                        <code
                          className="px-1.5 py-0.5 mx-0.5 rounded-md bg-teal-500/15 text-teal-300 font-mono text-[12px] border border-teal-500/25 inline-block align-baseline font-medium"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    blockquote: ({ node, ...props }) => (
                      <blockquote className="pl-3.5 border-l-2 border-teal-500/50 italic text-zinc-400 my-2.5 bg-teal-500/[0.03] py-1 rounded-r" {...props} />
                    ),
                    input: ({ node, ...props }) => (
                      <input type="checkbox" className="mr-2 rounded border-white/20 text-teal-500 pointer-events-none accent-teal-500" {...props} />
                    ),
                    hr: () => <hr className="my-4 border-white/[0.08]" />,
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto my-3 rounded-lg border border-white/[0.06]">
                        <table className="min-w-full text-xs divide-y divide-white/[0.06]" {...props} />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th className="px-3 py-2 text-left font-semibold text-zinc-200 bg-white/[0.04]" {...props} />
                    ),
                    td: ({ node, ...props }) => (
                      <td className="px-3 py-2 text-zinc-300 border-t border-white/[0.04]" {...props} />
                    )
                  }}
                >
                  {formatDocContent(content)}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-500">
                <FileText size={36} className="mb-2.5 opacity-25 text-teal-400" />
                <p className="text-xs text-zinc-400">{t.docPadEmpty}</p>
                <button
                  onClick={() => setViewMode('edit')}
                  className="mt-3 px-3.5 py-1.5 rounded-lg bg-teal-500/10 text-teal-300 hover:bg-teal-500/20 text-xs border border-teal-500/30 transition-all"
                >
                  {t.docPadStartWriting}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div
        className="px-4 py-2 text-[11px] flex items-center justify-between"
        style={{
          background: pageBg,
          borderTop: `1px solid ${subtleBorder}`,
          color: secondaryTextColor
        }}
      >
        <div className="flex items-center gap-2">
          <span>{content.split(/\s+/).filter(Boolean).length} {t.docPadWords}</span>
          {viewMode === 'preview' && content.trim() && (
            <span className="text-[10px] text-zinc-500 hidden sm:inline">{t.docPadDoubleClick}</span>
          )}
        </div>
        <span className={isDirty ? 'text-amber-400 font-medium' : 'text-zinc-500'}>
          {isDirty ? t.docPadUnsavedStatus : t.docPadSavedStatus}
        </span>
      </div>
    </div>
  );
};

export default CollabDocumentPad;
