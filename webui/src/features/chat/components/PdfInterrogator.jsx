import React from 'react';
import { useChatStore } from '../../../stores/chatStore';
import { X, ExternalLink } from 'lucide-react';

const PdfInterrogator = () => {
    const { isSplitScreen, activePdfUrl, setSplitScreen } = useChatStore((state) => ({
        isSplitScreen: state.isSplitScreen,
        activePdfUrl: state.activePdfUrl,
        setSplitScreen: state.setSplitScreen
    }));

    if (!isSplitScreen || !activePdfUrl) return null;

    return (
        <div className="flex flex-col h-full bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 shadow-xl transition-all duration-300 w-1/2">
            {/* Toolbar */}
            <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Document Interrogator
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                        Active
                    </span>
                </div>
                
                <div className="flex items-center space-x-2">
                    <button
                        onClick={() => window.open(activePdfUrl, '_blank')}
                        className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-gray-700 rounded transition-colors"
                        title="Open in new tab"
                    >
                        <ExternalLink size={16} />
                    </button>
                    <button
                        onClick={() => setSplitScreen(false, null)}
                        className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-gray-700 rounded transition-colors"
                        title="Close Split Screen"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {activePdfUrl.endsWith('.pdf') || activePdfUrl.includes('/api/') ? (
                    <iframe
                        src={`${activePdfUrl}#toolbar=0&navpanes=0`}
                        className="w-full h-full border-0"
                        title="Document Viewer"
                    />
                ) : (
                    <div className="flex items-center justify-center h-full p-4 text-center text-gray-500">
                        <p>Format file ini belum mendukung tampilan interaktif di sini.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PdfInterrogator;
