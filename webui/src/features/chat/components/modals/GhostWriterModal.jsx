import React, { useState } from 'react';
import { useChatStore } from '../../../../stores/chatStore';
import { X, Save, FileText, Download } from 'lucide-react';
import { translations } from '../../../../utils/translations';

const GhostWriterModal = ({ darkMode, theme, language = 'id' }) => {
    const tGlobal = translations[language] || translations.id;
    const { showGhostWriter, ghostWriterContent, setGhostWriter } = useChatStore((state) => ({
        showGhostWriter: state.showGhostWriter,
        ghostWriterContent: state.ghostWriterContent,
        setGhostWriter: state.setGhostWriter
    }));

    const [content, setContent] = useState(ghostWriterContent || tGlobal.ghostWriter.initialDraft);

    if (!showGhostWriter) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
            <div 
                className={`w-full max-w-4xl h-[85vh] rounded-2xl flex flex-col overflow-hidden shadow-2xl border ${
                    darkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'
                }`}
            >
                {/* Header */}
                <div className={`flex items-center justify-between p-4 border-b ${darkMode ? 'border-gray-800 bg-gray-800/50' : 'border-gray-100 bg-gray-50'}`}>
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${darkMode ? 'bg-indigo-500/20 text-indigo-400' : 'bg-indigo-100 text-indigo-600'}`}>
                            <FileText size={20} />
                        </div>
                        <div>
                            <h3 className={`font-semibold text-lg ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                                {tGlobal.ghostWriter.title}
                            </h3>
                            <p className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                                {tGlobal.ghostWriter.subtitle}
                            </p>
                        </div>
                    </div>
                    
                    <button 
                        onClick={() => setGhostWriter(false)}
                        className={`p-2 rounded-full transition-colors ${
                            darkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-500'
                        }`}
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Toolbar */}
                <div className={`flex items-center gap-2 p-2 px-4 border-b ${darkMode ? 'border-gray-800 bg-gray-800/30' : 'border-gray-100 bg-white'}`}>
                    <button className="px-3 py-1.5 text-sm font-medium rounded hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-300">
                        B
                    </button>
                    <button className="px-3 py-1.5 text-sm font-medium rounded hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-300 italic">
                        I
                    </button>
                    <button className="px-3 py-1.5 text-sm font-medium rounded hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-300 underline">
                        U
                    </button>
                    <div className="w-px h-6 bg-gray-300 dark:bg-gray-700 mx-2" />
                    <button className="px-3 py-1.5 text-sm font-medium rounded hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-2 dark:text-gray-300">
                        <Download size={16} /> {tGlobal.ghostWriter.exportPdf}
                    </button>
                </div>

                {/* Editor Area (Textarea for now, can be replaced with TipTap/Quill) */}
                <div className="flex-1 p-0 overflow-hidden relative bg-gray-50 dark:bg-gray-900/50">
                    <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        className={`w-full h-full p-8 resize-none focus:outline-none font-serif text-[15px] leading-relaxed
                            ${darkMode ? 'bg-transparent text-gray-300 placeholder-gray-600' : 'bg-transparent text-gray-800 placeholder-gray-400'}
                        `}
                        placeholder={tGlobal.ghostWriter.placeholder}
                    />
                </div>

                {/* Footer */}
                <div className={`flex items-center justify-end gap-3 p-4 border-t ${darkMode ? 'border-gray-800 bg-gray-800/50' : 'border-gray-100 bg-gray-50'}`}>
                    <button 
                        onClick={() => setGhostWriter(false)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                            darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-200'
                        }`}
                    >
                        {tGlobal.ghostWriter.close}
                    </button>
                    <button 
                        onClick={() => {
                            // save logic
                            setGhostWriter(false);
                        }}
                        className="px-6 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-2 shadow-md hover:shadow-lg transition-all"
                    >
                        <Save size={16} /> {tGlobal.ghostWriter.saveDraft}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default GhostWriterModal;
