import React, { useState, useEffect, useRef } from 'react';
import { FileText, Save, Check, Copy, Download, X, Sparkles, RefreshCw } from 'lucide-react';

const SE_TEMPLATE = `# SURAT EDARAN DIREKSI PT PINDAD
Nomor: SE /     /       / 2026

TENTANG
[PERIHAL SURAT EDARAN]

A. LATAR BELAKANG
1. ...
2. ...

B. DASAR HUKUM / MENGINGAT
1. Undang-Undang Nomor 19 Tahun 2003 tentang Badan Usaha Milik Negara;
2. Perjanjian Kerja Bersama (PKB) PT Pindad yang berlaku;
3. Surat Keputusan Direksi PT Pindad Nomor ...

C. KETENTUAN DAN PETUNJUK PELAKSANAAN
1. ...
2. ...

D. KETENTUAN PENUTUP
Surat Edaran ini berlaku sejak tanggal ditetapkan dengan ketentuan apabila di kemudian hari terdapat kekeliruan, akan diadakan perbaikan sebagaimana mestinya.

Ditetapkan di : Bandung
Pada tanggal  : 

DIREKSI PT PINDAD
`;

const CollabDocumentPad = ({
  documentContent,
  onSave,
  onClose,
  isSaving,
  roomTopic,
  darkMode = true,
  theme
}) => {
  const [content, setContent] = useState(documentContent || '');
  const [isDirty, setIsDirty] = useState(false);
  const [copied, setCopied] = useState(false);

  const pageBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const editorBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const buttonBg = darkMode ? '#1e1e20' : '#f3f4f6';

  useEffect(() => {
    setContent(documentContent || '');
    setIsDirty(false);
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
    if (content.trim() && !window.confirm('Timpa isi draf saat ini dengan Template Resmi Surat Edaran?')) {
      return;
    }
    setContent(SE_TEMPLATE);
    setIsDirty(true);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Draf_Dokumen_Tim_${Date.now()}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div
      className="h-full flex flex-col border-l shadow-2xl"
      style={{
        background: editorBg,
        borderColor: borderColor,
        color: textColor
      }}
    >
      {/* Header Pad */}
      <div
        className="p-4 border-b flex items-center justify-between"
        style={{
          background: pageBg,
          borderColor: borderColor
        }}
      >
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30">
            <FileText size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: textColor }}>
              Document Pad
              {isDirty && (
                <span className="h-2 w-2 rounded-full bg-amber-400" title="Ada perubahan belum disimpan" />
              )}
            </h3>
            <p className="text-[11px]" style={{ color: secondaryTextColor }}>Draf kolaboratif tim & formulasi regulasi</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              isDirty
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/40'
                : 'opacity-50 cursor-not-allowed border'
            }`}
            style={!isDirty ? { borderColor: borderColor, color: secondaryTextColor } : {}}
          >
            {isSaving ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span>Menyimpan...</span>
              </>
            ) : (
              <>
                <Save size={13} />
                <span>Simpan</span>
              </>
            )}
          </button>

          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              style={{ color: secondaryTextColor }}
              title="Tutup Panel Dokumen"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div
        className="px-4 py-2 border-b flex items-center justify-between text-xs flex-wrap gap-2"
        style={{
          background: pageBg,
          borderColor: borderColor,
          color: secondaryTextColor
        }}
      >
        <div className="flex items-center gap-2">
          <button
            onClick={handleInsertTemplate}
            className="flex items-center gap-1 px-2.5 py-1 rounded border transition-colors hover:border-teal-500 text-teal-400"
            style={{
              background: buttonBg,
              borderColor: borderColor
            }}
            title="Gunakan format Surat Edaran baku"
          >
            <Sparkles size={12} />
            <span>Format SE Baku</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
            title="Salin seluruh isi dokumen"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            <span>Salin</span>
          </button>

          <button
            onClick={handleDownload}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
            title="Unduh draf (.md)"
          >
            <Download size={13} />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Textarea Editor */}
      <div
        className="flex-1 p-4 flex flex-col min-h-0"
        style={{ background: editorBg }}
      >
        <textarea
          value={content}
          onChange={handleChange}
          placeholder="Mulai tulis atau susun draf Surat Edaran, SK, atau aturan bersama di sini. Anda juga dapat meminta CAKRA merumuskan draf lewat chat..."
          className="w-full h-full resize-none bg-transparent border-0 text-sm font-mono leading-relaxed focus:outline-none focus:ring-0 custom-scrollbar"
          style={{ color: textColor }}
          spellCheck={false}
        />
      </div>

      {/* Footer Info */}
      <div
        className="px-4 py-2 border-t text-[11px] flex items-center justify-between"
        style={{
          background: pageBg,
          borderColor: borderColor,
          color: secondaryTextColor
        }}
      >
        <span>{content.split(/\s+/).filter(Boolean).length} kata</span>
        <span>{isDirty ? 'Perubahan belum disimpan' : 'Semua perubahan tersimpan'}</span>
      </div>
    </div>
  );
};

export default CollabDocumentPad;
