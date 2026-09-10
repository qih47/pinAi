import React, { useState, useRef, useCallback } from 'react';
import { FileEdit, X, Maximize2, Minimize2, Sparkles, Check, GripVertical } from 'lucide-react';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import DocWriterToolbar from './DocWriterToolbar';
import DocWriterCanvas from './DocWriterCanvas';
import TemplateSelectorModal from './TemplateSelectorModal';

const DocWriterWorkspace = ({ darkMode = true, theme, isMobile = false }) => {
  const {
    isOpen,
    closeWriter,
    splitWidth,
    setSplitWidth,
    activeDocument,
    setDocumentTitle,
    activeTemplateId,
    isTemplateModalOpen,
    setTemplateModalOpen
  } = useDocWriterStore();

  const [editorInstance, setEditorInstance] = useState(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [tempTitle, setTempTitle] = useState(activeDocument?.title || '');
  const [isFullScreen, setIsFullScreen] = useState(false);
  const isResizingRef = useRef(false);

  // Resize handler drag horizontal
  const handleMouseDown = useCallback((e) => {
    isResizingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (moveEvent) => {
      if (!isResizingRef.current) return;
      const newWidth = moveEvent.clientX;
      setSplitWidth(newWidth);
    };

    const handleMouseUp = () => {
      isResizingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
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

  const panelWidth = isFullScreen || isMobile ? '100%' : `${splitWidth}px`;

  const handleTitleSubmit = () => {
    if (tempTitle.trim()) {
      setDocumentTitle(tempTitle.trim());
    }
    setIsEditingTitle(false);
  };

  return (
    <div
      className="doc-writer-split-container flex shrink-0 h-full relative z-20 animate-fadeIn"
      style={{
        width: panelWidth,
        borderRight: `1px solid ${borderColor}`,
        background: darkMode ? '#151518' : '#f8fafc',
        boxShadow: '4px 0 24px rgba(0,0,0,0.15)',
      }}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* ── Top Header: Document Title & Controls ── */}
        <div
          className="flex items-center justify-between px-4 py-2.5 border-b select-none shrink-0"
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
                  setTempTitle(activeDocument.title || '');
                  setIsEditingTitle(true);
                }}
                className="cursor-pointer group flex items-center gap-1.5 min-w-0"
                title="Klik untuk mengubah judul dokumen"
              >
                <h2
                  className="text-xs font-bold truncate group-hover:text-sky-400 transition-colors"
                  style={{ color: textColor }}
                >
                  {activeDocument?.title || 'Dokumen Resmi PT Pindad'}
                </h2>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 font-medium shrink-0">
                  {activeTemplateId === 'template_skep' ? 'SKEP' :
                   activeTemplateId === 'template_se' ? 'SE' :
                   activeTemplateId === 'template_memo' ? 'Nota Dinas' : 'Word A4'}
                </span>
              </div>
            )}
          </div>

          {/* Right Action Icons */}
          <div className="flex items-center gap-1 shrink-0">
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-medium mr-1 border border-emerald-500/20">
              <Sparkles size={10} />
              <span>AI Co-Author Ready</span>
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
              title="Tutup Dokumen Writer"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* ── Toolbar Pita Ribbon ── */}
        <DocWriterToolbar
          editor={editorInstance}
          onOpenTemplates={() => setTemplateModalOpen(true)}
          darkMode={darkMode}
          theme={theme}
        />

        {/* ── Kanvas Kertas A4 Editor ── */}
        <DocWriterCanvas
          onEditorReady={setEditorInstance}
          darkMode={darkMode}
          theme={theme}
        />
      </div>

      {/* ── Drag Handle Resizer (Horizontal) ── */}
      {!isFullScreen && !isMobile && (
        <div
          onMouseDown={handleMouseDown}
          className="absolute right-0 top-0 bottom-0 w-1.5 hover:w-2 cursor-col-resize z-30 group flex items-center justify-center transition-all"
          style={{ background: 'transparent' }}
          title="Geser untuk mengatur lebar dokumen"
        >
          <div className="w-1 h-12 rounded-full bg-slate-400/30 group-hover:bg-sky-500 transition-colors" />
        </div>
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
