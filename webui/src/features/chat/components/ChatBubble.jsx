import React, { useState, useEffect, useRef, memo, useCallback } from 'react';
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
import { translations } from '../../../utils/translations';

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

const ChatBubble = memo(function ChatBubble({ msg, idx, darkMode, theme, isThinking, isStreamingText, searchQuery = '', isLastMessage, onFileClick, setPreviewImage, onOpenArtifact, handleDownloadAllArtifacts, handleDownloadArtifact, language = 'id' }) {
    const tGlobal = translations[language] || translations.id;
    const tTTS = translations[language]?.tts || translations.id.tts;
    const [showToast, setShowToast] = useState(false);
    const [toastMsg, setToastMsg] = useState('');
    const ttsSpeed = useChatStore(state => state.ttsSpeed);
    const editAndRegenerate = useChatStore(state => state.editAndRegenerate);

    const handleInstantRetry = useCallback(() => {
        const storeMessages = useChatStore.getState().messages;
        const targetIdx = idx - 1;
        if (targetIdx >= 0 && storeMessages[targetIdx]) {
            const userText = storeMessages[targetIdx].content;
            editAndRegenerate(targetIdx, userText);
        } else {
            for (let i = idx - 1; i >= 0; i--) {
                if (storeMessages[i]?.role === 'user') {
                    editAndRegenerate(i, storeMessages[i].content);
                    break;
                }
            }
        }
    }, [idx, editAndRegenerate]);

    // TTS Audio State
    const [isAudioLoading, setIsAudioLoading] = useState(false);
    const [isAudioPlaying, setIsAudioPlaying] = useState(false);
    const [ttsActive, setTtsActive] = useState(false);
    const [feedbackState, setFeedbackState] = useState(msg.feedback?.rating || null);
    const [isCopied, setIsCopied] = useState(false);
    const [isAvatarHovered, setIsAvatarHovered] = useState(false);

    const ttsQueueRef = useRef({
        textChunks: [],
        audioUrls: [],
        cursor: 0,
        isFetching: false,
        isPlaying: false,
        isStopped: false,
    });
    const currentAudioRef = useRef(null);

    const isThisMessageStreaming = msg.isStreaming === true;
    const autoReadAloud = useChatStore((state) => state.autoReadAloud);
    const ttsVoice = useChatStore((state) => state.ttsVoice);

    // Clean text helper
    const cleanTextForTTS = useCallback((text) => {
        return text
            .replace(/\[\[CAKRA_FILE_PROCESS_LOG(?:_\d+)?\]\]/g, "")
            .replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, "")
            .replace(/[*_#`~>"]/g, "") // Removed " to avoid 'kutip dua'
            .replace(/:/g, ",") // Replaced : with , to avoid 'titik dua' and create a natural pause
            .trim();
    }, []);

    // Stop TTS completely
    const stopTTS = useCallback(() => {
        ttsQueueRef.current.isStopped = true;
        ttsQueueRef.current.textChunks = [];

        // Revoke all remaining URLs
        ttsQueueRef.current.audioUrls.forEach(url => URL.revokeObjectURL(url));
        ttsQueueRef.current.audioUrls = [];

        if (currentAudioRef.current) {
            currentAudioRef.current.pause();
            currentAudioRef.current = null;
        }

        setTtsActive(false);
        setIsAudioPlaying(false);
        setIsAudioLoading(false);
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopTTS();
        };
    }, [stopTTS]);

    // Auto trigger on mount/streaming if autoReadAloud is true
    useEffect(() => {
        if (isLastMessage && autoReadAloud && msg.role === 'assistant' && isThisMessageStreaming) {
            setTtsActive(true);
            ttsQueueRef.current.isStopped = false;
        }
    }, [isLastMessage, autoReadAloud, msg.role, isThisMessageStreaming]);

    const isThisMessageStreamingRef = useRef(isThisMessageStreaming);
    useEffect(() => {
        isThisMessageStreamingRef.current = isThisMessageStreaming;
    }, [isThisMessageStreaming]);

    // Process Audio Playback Queue
    const playNextAudio = useCallback(() => {
        if (ttsQueueRef.current.isStopped || ttsQueueRef.current.isPlaying) return;

        if (ttsQueueRef.current.audioUrls.length > 0) {
            ttsQueueRef.current.isPlaying = true;
            setIsAudioPlaying(true);

            const url = ttsQueueRef.current.audioUrls.shift();
            const audio = new Audio(url);
            currentAudioRef.current = audio;

            audio.onended = () => {
                URL.revokeObjectURL(url);
                currentAudioRef.current = null;
                ttsQueueRef.current.isPlaying = false;
                playNextAudio();

                // If everything is done
                if (ttsQueueRef.current.textChunks.length === 0 &&
                    ttsQueueRef.current.audioUrls.length === 0 &&
                    !isThisMessageStreamingRef.current &&
                    !ttsQueueRef.current.isFetching) {
                    setIsAudioPlaying(false);
                    setTtsActive(false);
                }
            };

            audio.onerror = () => {
                URL.revokeObjectURL(url);
                currentAudioRef.current = null;
                ttsQueueRef.current.isPlaying = false;
                setToastMsg(tTTS.failedPlay);
                setShowToast(true);
                setTimeout(() => setShowToast(false), 2000);
                playNextAudio();
            };

            audio.play().catch(e => {
                console.error("Audio play error", e);
                audio.onerror();
            });
        }
    }, [isThisMessageStreaming, tTTS.failedPlay]);

    // Process Text Fetching Queue
    const fetchNextTTS = useCallback(async () => {
        if (ttsQueueRef.current.isStopped || ttsQueueRef.current.isFetching || ttsQueueRef.current.textChunks.length === 0) return;

        ttsQueueRef.current.isFetching = true;
        setIsAudioLoading(true);

        const textToRead = ttsQueueRef.current.textChunks.shift();

        const detectLanguage = (text) => {
            const enWords = ['the', 'is', 'are', 'and', 'of', 'to', 'in', 'that', 'it', 'for', 'on', 'with', 'as', 'this', 'but'];
            const idWords = ['yang', 'di', 'ke', 'dari', 'dan', 'ini', 'itu', 'untuk', 'dengan', 'dalam', 'pada', 'adalah', 'akan', 'bisa', 'saya'];
            const words = text.toLowerCase().split(/\s+/);
            let enCount = 0, idCount = 0;
            words.forEach(w => {
                if (enWords.includes(w)) enCount++;
                if (idWords.includes(w)) idCount++;
            });
            return enCount > idCount ? 'en' : 'id';
        };

        try {
            let finalVoice = ttsVoice;
            if (!finalVoice) {
                const lang = detectLanguage(textToRead);
                finalVoice = lang === 'en' ? 'en-US-GuyNeural' : 'id-ID-ArdiNeural';
            }

            const res = await apiClient.post('/voice/tts', {
                text: textToRead,
                voice: finalVoice,
                speed: ttsSpeed || 'normal'
            }, { responseType: 'blob', timeout: 120000 });
            if (ttsQueueRef.current.isStopped) return;

            const url = URL.createObjectURL(res.data);
            ttsQueueRef.current.audioUrls.push(url);

            playNextAudio();
        } catch (err) {
            console.error("TTS Error:", err);
            const detail = err.response?.data?.detail;
            setToastMsg(typeof detail === 'string' ? detail : tTTS.failedPlay || "Gagal memutar suara.");
            setShowToast(true);
            setTimeout(() => setShowToast(false), 3500);
        } finally {
            ttsQueueRef.current.isFetching = false;
            setIsAudioLoading(false);

            if (ttsQueueRef.current.textChunks.length > 0) {
                fetchNextTTS();
            }
        }
    }, [playNextAudio, ttsVoice, ttsSpeed]);
    // Watch for text changes and chunk sentences
    useEffect(() => {
        if (!ttsActive || ttsQueueRef.current.isStopped) return;

        const isF5Voice = ttsVoice && (ttsVoice.startsWith('id-ID-Pria') || ttsVoice.startsWith('id-ID-Wanita'));

        // ── F5-TTS Mode (Indonesian voices) ─────────────────────────────────
        // Strategy: split at ANY newline or ~150 char sentence boundary.
        // Each chunk → 1 internal F5-TTS batch (no internal re-batching).
        // Pipeline: while chunk N plays, chunk N+1 is being fetched.
        if (isF5Voice) {
            const content = msg.content || '';
            let unprocessed = content.substring(ttsQueueRef.current.cursor);

            let foundChunk = false;

            // 1. Split at ANY newline (covers single \n for list items too)
            const lineRegex = /\n+/g;
            let lineMatch;
            lineRegex.lastIndex = 0;
            while ((lineMatch = lineRegex.exec(unprocessed)) !== null) {
                const boundaryIdx = lineMatch.index;
                const chunk = unprocessed.substring(0, boundaryIdx);
                const cleaned = cleanTextForTTS(chunk);
                if (cleaned) {
                    if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                    ttsQueueRef.current.chunkBuffer += cleaned + " ";
                    // Flush buffer when it has enough content (>= 40 chars) or is a real paragraph break (\n\n)
                    if (ttsQueueRef.current.chunkBuffer.length >= 40 || lineMatch[0].length > 1) {
                        ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                        ttsQueueRef.current.chunkBuffer = "";
                    }
                }
                ttsQueueRef.current.cursor += boundaryIdx + lineMatch[0].length;
                unprocessed = content.substring(ttsQueueRef.current.cursor);
                foundChunk = true;
                lineRegex.lastIndex = 0; // reset to scan new unprocessed
            }

            // 2. If buffer > 150 chars with no newline yet, split at sentence boundary
            if (!foundChunk && unprocessed.length > 150) {
                const sentRegex = /[.?!,]+\s/g;
                let lastEnd = -1;
                let sm;
                sentRegex.lastIndex = 0;
                while ((sm = sentRegex.exec(unprocessed)) !== null) {
                    const pos = sm.index + sm[0].length;
                    if (pos > 150) break;
                    lastEnd = pos;
                }
                if (lastEnd > 30) {
                    const chunk = unprocessed.substring(0, lastEnd);
                    const cleaned = cleanTextForTTS(chunk);
                    if (cleaned) {
                        if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                        ttsQueueRef.current.chunkBuffer += cleaned + " ";
                        if (ttsQueueRef.current.chunkBuffer.length >= 150) {
                            ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                            ttsQueueRef.current.chunkBuffer = "";
                        }
                    }
                    ttsQueueRef.current.cursor += lastEnd;
                    foundChunk = true;
                }
            }

            // 3. Flush remaining when LLM streaming is done
            if (!isThisMessageStreaming) {
                const remaining = content.substring(ttsQueueRef.current.cursor);
                const cleaned = cleanTextForTTS(remaining);
                const existingBuf = ttsQueueRef.current.chunkBuffer || "";
                const finalChunk = (existingBuf + " " + (cleaned || "")).trim();
                if (finalChunk) {
                    ttsQueueRef.current.textChunks.push(finalChunk);
                }
                ttsQueueRef.current.chunkBuffer = "";
                ttsQueueRef.current.cursor = content.length;
            }

            if (ttsQueueRef.current.textChunks.length > 0 && !ttsQueueRef.current.isFetching) {
                fetchNextTTS();
            }
            return;
        }

        // ── Edge-TTS Mode (real-time streaming per sentence) ─────────────────
        const content = msg.content || '';
        let unprocessed = content.substring(ttsQueueRef.current.cursor);

        const sentenceRegex = /([.?!]+[\s\n]+|\n{1,})/g;

        let match;
        let lastIndex = 0;
        let foundChunk = false;

        while ((match = sentenceRegex.exec(unprocessed)) !== null) {
            const boundaryIndex = match.index + match[0].length;
            const chunk = unprocessed.substring(lastIndex, boundaryIndex);

            const cleaned = cleanTextForTTS(chunk);
            if (cleaned) {
                if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                ttsQueueRef.current.chunkBuffer += cleaned + " ";

                if (ttsQueueRef.current.chunkBuffer.length > 50 || match[0].includes('\n')) {
                    ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                    ttsQueueRef.current.chunkBuffer = "";
                }
            }

            lastIndex = boundaryIndex;
            ttsQueueRef.current.cursor += chunk.length;
            foundChunk = true;
        }
        unprocessed = content.substring(ttsQueueRef.current.cursor);
        if (!foundChunk && unprocessed.length > 80 && unprocessed.includes(' ')) {
            const lastSpaceIndex = unprocessed.lastIndexOf(' ');
            if (lastSpaceIndex > 0) {
                const chunk = unprocessed.substring(0, lastSpaceIndex + 1);
                const cleaned = cleanTextForTTS(chunk);
                if (cleaned) {
                    if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                    ttsQueueRef.current.chunkBuffer += cleaned + " ";
                    ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                    ttsQueueRef.current.chunkBuffer = "";
                }
                ttsQueueRef.current.cursor += chunk.length;
            }
        }

        if (!isThisMessageStreaming && ttsQueueRef.current.cursor < content.length) {
            const remaining = content.substring(ttsQueueRef.current.cursor);
            const cleaned = cleanTextForTTS(remaining);
            if (cleaned || ttsQueueRef.current.chunkBuffer) {
                const finalChunk = (ttsQueueRef.current.chunkBuffer || "") + " " + (cleaned || "");
                if (finalChunk.trim()) {
                    ttsQueueRef.current.textChunks.push(finalChunk.trim());
                }
                ttsQueueRef.current.chunkBuffer = "";
            }
            ttsQueueRef.current.cursor = content.length;
        }

        if (ttsQueueRef.current.textChunks.length > 0 && !ttsQueueRef.current.isFetching) {
            fetchNextTTS();
        }

    }, [msg.content, ttsActive, isThisMessageStreaming, fetchNextTTS, ttsVoice, cleanTextForTTS]);

    // Safety effect to reset TTS state if it gets stuck at the end
    useEffect(() => {
        if (ttsActive &&
            !isThisMessageStreaming &&
            ttsQueueRef.current.textChunks.length === 0 &&
            ttsQueueRef.current.audioUrls.length === 0 &&
            !ttsQueueRef.current.isFetching &&
            !ttsQueueRef.current.isPlaying) {

            setIsAudioPlaying(false);
            setTtsActive(false);
        }
    });

    const toggleReadAloud = useCallback(() => {
        if (ttsActive) {
            stopTTS();
        } else {
            ttsQueueRef.current = {
                textChunks: [],
                audioUrls: [],
                cursor: 0,
                isFetching: false,
                isPlaying: false,
                isStopped: false,
            };
            setTtsActive(true);
        }
    }, [ttsActive, stopTTS]);


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
            setIsCopied(true);
            setTimeout(() => {
                setShowToast(false);
                setIsCopied(false);
            }, 2000);
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
                language={language}
            />
        );
    }

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
        <div style={{ ...styles.assistantRow, animation: 'fadeInUp 0.4s ease-out forwards' }}>
            <div style={styles.assistantMessageWrapper}>
                <div style={{ ...styles.assistantHeader, display: 'flex', alignItems: 'center' }}>
                    <div 
                        style={{ ...styles.avatarWrap, position: 'relative' }}
                        onMouseEnter={() => setIsAvatarHovered(true)}
                        onMouseLeave={() => setIsAvatarHovered(false)}
                    >
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
                        <div style={{ marginLeft: 8, display: 'flex', alignItems: 'center', height: '24px', overflow: 'hidden' }}>
                            {isAvatarHovered ? (
                                <div style={{
                                    display: 'inline-block',
                                    overflow: 'hidden',
                                    whiteSpace: 'nowrap',
                                    animation: 'typing 0.2s steps(40, end)',
                                    color: theme.textColor,
                                    fontSize: 12,
                                    fontWeight: 500
                                }}>
                                    Hi, I'm CAKRA. How can I help you today?
                                </div>
                            ) : (
                                <span style={{ ...styles.avatarLabel, color: theme.textColor, transition: 'opacity 0.3s' }}>
                                    CAKRA
                                </span>
                            )}
                        </div>
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
                                                language={language}
                                            />
                                        ) : null}
                                        language={language}
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
                                    language={language}
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
                                            key={`renderer-${i + 1}`}
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
                            gap: '2px',
                            marginTop: '4px', // Jarak aman mepet di bawah teks respons tanpa garis pembatas
                            width: '100%',
                            justifyContent: 'flex-start'
                        }}>
                            {/* 👍 TOMBOL GOOD (THUMB UP) */}
                            <button
                                type="button"
                                onClick={() => {
                                    if (feedbackState === 'good') return;
                                    apiClient.patch(`/chat/sessions/${useChatStore.getState().sessionUuid}/messages/feedback`, {
                                        message_index: idx,
                                        feedback: { rating: 'good' }
                                    }).then(() => {
                                        setFeedbackState('good');
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
                                    background: feedbackState === 'good' ? (darkMode ? 'rgba(16,185,129,0.15)' : 'rgba(16,185,129,0.1)') : 'transparent',
                                    border: 'none',
                                    cursor: feedbackState === 'good' ? 'default' : 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: feedbackState === 'good' ? 1 : 0.5,
                                    color: feedbackState === 'good' ? '#10b981' : (darkMode ? '#94a3b8' : '#64748b')
                                }}
                                title={tGlobal.chat.goodResponse}
                                onMouseEnter={(e) => {
                                    if (feedbackState === 'good') return;
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = '#10b981'; // Glow Hijau pas di-hover
                                    e.currentTarget.style.background = darkMode ? 'rgba(16,185,129,0.1)' : 'rgba(16,185,129,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    if (feedbackState === 'good') return;
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill={feedbackState === 'good' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                                </svg>
                            </button>

                            {/* 👎 TOMBOL BAD (THUMB DOWN) */}
                            <button
                                type="button"
                                onClick={() => {
                                    if (feedbackState === 'bad') return;
                                    apiClient.patch(`/chat/sessions/${useChatStore.getState().sessionUuid}/messages/feedback`, {
                                        message_index: idx,
                                        feedback: { rating: 'bad' }
                                    }).then(() => {
                                        setFeedbackState('bad');
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
                                    background: feedbackState === 'bad' ? (darkMode ? 'rgba(239,68,68,0.15)' : 'rgba(239,68,68,0.1)') : 'transparent',
                                    border: 'none',
                                    cursor: feedbackState === 'bad' ? 'default' : 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: feedbackState === 'bad' ? 1 : 0.5,
                                    color: feedbackState === 'bad' ? '#ef4444' : (darkMode ? '#94a3b8' : '#64748b')
                                }}
                                title={tGlobal.chat.badResponse}
                                onMouseEnter={(e) => {
                                    if (feedbackState === 'bad') return;
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = '#ef4444'; // Glow Merah pas di-hover
                                    e.currentTarget.style.background = darkMode ? 'rgba(239,68,68,0.1)' : 'rgba(239,68,68,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    if (feedbackState === 'bad') return;
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill={feedbackState === 'bad' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                                </svg>
                            </button>

                            {/* 📋 TOMBOL COPY (DOUBLE DOCUMENT LAYERS) */}
                            <button
                                type="button"
                                onClick={() => executeTextCopy(msg.content)}
                                style={{
                                    background: isCopied ? (darkMode ? 'rgba(16,185,129,0.15)' : 'rgba(16,185,129,0.1)') : 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: isCopied ? 1 : 0.5,
                                    color: isCopied ? '#10b981' : (darkMode ? '#94a3b8' : '#64748b')
                                }}
                                title={tGlobal.chat.copyResponse}
                                onMouseEnter={(e) => {
                                    if (isCopied) return;
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = darkMode ? '#6366f1' : '#2563eb'; // Glow Tema Utama Indigo/Blue
                                    e.currentTarget.style.background = darkMode ? 'rgba(99,102,241,0.1)' : 'rgba(37,99,235,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    if (isCopied) return;
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                {isCopied ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="20 6 9 17 4 12"></polyline>
                                    </svg>
                                ) : (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                    </svg>
                                )}
                            </button>

                            {/* 🔊 TOMBOL READ ALOUD (SPEAKER) */}
                            <button
                                type="button"
                                onClick={toggleReadAloud}
                                disabled={isAudioLoading}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    cursor: isAudioLoading ? 'wait' : 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: isAudioPlaying ? 1 : 0.5,
                                    color: isAudioPlaying
                                        ? '#3b82f6'
                                        : (darkMode ? '#94a3b8' : '#64748b')
                                }}
                                title={isAudioPlaying ? tTTS.stopReading : tTTS.readAloud}
                                onMouseEnter={(e) => {
                                    if (!isAudioPlaying) {
                                        e.currentTarget.style.opacity = '1';
                                        e.currentTarget.style.color = '#3b82f6';
                                        e.currentTarget.style.background = darkMode ? 'rgba(59,130,246,0.1)' : 'rgba(59,130,246,0.05)';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isAudioPlaying) {
                                        e.currentTarget.style.opacity = '0.5';
                                        e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                        e.currentTarget.style.background = 'transparent';
                                    }
                                }}
                            >
                                {isAudioLoading ? (
                                    <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                ) : isAudioPlaying ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <rect x="6" y="4" width="4" height="16"></rect>
                                        <rect x="14" y="4" width="4" height="16"></rect>
                                    </svg>
                                ) : (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                                    </svg>
                                )}
                            </button>

                            {/* 🔄 TOMBOL INSTANT RETRY / REGENERATE */}
                            <button
                                type="button"
                                onClick={handleInstantRetry}
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
                                title={tGlobal.chat.retryResponse || 'Ulangi Respons'}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.opacity = '1';
                                    e.currentTarget.style.color = darkMode ? '#10b981' : '#059669';
                                    e.currentTarget.style.background = darkMode ? 'rgba(16,185,129,0.1)' : 'rgba(5,150,105,0.05)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.opacity = '0.5';
                                    e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                                    <path d="M3 3v5h5"></path>
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
    // Jika bukan pesan terakhir dan objek msg sama persis, abaikan perubahan status streaming global
    if (!prevProps.isLastMessage && !nextProps.isLastMessage && prevProps.msg === nextProps.msg && prevProps.darkMode === nextProps.darkMode) {
        return true;
    }
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
        prevProps.msg.attachments === nextProps.msg.attachments &&
        prevProps.msg.fileGenerations === nextProps.msg.fileGenerations
    );
});

export default ChatBubble;