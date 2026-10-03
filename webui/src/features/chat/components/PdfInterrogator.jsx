import React, { useState, useRef, useCallback } from 'react';
import { useChatStore } from '../../../stores/chatStore';
import { X, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, PanelLeftClose, PanelLeftOpen, CheckSquare, Square, MessageSquare, Sparkles } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Virtuoso } from 'react-virtuoso';
import { translations } from '../../../utils/translations';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Konfigurasi worker react-pdf untuk Vite
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

const PdfInterrogator = ({ darkMode, language = 'id', isMobile = false }) => {
    const tGlobal = translations[language] || translations.id;
    const tPdf = tGlobal.pdfInterrogator || translations.id.pdfInterrogator || {};
    const { isSplitScreen, activePdfUrl, setSplitScreen, setTargetedPdfContext } = useChatStore((state) => ({
        isSplitScreen: state.isSplitScreen,
        activePdfUrl: state.activePdfUrl,
        setSplitScreen: state.setSplitScreen,
        setTargetedPdfContext: state.setTargetedPdfContext
    }));

    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [scale, setScale] = useState(1.0);
    const [viewMode, setViewMode] = useState('scroll'); // 'scroll' atau 'page'
    const [containerWidth, setContainerWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 800);
    const [showSidebar, setShowSidebar] = useState(true);
    const [selectedPages, setSelectedPages] = useState([]); // Array of 1-based page numbers: [1, 3]
    const virtuosoRef = useRef(null);

    React.useEffect(() => {
        const handleResize = () => {
            setContainerWidth(window.innerWidth);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // Reset selected pages saat activePdfUrl berganti
    React.useEffect(() => {
        setSelectedPages([]);
    }, [activePdfUrl]);

    const onDocumentLoadSuccess = ({ numPages }) => {
        setNumPages(numPages);
        setPageNumber(1);
    };

    const changePage = (offset) => {
        setPageNumber((prevPageNumber) => {
            const newPageNumber = prevPageNumber + offset;
            return Math.min(Math.max(1, newPageNumber), numPages);
        });
    };

    const zoomIn = () => setScale(prev => Math.min(prev + 0.2, 3.0));
    const zoomOut = () => setScale(prev => Math.max(prev - 0.2, 0.5));

    // Ekstraksi nama file yang bersih dari URL
    const cleanFileName = React.useMemo(() => {
        if (!activePdfUrl) return "Dokumen PDF";
        try {
            const pathParts = activePdfUrl.split('?')[0].split('/');
            const raw = decodeURIComponent(pathParts[pathParts.length - 1] || "Dokumen PDF");
            return raw.replace(/^[0-9a-fA-F-]{36}_/, '');
        } catch {
            return "Dokumen PDF";
        }
    }, [activePdfUrl]);

    // Menghitung lebar optimal PDF pada mobile & desktop saat sidebar aktif
    const computedPageWidth = React.useMemo(() => {
        const sidebarWidth = showSidebar && !isMobile ? 148 : 0;
        const availableWidth = containerWidth - sidebarWidth;
        if (isMobile || availableWidth < 768) {
            return Math.max(availableWidth - 32, 280) * scale;
        }
        return undefined;
    }, [isMobile, containerWidth, scale, showSidebar]);

    // Handle toggle page selection (maksimal 20 halaman sesuai kapasitas vLLM)
    const togglePageSelection = useCallback((pNum, e) => {
        if (e) e.stopPropagation();
        setSelectedPages(prev => {
            if (prev.includes(pNum)) {
                return prev.filter(p => p !== pNum);
            }
            if (prev.length >= 20) {
                // Maksimal 20 halaman sesuai kemampuan multimodal vision vLLM
                return prev;
            }
            return [...prev, pNum].sort((a, b) => a - b);
        });
    }, []);

    // Scroll ke halaman tertentu saat thumbnail diklik
    const jumpToPage = useCallback((pNum) => {
        setPageNumber(pNum);
        if (viewMode === 'scroll' && virtuosoRef.current) {
            virtuosoRef.current.scrollToIndex({
                index: pNum - 1,
                align: 'start',
                behavior: 'smooth'
            });
        }
    }, [viewMode]);

    // Kirim target halaman ke ChatInputArea
    const handleSendPagesToChat = useCallback(() => {
        if (selectedPages.length === 0) return;
        setTargetedPdfContext({
            fileName: cleanFileName,
            url: activePdfUrl,
            pages: selectedPages
        });
    }, [selectedPages, cleanFileName, activePdfUrl, setTargetedPdfContext]);

    return (
        <div 
            className={`flex flex-col shadow-xl transition-all ease-in-out ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'} ${
                isMobile 
                    ? `fixed inset-0 z-50 w-full h-[100dvh] ${isSplitScreen ? 'opacity-100 visible' : 'opacity-0 invisible pointer-events-none'}`
                    : `h-full relative ${isSplitScreen ? 'w-1/2 opacity-100 border-r visible' : 'w-0 opacity-0 border-none invisible pointer-events-none'}`
            }`}
            style={{ 
                transition: isMobile 
                    ? 'opacity 0.25s ease-in-out, visibility 0.25s' 
                    : 'width 0.4s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.3s ease-in-out, visibility 0.4s',
                overflow: 'hidden',
                flexShrink: 0
            }}
        >
            {/* Toolbar Atas */}
            <div className={`flex items-center justify-between px-3.5 py-2.5 border-b ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center space-x-2 min-w-0">
                    <button
                        onClick={() => setShowSidebar(prev => !prev)}
                        className={`p-1.5 rounded-lg border transition-all ${
                            showSidebar
                                ? (darkMode ? 'bg-blue-600/20 text-blue-400 border-blue-500/30' : 'bg-blue-50 text-blue-600 border-blue-200')
                                : (darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-gray-200' : 'text-gray-500 bg-white border-gray-200 hover:text-gray-700')
                        }`}
                        title={showSidebar ? (tPdf.toggleSidebarHide || "Sembunyikan Sidebar Thumbnail") : (tPdf.toggleSidebarShow || "Tampilkan Sidebar Thumbnail")}
                    >
                        {showSidebar ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
                    </button>
                    <div className="flex flex-col min-w-0">
                        <span className={`text-xs font-semibold truncate ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                            {cleanFileName}
                        </span>
                        <span className="text-[10px] text-gray-400 font-medium">
                            {tPdf.headerTitle || "Document Interrogator"} • {numPages ? (tPdf.pageCount ? tPdf.pageCount.replace('{count}', numPages) : `${numPages} Halaman`) : (tPdf.loading || 'Memuat...')}
                        </span>
                    </div>
                </div>

                <div className="flex items-center space-x-1.5 flex-shrink-0">
                    <button
                        onClick={() => window.open(activePdfUrl, '_blank')}
                        className={`p-1.5 sm:p-2 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400 hover:bg-[#252528]' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600 hover:bg-gray-50'}`}
                        title={tGlobal.pdf.openInNewTab}
                    >
                        <ExternalLink size={15} />
                    </button>
                    <button
                        onClick={() => setSplitScreen(false, null)}
                        className={`flex items-center space-x-1 p-1.5 sm:px-2 sm:py-1.5 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-red-400 bg-red-950/20 border-red-900/30 hover:bg-red-900/40' : 'text-red-600 bg-red-50 border-red-200 hover:bg-red-100'}`}
                        title={tGlobal.pdf.closeSplitScreen}
                    >
                        <X size={15} />
                        {isMobile && <span className="text-xs font-medium pr-0.5">Tutup</span>}
                    </button>
                </div>
            </div>

            {/* Content Area membungkus Document di level terluar agar Context react-pdf tersedia untuk sidebar & canvas */}
            {activePdfUrl && (activePdfUrl.endsWith('.pdf') || activePdfUrl.includes('/api/')) ? (
                <Document
                    file={activePdfUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={
                        <div className="flex items-center justify-center h-full w-full text-gray-400 text-sm p-8">
                            {tPdf.loadingDocument || "Memuat dokumen..."}
                        </div>
                    }
                    error={
                        <div className="flex items-center justify-center h-full w-full text-red-500 text-sm p-8">
                            {tGlobal.pdf.failLoad}
                        </div>
                    }
                    className="flex-1 flex overflow-hidden relative w-full h-full"
                >
                    {/* 📑 Sidebar Thumbnail Vertikal */}
                    {showSidebar && (
                        <aside className={`w-[140px] sm:w-[155px] flex-shrink-0 border-r flex flex-col transition-all z-10 ${
                            darkMode ? 'bg-[#18191c] border-[#2a2a2d]' : 'bg-gray-50 border-gray-200'
                        }`}>
                            <div className={`p-2 border-b flex items-center justify-between text-[11px] font-semibold ${
                                darkMode ? 'text-gray-300 border-[#2a2a2d]' : 'text-gray-700 border-gray-200'
                            }`}>
                                <span>{tPdf.sidebarTitle || "Halaman"}</span>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                                    selectedPages.length > 0 
                                        ? 'bg-blue-600 text-white' 
                                        : (darkMode ? 'bg-[#252528] text-gray-400' : 'bg-gray-200 text-gray-600')
                                }`}>
                                    {selectedPages.length}/20
                                </span>
                            </div>

                            {/* Thumbnail Scroll List */}
                            <div className="flex-1 overflow-y-auto p-2 space-y-2.5 custom-scroll">
                                {numPages ? (
                                    Array.from(new Array(numPages), (el, index) => {
                                        const pNum = index + 1;
                                        const isSelected = selectedPages.includes(pNum);
                                        const isCurrent = pageNumber === pNum;

                                        return (
                                            <div
                                                key={`thumb-${pNum}`}
                                                onClick={() => jumpToPage(pNum)}
                                                className={`relative group cursor-pointer rounded-lg p-1.5 transition-all border ${
                                                    isSelected 
                                                        ? 'border-blue-500 ring-2 ring-blue-500/30 bg-blue-500/10' 
                                                        : isCurrent 
                                                            ? (darkMode ? 'border-gray-500 bg-[#222327]' : 'border-gray-400 bg-white shadow-sm')
                                                            : (darkMode ? 'border-transparent hover:border-gray-700 hover:bg-[#202124]' : 'border-transparent hover:border-gray-200 hover:bg-white')
                                                }`}
                                            >
                                                {/* Header Mini Thumbnail */}
                                                <div className="flex items-center justify-between mb-1 text-[10px]">
                                                    <span className={`font-semibold ${isCurrent ? 'text-blue-400' : (darkMode ? 'text-gray-400' : 'text-gray-600')}`}>
                                                        {tPdf.pageBadge ? tPdf.pageBadge.replace('{pNum}', pNum) : `Hal ${pNum}`}
                                                    </span>
                                                    <button
                                                        type="button"
                                                        onClick={(e) => togglePageSelection(pNum, e)}
                                                        className={`transition-colors p-0.5 rounded hover:bg-black/10 ${
                                                            isSelected ? 'text-blue-500' : (darkMode ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-700')
                                                        }`}
                                                        title={isSelected ? (tPdf.unselectPageTooltip || "Batal pilih halaman") : (tPdf.selectPageTooltip || "Pilih halaman untuk interogasi")}
                                                    >
                                                        {isSelected ? <CheckSquare size={13} className="fill-blue-500/20" /> : <Square size={13} />}
                                                    </button>
                                                </div>

                                                {/* Preview Mini Page Frame */}
                                                <div className="bg-white rounded overflow-hidden shadow-sm flex items-center justify-center border border-gray-200/80 pointer-events-none">
                                                    <Page
                                                        pageNumber={pNum}
                                                        width={120}
                                                        renderTextLayer={false}
                                                        renderAnnotationLayer={false}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-32 text-center text-gray-400 text-xs p-2">
                                        <span className="animate-pulse">{tPdf.loadingThumbnails || "Memuat thumbnail..."}</span>
                                    </div>
                                )}
                            </div>

                            {/* Bar Aksi Bawah Sidebar: Masukkan ke Chat */}
                            {selectedPages.length > 0 && (
                                <div className={`p-2 border-t flex flex-col gap-1.5 ${
                                    darkMode ? 'bg-[#1e1f23] border-[#2a2a2d]' : 'bg-white border-gray-200 shadow-lg'
                                }`}>
                                    <button
                                        onClick={handleSendPagesToChat}
                                        className="w-full flex items-center justify-center gap-1.5 py-2 px-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-all shadow-md active:scale-98"
                                        title={tPdf.sendToChatTooltip || "Kirim halaman terpilih ke bilah input chat"}
                                    >
                                        <MessageSquare size={13} />
                                        <span>{tPdf.askPages ? tPdf.askPages.replace('{count}', selectedPages.length) : `Tanya (${selectedPages.length}) Hal`}</span>
                                    </button>
                                    <button
                                        onClick={() => setSelectedPages([])}
                                        className={`text-[10px] py-1 text-center font-medium transition-colors ${
                                            darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'
                                        }`}
                                    >
                                        {tPdf.resetSelection || "Reset Pilihan"}
                                    </button>
                                </div>
                            )}
                        </aside>
                    )}

                    {/* 📄 Main Content Area Canvas PDF */}
                    <div className={`flex-1 overflow-y-auto relative p-2 sm:p-4 flex flex-col items-center ${darkMode ? 'bg-[#151517]' : 'bg-gray-200'}`}>
                        {viewMode === 'scroll' && numPages ? (
                            <div className="w-full h-full">
                                <Virtuoso
                                    ref={virtuosoRef}
                                    style={{ height: '100%', width: '100%' }}
                                    totalCount={numPages}
                                    itemContent={(index) => (
                                        <div className="flex justify-center mb-4 sm:mb-6" style={{ minHeight: `${(isMobile ? 500 : 842) * scale}px` }}>
                                            <div className="relative shadow-2xl bg-white flex items-center justify-center max-w-full overflow-hidden">
                                                <Page
                                                    pageNumber={index + 1}
                                                    scale={computedPageWidth ? undefined : scale}
                                                    width={computedPageWidth}
                                                    renderTextLayer={true}
                                                    renderAnnotationLayer={true}
                                                    className={`transition-opacity ${darkMode ? 'opacity-95' : 'opacity-100'}`}
                                                />
                                            </div>
                                        </div>
                                    )}
                                />
                            </div>
                        ) : (
                            numPages && (
                                <div className="relative shadow-2xl bg-white mt-2 sm:mt-4 max-w-full overflow-hidden">
                                    <Page
                                        pageNumber={pageNumber}
                                        scale={computedPageWidth ? undefined : scale}
                                        width={computedPageWidth}
                                        renderTextLayer={true}
                                        renderAnnotationLayer={true}
                                        className={`transition-opacity ${darkMode ? 'opacity-95' : 'opacity-100'}`}
                                    />
                                </div>
                            )
                        )}
                    </div>
                </Document>
            ) : (
                <div className="flex-1 flex items-center justify-center h-full w-full text-center text-gray-500 text-sm p-4">
                    <p>{tPdf.unsupportedFormat || "Format file ini belum mendukung tampilan interaktif di sini."}</p>
                </div>
            )}

            {/* Toolbar Bawah: Pagination & Zoom */}
            {numPages && (
                <div className={`flex flex-wrap items-center justify-between gap-2 p-2.5 sm:p-3 border-t ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
                    <div className="flex items-center space-x-1.5 sm:space-x-2">
                        <button
                            onClick={zoomOut}
                            className={`p-1.5 sm:p-2 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600'}`}
                            title={tGlobal.pdf.zoomOut}
                        >
                            <ZoomOut size={15} />
                        </button>
                        <span className={`text-xs font-semibold w-10 sm:w-12 text-center ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                            {Math.round(scale * 100)}%
                        </span>
                        <button
                            onClick={zoomIn}
                            className={`p-1.5 sm:p-2 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600'}`}
                            title={tGlobal.pdf.zoomIn}
                        >
                            <ZoomIn size={15} />
                        </button>
                    </div>

                    <div className="flex items-center space-x-2 sm:space-x-3">
                        {/* Toggle Mode Scroll / Page */}
                        <button
                            onClick={() => setViewMode(viewMode === 'scroll' ? 'page' : 'scroll')}
                            className={`px-2.5 sm:px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${darkMode ? 'text-gray-200 bg-[#2a2a2d] hover:bg-gray-700' : 'text-gray-700 bg-gray-100 hover:bg-gray-200'}`}
                        >
                            {viewMode === 'scroll' ? tGlobal.pdf.modeScroll : tGlobal.pdf.modePage}
                        </button>

                        {viewMode === 'page' && (
                            <div className="flex items-center space-x-1.5">
                                <button
                                    disabled={pageNumber <= 1}
                                    onClick={() => changePage(-1)}
                                    className={`p-1.5 shadow-sm rounded-lg transition-all disabled:opacity-40 border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600'}`}
                                >
                                    <ChevronLeft size={15} />
                                </button>
                                <span className={`text-xs font-medium whitespace-nowrap ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                                    {pageNumber}/{numPages}
                                </span>
                                <button
                                    disabled={pageNumber >= numPages}
                                    onClick={() => changePage(1)}
                                    className={`p-1.5 shadow-sm rounded-lg transition-all disabled:opacity-40 border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600'}`}
                                >
                                    <ChevronRight size={15} />
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PdfInterrogator;
