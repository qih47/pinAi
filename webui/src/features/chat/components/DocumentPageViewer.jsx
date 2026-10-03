import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  ChevronLeft, 
  ChevronRight, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  ExternalLink, 
  Download,
  Eye,
  AlertCircle
} from 'lucide-react';
import { translations } from '../../../utils/translations';

/**
 * Generative UI DocumentPageViewer
 * Menampilkan snapshot halaman fisik dokumen/lampiran regulasi (PNG 150 DPI)
 * secara interaktif, tajam, dan responsif.
 */
export default function DocumentPageViewer({ toolData, darkMode, language = 'id' }) {
  const t = translations[language]?.chat?.docMedia || translations.id.chat.docMedia;
  
  const docId = toolData?.dokumen_id || toolData?.doc_id || null;
  const initialPage = Number(toolData?.page) || 1;
  const totalPages = Number(toolData?.total_pages) || 1;
  const docTitle = toolData?.title || toolData?.judul || `Dokumen #${docId || ''}`;
  const initialImageUrl = toolData?.image_url || (docId ? `/doc_pages/${docId}/page_${String(initialPage).padStart(3, '0')}.png` : '');

  const [currentPage, setCurrentPage] = useState(initialPage);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [imgLoading, setImgLoading] = useState(true);

  // Compute active image URL based on current page
  const currentImageUrl = docId 
    ? `/doc_pages/${docId}/page_${String(currentPage).padStart(3, '0')}.png`
    : initialImageUrl;

  useEffect(() => {
    setImgLoading(true);
    setImgError(false);
  }, [currentPage, currentImageUrl]);

  const handlePrev = (e) => {
    e.stopPropagation();
    if (currentPage > 1) {
      setCurrentPage(prev => prev - 1);
    }
  };

  const handleNext = (e) => {
    e.stopPropagation();
    if (currentPage < totalPages) {
      setCurrentPage(prev => prev + 1);
    }
  };

  const handleZoomIn = (e) => {
    e.stopPropagation();
    setZoomLevel(prev => Math.min(prev + 0.25, 2.5));
  };

  const handleZoomOut = (e) => {
    e.stopPropagation();
    setZoomLevel(prev => Math.max(prev - 0.25, 0.75));
  };

  const handleResetZoom = (e) => {
    e.stopPropagation();
    setZoomLevel(1);
  };

  return (
    <div 
      className={`my-3.5 rounded-2xl border transition-all duration-300 overflow-hidden shadow-sm ${
        darkMode 
          ? 'bg-[#18181b]/95 border-zinc-800 text-zinc-100 shadow-black/40' 
          : 'bg-white/95 border-slate-200 text-slate-800 shadow-slate-200/60'
      }`}
    >
      {/* Header Bar */}
      <div className={`px-4 py-3 border-b flex flex-wrap items-center justify-between gap-2.5 ${
        darkMode ? 'bg-zinc-900/80 border-zinc-800' : 'bg-slate-50/90 border-slate-100'
      }`}>
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
            darkMode ? 'bg-indigo-500/10 text-indigo-400' : 'bg-indigo-50 text-indigo-600'
          }`}>
            <FileText className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h4 className="text-xs font-semibold truncate leading-snug">
              {docTitle}
            </h4>
            <div className="flex items-center gap-2 text-[10px] text-zinc-400">
              <span className={`px-1.5 py-0.5 rounded font-mono font-medium ${
                darkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-slate-200/70 text-slate-700'
              }`}>
                ID #{docId || 'DOC'}
              </span>
              <span>•</span>
              <span>
                {t.pageIndicator.replace('{current}', currentPage).replace('{total}', totalPages)}
              </span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5">
          {totalPages > 1 && (
            <div className={`flex items-center rounded-lg border p-0.5 ${
              darkMode ? 'border-zinc-700 bg-zinc-800/80' : 'border-slate-200 bg-white'
            }`}>
              <button
                type="button"
                onClick={handlePrev}
                disabled={currentPage <= 1}
                title={t.prevPage}
                className="p-1 rounded hover:bg-zinc-700/50 disabled:opacity-30 disabled:pointer-events-none transition"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="px-2 text-[11px] font-mono font-medium">
                {currentPage}/{totalPages}
              </span>
              <button
                type="button"
                onClick={handleNext}
                disabled={currentPage >= totalPages}
                title={t.nextPage}
                className="p-1 rounded hover:bg-zinc-700/50 disabled:opacity-30 disabled:pointer-events-none transition"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Zoom controls */}
          <div className={`flex items-center rounded-lg border p-0.5 ${
            darkMode ? 'border-zinc-700 bg-zinc-800/80' : 'border-slate-200 bg-white'
          }`}>
            <button
              type="button"
              onClick={handleZoomOut}
              disabled={zoomLevel <= 0.75}
              title={t.zoomOut}
              className="p-1 rounded hover:bg-zinc-700/50 disabled:opacity-30 transition"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              title="Reset Zoom"
              className="px-1 text-[10px] font-mono hover:underline"
            >
              {Math.round(zoomLevel * 100)}%
            </button>
            <button
              type="button"
              onClick={handleZoomIn}
              disabled={zoomLevel >= 2.5}
              title={t.zoomIn}
              className="p-1 rounded hover:bg-zinc-700/50 disabled:opacity-30 transition"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Fullscreen / Open new tab */}
          <button
            type="button"
            onClick={() => setIsFullscreen(true)}
            title={t.fullView}
            className={`p-1.5 rounded-lg border transition ${
              darkMode ? 'border-zinc-700 hover:bg-zinc-800 text-zinc-300' : 'border-slate-200 hover:bg-slate-100 text-slate-600'
            }`}
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <a
            href={currentImageUrl}
            target="_blank"
            rel="noopener noreferrer"
            title={t.openNewTab}
            className={`p-1.5 rounded-lg border transition ${
              darkMode ? 'border-zinc-700 hover:bg-zinc-800 text-zinc-300' : 'border-slate-200 hover:bg-slate-100 text-slate-600'
            }`}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Main Image Stage */}
      <div 
        className={`relative overflow-auto max-h-[520px] flex items-center justify-center p-4 select-none ${
          darkMode ? 'bg-zinc-950/70' : 'bg-slate-100/60'
        }`}
      >
        {imgLoading && !imgError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-inherit z-10">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-zinc-400 font-medium">{t.loadingImage}</span>
          </div>
        )}

        {imgError ? (
          <div className="py-12 px-4 flex flex-col items-center justify-center gap-2 text-center text-zinc-400">
            <AlertCircle className="w-8 h-8 text-amber-500/80 mb-1" />
            <p className="text-xs font-medium">{t.failedImage}</p>
            <span className="text-[10px] text-zinc-500 font-mono">{currentImageUrl}</span>
          </div>
        ) : (
          <div 
            className="transition-transform duration-200 ease-out origin-top flex items-center justify-center"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <img
              src={currentImageUrl}
              alt={`Halaman ${currentPage} - ${docTitle}`}
              onLoad={() => setImgLoading(false)}
              onError={() => {
                setImgLoading(false);
                setImgError(true);
              }}
              className="max-w-full h-auto rounded-lg shadow-md border border-zinc-200/20 object-contain cursor-zoom-in"
              onClick={handleZoomIn}
            />
          </div>
        )}
      </div>

      {/* Fullscreen Lightbox Modal */}
      {isFullscreen && (
        <div 
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex flex-col p-4 animate-in fade-in duration-200"
          onClick={() => setIsFullscreen(false)}
        >
          <div className="flex items-center justify-between text-white pb-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-medium">{docTitle} - Hal. {currentPage}</span>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={currentImageUrl}
                download
                className="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg flex items-center gap-1.5 transition"
              >
                <Download className="w-3.5 h-3.5" />
                {t.download}
              </a>
              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                className="px-3 py-1.5 text-xs bg-white text-zinc-900 font-medium rounded-lg hover:bg-zinc-200 transition"
              >
                ✕ Tutup
              </button>
            </div>
          </div>
          <div 
            className="flex-1 flex items-center justify-center overflow-auto"
            onClick={e => e.stopPropagation()}
          >
            <img 
              src={currentImageUrl} 
              alt={docTitle} 
              className="max-h-[85vh] max-w-[90vw] object-contain rounded shadow-2xl" 
            />
          </div>
        </div>
      )}
    </div>
  );
}
