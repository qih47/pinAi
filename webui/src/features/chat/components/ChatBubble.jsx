import React, { useState, useEffect, useRef, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThoughtAccordion from './ThoughtAccordion';
import SourceCitation from './SourceCitation';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
// 🔥 IMPORT STORE BIAR BISA PANGGIL editAndRegenerate
import { useChatStore } from '../../../stores/chatStore';

const actionBtnStyle = {
    background: 'rgba(255, 255, 255, 0.03)',
    color: '#cbd5e1',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '5px',
    padding: '4px 10px',
    fontSize: '11px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    fontWeight: 500,
    fontFamily: "'Inter', sans-serif",
    transition: 'all 0.15s ease-in-out'
};

const hoverBtnStyle = {
    background: 'transparent',
    border: 'none',
    color: '#9ca3af',
    cursor: 'pointer',
    display: 'flex',
    padding: '4px',
    borderRadius: '4px',
    transition: 'color 0.15s, background 0.15s'
};

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

function CodeBlockHeader({ lang, code }) {
    const [showToast, setShowToast] = useState(false);
    const [toastMsg, setToastMsg] = useState('');

    const handleCopy = async () => {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(code);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = code;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
            setToastMsg('Kode berhasil disalin! 📋');
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        } catch (err) {
            setToastMsg('Gagal menyalin kode! ❌');
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        }
    };

    const handleDownload = () => {
        try {
            const extensionMap = {
                javascript: 'js', jsx: 'jsx', typescript: 'ts', tsx: 'tsx',
                html: 'html', css: 'css', python: 'py', sql: 'sql',
                php: 'php', java: 'java', kotlin: 'kt', bash: 'sh'
            };
            const ext = extensionMap[lang.toLowerCase()] || 'txt';
            const filename = `cakra_code_${Date.now()}.${ext}`;
            const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            setToastMsg(`Berkas ${filename} berhasil diunduh! 💾`);
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <div style={{
            background: '#1a1a1c',
            padding: '10px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            borderTopLeftRadius: '10px',
            borderTopRightRadius: '10px',
            position: 'relative'
        }}>
            <span style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 700, fontFamily: "'Inter', sans-serif", letterSpacing: '0.8px' }}>
                {lang.toUpperCase()}
            </span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button type="button" onClick={handleDownload} title="Unduh Kode" style={actionBtnStyle}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>Unduh</span>
                </button>
                <button type="button" onClick={handleCopy} title="Salin Kode" style={actionBtnStyle}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                    </svg>
                    <span>Salin</span>
                </button>
            </div>
            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
}

const getMarkdownComponents = (darkMode) => ({
    p({ children, ...props }) {
        return <p style={{ marginTop: 0, marginBottom: '12px', lineHeight: '1.6', padding: 0, whiteSpace: 'normal' }} {...props}>{children}</p>;
    },
    code({ node, inline, className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || '');
        const cleanCode = String(children).replace(/\n$/, '');

        return !inline && match ? (
            <div key={`code-block-${match[1]}`} style={{ borderRadius: '10px', overflow: 'hidden', margin: '8px 0', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <CodeBlockHeader lang={match[1]} code={cleanCode} />
                <SyntaxHighlighter
                    key={`highlighter-${match[1]}`}
                    children={cleanCode}
                    style={vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    className="custom-scroll-gemini"
                    customStyle={{
                        margin: 0,
                        padding: '16px',
                        background: '#222225',
                        fontSize: '13.5px',
                        lineHeight: '1.6',
                        fontFamily: "'Fira Code', 'Courier New', monospace"
                    }}
                    {...props}
                />
            </div>
        ) : (
            <code key="inline-code" className={className} style={{ background: darkMode ? '#2d2d30' : '#e5e7eb', color: darkMode ? '#f3f4f6' : '#1f2937', padding: '3px 6px', borderRadius: '4px', fontFamily: "monospace", fontSize: '14px' }} {...props}>
                {children}
            </code>
        );
    }
});

const DebouncedMarkdown = memo(function DebouncedMarkdown({ content, isStreaming, darkMode }) {
    const [renderedContent, setRenderedContent] = useState(content);
    const lastRenderedLengthRef = useRef(-1);
    const lastRenderTimeRef = useRef(Date.now());

    const markdownComponents = useMemo(() => getMarkdownComponents(darkMode), [darkMode]);

    useEffect(() => {
        if (content.length === 0) return;

        if (!isStreaming) {
            setRenderedContent(content);
            lastRenderedLengthRef.current = content.length;
            lastRenderTimeRef.current = Date.now();
            return;
        }

        const now = Date.now();
        const timeSinceLastRender = now - lastRenderTimeRef.current;
        const newChars = content.length - lastRenderedLengthRef.current;

        if (
            lastRenderedLengthRef.current === -1 ||
            timeSinceLastRender >= 200 ||
            newChars >= 50
        ) {
            setRenderedContent(content);
            lastRenderedLengthRef.current = content.length;
            lastRenderTimeRef.current = now;
        }
    }, [content, isStreaming]);

    return (
        <ReactMarkdown
            children={renderedContent}
            components={markdownComponents}
            remarkPlugins={[remarkGfm]}
        />
    );
});

// =========================================================================
// 🔥 MAIN COMPONENT
// =========================================================================
const ChatBubble = memo(function ChatBubble({ msg, idx, darkMode, theme, isThinking, isStreamingText }) {
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
            />
        );
    }

    // =========================================================================
    // 🔥 FIX TOTAL: BUBBLE MANDIRI (MERAH -> HIJAU)
    // =========================================================================
    // Ambil status langsung dari store
    const globalIsThinking = useChatStore((state) => state.isThinking);
    const globalIsStreaming = useChatStore((state) => state.isStreaming);

    // Kunci target bubble pakai memori lokal
    const isReceivingRef = useRef(false);

    // Kunci target JIKA global lagi mikir DAN teks di bubble ini kosong melompong
    if (globalIsThinking && (!msg.content || msg.content === '')) {
        isReceivingRef.current = true;
    } else if (!globalIsStreaming && !globalIsThinking) {
        // Lepas kuncian kalau stream beneran udah kelar semua
        isReceivingRef.current = false;
    }

    // Tentukan status saat ini secara akurat
    const isThinkingMsg = isReceivingRef.current && globalIsThinking && (!msg.content || msg.content === '');
    const isStreamingMsg = isReceivingRef.current && globalIsStreaming && msg.content !== '';
    const isActive = isThinkingMsg || isStreamingMsg;

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
                                // 🔥 KUNCI WARNA DI SINI ASU:
                                // Kalau isThinkingMsg true = Merah (#ef4444)
                                // Kalau isThinkingMsg false (berarti udah masuk fase streaming text) = Hijau (#10b981)
                                background: isThinkingMsg ? '#ef4444' : '#10b981',
                                borderColor: theme.mainBg
                            }} />
                        )}
                    </div>
                    {isThinkingMsg ? (
                        <span style={{ display: 'flex', alignItems: 'center', marginLeft: 10 }}>
                            <span style={{ animation: 'fadeText 1.5s infinite', color: theme.secondaryText, fontStyle: 'italic', fontSize: 14, marginLeft: 10 }}>
                                CAKRA sedang berpikir
                            </span>
                            <span style={{ display: 'inline-flex', marginLeft: 2 }}>
                                <span style={{ animation: 'dotPulse 1.4s infinite', fontSize: 20, color: theme.secondaryText }}>.</span>
                                <span style={{ animation: 'dotPulse 1.4s infinite 0.2s', fontSize: 20, color: theme.secondaryText }}>.</span>
                                <span style={{ animation: 'dotPulse 1.4s infinite 0.4s', fontSize: 20, color: theme.secondaryText }}>.</span>
                            </span>
                        </span>
                    ) : (
                        <span style={{ ...styles.avatarLabel, color: theme.textColor, marginLeft: 8 }}>CAKRA AI</span>
                    )}
                </div>

                <div style={styles.assistantContent} className="assistant-content-container">
                    {!isThinkingMsg && (
                        <>
                            {/* 🧠 THOUGHT ACCORDION - jika ada properti thought atau reasoning */}
                            {(msg.thought || msg.reasoning) && (
                                <ThoughtAccordion
                                    thought={msg.thought || msg.reasoning}
                                    darkMode={darkMode}
                                    theme={theme}
                                />
                            )}

                            {/* 📝 MARKDOWN UTAMA */}
                            <div style={{ ...styles.assistantText, color: theme.textColor }}>
                                <DebouncedMarkdown
                                    content={msg.content || ''}
                                    isStreaming={isStreamingMsg}
                                    darkMode={darkMode}
                                />
                            </div>

                            {/* 📚 SOURCE CITATION - jika ada citations atau sources */}
                            {(msg.citations || msg.sources) && (
                                <SourceCitation
                                    sources={msg.citations || msg.sources}
                                    darkMode={darkMode}
                                    theme={theme}
                                    onPreview={(source) => {
                                        // opsional: buka modal preview / console.log
                                        console.log('Preview dokumen:', source);
                                    }}
                                />
                            )}

                            {/* TOMBOL SALIN (existing) */}
                            {!isStreamingMsg && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '10px', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '8px' }}>
                                    <button
                                        type="button"
                                        onClick={() => executeTextCopy(msg.content)}
                                        title="Salin Seluruh Jawaban AI"
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            color: theme.secondaryText,
                                            fontSize: '12px',
                                            cursor: 'pointer',
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '4px 8px',
                                            borderRadius: '6px',
                                            transition: 'background 0.2s'
                                        }}
                                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
                                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                    >
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                                        </svg>
                                        <span>Salin Jawaban</span>
                                    </button>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
}, (prevProps, nextProps) => {
    return (
        prevProps.msg.content === nextProps.msg.content &&
        prevProps.msg.role === nextProps.msg.role &&
        prevProps.isThinking === nextProps.isThinking &&
        prevProps.isStreamingText === nextProps.isStreamingText &&
        prevProps.darkMode === nextProps.darkMode &&
        prevProps.idx === nextProps.idx &&
        prevProps.msg.totalMessages === nextProps.msg.totalMessages
    );
});

// =========================================================================
// 👤 USER BUBBLE — FIX THINKING & RESET RESPONSE ON EDIT
// =========================================================================
const UserBubble = memo(function UserBubble({ msg, idx, darkMode, theme, executeTextCopy, showToast, toastMsg }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(msg.content || '');

    // Ambil fungsi editAndRegenerate dan state global dari store lu
    const editAndRegenerate = useChatStore((state) => state.editAndRegenerate);
    const isStreaming = useChatStore((state) => state.isStreaming);

    // 🔥 TAMBAHIN INI JALUR AMAN: Ambil messages dan setMessages (atau fungsi update) dari store lu jika ada.
    // Kalau di store lu ada fungsi buat ngosongin index tertentu secara instan, panggil di sini.
    // Tapi kalau arsitektur store lu langsung nge-handle pembersihan di dalam editAndRegenerate, 
    // pastikan di dalam store/chatStore.js lu pada fungsi `editAndRegenerate`, langkah pertamanya adalah:
    // messages[idx + 1].content = ''; 

    const CHARACTER_LIMIT = 300;
    const shouldTruncate = msg.content && msg.content.length > CHARACTER_LIMIT;

    const displayContent = (shouldTruncate && !isExpanded && !isEditing)
        ? `${msg.content.slice(0, CHARACTER_LIMIT)}...`
        : msg.content;

    // =========================================================================
    // 🔥 FIX: Clear Response Dulu $\rightarrow$ Pemicu Thinking $\rightarrow$ Stream New Data
    // =========================================================================
    const handleEditSubmit = async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (!editValue.trim()) return;
        if (isStreaming) return; // Cegah spam klik pas lagi streaming

        const newContent = editValue;

        // 1. Matikan mode editor text area biar bubble balik normal
        setIsEditing(false);

        // 2. 🔥 TIPS UTAMA BIAR TEMBUS THINKING:
        // Di dalam file `stores/chatStore.js` lu, pastiin isi fungsi `editAndRegenerate(idx, newContent)` 
        // itu ngereset text index assistant sesudahnya jadi kosong murni dulu ya cok! 
        // Contoh logikanya di file store lu kudu begini:
        // set((state) => {
        //    const newMsg = [...state.messages];
        //    newMsg[idx].content = newContent; // update text user
        //    if(newMsg[idx + 1]) newMsg[idx + 1].content = ''; // 🔥 KUNCI UTAMA: KOSONGIN JAWABAN AI BIAR ANIMASI THINKING JALAN
        //    return { messages: newMsg, isStreaming: true, isThinking: true };
        // });

        // Panggil fungsi regenerasi bawaan store lu
        editAndRegenerate(idx, newContent);
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditValue(msg.content || '');
    };

    return (
        <div
            style={{
                ...styles.userChatRow,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                marginBottom: '16px'
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* 📦 BUBBLE CHAT USER */}
            <div style={{
                width: isEditing ? '75%' : 'auto',
                maxWidth: '75%',
                padding: (shouldTruncate && !isEditing) ? '12px 18px 36px 18px' : '12px 18px',
                borderRadius: 22,
                fontSize: 15,
                lineHeight: 1.55,
                whiteSpace: isEditing ? 'normal' : 'pre-wrap',
                wordBreak: 'break-word',
                boxShadow: '0 2px 8px rgba(99, 102, 241, 0.18)',
                background: darkMode ? '#3a3a3f' : '#f3f4f6',
                color: darkMode ? '#e2e8f0' : '#1f2937',
                position: 'relative',
                transition: 'all 0.2s ease-in-out'
            }}>
                {isEditing ? (
                    /* ✏️ MODE: INLINE FORM EDITOR */
                    // 🔥 FIX: Ganti <form> jadi <div> biar ga kena bug Nested Form HTML!
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <textarea
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                                // 🔥 FIX: Tetap bisa submit pakai Enter (Shift+Enter buat newline)
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleEditSubmit(e);
                                }
                            }}
                            rows={3}
                            style={{
                                width: '100%',
                                background: darkMode ? '#2d2d30' : '#ffffff',
                                color: darkMode ? '#e2e8f0' : '#1f2937',
                                border: darkMode ? '1px solid rgba(255,255,255,0.1)' : '1px solid #d1d5db',
                                borderRadius: '12px',
                                padding: '10px',
                                fontSize: '14px',
                                fontFamily: 'inherit',
                                resize: 'vertical',
                                outline: 'none',
                                boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.05)'
                            }}
                            autoFocus
                        />
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button
                                type="button"
                                onClick={handleCancelEdit}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: darkMode ? '#9ca3af' : '#6b7280',
                                    fontSize: '13px',
                                    fontWeight: 500,
                                    cursor: 'pointer',
                                    padding: '6px 12px',
                                    borderRadius: '18px'
                                }}
                            >
                                Batal
                            </button>
                            <button
                                type="button" // 🔥 FIX: Ganti dari type="submit" jadi type="button"
                                onClick={handleEditSubmit} // 🔥 FIX: Panggil manual via onClick
                                disabled={!editValue.trim() || isStreaming}
                                style={{
                                    background: '#6366f1',
                                    color: '#ffffff',
                                    border: 'none',
                                    fontSize: '13px',
                                    fontWeight: 600,
                                    cursor: (editValue.trim() && !isStreaming) ? 'pointer' : 'not-allowed',
                                    padding: '6px 16px',
                                    borderRadius: '18px',
                                    opacity: (editValue.trim() && !isStreaming) ? 1 : 0.5,
                                    boxShadow: '0 2px 4px rgba(99, 102, 241, 0.3)'
                                }}
                            >
                                Kirim
                            </button>
                        </div>
                    </div>
                ) : (
                    /* 💬 MODE: TAMPILAN TEXT CHAT NORMAL */
                    <>
                        <div>{displayContent}</div>

                        {shouldTruncate && !isExpanded && (
                            <div style={{
                                position: 'absolute',
                                bottom: '32px',
                                left: 0,
                                right: 0,
                                height: '20px',
                                background: darkMode
                                    ? 'linear-gradient(to bottom, transparent, #3a3a3f)'
                                    : 'linear-gradient(to bottom, transparent, #f3f4f6)',
                                pointerEvents: 'none'
                            }} />
                        )}

                        {/* 🔽 EXPAND-COLLAPSE BUTTON */}
                        {shouldTruncate && (
                            <button
                                type="button"
                                onClick={() => setIsExpanded(!isExpanded)}
                                title={isExpanded ? "Sembunyikan pesan" : "Tampilkan selengkapnya"}
                                style={{
                                    position: 'absolute',
                                    bottom: '6px',
                                    right: '12px',
                                    background: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
                                    border: 'none',
                                    color: darkMode ? '#cbd5e1' : '#4b5563',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: '5px',
                                    borderRadius: '50%',
                                    transition: 'transform 0.2s, background 0.15s'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'}
                            >
                                <svg
                                    width="14"
                                    height="14"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    style={{
                                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                        transition: 'transform 0.2s ease-in-out'
                                    }}
                                >
                                    <polyline points="6 9 12 15 18 9" />
                                </svg>
                            </button>
                        )}
                    </>
                )}
            </div>

            {/* 🛰️ HOVER ACTIONS */}
            {!isEditing && (
                <div style={{
                    display: 'flex',
                    gap: '12px',
                    alignItems: 'center',
                    marginRight: '12px',
                    marginTop: '4px',
                    height: '20px',
                    opacity: isHovered ? 1 : 0,
                    transition: 'opacity 0.2s ease-in-out',
                    pointerEvents: isHovered ? 'auto' : 'none'
                }}>
                    <button type="button" onClick={() => executeTextCopy(msg.content)} title="Salin Pesan" style={hoverBtnStyle}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                        </svg>
                    </button>
                    {/* 🔥 EDIT BUTTON — Hanya muncul kalau ga lagi streaming */}
                    {!isStreaming && (
                        <button type="button" onClick={() => setIsEditing(true)} title="Edit Perintah" style={hoverBtnStyle}>
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                        </button>
                    )}
                </div>
            )}
            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
});

export default ChatBubble;