import React, { useState } from 'react';
import { useChatStore } from '../../../stores/chatStore';
import { X, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
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
    const { isSplitScreen, activePdfUrl, setSplitScreen } = useChatStore((state) => ({
        isSplitScreen: state.isSplitScreen,
        activePdfUrl: state.activePdfUrl,
        setSplitScreen: state.setSplitScreen
    }));

    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [scale, setScale] = useState(1.0);
    const [viewMode, setViewMode] = useState('scroll'); // 'scroll' atau 'page'
    const [containerWidth, setContainerWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 800);

    React.useEffect(() => {
        const handleResize = () => {
            setContainerWidth(window.innerWidth);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

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

    // Menghitung lebar optimal PDF pada mobile agar langsung pas di layar
    const computedPageWidth = React.useMemo(() => {
        if (isMobile || containerWidth < 768) {
            return Math.max(containerWidth - 32, 280) * scale;
        }
        return undefined;
    }, [isMobile, containerWidth, scale]);

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
            <div className={`flex items-center justify-between px-3.5 py-3 border-b ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center space-x-2 min-w-0">
                    <span className={`text-sm font-semibold truncate ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                        Document Interrogator
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium flex-shrink-0 ${darkMode ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                        Active
                    </span>
                </div>

                <div className="flex items-center space-x-2 flex-shrink-0">
                    <button
                        onClick={() => window.open(activePdfUrl, '_blank')}
                        className={`p-1.5 sm:p-2 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-gray-400 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400 hover:bg-[#252528]' : 'text-gray-600 bg-white border-gray-200 hover:text-blue-600 hover:bg-gray-50'}`}
                        title={tGlobal.pdf.openInNewTab}
                    >
                        <ExternalLink size={16} />
                    </button>
                    <button
                        onClick={() => setSplitScreen(false, null)}
                        className={`flex items-center space-x-1 p-1.5 sm:px-2.5 sm:py-1.5 shadow-sm hover:shadow-md rounded-lg transition-all border ${darkMode ? 'text-red-400 bg-red-950/20 border-red-900/30 hover:bg-red-900/40' : 'text-red-600 bg-red-50 border-red-200 hover:bg-red-100'}`}
                        title={tGlobal.pdf.closeSplitScreen}
                    >
                        <X size={16} />
                        {isMobile && <span className="text-xs font-medium pr-0.5">Tutup</span>}
                    </button>
                </div>
            </div>

            {/* Content Area dengan Custom Scrollbar */}
            <div className={`flex-1 overflow-y-auto relative p-2 sm:p-4 ${darkMode ? 'bg-[#151517]' : 'bg-gray-200'}`}>
                {activePdfUrl && (activePdfUrl.endsWith('.pdf') || activePdfUrl.includes('/api/')) ? (
                    <Document
                        file={activePdfUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={
                            <div className="flex items-center justify-center h-full w-full text-gray-400 text-sm">
                                Memuat dokumen...
                            </div>
                        }
                        error={
                            <div className="flex items-center justify-center h-full w-full text-red-500 text-sm">
                                {tGlobal.pdf.failLoad}
                            </div>
                        }
                        className="flex flex-col items-center h-full w-full"
                    >
                        {viewMode === 'scroll' && numPages ? (
                            <div className="w-full h-full">
                                <Virtuoso
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
                    </Document>
                ) : (
                    <div className="flex items-center justify-center h-full w-full text-center text-gray-500 text-sm p-4">
                        <p>Format file ini belum mendukung tampilan interaktif di sini.</p>
                    </div>
                )}
            </div>

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
