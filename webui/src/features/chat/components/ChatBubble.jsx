import React, { useState, useEffect, useRef, memo } from 'react';
import CakraResponseRenderer from './CakraResponseRenderer';
import SourceCitation from './SourceCitation';
import RAGMetrics from './RAGMetrics';
import FileGenerationCard from './FileGenerationCard';
import FileProcessLog from './FileProcessLog';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
import { useChatStore } from '../../../stores/chatStore';
import UserBubble from './UserBubble';
import apiClient from '../../../services/apiClient';

const toastFloatingStyle = {
    position: 'fixed',
    top: '24px',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#1e293b',
    color: '#e2e8f0',
    padding: '10px 20px',
    borderRadius: '8px',
    fontSize: '13px',
    fontWeight: 500,
    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(99, 102, 241, 0.3)',
    border: '1px solid rgba(99, 102, 241, 0.2)',
    zIndex: 99999,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    animation: 'fadeInUp 0.2s ease-out'
};

function formatThinkingPhase(thought) {
    if (!thought) return "CAKRA sedang berpikir";

    // Gunakan lastIndexOf agar selalu menangkap fase terakhir (paling baru)
    const phases = [
        { key: "jalur", label: "🚦 Layer 0: Menganalisis intent & jalur..." },
        { key: "Gateway", label: "🚦 Layer 0: Menganalisis intent & jalur..." },
        { key: "dokumen", label: "📚 RAG: Mencari regulasi internal Pindad..." },
        { key: "RAG", label: "📚 RAG: Mencari regulasi internal Pindad..." },
        { key: "cepat", label: "✍️ Layer 2: Menyusun formulasi respons..." },
        { key: "respons", label: "✍️ Layer 2: Menyusun formulasi respons..." },
        { key: "Gemma", label: "✍️ Layer 2: Menyusun formulasi respons..." },
        { key: "LANGKAH 1", label: "🔍 Mencari dokumen relevan..." },
        { key: "SELEKSI DOKUMEN", label: "🔍 Mencari dokumen relevan..." },
        { key: "LANGKAH 2", label: "🧠 Analisa isi dokumen..." },
        { key: "ANALISIS ISI", label: "🧠 Analisa isi dokumen..." },
        { key: "LANGKAH 3", label: "✍️ Membuat Response..." },
        { key: "RENCANA JAWABAN", label: "✍️ Membuat Response..." },
        { key: "PDF", label: "📄 Membaca lampiran PDF..." },
        { key: "visual", label: "🖼️ Menganalisis visual..." }
    ];

    let lastIndex = -1;
    let activePhase = "CAKRA sedang berpikir";

    for (const phase of phases) {
        const idx = thought.lastIndexOf(phase.key);
        if (idx > lastIndex) {
            lastIndex = idx;
            activePhase = phase.label;
        }
    }
    return activePhase;
}

const ChatBubble = memo(function ChatBubble({ msg, idx, darkMode, theme, isThinking, isStreamingText, searchQuery = '', isLastMessage, onFileClick, setPreviewImage, onOpenArtifact, handleDownloadAllArtifacts, handleDownloadArtifact }) {
    const [showToast, setShowToast] = useState(false);
    const [toastMsg, setToastMsg] = useState('');

    const executeTextCopy = async (textToCopy) => {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(textToCopy);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = textToCopy;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
            setToastMsg('Teks berhasil disalin! 📋');
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        } catch (err) {
            console.error(err);
        }
    };

    const globalIsThinking = useChatStore((state) => state.isThinking);
    const globalIsStreaming = useChatStore((state) => state.isStreaming);
    const activeIsolatedDocId = useChatStore((state) => state.activeIsolatedDocId);
    const setContextIsolation = useChatStore((state) => state.setContextIsolation);

    if (msg.role === 'user') {
        return (
            <UserBubble
                msg={msg}
                idx={idx}
                darkMode={darkMode}
                theme={theme}
                executeTextCopy={executeTextCopy}
                showToast={showToast}
                toastMsg={toastMsg}
                searchQuery={searchQuery}
                onFileClick={onFileClick}
                setPreviewImage={setPreviewImage}
            />
        );
    }

    const isThisMessageStreaming = msg.isStreaming === true;
    const isThinkingMsg = isThisMessageStreaming && globalIsThinking && (!msg.content || msg.content === '');
    const isStreamingMsg = isThisMessageStreaming && msg.content !== '';
    const isActive = isThinkingMsg || isStreamingMsg;

    // 🔥 Smooth transition & animasi untuk teks berpikir
    const [displayThought, setDisplayThought] = useState("CAKRA sedang berpikir");
    const [isThoughtVisible, setIsThoughtVisible] = useState(true);
    const thoughtTimerRef = useRef(null);

    useEffect(() => {
        if (!isThinkingMsg) return;

        // PRIORITIZE msg.statusMessage (e.g. from RAG SSE status event) over static fallback
        const nextThought = msg.statusMessage ? msg.statusMessage : formatThinkingPhase(msg.thought);

        if (nextThought !== displayThought) {
            if (thoughtTimerRef.current) {
                clearTimeout(thoughtTimerRef.current);
            }
            setIsThoughtVisible(false);

            thoughtTimerRef.current = setTimeout(() => {
                setDisplayThought(nextThought);
                setIsThoughtVisible(true);
                thoughtTimerRef.current = null;
            }, 250);
        }

        return () => {
            if (thoughtTimerRef.current) clearTimeout(thoughtTimerRef.current);
        };
    }, [msg.thought, msg.statusMessage, isThinkingMsg, displayThought]);

    return (
        <div style={styles.assistantRow}>
            <div style={styles.assistantMessageWrapper}>
                <div style={styles.assistantHeader}>
                    <div style={styles.avatarWrap}>
                        <img
                            src={cakraLogo}
                            alt="CAKRA"
                            style={{
                                width: 25,
                                height: 25,
                                borderRadius: 8,
                                objectFit: 'cover',
                                background: 'transparent',
                                animation: isActive ? 'cakraSpin 1.2s linear infinite' : 'none',
                                transition: 'transform 0.3s ease',
                                transform: isActive ? undefined : 'rotate(0deg)',
                            }}
                        />
                        {isActive && (
                            <span style={{
                                ...styles.statusDot,
                                background: isThinkingMsg ? '#ef4444' : '#10b981',
                                borderColor: theme.mainBg
                            }} />
                        )}
                    </div>
                    {isThinkingMsg ? (
                        <span style={{ display: 'flex', alignItems: 'center', marginLeft: 10, overflow: 'hidden', opacity: isThoughtVisible ? 1 : 0, transition: 'opacity 0.2s ease' }}>
                            <span
                                style={{
                                    fontSize: 14,
                                    fontStyle: 'italic',
                                    background: 'linear-gradient(90deg, #94a3b8 0%, #e2e8f0 50%, #94a3b8 100%)',
                                    backgroundSize: '200% 100%',
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                    backgroundClip: 'text',
                                    animation: 'shimmerFlow 2.5s linear infinite',
                                    display: 'inline-block',
                                    whiteSpace: 'nowrap'
                                }}
                            >
                                {displayThought}
                            </span>
                            <span style={{ display: 'inline-flex', marginLeft: 4, alignItems: 'baseline' }}>
                                <span style={{ fontSize: 18, color: theme.secondaryText, animation: 'dotBounce 1.4s infinite ease-in-out', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 18, color: theme.secondaryText, animation: 'dotBounce 1.4s infinite ease-in-out 0.2s', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 18, color: theme.secondaryText, animation: 'dotBounce 1.4s infinite ease-in-out 0.4s', display: 'inline-block' }}>.</span>
                            </span>
                        </span>
                    ) : (
                        <span style={{ ...styles.avatarLabel, color: theme.textColor, marginLeft: 8, transition: 'opacity 0.3s' }}>
                            CAKRA AI
                        </span>
                    )}
                </div>

                <div style={styles.assistantContent} className="assistant-content-container">
                    <div style={{ ...styles.assistantText, color: theme.textColor, width: '100%' }}>

                        {/* 🔥 Pisahkan preamble dan explanation menggunakan placeholder CAKRA_FILE_PROCESS_LOG 🔥 */}
                        {(() => {
                            const rawContent = msg.content || '';
                            const logRegex = /\[\[CAKRA_FILE_PROCESS_LOG(?:_(\d+))?\]\]/;
                            const parts = rawContent.split(logRegex);

                            const fileGens = msg.fileGenerations || [];
                            const highestBatchIndex = fileGens.reduce((max, fg) => Math.max(max, fg.batchIndex || 0), 0);

                            if (parts.length === 1) {
                                return (
                                    <CakraResponseRenderer
                                        rawContent={parts[0]}
                                        thinkingContent={msg.thinking || msg.thought || ''}
                                        isStreaming={isThisMessageStreaming}
                                        darkMode={darkMode}
                                        theme={theme}
                                        searchQuery={searchQuery}
                                        statusMessage={msg.statusMessage}
                                        middleContent={fileGens.length > 0 ? (
                                            <FileProcessLog 
                                                fileGenerations={fileGens} 
                                                darkMode={darkMode} 
                                                batchIndex={0} 
                                                isFinalBatch={true} 
                                            />
                                        ) : null}
                                    />
                                );
                            }

                            const renderedParts = [];
                            
                            renderedParts.push(
                                <CakraResponseRenderer
                                    key="renderer-0"
                                    rawContent={parts[0]}
                                    thinkingContent={msg.thinking || msg.thought || ''}
                                    isStreaming={isThisMessageStreaming}
                                    darkMode={darkMode}
                                    theme={theme}
                                    searchQuery={searchQuery}
                                    statusMessage={msg.statusMessage}
                                />
                            );

                            for (let i = 1; i < parts.length; i += 2) {
                                const bIdx = parts[i] ? parseInt(parts[i], 10) : 0;
                                const nextText = parts[i + 1] || '';
                                
                                renderedParts.push(
                                    <FileProcessLog 
                                        key={`log-${bIdx}`} 
                                        fileGenerations={fileGens} 
                                        darkMode={darkMode} 
                                        batchIndex={bIdx}
                                        isFinalBatch={bIdx === highestBatchIndex} 
                                    />
                                );
                                
                                if (nextText) {
                                    renderedParts.push(
                                        <CakraResponseRenderer
                                            key={`renderer-${i+1}`}
                                            rawContent={nextText}
                                            thinkingContent=""
                                            isStreaming={isThisMessageStreaming}
                                            darkMode={darkMode}
                                            theme={theme}
                                            searchQuery={searchQuery}
                                            statusMessage={msg.statusMessage}
                                        />
                                    );
                                }
                            }

                            return <>{renderedParts}</>;
                        })()}

                        {/* 🔥 POSISI BERHASIL DIPINDAHKAN DI AKHIR STREAM (DI BAWAH RENDERING TEKS JAWABAN) */}
                        {msg.fileGenerations && msg.fileGenerations.length > 0 && msg.statusMessage !== "✍️ Sedang membuat file..." && msg.fileGenerations.every(g => g.stage === 'done' || g.stage === 'error') && (
                            <div style={{ marginTop: '12px', marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {msg.fileGenerations.map((fg, fgIdx) => (
                                    <FileGenerationCard 
                                        key={fg.filename + fgIdx}
                                        filename={fg.filename}
                                        stage={fg.stage}
                                        liveCode={fg.liveCode}
                                        darkMode={darkMode}
                                        onOpenArtifact={onOpenArtifact}
                                        file_path={fg.file_path || null}
                                        theme={theme}
                                        handleDownloadArtifact={handleDownloadArtifact}
                                    />
                                ))}
                                {msg.fileGenerations.length > 1 && msg.fileGenerations.every(fg => fg.stage === 'done') && (
                                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: '4px' }}>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (handleDownloadAllArtifacts) {
                                                    // Mapping fg (fileGenerations) ke format yang diharapkan: art.filename, art.file_path, art.code
                                                    const mappedArtifacts = msg.fileGenerations.map(fg => ({
                                                        filename: fg.filename,
                                                        file_path: fg.file_path,
                                                        code: fg.liveCode
                                                    }));
                                                    handleDownloadAllArtifacts(mappedArtifacts);
                                                } else {
                                                    msg.fileGenerations.forEach((fg, idx) => {
                                                        setTimeout(() => {
                                                            const blob = new Blob([fg.liveCode || ''], { type: 'text/plain;charset=utf-8' });
                                                            const url = URL.createObjectURL(blob);
                                                            const a = document.createElement('a');
                                                            a.href = url;
                                                            a.download = fg.filename || `file_${idx}.txt`;
                                                            a.click();
                                                            URL.revokeObjectURL(url);
                                                        }, idx * 200);
                                                    });
                                                }
                                            }}
                                            style={{
                                                background: 'transparent',
                                                border: '1px solid rgba(255, 255, 255, 0.15)',
                                                borderRadius: '8px',
                                                padding: '8px 16px',
                                                color: '#ffffff',
                                                fontSize: '13px',
                                                fontWeight: '500',
                                                cursor: 'pointer',
                                                transition: 'all 0.2s ease',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '8px'
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.background = 'transparent';
                                            }}
                                        >
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                                <polyline points="7 10 12 15 17 10"></polyline>
                                                <line x1="12" y1="15" x2="12" y2="3"></line>
                                            </svg>
                                            Download all
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                    </div>

                    {!isThisMessageStreaming && (
                        <>
                            {(msg.eval_count || msg.citations || msg.sources) && (
                                <RAGMetrics
                                    sources={msg.citations || msg.sources}
                                    eval_count={msg.eval_count}
                                    eval_duration={msg.eval_duration}
                                    darkMode={darkMode}
                                    theme={theme}
                                />
                            )}
                            {(msg.citations || msg.sources) && (
                                <SourceCitation
                                    sources={msg.citations || msg.sources}
                                    darkMode={darkMode}
                                    theme={theme}
                                    activeIsolatedDocId={activeIsolatedDocId}
                                    onActivateIsolation={(source) => {
                                        const docId = source.id || source.dokumen_id;
                                        const docTitle = source.title || source.filename || source.name;
                                        setContextIsolation(docId, docTitle);
                                    }}
                                    onPreview={(source) => {
                                        const fileUrl = source.url || source.file_path;
                                        if (fileUrl) window.open(fileUrl, '_blank');
                                    }}
                                />
                            )}
                        </>
                    )}

                    {/* ── TOOLBAR AKSI MINIMALIS (HOVER ONLY ICONS) ── */}
                    {!isThisMessageStreaming && (
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            marginTop: '4px', // Jarak aman mepet di bawah teks respons tanpa garis pembatas
                            width: '100%',
                            justifyContent: 'flex-start'
                        }}>
                            {/* 👍 TOMBOL GOOD (THUMB UP) */}
                            <button
                                type="button"
                                onClick={() => {
                                    apiClient.patch(`/chat/sessions/${useChatStore.getState().sessionUuid}/messages/feedback`, {
                                        message_index: idx,
                                        feedback: { rating: 'good' }
                                    }).then(() => {
                                        setToastMsg('Feedback Good terkirim! 👍');
                                        setShowToast(true);
                                        setTimeout(() => setShowToast(false), 2000);
                                    }).catch(err => {
                                        console.error("Gagal mengirim feedback:", err);
                                        setToastMsg('Gagal mengirim feedback ❌');
                                        setShowToast(true);
                                        setTimeout(() => setShowToast(false), 2000);
                                    });
                                }}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: 0.5,
                                    color: darkMode ? '#94a3b8' : '#64748b' // Warna default abu-abu elegan monokrom
                                }}
                                title="Respons Bagus"
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = '#10b981'; // Glow Hijau pas di-hover
                                    e.currentTarget.style.background = darkMode ? 'rgba(16,185,129,0.1)' : 'rgba(16,185,129,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                                </svg>
                            </button>

                            {/* 👎 TOMBOL BAD (THUMB DOWN) */}
                            <button
                                type="button"
                                onClick={() => {
                                    apiClient.patch(`/chat/sessions/${useChatStore.getState().sessionUuid}/messages/feedback`, {
                                        message_index: idx,
                                        feedback: { rating: 'bad' }
                                    }).then(() => {
                                        setToastMsg('Feedback Bad terkirim! 👎');
                                        setShowToast(true);
                                        setTimeout(() => setShowToast(false), 2000);
                                    }).catch(err => {
                                        console.error("Gagal mengirim feedback:", err);
                                        setToastMsg('Gagal mengirim feedback ❌');
                                        setShowToast(true);
                                        setTimeout(() => setShowToast(false), 2000);
                                    });
                                }}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: 0.5,
                                    color: darkMode ? '#94a3b8' : '#64748b'
                                }}
                                title="Respons Buruk"
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = '#ef4444'; // Glow Merah pas di-hover
                                    e.currentTarget.style.background = darkMode ? 'rgba(239,68,68,0.1)' : 'rgba(239,68,68,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                                </svg>
                            </button>

                            {/* 📋 TOMBOL COPY (DOUBLE DOCUMENT LAYERS) */}
                            <button
                                type="button"
                                onClick={() => executeTextCopy(msg.content)}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: 0.5,
                                    color: darkMode ? '#94a3b8' : '#64748b'
                                }}
                                title="Salin Respons"
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = darkMode ? '#6366f1' : '#2563eb'; // Glow Tema Utama Indigo/Blue
                                    e.currentTarget.style.background = darkMode ? 'rgba(99,102,241,0.1)' : 'rgba(37,99,235,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                            </button>
                        </div>
                    )}

                </div>
            </div>
            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
}, (prevProps, nextProps) => {
    return (
        prevProps.msg.content === nextProps.msg.content &&
        prevProps.msg.thinking === nextProps.msg.thinking &&
        prevProps.msg.thought === nextProps.msg.thought &&
        prevProps.msg.statusMessage === nextProps.msg.statusMessage &&
        prevProps.msg.reasoning === nextProps.msg.reasoning &&
        prevProps.msg.role === nextProps.msg.role &&
        prevProps.isThinking === nextProps.isThinking &&
        prevProps.isStreamingText === nextProps.isStreamingText &&
        prevProps.darkMode === nextProps.darkMode &&
        prevProps.idx === nextProps.idx &&
        prevProps.searchQuery === nextProps.searchQuery &&
        prevProps.msg.totalMessages === nextProps.msg.totalMessages &&
        JSON.stringify(prevProps.msg.attachments) === JSON.stringify(nextProps.msg.attachments) &&
        JSON.stringify(prevProps.msg.fileGenerations) === JSON.stringify(nextProps.msg.fileGenerations)
    );
});

export default ChatBubble;