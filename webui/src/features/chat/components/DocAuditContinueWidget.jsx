import React, { useState, useMemo, useEffect } from 'react';
import { FileSearch, ArrowRight, CheckCircle2, Sparkles, Layers, RotateCcw } from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';
import { translations } from '../../../utils/translations';

const DocAuditContinueWidget = ({ 
    rawContent, 
    darkMode = true, 
    messageIndex = null, 
    isLastMessage = false, 
    language = 'id' 
}) => {
    const t = translations[language]?.docAudit || translations.id.docAudit || {};
    const [localProcessing, setLocalProcessing] = useState(false);

    const messages = useChatStore(state => state.messages);
    const globalIsStreaming = useChatStore(state => state.isStreaming);

    let data = null;
    try {
        if (typeof rawContent === 'string') {
            data = JSON.parse(rawContent.trim());
        } else if (typeof rawContent === 'object' && rawContent !== null) {
            data = rawContent;
        }
    } catch (e) {
        // Fallback jika formatting kode mengandung teks ekstra
        try {
            const match = rawContent.match(/\{[\s\S]*\}/);
            if (match) {
                data = JSON.parse(match[0]);
            }
        } catch (err) {
            console.error('[DocAuditContinueWidget] Parse error:', err);
        }
    }

    const isCompletedStatus = Boolean(
        data?.is_complete || 
        (typeof data?.status === 'string' && data?.status.toUpperCase().includes('COMPLET'))
    );
    const totalPages = Number(data?.total_pages || data?.total_pages_audited || 5);
    const currentEnd = isCompletedStatus ? totalPages : Number(data?.current_end || totalPages);
    const currentBatch = data?.current_batch || (isCompletedStatus ? `1-${totalPages}` : "1-5");
    const nextBatch = isCompletedStatus ? null : data?.next_batch;
    const isComplete = Boolean(isCompletedStatus || currentEnd >= totalPages);

    const progressPercent = Math.min(Math.round((currentEnd / totalPages) * 100), 100);

    // ── EVALUASI RIWAYAT PERCAKAPAN (CONVERSATION HISTORY INSPECTION) ──
    const continuationStatus = useMemo(() => {
        if (!data || isComplete) return { status: 'completed' };

        // 1. Periksa pesan-pesan setelah pesan asisten ini (idx > messageIndex)
        if (messageIndex !== null && Array.isArray(messages) && messages.length > messageIndex + 1) {
            const subsequent = messages.slice(messageIndex + 1);

            for (let i = 0; i < subsequent.length; i++) {
                const subMsg = subsequent[i];

                if (subMsg.role === 'assistant') {
                    const content = subMsg.content || '';
                    const isStreaming = Boolean(subMsg.isStreaming);
                    const isError = Boolean(
                        subMsg.isError || 
                        content.includes('Gagal memuat balasan') ||
                        (content.includes('Respons dihentikan') && !content.includes('doc-audit-continue'))
                    );

                    if (isStreaming) {
                        return { status: 'processing' };
                    }

                    if (isError) {
                        return { status: 'failed' };
                    }

                    // Jika ada widget audit di asisten berikutnya
                    if (
                        content.includes('doc-audit-continue') || 
                        content.includes('docauditcontinue') || 
                        content.includes('audit-continue') ||
                        content.includes('doc-audit-final')
                    ) {
                        return { status: 'completed' };
                    }

                    // Jika asisten sudah memberikan jawaban audit teks yang valid
                    if (content.length > 50 && !isError) {
                        return { status: 'completed' };
                    }
                }
            }

            // Cek jika user setelahnya sudah mengirim pesan dan streaming sedang aktif
            const subsequentUser = subsequent.find(m => m.role === 'user');
            if (subsequentUser) {
                if (globalIsStreaming) {
                    return { status: 'processing' };
                }
                return { status: 'completed' };
            }
        }

        // 2. Global fallback: Cek apakah di riwayat terdapat batch halaman yang lebih tinggi
        if (messageIndex !== null && Array.isArray(messages)) {
            for (let i = messageIndex + 1; i < messages.length; i++) {
                const msg = messages[i];
                if (msg.role === 'assistant' && msg.content) {
                    const matchEnd = msg.content.match(/"current_end"\s*:\s*(\d+)/);
                    if (matchEnd && Number(matchEnd[1]) > currentEnd) {
                        return { status: 'completed' };
                    }
                    if (msg.content.includes('"is_complete": true') || msg.content.includes('"is_complete":true')) {
                        return { status: 'completed' };
                    }
                }
            }
        }

        return { status: 'idle' };
    }, [data, messages, messageIndex, isComplete, currentEnd, globalIsStreaming]);

    // Reset local processing jika status di riwayat sudah tersinkronisasi
    useEffect(() => {
        if (continuationStatus.status === 'completed' || continuationStatus.status === 'failed') {
            setLocalProcessing(false);
        }
    }, [continuationStatus.status]);

    if (!data) return null;

    const isProcessing = Boolean(localProcessing || continuationStatus.status === 'processing');
    const isAlreadyContinued = continuationStatus.status === 'completed';
    const isFailed = continuationStatus.status === 'failed';

    const isButtonDisabled = Boolean(isProcessing || isAlreadyContinued || isComplete);

    const handleContinue = () => {
        if (isButtonDisabled) return;
        setLocalProcessing(true);

        const promptText = nextBatch 
            ? (t.promptContinue ? t.promptContinue.replace('{nextBatch}', nextBatch) : `Lanjut audit Halaman ${nextBatch}`)
            : (t.promptFallback || `Lanjutkan audit dokumen ke batch halaman selanjutnya`);

        window.dispatchEvent(new CustomEvent('cakra_send_prompt', {
            detail: { text: promptText }
        }));
    };

    const nextBatchRangeStr = nextBatch || (t.toEnd ? t.toEnd.replace('{range}', `${currentEnd + 1}`) : `${currentEnd + 1} s/d selesai`);

    return (
        <div 
            className={`my-4 p-4 rounded-xl border transition-all duration-300 select-none shadow-sm ${
                darkMode 
                    ? 'bg-[#18181b]/90 border-blue-500/30 text-gray-200' 
                    : 'bg-blue-50/70 border-blue-200 text-gray-800'
            }`}
        >
            {/* Header info bar */}
            <div className="flex items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2 min-w-0">
                    <div className={`p-1.5 rounded-lg ${darkMode ? 'bg-blue-600/20 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                        <FileSearch size={16} />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <span className="text-xs font-bold tracking-tight flex items-center gap-1.5">
                            {t.title || "Audit Dokumen Kedinasan"}
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                                isComplete 
                                    ? (darkMode ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-emerald-100 text-emerald-700 border border-emerald-200')
                                    : (darkMode ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-blue-100 text-blue-700 border border-blue-200')
                            }`}>
                                {isComplete 
                                    ? (t.completedBadge || 'Selesai 100%') 
                                    : (t.batchBadge ? t.batchBadge.replace('{batch}', currentBatch) : `Batch Hal ${currentBatch}`)
                                }
                            </span>
                        </span>
                        <span className="text-[11px] opacity-70">
                            {isComplete 
                                ? (t.completedSubtitle ? t.completedSubtitle.replace('{totalPages}', totalPages) : `Seluruh ${totalPages} halaman telah tuntas diperiksa`) 
                                : (t.batchSubtitle ? t.batchSubtitle.replace('{batch}', currentBatch).replace('{totalPages}', totalPages) : `Pemeriksaan Halaman ${currentBatch} dari total ${totalPages} Halaman`)
                            }
                        </span>
                    </div>
                </div>

                <div className="text-right flex-shrink-0">
                    <span className="text-xs font-bold font-mono text-blue-500">{progressPercent}%</span>
                </div>
            </div>

            {/* Visual Progress Bar */}
            <div className={`w-full h-2 rounded-full overflow-hidden mb-3.5 ${darkMode ? 'bg-zinc-800' : 'bg-gray-200'}`}>
                <div 
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{ 
                        width: `${progressPercent}%`,
                        background: isComplete
                            ? 'linear-gradient(90deg, #10b981, #059669)'
                            : 'linear-gradient(90deg, #3b82f6, #6366f1)'
                    }}
                />
            </div>

            {/* Action Bar / Completion State */}
            {isComplete ? (
                <div className="flex flex-col gap-2">
                    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium ${
                        darkMode ? 'bg-emerald-950/40 border border-emerald-500/20 text-emerald-300' : 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                    }`}>
                        <CheckCircle2 size={15} className="text-emerald-500 flex-shrink-0" />
                        <span>{t.completedBox ? t.completedBox.replace('{totalPages}', totalPages) : `Audit dokumen telah selesai sepenuhnya dari Halaman 1 hingga ${totalPages}.`}</span>
                    </div>
                    {(data.critical_findings !== undefined || data.major_findings !== undefined || data.minor_findings !== undefined) && (
                        <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px]">
                            {data.critical_findings !== undefined && (
                                <span className={`px-2 py-0.5 rounded-md font-medium ${darkMode ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-red-100 text-red-700 border border-red-200'}`}>
                                    {t.criticalFindings ? t.criticalFindings.replace('{count}', data.critical_findings) : `Kritis: ${data.critical_findings}`}
                                </span>
                            )}
                            {data.major_findings !== undefined && (
                                <span className={`px-2 py-0.5 rounded-md font-medium ${darkMode ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-amber-100 text-amber-700 border border-amber-200'}`}>
                                    {t.majorFindings ? t.majorFindings.replace('{count}', data.major_findings) : `Mayor: ${data.major_findings}`}
                                </span>
                            )}
                            {data.minor_findings !== undefined && (
                                <span className={`px-2 py-0.5 rounded-md font-medium ${darkMode ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-blue-100 text-blue-700 border border-blue-200'}`}>
                                    {t.minorFindings ? t.minorFindings.replace('{count}', data.minor_findings) : `Minor: ${data.minor_findings}`}
                                </span>
                            )}
                            {data.recommendation && (
                                <span className={`text-[11px] font-medium ml-1 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                                    💡 {data.recommendation}
                                </span>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pt-1 border-t border-dashed border-gray-500/20">
                    <div className="flex items-center gap-1.5 text-xs opacity-75">
                        <Layers size={13} />
                        <span>{t.nextBatch || "Batch berikutnya:"} <strong className="text-blue-500">{t.pageRange ? t.pageRange.replace('{nextBatch}', nextBatchRangeStr) : `Halaman ${nextBatchRangeStr}`}</strong></span>
                    </div>

                    {/* Tombol Interaktif dengan State History & Fail-Safe */}
                    {isAlreadyContinued ? (
                        <div className={`flex items-center justify-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold cursor-not-allowed border ${
                            darkMode 
                                ? 'bg-zinc-800/80 border-zinc-700/60 text-emerald-400/90' 
                                : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                        }`}>
                            <CheckCircle2 size={13} className="text-emerald-500 flex-shrink-0" />
                            <span>{t.completedBtn || "✓ Telah Dilanjutkan"}</span>
                        </div>
                    ) : (
                        <button
                            type="button"
                            onClick={handleContinue}
                            disabled={isButtonDisabled}
                            className={`flex items-center justify-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm ${
                                isProcessing
                                    ? (darkMode ? 'bg-zinc-800 text-gray-500 cursor-not-allowed border border-zinc-700' : 'bg-gray-200 text-gray-400 cursor-not-allowed')
                                    : isFailed
                                    ? (darkMode 
                                        ? 'bg-amber-600/20 border border-amber-500/40 text-amber-300 hover:bg-amber-600/30 active:scale-[0.98]' 
                                        : 'bg-amber-100 border border-amber-300 text-amber-800 hover:bg-amber-200 active:scale-[0.98]')
                                    : (darkMode
                                        ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-500/20 hover:shadow-md active:scale-[0.98]'
                                        : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-blue-500/20 hover:shadow-md active:scale-[0.98]')
                            }`}
                        >
                            {isProcessing ? (
                                <>
                                    <Sparkles size={13} className="animate-spin text-blue-400" />
                                    <span>{t.processingBtn || "Sedang Memproses..."}</span>
                                </>
                            ) : isFailed ? (
                                <>
                                    <RotateCcw size={13} className="text-amber-400" />
                                    <span>{t.failedBtn ? t.failedBtn.replace('{nextBatch}', nextBatch || '') : `⚠️ Gagal - Coba Lagi Halaman ${nextBatch || ''}`}</span>
                                </>
                            ) : (
                                <>
                                    <Sparkles size={13} />
                                    <span>{t.continueBtn ? t.continueBtn.replace('{nextBatch}', nextBatchRangeStr) : `Lanjut Audit Halaman ${nextBatchRangeStr}`}</span>
                                    <ArrowRight size={13} />
                                </>
                            )}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default DocAuditContinueWidget;
