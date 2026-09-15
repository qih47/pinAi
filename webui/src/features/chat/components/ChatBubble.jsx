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
import MessageTimer from './MessageTimer';
import apiClient from '../../../services/apiClient';
import { translations, resolveStatusMessage } from '../../../utils/translations';

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

function formatThinkingPhase(thought, language = 'id') {
    if (!thought) return language === 'en' ? "CAKRA is thinking" : "CAKRA sedang berpikir";

    const isEn = language === 'en';
    const phases = isEn ? [
        { key: "jalur", label: "🚦 Analyzing intent" },
        { key: "Gateway", label: "🚦 Analyzing intent" },
        { key: "dokumen", label: "📚 Searching regulations" },
        { key: "RAG", label: "📚 Searching regulations" },
        { key: "cepat", label: "✍️ Drafting response" },
        { key: "respons", label: "✍️ Drafting response" },
        { key: "Gemma", label: "✍️ Drafting response" },
        { key: "LANGKAH 1", label: "🔍 Searching documents" },
        { key: "SELEKSI DOKUMEN", label: "🔍 Searching documents" },
        { key: "LANGKAH 2", label: "🧠 Analyzing documents" },
        { key: "ANALISIS ISI", label: "🧠 Analyzing documents" },
        { key: "LANGKAH 3", label: "✍️ Drafting answer" },
        { key: "RENCANA JAWABAN", label: "✍️ Drafting answer" },
        { key: "PDF", label: "📄 Reading PDF attachment" },
        { key: "visual", label: "🖼️ Analyzing visual" }
    ] : [
        { key: "jalur", label: "🚦 Menganalisis intent" },
        { key: "Gateway", label: "🚦 Menganalisis intent" },
        { key: "dokumen", label: "📚 Menelusuri regulasi" },
        { key: "RAG", label: "📚 Menelusuri regulasi" },
        { key: "cepat", label: "✍️ Menyusun respon" },
        { key: "respons", label: "✍️ Menyusun respon" },
        { key: "Gemma", label: "✍️ Menyusun respon" },
        { key: "LANGKAH 1", label: "🔍 Mencari dokumen" },
        { key: "SELEKSI DOKUMEN", label: "🔍 Mencari dokumen" },
        { key: "LANGKAH 2", label: "🧠 Menganalisis dokumen" },
        { key: "ANALISIS ISI", label: "🧠 Menganalisis dokumen" },
        { key: "LANGKAH 3", label: "✍️ Menyusun jawaban" },
        { key: "RENCANA JAWABAN", label: "✍️ Menyusun jawaban" },
        { key: "PDF", label: "📄 Membaca lampiran PDF" },
        { key: "visual", label: "🖼️ Menganalisis visual" }
    ];

    let lastIndex = -1;
    let activePhase = isEn ? "CAKRA is thinking" : "CAKRA sedang berpikir";

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
    const tChat = tGlobal.chat || translations.id.chat || {};
    const [showToast, setShowToast] = useState(false);
    const [toastMsg, setToastMsg] = useState('');
    const ttsSpeed = useChatStore(state => state.ttsSpeed);
    const editAndRegenerate = useChatStore(state => state.editAndRegenerate);
    const regenerateAssistant = useChatStore(state => state.regenerateAssistant);
    const switchMessageVariant = useChatStore(state => state.switchMessageVariant);

    const handleInstantRetry = useCallback(() => {
        if (regenerateAssistant) {
            regenerateAssistant(idx);
        } else {
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
        }
    }, [idx, regenerateAssistant, editAndRegenerate]);

    // TTS Audio State
    const [isAudioLoading, setIsAudioLoading] = useState(false);
    const [isAudioPlaying, setIsAudioPlaying] = useState(false);
    const [ttsActive, setTtsActive] = useState(false);
    const [isHoveredOnTTS, setIsHoveredOnTTS] = useState(false);
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
        chunkBuffer: "",
    });
    const currentAudioRef = useRef(null);
    const ttsAbortControllerRef = useRef(null);
    const globalIsStreaming = useChatStore((state) => state.isStreaming);
    const isEditRegenerating = useChatStore((state) => state.isEditRegenerating);
    const isThisMessageStreaming = Boolean(
        msg.isStreaming === true ||
        (!isEditRegenerating && isLastMessage && globalIsStreaming && msg.role === 'assistant' && msg.isStreaming !== false && (!msg.content || msg.content === ''))
    );
    const autoReadAloud = useChatStore((state) => state.autoReadAloud);
    const ttsVoice = useChatStore((state) => state.ttsVoice);
    const activeTtsMessageId = useChatStore((state) => state.activeTtsMessageId);
    const setActiveTtsMessageId = useChatStore((state) => state.setActiveTtsMessageId);
    const messageId = msg.id || msg.uuid || `msg-${idx}`;

    // Clean text helper tingkat lanjut
    const cleanTextForTTS = useCallback((text) => {
        if (!text) return "";
        let t = text;
        // 1. Buang total blok code / metadata yang mungkin tersisa
        t = t.replace(/```(?:websearch|urlfetch|docsearch|document_meta|json)?[\s\S]*?```/g, "");
        t = t.replace(/\[\[CAKRA_FILE_PROCESS_LOG(?:_\d+)?\]\]/g, "");

        // 2. Format Sitasi Sumber: [Sumber: UMY](...) atau [Sumber: UMY]
        t = t.replace(/\[Sumber\s*:?\s*([^\]]+)\](?:\([^)]*\))?/gi, (match, label) => {
            let src = label.trim().replace(/^:\s*/, '');
            // Spasi huruf jika akronim (misal UMY -> U M Y)
            if (/^[A-Z]{2,5}$/.test(src)) {
                src = src.split('').join(' ');
            }
            src = src.replace(/\.com\b/gi, ' dot com')
                     .replace(/\.co\.id\b/gi, ' dot co dot i d')
                     .replace(/\.id\b/gi, ' dot i d')
                     .replace(/\.ac\.id\b/gi, ' dot a c dot i d');
            return `, sumber dari ${src}.`;
        });

        // 3. Buang tautan markdown umum [Label](url) -> ambil Labelnya saja
        t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
        // Buang URL langsung
        t = t.replace(/https?:\/\/\S+/gi, "");

        // 4. Rentang Angka (misal: 4–6 September -> 4 sampai 6 September)
        t = t.replace(/(\d+)\s*[-–—]\s*(\d+)/g, "$1 sampai $2");

        // 5. Hapus emoji & markdown visual
        t = t.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, "");
        t = t.replace(/[*_#`~>"]/g, ""); // Hapus tanda bintang, pagar, petik ganda
        
        // 6. Rapikan titik dua: jika ada di dalam kalimat, ganti titik
        t = t.replace(/:/g, ".");
        
        // 7. Rapikan koma dan spasi
        t = t.replace(/,\s*,+/g, ", ");
        t = t.replace(/\s*,\s*/g, ", ");
        t = t.replace(/,\s*\./g, ".");
        t = t.replace(/\s{2,}/g, " ").trim();

        return t;
    }, []);

    // Stop TTS completely and abort any in-flight network request immediately
    const stopTTS = useCallback(() => {
        if (ttsAbortControllerRef.current) {
            ttsAbortControllerRef.current.abort();
            ttsAbortControllerRef.current = null;
        }

        ttsQueueRef.current.isStopped = true;
        ttsQueueRef.current.isFetching = false;
        ttsQueueRef.current.isPlaying = false;
        ttsQueueRef.current.textChunks = [];

        // Revoke all remaining URLs
        ttsQueueRef.current.audioUrls.forEach(url => URL.revokeObjectURL(url));
        ttsQueueRef.current.audioUrls = [];

        if (currentAudioRef.current) {
            currentAudioRef.current.pause();
            currentAudioRef.current.src = "";
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

    // If another message took over active TTS, stop and abort this one immediately
    useEffect(() => {
        if (activeTtsMessageId !== messageId && (ttsActive || isAudioLoading || isAudioPlaying)) {
            stopTTS();
        }
    }, [activeTtsMessageId, messageId, ttsActive, isAudioLoading, isAudioPlaying, stopTTS]);

    // Auto trigger on mount/streaming if autoReadAloud is true
    useEffect(() => {
        if (isLastMessage && autoReadAloud && msg.role === 'assistant' && isThisMessageStreaming) {
            setActiveTtsMessageId(messageId);
            setTtsActive(true);
            ttsQueueRef.current.isStopped = false;
        }
    }, [isLastMessage, autoReadAloud, msg.role, isThisMessageStreaming, messageId, setActiveTtsMessageId]);

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

                // If everything is done
                if (ttsQueueRef.current.textChunks.length === 0 &&
                    ttsQueueRef.current.audioUrls.length === 0 &&
                    !isThisMessageStreamingRef.current &&
                    !ttsQueueRef.current.isFetching) {
                    setIsAudioPlaying(false);
                    setTtsActive(false);
                } else {
                    // Jeda nafas alami 120ms sebelum chunk berikutnya diputar
                    setTimeout(() => {
                        if (!ttsQueueRef.current.isStopped) {
                            playNextAudio();
                        }
                    }, 120);
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

        const controller = new AbortController();
        ttsAbortControllerRef.current = controller;

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
            }, { 
                responseType: 'blob', 
                timeout: 120000,
                signal: controller.signal,
            });
            if (ttsQueueRef.current.isStopped || controller.signal.aborted) return;

            const url = URL.createObjectURL(res.data);
            ttsQueueRef.current.audioUrls.push(url);

            playNextAudio();
        } catch (err) {
            if (controller.signal.aborted || err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') {
                return;
            }
            console.error("TTS Error:", err);
            const detail = err.response?.data?.detail;
            setToastMsg(typeof detail === 'string' ? detail : tTTS.failedPlay || "Gagal memutar suara.");
            setShowToast(true);
            setTimeout(() => setShowToast(false), 3500);
        } finally {
            if (ttsAbortControllerRef.current === controller) {
                ttsAbortControllerRef.current = null;
            }
            ttsQueueRef.current.isFetching = false;
            setIsAudioLoading(false);

            if (!ttsQueueRef.current.isStopped && ttsQueueRef.current.textChunks.length > 0) {
                fetchNextTTS();
            }
        }
    }, [playNextAudio, ttsVoice, ttsSpeed]);
    // Watch for text changes and chunk sentences
    useEffect(() => {
        if (!ttsActive || ttsQueueRef.current.isStopped) return;

        const isF5Voice = ttsVoice && (ttsVoice.startsWith('id-ID-Pria') || ttsVoice.startsWith('id-ID-Wanita'));

        // ── F5-TTS Mode (Indonesian voices) ─────────────────────────────────
        // Pipeline: while chunk N plays, chunk N+1 is being fetched.
        // Lewati total blok metadata seperti ```websearch ... ``` agar tidak pernah dibaca.
        if (isF5Voice) {
            const content = msg.content || '';

            // Lewati metadata code block di awal (misal: ```websearch ... ``` atau ```urlfetch ... ```)
            let currentCursor = ttsQueueRef.current.cursor || 0;
            const leadingMetaRegex = /^\s*```(?:websearch|urlfetch|docsearch|document_meta|json)?[\s\S]*?(?:```|$)/;
            const metaMatch = content.match(leadingMetaRegex);
            if (metaMatch) {
                const metaEnd = metaMatch[0].length;
                // Jika blok code di awal belum tuntas di-stream oleh LLM, tunggu sampai selesai
                if (!metaMatch[0].endsWith('```') && isThisMessageStreaming) {
                    return;
                }
                if (currentCursor < metaEnd) {
                    currentCursor = metaEnd;
                    ttsQueueRef.current.cursor = metaEnd;
                }
            }

            let unprocessed = content.substring(currentCursor);
            let foundChunk = false;

            // 1. Pemisahan berbasis kalimat utuh (. ? !) atau baris list / paragraf
            const sentenceRegex = /([.?!]+(?:\s+|\n+|$)|(?:\n\s*[-*•]|\n\s*\d+\.|\n\n+))/g;
            let match;
            sentenceRegex.lastIndex = 0;

            while ((match = sentenceRegex.exec(unprocessed)) !== null) {
                const boundaryIdx = match.index + match[0].length;
                const rawChunk = unprocessed.substring(0, boundaryIdx);
                const cleaned = cleanTextForTTS(rawChunk);

                if (cleaned) {
                    if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                    ttsQueueRef.current.chunkBuffer += (ttsQueueRef.current.chunkBuffer ? " " : "") + cleaned;

                    // Flush jika mencapai satu kalimat matang (>= 30 karakter) atau tanda pemutus kuat (!, ?, \n)
                    const isStrongPunct = match[0].includes('!') || match[0].includes('?') || match[0].includes('\n');
                    if (ttsQueueRef.current.chunkBuffer.length >= 30 || isStrongPunct) {
                        ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                        ttsQueueRef.current.chunkBuffer = "";
                    }
                }

                ttsQueueRef.current.cursor += boundaryIdx;
                unprocessed = content.substring(ttsQueueRef.current.cursor);
                foundChunk = true;
                sentenceRegex.lastIndex = 0;
            }

            // 2. Jika buffer teks terus mengalir tanpa tanda baca hingga > 120 karakter, cari spasi aman
            if (!foundChunk && unprocessed.length > 120) {
                const lastSpace = unprocessed.lastIndexOf(' ');
                if (lastSpace > 40) {
                    const rawChunk = unprocessed.substring(0, lastSpace + 1);
                    const cleaned = cleanTextForTTS(rawChunk);
                    if (cleaned) {
                        if (!ttsQueueRef.current.chunkBuffer) ttsQueueRef.current.chunkBuffer = "";
                        ttsQueueRef.current.chunkBuffer += (ttsQueueRef.current.chunkBuffer ? " " : "") + cleaned;
                        if (ttsQueueRef.current.chunkBuffer.length >= 60) {
                            ttsQueueRef.current.textChunks.push(ttsQueueRef.current.chunkBuffer.trim());
                            ttsQueueRef.current.chunkBuffer = "";
                        }
                    }
                    ttsQueueRef.current.cursor += lastSpace + 1;
                    foundChunk = true;
                }
            }

            // 3. Flush sisa teks saat streaming LLM telah tuntas
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
        if (ttsActive || isAudioLoading || isAudioPlaying) {
            stopTTS();
            if (activeTtsMessageId === messageId) {
                setActiveTtsMessageId(null);
            }
        } else {
            // Claim active TTS globally so all other messages stop & abort immediately
            setActiveTtsMessageId(messageId);
            ttsQueueRef.current = {
                textChunks: [],
                audioUrls: [],
                cursor: 0,
                isFetching: false,
                isPlaying: false,
                isStopped: false,
                chunkBuffer: "",
            };
            setTtsActive(true);
        }
    }, [ttsActive, isAudioLoading, isAudioPlaying, stopTTS, activeTtsMessageId, messageId, setActiveTtsMessageId]);


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

    const fileGens = msg.fileGenerations || [];
    const isFileProcessing = fileGens.some(g => g.stage !== 'done' && g.stage !== 'error');
    const showStatusText = isThisMessageStreaming && (!msg.content || msg.content === '' || isFileProcessing);
    const isThinkingMsg = isThisMessageStreaming && Boolean(msg.isThinking || msg.thinking || (globalIsThinking && (!msg.content || msg.content === '')));
    const isStreamingMsg = isThisMessageStreaming && msg.content !== '';
    const isActive = isThisMessageStreaming;

    // 🔥 Smooth transition & animasi untuk teks status / berpikir dinamis (Claude Style)
    const [displayThought, setDisplayThought] = useState(language === 'en' ? '✨ Responding' : '✨ Merespons');
    const [isThoughtVisible, setIsThoughtVisible] = useState(true);
    const thoughtTimerRef = useRef(null);

    useEffect(() => {
        if (!showStatusText) return;

        // PRIORITIZE msg.statusMessage / msg.statusKey (e.g. from SSE status event) over static fallback
        const localizedStatus = (msg.statusMessage || msg.statusKey) ? resolveStatusMessage(msg, language) : '';
        const rawNext = localizedStatus ? localizedStatus : (formatThinkingPhase(msg.thought, language) || (language === 'en' ? '🧠 Thinking' : '🧠 Berpikir'));
        const nextThought = typeof rawNext === 'string' ? rawNext.replace(/\s*\.{2,}\s*$/, '').trim() : rawNext;

        if (nextThought !== displayThought) {
            if (thoughtTimerRef.current) {
                clearTimeout(thoughtTimerRef.current);
            }
            setIsThoughtVisible(false);

            thoughtTimerRef.current = setTimeout(() => {
                setDisplayThought(nextThought);
                setIsThoughtVisible(true);
                thoughtTimerRef.current = null;
            }, 60);
        }

        return () => {
            if (thoughtTimerRef.current) clearTimeout(thoughtTimerRef.current);
        };
    }, [msg.thought, msg.statusMessage, showStatusText, displayThought, language]);

    return (
        <div style={{ ...styles.assistantRow, animation: 'fadeInUp 0.15s ease-out forwards' }}>
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
                                animation: isActive ? 'cakraSpin 0.7s linear infinite' : 'none',
                                transform: isActive ? undefined : 'rotate(0deg)',
                            }}
                        />
                        {isActive && (
                            <span style={{
                                ...styles.statusDot,
                                background: showStatusText ? '#ef4444' : '#10b981',
                                borderColor: theme.mainBg
                            }} />
                        )}
                    </div>
                    {showStatusText ? (
                        <span style={{ display: 'flex', alignItems: 'center', marginLeft: 10, opacity: isThoughtVisible ? 1 : 0, transition: 'opacity 0.1s ease', flexShrink: 0 }}>
                            <span
                                style={{
                                    fontSize: 13.5,
                                    fontStyle: 'italic',
                                    paddingRight: 6,
                                    paddingLeft: 1,
                                    background: 'linear-gradient(90deg, #94a3b8 0%, #e2e8f0 50%, #94a3b8 100%)',
                                    backgroundSize: '200% 100%',
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                    backgroundClip: 'text',
                                    animation: 'shimmerFlow 1.2s linear infinite',
                                    display: 'inline-block',
                                    whiteSpace: 'nowrap'
                                }}
                            >
                                {displayThought}
                            </span>
                            <span style={{ display: 'inline-flex', gap: '2px', alignItems: 'center', height: '14px', lineHeight: 1 }}>
                                <span style={{ fontSize: 16, color: theme.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 16, color: theme.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out 0.15s', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 16, color: theme.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out 0.3s', display: 'inline-block' }}>.</span>
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
                                    {tGlobal.chat.cakraGreeting}
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
                                    <div style={{ width: '100%', display: 'flex', flexDirection: 'column' }}>
                                        <CakraResponseRenderer
                                            rawContent={parts[0]}
                                            thinkingContent={msg.thinking || msg.thought || ''}
                                            isStreaming={isThisMessageStreaming}
                                            darkMode={darkMode}
                                            theme={theme}
                                            searchQuery={searchQuery}
                                            statusMessage={resolveStatusMessage(msg, language)}
                                            messageIndex={idx}
                                            isLastMessage={isLastMessage}
                                            language={language}
                                        />
                                        {fileGens.length > 0 && (
                                            <FileProcessLog
                                                fileGenerations={fileGens}
                                                darkMode={darkMode}
                                                batchIndex={0}
                                                isFinalBatch={true}
                                                language={language}
                                                isStreaming={isThisMessageStreaming}
                                                allFilesCompleted={Boolean(msg.allFilesDone)}
                                            />
                                        )}
                                    </div>
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
                                    statusMessage={resolveStatusMessage(msg, language)}
                                    messageIndex={idx}
                                    isLastMessage={isLastMessage}
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
                                        isStreaming={isThisMessageStreaming}
                                        allFilesCompleted={Boolean(msg.allFilesDone)}
                                        language={language}
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
                                            statusMessage={resolveStatusMessage(msg, language)}
                                            messageIndex={idx}
                                            isLastMessage={isLastMessage}
                                            language={language}
                                        />
                                    );
                                }
                            }

                            return <>{renderedParts}</>;
                        })()}

                        {/* 🔥 POSISI BERHASIL DIPINDAHKAN DI AKHIR STREAM (DI BAWAH RENDERING TEKS JAWABAN) */}
                        {!isThisMessageStreaming && msg.fileGenerations && msg.fileGenerations.length > 0 && msg.fileGenerations.every(g => g.stage === 'done' || g.stage === 'error') && (
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
                                    language={language}
                                />
                            )}
                            {(msg.citations || msg.sources) && (
                                <SourceCitation
                                    sources={msg.citations || msg.sources}
                                    darkMode={darkMode}
                                    theme={theme}
                                    language={language}
                                    activeIsolatedDocId={activeIsolatedDocId}
                                    onActivateIsolation={(source) => {
                                        const docId = source.id || source.dokumen_id;
                                        const docTitle = source.title || source.filename || source.name;
                                        setContextIsolation(docId, docTitle, null, source);
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
                                style={{
                                    background: isHoveredOnTTS && (isAudioLoading || isAudioPlaying) 
                                        ? (darkMode ? 'rgba(239, 68, 68, 0.15)' : 'rgba(239, 68, 68, 0.08)')
                                        : isAudioPlaying 
                                            ? (darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.08)')
                                            : 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '6px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                    opacity: (isAudioPlaying || isAudioLoading || isHoveredOnTTS) ? 1 : 0.5,
                                    color: isHoveredOnTTS && (isAudioLoading || isAudioPlaying)
                                        ? '#ef4444'
                                        : (isAudioPlaying || isAudioLoading)
                                            ? '#3b82f6'
                                            : (darkMode ? '#94a3b8' : '#64748b')
                                }}
                                title={
                                    (isAudioPlaying || isAudioLoading)
                                        ? (isHoveredOnTTS ? "Hentikan Baca" : (isAudioLoading ? "Menyiapkan suara... (Klik untuk batal)" : tTTS.stopReading))
                                        : tTTS.readAloud
                                }
                                onMouseEnter={() => setIsHoveredOnTTS(true)}
                                onMouseLeave={() => setIsHoveredOnTTS(false)}
                            >
                                {isAudioLoading ? (
                                    isHoveredOnTTS ? (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                            <rect x="5" y="5" width="14" height="14" rx="2"></rect>
                                        </svg>
                                    ) : (
                                        <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                        </svg>
                                    )
                                ) : isAudioPlaying ? (
                                    isHoveredOnTTS ? (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                            <rect x="5" y="5" width="14" height="14" rx="2"></rect>
                                        </svg>
                                    ) : (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <rect x="6" y="4" width="4" height="16"></rect>
                                            <rect x="14" y="4" width="4" height="16"></rect>
                                        </svg>
                                    )
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

                            {/* 📑 VARIANT NAVIGATOR (< 1 / 3 >) */}
                            {Array.isArray(msg.variants) && msg.variants.length > 1 && (
                                <div
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '2px',
                                        marginLeft: '4px',
                                        marginRight: '4px',
                                        fontSize: '12px',
                                        fontWeight: 500,
                                        userSelect: 'none',
                                        color: darkMode ? '#94a3b8' : '#64748b'
                                    }}
                                >
                                    {/* Tombol < (Previous) */}
                                    <button
                                        type="button"
                                        disabled={(msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) <= 0}
                                        onClick={() => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            if (currentVIdx > 0 && switchMessageVariant) {
                                                switchMessageVariant(idx, currentVIdx - 1);
                                            }
                                        }}
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            cursor: (msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) <= 0 ? 'default' : 'pointer',
                                            padding: '2px 4px',
                                            borderRadius: '4px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            opacity: (msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) <= 0 ? 0.25 : 0.7,
                                            color: 'inherit',
                                            transition: 'all 0.15s ease'
                                        }}
                                        title={tChat.prevVersion || (language === 'en' ? 'Previous version' : 'Versi sebelumnya')}
                                        onMouseEnter={(e) => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            if (currentVIdx > 0) {
                                                e.currentTarget.style.opacity = '1';
                                                e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            e.currentTarget.style.opacity = currentVIdx <= 0 ? 0.25 : 0.7;
                                            e.currentTarget.style.background = 'transparent';
                                        }}
                                    >
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="15 18 9 12 15 6"></polyline>
                                        </svg>
                                    </button>

                                    {/* Indikator Versi "1 / 3" */}
                                    <span style={{ padding: '0 2px', minWidth: '28px', textAlign: 'center' }}>
                                        {((msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) + 1)} / {msg.variants.length}
                                    </span>

                                    {/* Tombol > (Next) */}
                                    <button
                                        type="button"
                                        disabled={(msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) >= msg.variants.length - 1}
                                        onClick={() => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            if (currentVIdx < msg.variants.length - 1 && switchMessageVariant) {
                                                switchMessageVariant(idx, currentVIdx + 1);
                                            }
                                        }}
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            cursor: (msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) >= msg.variants.length - 1 ? 'default' : 'pointer',
                                            padding: '2px 4px',
                                            borderRadius: '4px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            opacity: (msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1)) >= msg.variants.length - 1 ? 0.25 : 0.7,
                                            color: 'inherit',
                                            transition: 'all 0.15s ease'
                                        }}
                                        title={tChat.nextVersion || (language === 'en' ? 'Next version' : 'Versi berikutnya')}
                                        onMouseEnter={(e) => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            if (currentVIdx < msg.variants.length - 1) {
                                                e.currentTarget.style.opacity = '1';
                                                e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            const currentVIdx = msg.activeVariantIndex !== undefined ? msg.activeVariantIndex : (msg.variants.length - 1);
                                            e.currentTarget.style.opacity = currentVIdx >= msg.variants.length - 1 ? 0.25 : 0.7;
                                            e.currentTarget.style.background = 'transparent';
                                        }}
                                    >
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="9 18 15 12 9 6"></polyline>
                                        </svg>
                                    </button>
                                </div>
                            )}

                            {/* ⏱️ LABEL TIMER DI SEBELAH KANAN REGENERATE (DINAMIS SESUAI VARIAN AKTIF) */}
                            {(() => {
                                const activeVariant = Array.isArray(msg.variants) && msg.activeVariantIndex !== undefined
                                    ? msg.variants[msg.activeVariantIndex]
                                    : null;
                                const displayTimestamp = activeVariant?.created_at || activeVariant?.timestamp || msg.created_at || msg.timestamp;
                                return (
                                    <MessageTimer
                                        timestamp={displayTimestamp}
                                        language={language}
                                        darkMode={darkMode}
                                        style={{ marginLeft: '4px' }}
                                    />
                                );
                            })()}
                        </div>
                    )}

                </div>
            </div>

            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
}, (prevProps, nextProps) => {
    // Jika bukan pesan terakhir dan objek msg sama persis serta bahasa sama, abaikan perubahan status streaming global
    if (!prevProps.isLastMessage && !nextProps.isLastMessage && prevProps.msg === nextProps.msg && prevProps.darkMode === nextProps.darkMode && prevProps.language === nextProps.language) {
        return true;
    }
    return (
        prevProps.msg.content === nextProps.msg.content &&
        prevProps.msg.thinking === nextProps.msg.thinking &&
        prevProps.msg.thought === nextProps.msg.thought &&
        prevProps.msg.statusMessage === nextProps.msg.statusMessage &&
        prevProps.msg.reasoning === nextProps.msg.reasoning &&
        prevProps.msg.role === nextProps.msg.role &&
        prevProps.msg.isStreaming === nextProps.msg.isStreaming &&
        prevProps.isThinking === nextProps.isThinking &&
        prevProps.isStreamingText === nextProps.isStreamingText &&
        prevProps.darkMode === nextProps.darkMode &&
        prevProps.language === nextProps.language &&
        prevProps.idx === nextProps.idx &&
        prevProps.searchQuery === nextProps.searchQuery &&
        prevProps.msg.totalMessages === nextProps.msg.totalMessages &&
        prevProps.msg.attachments === nextProps.msg.attachments &&
        prevProps.msg.fileGenerations === nextProps.msg.fileGenerations &&
        prevProps.msg.sources === nextProps.msg.sources &&
        prevProps.msg.citations === nextProps.msg.citations &&
        prevProps.msg.activeVariantIndex === nextProps.msg.activeVariantIndex &&
        prevProps.msg.variants === nextProps.msg.variants
    );
});

export default ChatBubble;