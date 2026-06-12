import React, { useState, useEffect, useRef, memo } from 'react';
import CakraResponseRenderer from './CakraResponseRenderer';
import SourceCitation from './SourceCitation';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
import { useChatStore } from '../../../stores/chatStore';
import UserBubble from './UserBubble';

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

                    {/* INTEGRASI CAKRA PIPELINE: Mengamankan body stream menggunakan Custom Index Parser */}
                    {!isThinkingMsg && (
                        <>
                            <div style={{ ...styles.assistantText, color: theme.textColor, width: '100%' }}>
                                {/* Menggunakan CakraResponseRenderer untuk memisahkan
                                    proses berpikir internal <think> ke dalam ThoughtAccordion
                                    secara otomatis tanpa merusak spasi format Markdown. */}
                                <CakraResponseRenderer
                                    rawContent={msg.content || ''}
                                    isStreaming={isStreamingMsg}
                                    darkMode={darkMode}
                                    theme={theme}
                                />
                            </div>

                            {!isStreamingMsg && (msg.citations || msg.sources) && (
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
    // REKONSILIASI MEMOISASI: Membandingkan msg.thought untuk memastikan React merender ulang komponen secara real-time.
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