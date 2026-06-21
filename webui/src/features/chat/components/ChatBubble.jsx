import React, { useState, useEffect, useRef, memo } from 'react';
import CakraResponseRenderer from './CakraResponseRenderer';
import SourceCitation from './SourceCitation';
import RAGMetrics from './RAGMetrics';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../chatPage.styles';
import { useChatStore } from '../../../stores/chatStore';
import UserBubble from './UserBubble';

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
  if (!thought) return "CAKRA sedang berpikir...";
  
  // Gunakan lastIndexOf agar selalu menangkap fase terakhir (paling baru)
  const phases = [
    { key: "jalur", label: "🚦 Layer 0: Menganalisis intent & jalur..." },
    { key: "Gateway", label: "🚦 Layer 0: Menganalisis intent & jalur..." },
    { key: "dokumen", label: "📚 RAG: Mencari regulasi internal Pindad..." },
    { key: "RAG", label: "📚 RAG: Mencari regulasi internal Pindad..." },
    { key: "cepat", label: "✍️ Layer 2: Menyusun formulasi respons..." },
    { key: "respons", label: "✍️ Layer 2: Menyusun formulasi respons..." },
    { key: "Gemma", label: "✍️ Layer 2: Menyusun formulasi respons..." },
    { key: "PDF", label: "📄 Membaca lampiran PDF..." },
    { key: "visual", label: "🖼️ Menganalisis visual..." }
  ];

  let lastIndex = -1;
  let activePhase = "CAKRA sedang berpikir...";

  for (const phase of phases) {
      const idx = thought.lastIndexOf(phase.key);
      if (idx > lastIndex) {
          lastIndex = idx;
          activePhase = phase.label;
      }
  }
  return activePhase;
}

const ChatBubble = memo(function ChatBubble({ msg, idx, darkMode, theme, isThinking, isStreamingText, searchQuery = '' }) {
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
                searchQuery={searchQuery}
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

    // 🔥 Smooth transition & animasi untuk teks berpikir
    const [displayThought, setDisplayThought] = useState("CAKRA sedang berpikir...");
    const [isThoughtVisible, setIsThoughtVisible] = useState(true);
    const thoughtTimerRef = useRef(null);

    useEffect(() => {
        if (!isThinkingMsg) return;

        const nextThought = formatThinkingPhase(msg.thought);

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
                                <CakraResponseRenderer
                                    rawContent={msg.content || ''}
                                    thinkingContent={msg.thinking || msg.thought || ''}
                                    isStreaming={isStreamingMsg}
                                    darkMode={darkMode}
                                    theme={theme}
                                    searchQuery={searchQuery}
                                />
                            </div>

                            {!isStreamingMsg && (msg.citations || msg.sources) && (
                                <>
                                    <RAGMetrics
                                        sources={msg.citations || msg.sources}
                                        darkMode={darkMode}
                                        theme={theme}
                                    />
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
                                </>
                            )}

                            {/* Tombol Salin Markdown kedua dihapus karena sudah ada di pojok atas */}

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
        prevProps.msg.reasoning === nextProps.msg.reasoning &&
        prevProps.msg.role === nextProps.msg.role &&
        prevProps.isThinking === nextProps.isThinking &&
        prevProps.isStreamingText === nextProps.isStreamingText &&
        prevProps.darkMode === nextProps.darkMode &&
        prevProps.idx === nextProps.idx &&
        prevProps.searchQuery === nextProps.searchQuery &&
        prevProps.msg.totalMessages === nextProps.msg.totalMessages &&
        JSON.stringify(prevProps.msg.attachments) === JSON.stringify(nextProps.msg.attachments)
    );
});

export default ChatBubble;