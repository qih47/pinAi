import React, { useState, useEffect, useRef, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThoughtAccordion from './ThoughtAccordion';
import SourceCitation from './SourceCitation';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
import { useChatStore, getUploadUrl } from '../../../stores/chatStore';

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
        return <p                 style={{ 
                    marginTop: 0, 
                    marginBottom: '16px', 
                    lineHeight: '1.7', 
                    padding: 0, 
                    whiteSpace: 'normal',
                    // 🌊 Smooth paragraph entrance
                    opacity: 0,
                    animation: 'geminiFadeIn 0.4s ease-out forwards',
                    animationDelay: '0.1s',  // Delay dikit biar staggered
                }}  {...props}>{children}</p>;
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
                        fontSize: '13px',
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

        // 🔥 LEBIH SMOOTH - Update lebih sering tapi dengan threshold yang pas
        if (
            lastRenderedLengthRef.current === -1 ||
            timeSinceLastRender >= 100 ||  // Turunin dari 200ms ke 100ms (lebih responsive)
            newChars >= 30  // Turunin dari 50 chars ke 30 (lebih smooth)
        ) {
            setRenderedContent(content);
            lastRenderedLengthRef.current = content.length;
            lastRenderTimeRef.current = now;
        }
    }, [content, isStreaming]);

    return (
        <div style={{
            // Container dengan smooth transition
            transition: 'all 0.3s cubic-bezier(0.22, 0.61, 0.36, 1)',
        }}>
            <ReactMarkdown
                children={renderedContent}
                components={markdownComponents}
                remarkPlugins={[remarkGfm]}
            />
        </div>
    );
});

// =========================================================================
// 👤 USER BUBBLE — ATTACHMENT & TEXT TERPISAH DALAM BUBBLE BERBEDA
// =========================================================================
const UserBubble = memo(function UserBubble({ msg, idx, darkMode, theme, executeTextCopy, showToast, toastMsg }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(msg.content || '');

    const editAndRegenerate = useChatStore((state) => state.editAndRegenerate);
    const isStreaming = useChatStore((state) => state.isStreaming);

    const CHARACTER_LIMIT = 300;
    const shouldTruncate = msg.content && msg.content.length > CHARACTER_LIMIT;

    const displayContent = (shouldTruncate && !isExpanded && !isEditing)
        ? `${msg.content.slice(0, CHARACTER_LIMIT)}...`
        : msg.content;

    const handleEditSubmit = async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (!editValue.trim()) return;
        if (isStreaming) return;

        const newContent = editValue;
        setIsEditing(false);
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
            {/* 📎 BUBBLE ATTACHMENT TERPISAH */}
            {!isEditing && msg.attachments && msg.attachments.length > 0 && (
                <div style={{
                    width: 'auto',
                    maxWidth: '75%',
                    padding: '12px 16px',
                    borderRadius: 18,
                    background: darkMode ? '#3a3a3f' : '#f3f4f6',
                    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.12)',
                    marginBottom: '8px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px',
                    justifyContent: 'flex-end'
                }}>
                    {msg.attachments.map((file, fIdx) => {
                        const fileName = file.file_name || file.original_filename || 'lampiran';
                        const assetUrl = getUploadUrl(file.file_path);
                        const isPDF = file.mime_type === 'application/pdf' || fileName.toLowerCase().endsWith('.pdf');
                        return (
                            <div
                                key={`attach-${file.id || fIdx}`}
                                title={fileName}
                                onClick={() => {
                                    if (assetUrl) window.open(assetUrl, '_blank');
                                }}
                                style={{
                                    width: '60px',
                                    height: '60px',
                                    borderRadius: '10px',
                                    overflow: 'hidden',
                                    background: darkMode ? '#222225' : '#e5e7eb',
                                    border: `1px solid ${darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    transition: 'transform 0.15s ease'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.04)'}
                                onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                            >
                                {isPDF ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                                        <span style={{ fontSize: '20px' }}>📄</span>
                                        <span style={{
                                            fontSize: '8px',
                                            fontWeight: 800,
                                            color: '#ef4444',
                                            maxWidth: '48px',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap'
                                        }}>PDF</span>
                                    </div>
                                ) : assetUrl ? (
                                    <img
                                        src={assetUrl}
                                        alt={fileName}
                                        onError={(e) => {
                                            e.target.style.display = 'none';
                                            e.target.parentNode.innerHTML = '<span style="font-size:20px;">🖼️</span>';
                                        }}
                                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                    />
                                ) : (
                                    <span style={{ fontSize: '20px' }}>🖼️</span>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* 💬 BUBBLE TEXT TERPISAH — sembunyikan jika hanya lampiran */}
            {(isEditing || (msg.content && msg.content.trim())) && (
                <div style={{
                    width: isEditing ? '75%' : 'auto',
                    maxWidth: '75%',
                    padding: (shouldTruncate && !isEditing) ? '14px 20px 36px 20px' : '14px 20px',
                    borderRadius: 22,
                    fontSize: 15,
                    lineHeight: 1.55,
                    whiteSpace: isEditing ? 'normal' : 'pre-wrap',
                    wordBreak: 'break-word',
                    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.12)',
                    background: darkMode ? '#3a3a3f' : '#f3f4f6',
                    color: darkMode ? '#e2e8f0' : '#1f2937',
                    position: 'relative',
                    transition: 'all 0.2s ease-in-out',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                }}>
                    {isEditing ? (
                        /* ✏️ MODE: INLINE FORM EDITOR */
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            <textarea
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onKeyDown={(e) => {
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
                                    type="button"
                                    onClick={handleEditSubmit}
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
                            {displayContent ? <div>{displayContent}</div> : null}

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
            )}

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

    const globalIsThinking = useChatStore((state) => state.isThinking);
    const globalIsStreaming = useChatStore((state) => state.isStreaming);
    const activeIsolatedDocId = useChatStore((state) => state.activeIsolatedDocId);
    const setContextIsolation = useChatStore((state) => state.setContextIsolation);

    const isReceivingRef = useRef(false);

    if (globalIsThinking && (!msg.content || msg.content === '')) {
        isReceivingRef.current = true;
    } else if (!globalIsStreaming && !globalIsThinking) {
        isReceivingRef.current = false;
    }

    const isThinkingMsg = isReceivingRef.current && globalIsThinking && (!msg.content || msg.content === '');
    const isStreamingMsg = isReceivingRef.current && globalIsStreaming && msg.content !== '';
    const isActive = isThinkingMsg || isStreamingMsg;

    // 🔥 FIX: Smooth transition & animasi untuk teks berpikir (thinking text)
    const [displayThought, setDisplayThought] = useState("CAKRA sedang berpikir");
    const [isThoughtVisible, setIsThoughtVisible] = useState(true);
    const thoughtTimerRef = useRef(null);

    useEffect(() => {
        if (!isThinkingMsg) return;

        const nextThought = msg.thought || "CAKRA sedang berpikir";

        if (nextThought !== displayThought) {
            if (thoughtTimerRef.current) {
                clearTimeout(thoughtTimerRef.current);
            }

            // Fade out & slide down
            setIsThoughtVisible(false);

            // Ganti teks dan fade in & slide up setelah durasi transisi
            thoughtTimerRef.current = setTimeout(() => {
                setDisplayThought(nextThought);
                setIsThoughtVisible(true);
                thoughtTimerRef.current = null;
            }, 250);
        }

        return () => {
            if (thoughtTimerRef.current) {
                clearTimeout(thoughtTimerRef.current);
            }
        };
    }, [msg.thought, isThinkingMsg, displayThought]);

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
                        <span style={{ display: 'flex', alignItems: 'center', marginLeft: 10, overflow: 'hidden' }}>
                            <span
                                key={msg.thought}
                                style={{
                                    fontSize: 14,
                                    marginLeft: 10,
                                    fontStyle: 'italic',
                                    background: 'linear-gradient(90deg, #94a3b8 0%, #e2e8f0 50%, #94a3b8 100%)',
                                    backgroundSize: '200% 100%',
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                    backgroundClip: 'text',
                                    animation: 'shimmerFlow 2.5s linear infinite, fadeSlideIn 0.4s ease-out',
                                    display: 'inline-block',
                                    whiteSpace: 'nowrap'
                                }}
                            >
                                {msg.thought || "CAKRA sedang berpikir"}
                            </span>
                            <span style={{ display: 'inline-flex', marginLeft: 4, alignItems: 'baseline' }}>
                                <span style={{
                                    fontSize: 18,
                                    color: theme.secondaryText,
                                    animation: 'dotBounce 1.4s infinite ease-in-out',
                                    display: 'inline-block'
                                }}>.</span>
                                <span style={{
                                    fontSize: 18,
                                    color: theme.secondaryText,
                                    animation: 'dotBounce 1.4s infinite ease-in-out 0.2s',
                                    display: 'inline-block'
                                }}>.</span>
                                <span style={{
                                    fontSize: 18,
                                    color: theme.secondaryText,
                                    animation: 'dotBounce 1.4s infinite ease-in-out 0.4s',
                                    display: 'inline-block'
                                }}>.</span>
                            </span>
                        </span>
                    ) : (
                        <span style={{ ...styles.avatarLabel, color: theme.textColor, marginLeft: 8, transition: 'opacity 0.3s' }}>
                            CAKRA AI
                        </span>
                    )}
                </div>

                <div style={styles.assistantContent} className="assistant-content-container">

                    {/* 🔥 ACCORDION FIX: Selalu tampilkan Accordion baik saat berpikir (live stream) maupun saat riwayat lama dimuat */}
                    {(msg.thought || msg.reasoning) && (
                        <ThoughtAccordion
                            thought={msg.thought || msg.reasoning}
                            darkMode={darkMode}
                            theme={theme}
                        />
                    )}

                    {!isThinkingMsg && (
                        <>
                            <div style={{ ...styles.assistantText, color: theme.textColor }}>
                                <DebouncedMarkdown
                                    content={msg.content || ''}
                                    isStreaming={isStreamingMsg}
                                    darkMode={darkMode}
                                />
                            </div>

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
    // 🔥 MEMOIZATION RECONCILIATION: Pastikan membandingkan msg.thought agar React mau mengeksekusi re-render komponen secara live!
    return (
        prevProps.msg.content === nextProps.msg.content &&
        prevProps.msg.thought === nextProps.msg.thought &&
        prevProps.msg.reasoning === nextProps.msg.reasoning &&
        prevProps.msg.role === nextProps.msg.role &&
        prevProps.isThinking === nextProps.isThinking &&
        prevProps.isStreamingText === nextProps.isStreamingText &&
        prevProps.darkMode === nextProps.darkMode &&
        prevProps.idx === nextProps.idx &&
        prevProps.msg.totalMessages === nextProps.msg.totalMessages &&
        JSON.stringify(prevProps.msg.attachments) === JSON.stringify(nextProps.msg.attachments)
    );
});

export default ChatBubble;