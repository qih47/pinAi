import React, { useState, useRef, useCallback } from 'react';
import { 
  FileEdit, 
  X, 
  Maximize2, 
  Minimize2, 
  Sparkles, 
  Check, 
  GripVertical,
  LayoutTemplate
} from 'lucide-react';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import DocWriterToolbar from './DocWriterToolbar';
import DocWriterCanvas from './DocWriterCanvas';
import OnlyOfficeWorkspace from './OnlyOfficeWorkspace';
import TemplateSelectorModal from './TemplateSelectorModal';

const DocWriterWorkspace = ({ darkMode = true, theme, isMobile = false, sessionId = null, roomId = null }) => {
  const {
    isOpen,
    closeWriter,
    splitWidth,
    setSplitWidth,
    activeDocument,
    setDocumentTitle,
    activeTemplateId,
    currentDocId,
    isTemplateModalOpen,
    setTemplateModalOpen
  } = useDocWriterStore();

  const [editorInstance, setEditorInstance] = useState(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [tempTitle, setTempTitle] = useState(activeDocument?.title || '');
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const isResizingRef = useRef(false);
  const containerRef = useRef(null);

  // Resize handler drag horizontal berbasis delta posisi
  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isResizingRef.current = true;
    setIsDragging(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const startX = e.clientX;
    const startWidth = containerRef.current
      ? containerRef.current.getBoundingClientRect().width
      : (window.innerWidth * 0.5);

    const handleMouseUp = () => {
      isResizingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('mouseleave', handleMouseUp);
      window.removeEventListener('blur', handleMouseUp);
    };

    const handleMouseMove = (moveEvent) => {
      if (!isResizingRef.current) return;
      if (moveEvent.buttons === 0) {
        handleMouseUp();
        return;
      }
      const deltaX = moveEvent.clientX - startX;
      const parentWidth = containerRef.current?.parentElement
        ? containerRef.current.parentElement.getBoundingClientRect().width
        : window.innerWidth;
      const newWidth = Math.max(360, Math.min(startWidth + deltaX, parentWidth - 360));
      setSplitWidth(Math.round(newWidth));
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('mouseleave', handleMouseUp);
    window.addEventListener('blur', handleMouseUp);
  }, [setSplitWidth]);

  const isGuest = (() => {
    try {
      const raw = localStorage.getItem('cakra_user');
      if (!raw) return true;
      const u = JSON.parse(raw);
      return Boolean(u?.isGuest || u?.role === 'guest' || u?.npp === 'GUEST');
    } catch {
      return false;
    }
  })();

  if (isGuest || !isOpen) return null;

  const bgHeader = darkMode ? '#18181b' : '#ffffff';
  const borderColor = darkMode ? '#2d2d32' : '#e5e7eb';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  // Default: tepat 50% split-screen (setengah dokumen, setengah chat)
  const panelWidth = isFullScreen || isMobile 
    ? '100%' 
    : (typeof splitWidth === 'number' ? `${splitWidth}px` : '50%');

  const handleTitleSubmit = () => {
    if (tempTitle.trim()) {
      setDocumentTitle(tempTitle.trim());
    }
    setIsEditingTitle(false);
  };

  const getTemplateBadge = (tId) => {
    switch (tId) {
      case 'template_se': return 'SE';
      case 'template_skep': return 'SKEP';
      case 'template_ik': return 'IK';
      case 'template_prosedur': return 'SOP';
      case 'template_nota_dinas': return 'Nota Dinas';
      default: return 'Word A4';
    }
  };

  return (
    <div
      ref={containerRef}
      className="doc-writer-split-container flex shrink-0 h-full relative z-20 animate-fadeIn select-none"
      style={{
        width: panelWidth,
        minWidth: isFullScreen || isMobile ? '100%' : '360px',
        maxWidth: isFullScreen || isMobile ? '100%' : 'calc(100% - 360px)',
        borderRight: `1px solid ${borderColor}`,
        background: darkMode ? '#151518' : '#f8fafc',
        boxShadow: '4px 0 24px rgba(0,0,0,0.15)',
      }}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* ── Top Header: Document Title & Controls ── */}
        <div
          className="flex items-center justify-between px-4 py-2 border-b select-none shrink-0"
          style={{ background: bgHeader, borderColor: borderColor }}
        >
          <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-2">
            <div className="w-7 h-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
              <FileEdit size={15} />
            </div>

            {/* Editable Title */}
            {isEditingTitle ? (
              <div className="flex items-center gap-1.5 flex-1 max-w-sm">
                <input
                  type="text"
                  value={tempTitle}
                  onChange={(e) => setTempTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleTitleSubmit();
                    if (e.key === 'Escape') setIsEditingTitle(false);
                  }}
                  autoFocus
                  className="px-2 py-0.5 rounded text-xs font-semibold w-full bg-transparent border border-sky-500 focus:outline-none"
                  style={{ color: textColor }}
                />
                <button
                  type="button"
                  onClick={handleTitleSubmit}
                  className="p-1 rounded text-emerald-400 hover:bg-emerald-500/10"
                >
                  <Check size={14} />
                </button>
              </div>
            ) : (
              <div
                onClick={() => {
                  setTempTitle(activeDocument?.title || '');
                  setIsEditingTitle(true);
                }}
                className="cursor-pointer group flex items-center gap-1.5 min-w-0"
                title="Klik untuk mengubah judul dokumen"
              >
                <h2
                  className="text-xs font-bold truncate group-hover:text-sky-400 transition-colors max-w-[200px] sm:max-w-xs"
                  style={{ color: textColor }}
                >
                  {activeDocument?.title || 'Dokumen Resmi PT Pindad'}
                </h2>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 font-medium shrink-0">
                  {getTemplateBadge(activeTemplateId)}
                </span>
              </div>
            )}
          </div>

          {/* Right Action Icons */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Template Selector Button */}
            <button
              type="button"
              onClick={() => setTemplateModalOpen(true)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all"
              style={{
                background: darkMode ? 'rgba(56, 189, 248, 0.1)' : '#e0f2fe',
                borderColor: darkMode ? 'rgba(56, 189, 248, 0.25)' : '#bae6fd',
                color: darkMode ? '#38bdf8' : '#0284c7'
              }}
              title="Ganti Format Template Dokumen"
            >
              <LayoutTemplate size={13} />
              <span className="hidden sm:inline">Template</span>
            </button>

            <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-medium mr-1 border border-emerald-500/20">
              <Sparkles size={10} />
              <span>AI Active</span>
            </div>

            {!isMobile && (
              <button
                type="button"
                onClick={() => setIsFullScreen(!isFullScreen)}
                className="p-1.5 rounded-md hover:bg-white/5 transition-colors"
                style={{ color: secondaryTextColor }}
                title={isFullScreen ? "Kecilkan Panel" : "Perbesar Penuh"}
              >
                {isFullScreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              </button>
            )}

            <button
              type="button"
              onClick={closeWriter}
              className="p-1.5 rounded-md hover:bg-red-500/10 hover:text-red-400 transition-colors"
              style={{ color: secondaryTextColor }}
              title="Tutup Dokumen Studio"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* ── Editor Body: ONLYOFFICE Document Studio ── */}
        {currentDocId ? (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <OnlyOfficeWorkspace
              docId={currentDocId}
              docTitle={activeDocument?.title}
              templateId={activeTemplateId}
              darkMode={darkMode}
              theme={theme}
              sessionId={sessionId}
              roomId={roomId}
              onClose={closeWriter}
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Fallback Legacy Editor jika docId belum dibuat */}
            <DocWriterToolbar
              editor={editorInstance}
              onOpenTemplates={() => setTemplateModalOpen(true)}
              darkMode={darkMode}
              theme={theme}
            />
            <DocWriterCanvas
              onEditorReady={setEditorInstance}
              darkMode={darkMode}
              theme={theme}
            />
          </div>
        )}
      </div>

      {/* ── Drag Handle Resizer (Horizontal) ── */}
      {!isFullScreen && !isMobile && (
        <div
          onMouseDown={handleMouseDown}
          onDoubleClick={() => setSplitWidth(null)}
          className="absolute right-0 top-0 bottom-0 w-2 hover:w-2.5 cursor-col-resize z-30 group flex items-center justify-center transition-all"
          style={{ background: 'transparent' }}
          title="Geser untuk mengatur lebar, atau klik 2x untuk kembali ke default 50:50"
        >
          <div className="w-1.5 h-14 rounded-full bg-slate-400/40 group-hover:bg-sky-500 shadow-sm transition-colors" />
        </div>
      )}

      {/* ── Transparent drag barrier overlay to prevent iframe from capturing mouseup ── */}
      {isDragging && (
        <div
          className="fixed inset-0 z-[999999] cursor-col-resize select-none"
          style={{ pointerEvents: 'auto', background: 'transparent' }}
        />
      )}

      {/* ── Modal Pilihan Template ── */}
      <TemplateSelectorModal
        isOpen={isTemplateModalOpen}
        onClose={() => setTemplateModalOpen(false)}
        darkMode={darkMode}
        theme={theme}
      />
    </div>
  );
};

export default DocWriterWorkspace;
