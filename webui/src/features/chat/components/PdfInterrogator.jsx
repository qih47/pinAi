import React, { useState } from 'react';
import { useChatStore } from '../../../stores/chatStore';
import { X, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Virtuoso } from 'react-virtuoso';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Konfigurasi worker react-pdf untuk Vite
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

const PdfInterrogator = ({ darkMode }) => {
    const { isSplitScreen, activePdfUrl, setSplitScreen } = useChatStore((state) => ({
        isSplitScreen: state.isSplitScreen,
        activePdfUrl: state.activePdfUrl,
        setSplitScreen: state.setSplitScreen
    }));

    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [scale, setScale] = useState(1.0);
    const [viewMode, setViewMode] = useState('scroll'); // 'scroll' atau 'page'

    if (!isSplitScreen || !activePdfUrl) return null;

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

    return (
        <div className={`flex flex-col h-full shadow-xl transition-all duration-300 w-1/2 ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
            {/* Toolbar Atas */}
            <div className={`flex items-center justify-between p-3 ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center space-x-2">
                    <span className={`text-sm font-medium ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                        Document Interrogator
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs ${darkMode ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                        Active
                    </span>
                </div>

                <div className="flex items-center space-x-2">
                    <button
                        onClick={() => window.open(activePdfUrl, '_blank')}
                        className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-500 bg-white border-gray-200 hover:text-blue-600'}`}
                        title="Open in new tab"
                    >
                        <ExternalLink size={16} />
                    </button>
                    <button
                        onClick={() => setSplitScreen(false, null)}
                        className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-red-400' : 'text-gray-500 bg-white border-gray-200 hover:text-red-600'}`}
                        title="Close Split Screen"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Content Area dengan Custom Scrollbar bawaan CSS Global */}
            <div className={`flex-1 overflow-y-auto relative p-4 ${darkMode ? 'bg-[#151517]' : 'bg-gray-200'}`}>
                {activePdfUrl.endsWith('.pdf') || activePdfUrl.includes('/api/') ? (
                    <Document
                        file={activePdfUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={
                            <div className="flex items-center justify-center h-full w-full text-gray-500">
                                Memuat dokumen...
                            </div>
                        }
                        error={
                            <div className="flex items-center justify-center h-full w-full text-red-500">
                                Gagal memuat dokumen.
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
                                        <div className="flex justify-center mb-6">
                                            <div className="relative shadow-2xl bg-white">
                                                <Page
                                                    pageNumber={index + 1}
                                                    scale={scale}
                                                    renderTextLayer={true}
                                                    renderAnnotationLayer={true}
                                                    className={`transition-opacity ${darkMode ? 'opacity-90' : 'opacity-100'}`}
                                                />
                                            </div>
                                        </div>
                                    )}
                                />
                            </div>
                        ) : (
                            numPages && (
                                <div className="relative shadow-2xl bg-white mt-4">
                                    <Page
                                        pageNumber={pageNumber}
                                        scale={scale}
                                        renderTextLayer={true}
                                        renderAnnotationLayer={true}
                                        className={`transition-opacity ${darkMode ? 'opacity-90' : 'opacity-100'}`}
                                    />
                                </div>
                            )
                        )}
                    </Document>
                ) : (
                    <div className="flex items-center justify-center h-full w-full text-center text-gray-500">
                        <p>Format file ini belum mendukung tampilan interaktif di sini.</p>
                    </div>
                )}
            </div>

            {/* Toolbar Bawah: Pagination & Zoom */}
            {numPages && (
                <div className={`flex items-center justify-between p-3  ${darkMode ? 'bg-[#151517] border-[#2a2a2d]' : 'bg-white border-gray-200'}`}>
                    <div className="flex items-center space-x-2">
                        <button
                            onClick={zoomOut}
                            className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-500 bg-white border-gray-200 hover:text-blue-600'}`}
                            title="Zoom Out"
                        >
                            <ZoomOut size={16} />
                        </button>
                        <span className={`text-xs font-medium w-12 text-center ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                            {Math.round(scale * 100)}%
                        </span>
                        <button
                            onClick={zoomIn}
                            className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-500 bg-white border-gray-200 hover:text-blue-600'}`}
                            title="Zoom In"
                        >
                            <ZoomIn size={16} />
                        </button>
                    </div>

                    <div className="flex items-center space-x-3">
                        {/* Toggle Mode Scroll / Page */}
                        <button
                            onClick={() => setViewMode(viewMode === 'scroll' ? 'page' : 'scroll')}
                            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${darkMode ? 'text-gray-300 bg-[#2a2a2d] hover:bg-gray-700' : 'text-gray-600 bg-gray-100 hover:bg-gray-200'}`}
                        >
                            {viewMode === 'scroll' ? 'Mode: Scroll' : 'Mode: Page'}
                        </button>

                        {viewMode === 'page' && (
                            <>
                                <button
                                    disabled={pageNumber <= 1}
                                    onClick={() => changePage(-1)}
                                    className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all disabled:opacity-50 disabled:hover:shadow-sm disabled:hover:translate-y-0 active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-500 bg-white border-gray-200 hover:text-blue-600'}`}
                                >
                                    <ChevronLeft size={16} />
                                </button>
                                <span className={`text-xs font-medium ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                                    Hal {pageNumber} dari {numPages}
                                </span>
                                <button
                                    disabled={pageNumber >= numPages}
                                    onClick={() => changePage(1)}
                                    className={`p-1.5 shadow-sm hover:shadow-md hover:-translate-y-0.5 rounded transition-all disabled:opacity-50 disabled:hover:shadow-sm disabled:hover:translate-y-0 active:translate-y-0 active:shadow-sm border ${darkMode ? 'text-gray-500 bg-[#1e1e20] border-[#2a2a2d] hover:text-blue-400' : 'text-gray-500 bg-white border-gray-200 hover:text-blue-600'}`}
                                >
                                    <ChevronRight size={16} />
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PdfInterrogator;
