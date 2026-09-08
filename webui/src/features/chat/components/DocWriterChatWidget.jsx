import React, { useState, useEffect, useMemo } from 'react';
import { 
  FileText, 
  ExternalLink, 
  CheckCircle2, 
  Sparkles, 
  Download, 
  Printer, 
  Edit3, 
  Layers,
  ChevronRight,
  ShieldCheck
} from 'lucide-react';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import { defaultTemplates } from '../../doc_writer/templates/defaultTemplates';
import { translations } from '../../../utils/translations';

const DocWriterChatWidget = ({ 
  codeBlockContent, 
  darkMode = true, 
  theme, 
  language = 'id',
  isStreaming = false 
}) => {
  const tGlobal = translations[language] || translations.id;
  const { 
    openWriter, 
    isOpen, 
    patchSection, 
    setDocumentTitle, 
    setDocumentContent, 
    exportDocx,
    isExporting,
    activeDocument 
  } = useDocWriterStore();

  const [applied, setApplied] = useState(false);
  const [parseError, setParseError] = useState(false);

  // Parse JSON data dari blok markdown ```docwriter
  const docData = useMemo(() => {
    if (!codeBlockContent) return null;
    try {
      const clean = codeBlockContent.trim();
      return JSON.parse(clean);
    } catch (e) {
      // Tangani unclosed JSON saat streaming
      try {
        const firstBrace = codeBlockContent.indexOf('{');
        const lastBrace = codeBlockContent.lastIndexOf('}');
        if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
          return JSON.parse(codeBlockContent.substring(firstBrace, lastBrace + 1));
        }
      } catch (e2) {
        // Partial JSON
      }
      return null;
    }
  }, [codeBlockContent]);

  const action = docData?.action || 'draft'; // 'open', 'draft', 'patch'
  const templateKey = docData?.template || 'template_skep';
  const docTitle = docData?.title || defaultTemplates[templateKey]?.title || 'Draf Dokumen Resmi';
  const summary = docData?.summary || (action === 'patch' ? `Revisi bagian "${docData?.sectionId || 'dokumen'}" oleh CAKRA` : 'Draf naskah dinas siap sunting');
  const sectionId = docData?.sectionId || null;
  const rawHtml = docData?.content || '';

  // Dapatkan detail template
  const templateMeta = defaultTemplates[templateKey] || {
    name: 'Dokumen Standar',
    id: templateKey
  };

  // Auto-open jika action eksplisit adalah 'open' dan belum dibuka
  useEffect(() => {
    if (!isStreaming && docData?.autoOpen && !isOpen) {
      handleOpenInEditor();
    }
  }, [isStreaming, docData]);

  const handleOpenInEditor = () => {
    openWriter(
      templateKey,
      docTitle,
      rawHtml || undefined
    );
  };

  const handleApplyPatch = () => {
    if (!sectionId && !rawHtml) return;
    if (sectionId) {
      patchSection(sectionId, rawHtml);
    } else if (rawHtml) {
      setDocumentContent(rawHtml);
      if (docTitle) setDocumentTitle(docTitle);
    }
    setApplied(true);
    if (!isOpen) {
      openWriter(templateKey, docTitle);
    }
    setTimeout(() => setApplied(false), 3000);
  };

  const handleDownloadDocx = () => {
    if (isOpen) {
      exportDocx();
    } else {
      // Buka dulu agar dokumen aktif sinkron, lalu trigger export
      openWriter(templateKey, docTitle, rawHtml || undefined);
      setTimeout(() => {
        exportDocx();
      }, 300);
    }
  };

  const handlePrintPdf = () => {
    if (!isOpen) {
      openWriter(templateKey, docTitle, rawHtml || undefined);
    }
    setTimeout(() => {
      window.print();
    }, 400);
  };

  return (
    <div 
      className="doc-writer-chat-widget my-3 rounded-xl overflow-hidden border shadow-lg transition-all duration-200"
      style={{
        background: darkMode 
          ? 'linear-gradient(135deg, rgba(24, 24, 27, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)' 
          : 'linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%)',
        borderColor: darkMode ? 'rgba(56, 189, 248, 0.25)' : 'rgba(14, 165, 233, 0.3)',
        boxShadow: darkMode 
          ? '0 8px 24px -4px rgba(0, 0, 0, 0.5), 0 0 12px rgba(56, 189, 248, 0.1)' 
          : '0 8px 24px -4px rgba(14, 165, 233, 0.12)'
      }}
    >
      {/* Header Widget */}
      <div 
        className="px-4 py-3 flex items-center justify-between border-b"
        style={{
          borderColor: darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
          background: darkMode ? 'rgba(56, 189, 248, 0.05)' : 'rgba(14, 165, 233, 0.04)'
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div 
            className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
            style={{
              background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(37, 99, 235, 0.35)'
            }}
          >
            <FileText className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-bold tracking-wide truncate" style={{ color: darkMode ? '#f8fafc' : '#0f172a' }}>
                CAKRA Document Studio
              </span>
              <span 
                className="text-[10px] font-medium px-2 py-0.5 rounded-full border uppercase shrink-0"
                style={{
                  background: darkMode ? 'rgba(56, 189, 248, 0.12)' : 'rgba(14, 165, 233, 0.1)',
                  borderColor: darkMode ? 'rgba(56, 189, 248, 0.3)' : 'rgba(14, 165, 233, 0.25)',
                  color: darkMode ? '#38bdf8' : '#0284c7'
                }}
              >
                {templateMeta.name}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <span 
            className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md"
            style={{
              color: darkMode ? '#94a3b8' : '#64748b'
            }}
          >
            <Sparkles className="w-3 h-3 text-sky-400 animate-pulse" />
            {action === 'patch' ? 'Revisi Terarah' : 'Draf Otomatis'}
          </span>
        </div>
      </div>

      {/* Konten / Summary Preview */}
      <div className="p-4 space-y-3">
        <div>
          <h4 
            className="text-[14px] font-bold mb-1 line-clamp-1"
            style={{ color: darkMode ? '#f1f5f9' : '#1e293b' }}
          >
            {docTitle}
          </h4>
          <p 
            className="text-[12.5px] leading-relaxed line-clamp-2"
            style={{ color: darkMode ? '#94a3b8' : '#64748b' }}
          >
            {summary}
          </p>
        </div>

        {/* Section Patch Badge jika spesifik */}
        {sectionId && (
          <div 
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs"
            style={{
              background: darkMode ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.05)',
              borderColor: darkMode ? 'rgba(16, 185, 129, 0.25)' : 'rgba(16, 185, 129, 0.2)',
              color: darkMode ? '#34d399' : '#059669'
            }}
          >
            <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">
              Target Seksi: <strong>{sectionId.toUpperCase()}</strong> (A4 BUMN Compliant)
            </span>
          </div>
        )}

        {/* Action Buttons Bar */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {/* Main Button: Buka di Editor */}
          <button
            onClick={handleOpenInEditor}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-[12.5px] font-semibold text-white shadow-md hover:brightness-110 active:scale-95 transition-all"
            style={{
              background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)',
              boxShadow: '0 2px 10px rgba(37, 99, 235, 0.3)'
            }}
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>{isOpen ? 'Lihat di Dokumen Editor' : 'Buka Dokumen Editor (Split-Screen)'}</span>
          </button>

          {/* Tombol Terapkan jika patch */}
          {action === 'patch' && (
            <button
              onClick={handleApplyPatch}
              disabled={applied}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium border hover:bg-emerald-500/10 active:scale-95 transition-all"
              style={{
                borderColor: darkMode ? 'rgba(16, 185, 129, 0.35)' : 'rgba(16, 185, 129, 0.3)',
                color: applied ? '#34d399' : (darkMode ? '#a7f3d0' : '#065f46')
              }}
            >
              {applied ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Diterapkan!</span>
                </>
              ) : (
                <>
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>Terapkan ke Editor</span>
                </>
              )}
            </button>
          )}

          {/* Quick Export DOCX */}
          <button
            onClick={handleDownloadDocx}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium border hover:bg-sky-500/10 active:scale-95 transition-all"
            style={{
              borderColor: darkMode ? 'rgba(148, 163, 184, 0.25)' : 'rgba(203, 213, 225, 0.8)',
              color: darkMode ? '#cbd5e1' : '#475569'
            }}
            title="Download file Word (.docx) resmi dengan Kop Surat PT Pindad"
          >
            <Download className="w-3.5 h-3.5 text-sky-400" />
            <span>{isExporting ? 'Mengonversi...' : 'Unduh .DOCX'}</span>
          </button>

          {/* Quick Print PDF */}
          <button
            onClick={handlePrintPdf}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium border hover:bg-slate-500/10 active:scale-95 transition-all"
            style={{
              borderColor: darkMode ? 'rgba(148, 163, 184, 0.25)' : 'rgba(203, 213, 225, 0.8)',
              color: darkMode ? '#94a3b8' : '#64748b'
            }}
            title="Cetak langsung ke PDF A4 Presisi"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Cetak PDF</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocWriterChatWidget;
