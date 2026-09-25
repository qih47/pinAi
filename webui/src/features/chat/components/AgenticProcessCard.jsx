import React, { useState, useEffect } from 'react';
import { 
    Terminal, 
    BookOpen, 
    ChevronDown, 
    ChevronUp, 
    CheckCircle2, 
    Clock, 
    FileText, 
    AlertCircle,
    ExternalLink 
} from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl } from '../../../services/endpoints';
import { translations } from '../../../utils/translations';

/**
 * AgenticProcessCard
 * ==================
 * Menampilkan alur proses autonomous tool (python_calc, docsearch) dengan konsep
 * Timeline Vertikal + Terminal Console (Opsi A - seperti Gambar 2) yang 100% selaras
 * dengan WebSearchWidget bawaan CAKRA AI.
 */
const AgenticProcessCard = ({
    toolData,
    toolType = 'python_calc',
    isStreaming = false,
    hasStartedResponding = false,
    darkMode = true,
    language = 'id',
    statusText
}) => {
    // Parsing payload jika masih string
    const data = React.useMemo(() => {
        if (!toolData) return {};
        if (typeof toolData === 'string') {
            try {
                return JSON.parse(toolData);
            } catch (e) {
                return { raw: toolData };
            }
        }
        return toolData;
    }, [toolData]);

    const resolvedTool = (data.tool || toolType || 'python_calc').toLowerCase();
    const isCalc = resolvedTool.includes('calc');
    const isDoc = resolvedTool.includes('doc');

    const [isOpen, setIsOpen] = useState(() => Boolean(isStreaming && !hasStartedResponding));
    const [elapsedSec, setElapsedSec] = useState(0);

    const setSplitScreen = useChatStore(state => state.setSplitScreen);
    const t = translations[language]?.agentic || translations.id.agentic || {};

    // Ekstraksi kode dan output yang tahan banting (anti kotak kosong)
    const codeContent = data.code || data.script || (typeof data.raw === 'string' ? data.raw : (typeof toolData === 'string' ? toolData : ''));
    const outputContent = data.output || data.result || '';
    const errorContent = data.error || (data.status === 'error' ? (data.output || 'Eksekusi gagal') : null);

    const isExecuting = isStreaming && !outputContent && !data.documents && !data.results;
    const isAnalyzing = isStreaming && (outputContent || data.documents) && !hasStartedResponding;
    const isComplete = hasStartedResponding || (!isStreaming && (outputContent || data.documents || data.stage === 'done'));
    const isError = Boolean(errorContent || data.status === 'error' || data.stage === 'error');

    // Timer durasi eksekusi saat streaming
    useEffect(() => {
        let timer;
        if (isExecuting) {
            timer = setInterval(() => {
                setElapsedSec(prev => +(prev + 0.1).toFixed(1));
            }, 100);
        }
        return () => {
            if (timer) clearInterval(timer);
        };
    }, [isExecuting]);

    // Auto-collapse saat AI mulai mengetik respon teks kelanjutan (persis seperti WebSearchWidget)
    useEffect(() => {
        if (!isStreaming) return;
        if (isComplete) {
            const timer = setTimeout(() => {
                setIsOpen(false);
            }, 800);
            return () => clearTimeout(timer);
        } else {
            setIsOpen(true);
        }
    }, [isComplete, isStreaming]);

    if (!toolData && !isStreaming) return null;

    // Header label
    const getHeaderLabel = () => {
        if (isComplete) {
            if (isCalc) return isError ? (t.calcFailed || "Kalkulasi matematis (terkendala)") : (t.calcComplete || "Hasil kalkulasi matematis presisi");
            if (isDoc) return t.docSearchComplete || "Hasil penelusuran regulasi internal";
            return t.genericComplete || "Hasil proses alat otonom";
        }
        if (statusText) return statusText;
        if (isCalc) {
            if (isExecuting) return (t.calcRunning || "Menjalankan komputasi ({elapsed}s)").replace('{elapsed}', elapsedSec);
            if (isAnalyzing) return t.calcAnalyzing || "Menganalisis hasil komputasi";
            return t.calcDefault || "Kalkulasi matematis via Python Sandbox";
        }
        if (isDoc) {
            if (isExecuting) return (t.docSearching || "Menelusuri regulasi internal ({elapsed}s)").replace('{elapsed}', elapsedSec);
            if (isAnalyzing) return t.docAnalyzing || "Menganalisis dokumen peraturan";
            return t.docSearchDefault || "Pencarian regulasi & SOP internal";
        }
        return t.genericRunning || "Proses alat otonom";
    };

    const displayQuery = data.query || data.intent || (isCalc ? (t.calcDefault || "Kalkulasi matematis via Python Sandbox") : (t.docSearchDefault || "Pencarian regulasi internal"));

    return (
        <div className="my-4 w-full max-w-3xl font-sans">
            {/* Top Level Accordion Header */}
            <div
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 mb-3 cursor-pointer select-none group w-fit"
            >
                <span className={`text-[14px] font-medium transition-colors line-clamp-1 flex items-center gap-2 ${
                    darkMode ? 'text-[#9e9e9e] group-hover:text-[#c4c4c4]' : 'text-slate-600 group-hover:text-slate-900'
                }`}>
                    {isExecuting ? (
                        <>
                            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                            <span>{getHeaderLabel()}</span>
                        </>
                    ) : isAnalyzing ? (
                        <>
                            <span className={`inline-block w-2 h-2 rounded-full animate-pulse ${darkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`} />
                            <span className={darkMode ? 'text-indigo-300' : 'text-indigo-600'}>{getHeaderLabel()}</span>
                        </>
                    ) : isComplete ? (
                        <span className="flex items-center gap-2">
                            {getHeaderLabel()}
                        </span>
                    ) : (
                        getHeaderLabel()
                    )}
                </span>
                <span className={`flex items-center justify-center transition-colors ${
                    darkMode ? 'text-[#888888] group-hover:text-[#c4c4c4]' : 'text-slate-400 group-hover:text-slate-600'
                }`}>
                    {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </span>
            </div>

            {/* Collapsible Timeline Container */}
            <div
                className={`transition-all duration-300 ease-in-out origin-top overflow-hidden relative ${
                    isOpen ? 'max-h-[650px] opacity-100 scale-y-100' : 'max-h-0 opacity-0 scale-y-0'
                }`}
            >
                {/* Timeline Vertical Line */}
                <div className={`absolute left-[9px] top-[14px] bottom-[14px] w-[2px] z-0 ${
                    darkMode ? 'bg-[#333333]' : 'bg-slate-200'
                }`}></div>

                <div className="flex flex-col gap-4 relative z-10 pl-0">
                    {/* Step 1: Execution Details */}
                    <div>
                        <div className="flex items-center gap-3 mb-2.5">
                            <div className={`py-1 px-1 rounded-full z-10 relative flex items-center justify-center ${
                                darkMode ? 'bg-[#1e1e1e]' : 'bg-white border border-slate-200 shadow-sm'
                            }`}>
                                {isCalc ? (
                                    <Terminal className={`w-[14px] h-[14px] flex-shrink-0 ${darkMode ? 'text-emerald-400' : 'text-emerald-600'}`} />
                                ) : (
                                    <BookOpen className={`w-[14px] h-[14px] flex-shrink-0 ${darkMode ? 'text-amber-400' : 'text-amber-600'}`} />
                                )}
                            </div>
                            <span className={`text-[13.5px] font-medium truncate flex-grow ${
                                darkMode ? 'text-[#888888]' : 'text-slate-700'
                            }`} title={data.intent ? `Maksud: ${data.intent}` : undefined}>
                                "{displayQuery}"
                                {data.intent && data.query && data.intent.toLowerCase() !== data.query.toLowerCase() && (
                                    <span className={`ml-2 text-[12px] font-normal opacity-75 hidden sm:inline`}>
                                        ({data.intent})
                                    </span>
                                )}
                            </span>
                            <span className={`text-[12px] whitespace-nowrap ${
                                darkMode ? 'text-[#666666]' : 'text-slate-400'
                            }`}>
                                {isCalc 
                                    ? (t.sandboxExecution || "sandbox execution") 
                                    : (isExecuting && (!data.documents || data.documents.length === 0))
                                        ? (t.searchingReferences || "Mencari referensi...")
                                        : `${data.documents?.length || 0} ${t.referencesCount || (language === 'en' ? 'references' : 'referensi')}`}
                            </span>
                        </div>

                        {/* Inner Terminal / Content Box */}
                        <div className="ml-[26px]">
                            {/* A. TERMINAL CONSOLE (Untuk Python Calc - Gaya Gambar 2) */}
                            {isCalc && (
                                <div className={`rounded-xl border overflow-hidden transition-colors ${
                                    darkMode
                                        ? 'border-[#2a2a2a] bg-[#0c0d0e] shadow-[0_4px_20px_rgba(0,0,0,0.3)]'
                                        : 'border-slate-800 bg-slate-900 text-slate-100 shadow-[0_4px_20px_rgba(0,0,0,0.06)]'
                                }`}>
                                    {/* Top Bar Terminal */}
                                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/5 bg-[#141517]">
                                        <div className="flex items-center gap-2">
                                            <Terminal className="w-3.5 h-3.5 text-gray-400" />
                                            <span className="text-[11.5px] font-mono font-medium text-gray-300">Terminal</span>
                                        </div>
                                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                                            isError 
                                                ? 'text-rose-400 bg-rose-950/60 border-rose-500/20'
                                                : isComplete 
                                                    ? 'text-emerald-400 bg-emerald-950/60 border-emerald-500/20' 
                                                    : 'text-amber-400 bg-amber-950/60 border-amber-500/20'
                                        }`}>
                                            {isError ? 'exit: 1' : isComplete ? 'exit: 0' : 'running...'}
                                        </span>
                                    </div>

                                    {/* Console Body */}
                                    <div className="p-3 text-xs font-mono space-y-2.5 max-h-[260px] overflow-y-auto">
                                        {codeContent && (
                                            <div className="space-y-1">
                                                <div className="text-gray-500 text-[11px] select-none flex items-center gap-1.5">
                                                    <span className="text-emerald-500">&gt;</span>
                                                    <span>cat &lt;&lt; 'EOF' | python3</span>
                                                </div>
                                                <pre className="text-gray-300 whitespace-pre-wrap pl-3 border-l-2 border-emerald-500/40 font-mono text-[12px] leading-relaxed overflow-x-auto">
                                                    {codeContent}
                                                </pre>
                                                <div className="text-gray-500 text-[11px] select-none">
                                                    EOF
                                                </div>
                                            </div>
                                        )}

                                        {/* Output Terminal */}
                                        {outputContent && (
                                            <div className="pt-2 border-t border-white/5">
                                                <div className="text-[10.5px] text-gray-500 uppercase tracking-wider select-none mb-1 font-sans">
                                                    Output:
                                                </div>
                                                <pre className="text-emerald-400 font-semibold whitespace-pre-wrap pl-3 bg-black/40 p-2 rounded font-mono text-[12px]">
                                                    {outputContent}
                                                </pre>
                                            </div>
                                        )}

                                        {/* Error Terminal */}
                                        {errorContent && (
                                            <div className="pt-2 border-t border-rose-500/20">
                                                <pre className="text-rose-400 font-semibold whitespace-pre-wrap pl-3 bg-rose-950/40 p-2 rounded font-mono text-[11.5px]">
                                                    {errorContent}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* B. DOCSEARCH / REGULASI BOX */}
                            {isDoc && (
                                <div className={`rounded-xl border overflow-hidden transition-colors ${
                                    darkMode
                                        ? 'border-[#2a2a2a] bg-[#1c1c1c] shadow-[0_4px_20px_rgba(0,0,0,0.3)]'
                                        : 'border-slate-200/90 bg-white shadow-[0_4px_20px_rgba(0,0,0,0.06)]'
                                }`}>
                                    <div className="flex flex-col max-h-[260px] overflow-y-auto p-1.5 custom-scrollbar space-y-1">
                                        {data.documents && data.documents.length > 0 ? (
                                            data.documents.map((doc, idx) => {
                                                const title = doc.title || doc.judul || doc.name || `Dokumen #${idx + 1}`;
                                                const docId = doc.id || doc.doc_id || doc.dokumen_id;
                                                const regNomor = (doc.nomor && doc.nomor !== 'N/A' && doc.nomor !== 'No Regulasi ----') ? doc.nomor : '';
                                                const rawPath = doc.file_path || (doc.filename && doc.filename.endsWith('.pdf') ? doc.filename : null);
                                                const fileUrl = rawPath ? getUploadUrl(rawPath) : (doc.url && doc.url.endsWith('.pdf') ? doc.url : null);

                                                const handleClickDoc = (e) => {
                                                    e.stopPropagation();
                                                    if (fileUrl) {
                                                        setSplitScreen(true, fileUrl);
                                                    } else if (docId) {
                                                        window.open(`https://peraturan.pindad.com/content/detail/${docId}`, '_blank', 'noopener,noreferrer');
                                                    }
                                                };

                                                return (
                                                    <div 
                                                        key={idx} 
                                                        onClick={handleClickDoc}
                                                        className={`flex items-center justify-between p-2.5 rounded-lg border transition-all group/item cursor-pointer ${
                                                            darkMode 
                                                                ? 'border-white/5 bg-[#141414] hover:bg-[#222222] hover:border-white/10' 
                                                                : 'border-slate-100 bg-slate-50 hover:bg-white hover:border-slate-200 hover:shadow-sm'
                                                        }`}
                                                    >
                                                        <div className="flex items-start gap-2.5 overflow-hidden flex-1 pr-3">
                                                            <FileText className={`w-4 h-4 flex-shrink-0 mt-0.5 transition-colors ${
                                                                darkMode ? 'text-amber-400 group-hover/item:text-amber-300' : 'text-amber-600 group-hover/item:text-amber-700'
                                                            }`} />
                                                            <div className="flex flex-col min-w-0 flex-1">
                                                                <span className={`text-[12.5px] font-medium leading-snug line-clamp-2 transition-colors ${
                                                                    darkMode ? 'text-[#d4d4d4] group-hover/item:text-white' : 'text-slate-800 group-hover/item:text-indigo-600'
                                                                }`}>
                                                                    {title}
                                                                </span>

                                                                {/* Opsi 2: Metadata Dokumen Ringkas & Informatif */}
                                                                <div className="flex items-center gap-1.5 mt-1 flex-wrap text-[10.5px]">
                                                                    {(doc.cache_hit || doc._from_session_brain) && (
                                                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${
                                                                            darkMode 
                                                                                ? 'bg-purple-500/15 text-purple-300 border border-purple-500/25' 
                                                                                : 'bg-purple-50 text-purple-700 border border-purple-200'
                                                                        }`}>
                                                                            {t.fromSessionBrain || (language === 'en' ? '🧠 Session Memory' : '🧠 Memori Sesi')}
                                                                        </span>
                                                                    )}
                                                                    {doc.jenis && (
                                                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${
                                                                            darkMode 
                                                                                ? 'bg-amber-500/15 text-amber-300 border border-amber-500/20' 
                                                                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                                                                        }`}>
                                                                            {doc.jenis}
                                                                        </span>
                                                                    )}
                                                                    {regNomor && (
                                                                        <span className={`${darkMode ? 'text-gray-400 font-mono' : 'text-slate-500 font-mono'}`}>
                                                                            {regNomor}
                                                                        </span>
                                                                    )}
                                                                    {doc.stataktif && (
                                                                        <>
                                                                            <span className="text-gray-500 select-none">•</span>
                                                                            <span className={`font-medium ${
                                                                                doc.stataktif.toLowerCase().includes('berlaku') 
                                                                                    ? (darkMode ? 'text-emerald-400' : 'text-emerald-600') 
                                                                                    : (darkMode ? 'text-rose-400' : 'text-rose-600')
                                                                            }`}>
                                                                                {doc.stataktif}
                                                                            </span>
                                                                        </>
                                                                    )}
                                                                    {doc.total_pages && (
                                                                        <>
                                                                            <span className="text-gray-500 select-none">•</span>
                                                                            <span className={`${darkMode ? 'text-gray-400' : 'text-slate-500'}`}>
                                                                                {doc.total_pages} {t.pages || (language === 'en' ? 'Pages' : 'Halaman')}
                                                                            </span>
                                                                        </>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* Icon Aksi: Buka PDF / Detail Integrator */}
                                                        <div className="flex items-center gap-1 flex-shrink-0">
                                                            <div 
                                                                className={`px-2 py-1 rounded-md text-[10px] font-semibold flex items-center gap-1.5 transition-all ${
                                                                    darkMode 
                                                                        ? 'bg-white/5 group-hover/item:bg-amber-500/20 text-gray-400 group-hover/item:text-amber-300 border border-white/5 group-hover/item:border-amber-500/30' 
                                                                        : 'bg-slate-200/60 group-hover/item:bg-amber-50 text-slate-600 group-hover/item:text-amber-700 border border-slate-200 group-hover/item:border-amber-300'
                                                                }`}
                                                                title={fileUrl ? (t.openPdfTooltip || "Buka Dokumen PDF (Integrator Split-Screen)") : (t.openDocTooltip || "Buka Portal Peraturan Resmi")}
                                                            >
                                                                <ExternalLink className="w-3 h-3" />
                                                                <span>{fileUrl ? (t.openPdf || 'PDF') : (t.openDoc || 'Buka')}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })
                                        ) : (
                                            <div className={`p-3 text-[12px] ${darkMode ? 'text-gray-400' : 'text-slate-600'}`}>
                                                {isExecuting ? (
                                                    <div className="flex items-center gap-2">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                                                        <span>{t.searchingInternalArchive || (language === 'en' ? "Searching internal regulation archive..." : "Menelusuri arsip regulasi internal...")}</span>
                                                    </div>
                                                ) : (
                                                    data.message || t.noMatchingRegulation || (language === 'en' ? "No matching internal regulation documents found." : "Tidak ditemukan dokumen regulasi internal yang cocok.")
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Step 2: Analyzing / Done */}
                    {(outputContent || data.documents || isComplete) && (
                        <div className="flex flex-col gap-3 mt-1 ml-[1px]">
                            <div className="flex items-center gap-3">
                                <div className={`py-0.5 rounded-full z-10 relative flex items-center justify-center w-[18px] ${
                                    darkMode ? 'bg-[#1e1e1e]' : 'bg-white border border-slate-200 shadow-sm'
                                }`}>
                                    {isAnalyzing ? (
                                        <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
                                    ) : (
                                        <Clock className={`w-[14px] h-[14px] ${darkMode ? 'text-[#888888]' : 'text-slate-400'}`} />
                                    )}
                                </div>
                                <span className={`text-[13.5px] ${
                                    isAnalyzing
                                        ? (darkMode ? 'text-indigo-300 font-medium' : 'text-indigo-600 font-medium')
                                        : (darkMode ? 'text-[#888888]' : 'text-slate-500')
                                }`}>
                                    {isCalc ? (t.analyzingCalcResults || "Menganalisis hasil kalkulasi...") : (t.analyzingDocResults || "Menganalisis hasil penelusuran...")}
                                </span>
                            </div>

                            {isComplete && (
                                <div className="flex items-center gap-3">
                                    <div className={`py-0.5 rounded-full z-10 relative flex items-center justify-center w-[18px] ${
                                        darkMode ? 'bg-[#1e1e1e]' : 'bg-white border border-slate-200 shadow-sm'
                                    }`}>
                                        {isError ? (
                                            <AlertCircle className="w-[14px] h-[14px] text-rose-500" />
                                        ) : (
                                            <CheckCircle2 className={`w-[14px] h-[14px] ${darkMode ? 'text-emerald-400' : 'text-emerald-600'}`} />
                                        )}
                                    </div>
                                    <span className={`text-[13.5px] font-medium ${
                                        isError
                                            ? 'text-rose-500'
                                            : (darkMode ? 'text-emerald-400' : 'text-emerald-600')
                                    }`}>
                                        {isError ? (t.doneWithError || "Selesai (dengan catatan error)") : (t.done || (language === 'en' ? "Done" : "Selesai"))}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgenticProcessCard;
