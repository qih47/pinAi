import React, { useState, useEffect, useRef, memo, useCallback } from 'react';
import CakraResponseRenderer from '../../chat/components/CakraResponseRenderer';
import SourceCitation from '../../chat/components/SourceCitation';
import RAGMetrics from '../../chat/components/RAGMetrics';
import FileGenerationCard from '../../chat/components/FileGenerationCard';
import FileProcessLog from '../../chat/components/FileProcessLog';
import cakraLogo from '../../../assets/cakra.png';
import { styles } from '../../chat/chatPage.styles';
import { translations, resolveStatusMessage } from '../../../utils/translations';
import { FileText } from 'lucide-react';

const formatTime = (isoString, language = 'id') => {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return '';
        if (language === 'en') {
            return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        }
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        return `${hours}.${minutes} WIB`;
    } catch (e) {
        return '';
    }
};

// 🧹 Pembersih otomatis untuk mendecode chunk JSON string jika ada sisa data mentah di database
const cleanCakraResponseText = (text) => {
    if (!text || typeof text !== 'string') return text || '';
    if (text.includes('{"chunk":') || text.includes('"event_type":')) {
        try {
            const matches = [];
            const regex = /\{"chunk":\s*"((?:\\.|[^"\\])*)"/g;
            let m;
            while ((m = regex.exec(text)) !== null) {
                try {
                    matches.push(JSON.parse(`"${m[1]}"`));
                } catch {
                    matches.push(m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"'));
                }
            }
            if (matches.length > 0) {
                return matches.join('');
            }
        } catch (err) {
            console.error('cleanCakraResponseText error:', err);
        }
    }
    return text;
};

const CollabChatBubble = memo(function CollabChatBubble({
    msg,
    idx,
    isStreaming = false,
    thinkingPhase = '',
    darkMode = true,
    theme = {},
    language = 'id',
    isLastMessage = false,
    onApplyToDocument,
    onFileClick,
    setPreviewImage,
    onOpenArtifact,
    handleDownloadArtifact,
    handleDownloadAllArtifacts
}) {
    const tGlobal = translations[language] || translations.id;
    const [isCopied, setIsCopied] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [feedbackState, setFeedbackState] = useState(null);
    const [isAvatarHovered, setIsAvatarHovered] = useState(false);

    // Ambil konten teks yang sudah dibersihkan secara aman
    const rawContent = cleanCakraResponseText(msg.content || msg.message_text || '');
    
    // Ambil metadata RAG (sources & metrics) jika ada
    const sources = msg.sources || msg.attachments?.sources || (Array.isArray(msg.attachments) ? msg.attachments.find(a => a?.sources)?.sources : null) || [];
    const metrics = msg.metrics || msg.attachments?.metrics || (Array.isArray(msg.attachments) ? msg.attachments.find(a => a?.metrics)?.metrics : null) || null;

    const isActive = isStreaming;
    const isProactive = msg.interjection_type === 'PROACTIVE_SUGGESTION';
    const isMention = msg.is_mention || msg.interjection_type === 'EXPLICIT_MENTION';
    const isWelcome = msg.interjection_type === 'WELCOME';

    const isMode = msg.interjection_type?.startsWith('MODE_');
    const modeLabel = isMode ? msg.interjection_type.replace('MODE_', '') : '';

    const executeTextCopy = (text) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    // Text to Speech
    const handleSpeak = () => {
        if (!('speechSynthesis' in window)) return;
        if (isSpeaking) {
            window.speechSynthesis.cancel();
            setIsSpeaking(false);
            return;
        }

        const cleanText = rawContent
            .replace(/```[\s\S]*?```/g, '')
            .replace(/[#*`_~]/g, '')
            .trim();

        if (!cleanText) return;

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = language === 'en' ? 'en-US' : 'id-ID';
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        setIsSpeaking(true);
        window.speechSynthesis.speak(utterance);
    };

    const timeFormatted = formatTime(msg.created_at, language);

    return (
        <div style={{ ...styles.assistantRow, animation: 'fadeInUp 0.15s ease-out forwards', marginBottom: '28px' }}>
            <div style={{ ...styles.assistantMessageWrapper, maxWidth: '100%' }}>
                {/* ── HEADER ASSISTANT (Identik dengan ChatBubble ChatPage Utama) ── */}
                <div style={{ ...styles.assistantHeader, display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
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
                            <span
                                style={{
                                    ...styles.statusDot,
                                    background: '#10b981',
                                    borderColor: theme.mainBg || (darkMode ? '#151517' : '#ffffff')
                                }}
                            />
                        )}
                    </div>

                    {isActive && (!rawContent || rawContent.length < 5) ? (
                        <span style={{ display: 'flex', alignItems: 'center', marginLeft: 10, flexShrink: 0 }}>
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
                                {thinkingPhase || "CAKRA sedang merumuskan jawaban..."}
                            </span>
                            <span style={{ display: 'inline-flex', gap: '2px', alignItems: 'center', height: '14px', lineHeight: 1 }}>
                                <span style={{ fontSize: 16, color: theme?.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 16, color: theme?.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out 0.15s', display: 'inline-block' }}>.</span>
                                <span style={{ fontSize: 16, color: theme?.secondaryText || '#94a3b8', animation: 'dotBounce 0.8s infinite ease-in-out 0.3s', display: 'inline-block' }}>.</span>
                            </span>
                        </span>
                    ) : (
                        <div style={{ marginLeft: 8, display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ ...styles.avatarLabel, color: theme.textColor || (darkMode ? '#ffffff' : '#1e293b') }}>
                                CAKRA
                            </span>

                            {isProactive && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                                    💡 Masukan Proaktif
                                </span>
                            )}

                            {isMention && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 font-medium">
                                    🎯 Respons @cakra
                                </span>
                            )}

                            {isWelcome && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                                    👋 Tim Kolaborasi
                                </span>
                            )}

                            {isMode && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                                    ⚡ Mode: {modeLabel}
                                </span>
                            )}
                        </div>
                    )}
                </div>

                {/* ── KONTEN JAWABAN (Identik dengan ChatBubble ChatPage Utama) ── */}
                <div style={styles.assistantContent} className="assistant-content-container">
                    <div style={{ ...styles.assistantText, color: theme.textColor, width: '100%', paddingLeft: '4px' }}>
                        <CakraResponseRenderer
                            rawContent={rawContent}
                            thinkingContent={msg.thinking || msg.thought || ''}
                            isStreaming={isActive}
                            darkMode={darkMode}
                            theme={theme}
                            language={language}
                            onFileClick={onFileClick}
                            setPreviewImage={setPreviewImage}
                            onOpenArtifact={onOpenArtifact}
                            handleDownloadArtifact={handleDownloadArtifact}
                        />

                        {/* File Generation Card jika ada berkas yang dihasilkan CAKRA */}
                        {!isActive && msg.fileGenerations && msg.fileGenerations.length > 0 && (
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
                            </div>
                        )}

                        {/* ── RAG METRICS & SOURCE CITATIONS (Sama persis seperti Screenshot) ── */}
                        {!isActive && (
                            <>
                                {metrics && (
                                    <RAGMetrics
                                        metrics={metrics}
                                        sources={sources}
                                        darkMode={darkMode}
                                        language={language}
                                        theme={theme}
                                    />
                                )}

                                {sources && sources.length > 0 && (
                                    <SourceCitation
                                        sources={sources}
                                        darkMode={darkMode}
                                        theme={theme}
                                        language={language}
                                        onPreview={(source) => {
                                            const fileUrl = source.url || source.file_path;
                                            if (fileUrl) window.open(fileUrl, '_blank');
                                        }}
                                    />
                                )}
                            </>
                        )}

                        {/* ── TOOLBAR AKSI (Thumb Up/Down, Copy, TTS, Timestamp) ── */}
                        {!isActive && rawContent && (
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                    marginTop: '8px',
                                    width: '100%',
                                    justifyContent: 'flex-start'
                                }}
                            >
                                {/* 👍 TOMBOL GOOD */}
                                <button
                                    type="button"
                                    onClick={() => setFeedbackState('good')}
                                    style={{
                                        background: feedbackState === 'good' ? 'rgba(16,185,129,0.15)' : 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '6px',
                                        borderRadius: '6px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        color: feedbackState === 'good' ? '#10b981' : (darkMode ? '#94a3b8' : '#64748b'),
                                        opacity: feedbackState === 'good' ? 1 : 0.6
                                    }}
                                    title="Tanggapan Membantu"
                                >
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill={feedbackState === 'good' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                                    </svg>
                                </button>

                                {/* 👎 TOMBOL BAD */}
                                <button
                                    type="button"
                                    onClick={() => setFeedbackState('bad')}
                                    style={{
                                        background: feedbackState === 'bad' ? 'rgba(239,68,68,0.15)' : 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '6px',
                                        borderRadius: '6px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        color: feedbackState === 'bad' ? '#ef4444' : (darkMode ? '#94a3b8' : '#64748b'),
                                        opacity: feedbackState === 'bad' ? 1 : 0.6
                                    }}
                                    title="Tanggapan Kurang Tepat"
                                >
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill={feedbackState === 'bad' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
                                    </svg>
                                </button>

                                {/* 📋 TOMBOL COPY */}
                                <button
                                    type="button"
                                    onClick={() => executeTextCopy(rawContent)}
                                    style={{
                                        background: isCopied ? 'rgba(16,185,129,0.15)' : 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '6px',
                                        borderRadius: '6px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        color: isCopied ? '#10b981' : (darkMode ? '#94a3b8' : '#64748b'),
                                        opacity: isCopied ? 1 : 0.6
                                    }}
                                    title="Salin Tanggapan"
                                >
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                    </svg>
                                </button>

                                {/* 🔊 TOMBOL SUARA (TTS) */}
                                <button
                                    type="button"
                                    onClick={handleSpeak}
                                    style={{
                                        background: isSpeaking ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '6px',
                                        borderRadius: '6px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        color: isSpeaking ? '#6366f1' : (darkMode ? '#94a3b8' : '#64748b'),
                                        opacity: isSpeaking ? 1 : 0.6
                                    }}
                                    title="Dengarkan Suara"
                                >
                                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
                                    </svg>
                                </button>

                                {/* 📝 TOMBOL SALIN KE CATATAN TIM (DOCUMENT PAD) */}
                                {onApplyToDocument && (
                                    <button
                                        type="button"
                                        onClick={() => onApplyToDocument(rawContent)}
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            cursor: 'pointer',
                                            padding: '5px 8px',
                                            borderRadius: '6px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            color: darkMode ? '#94a3b8' : '#64748b',
                                            opacity: 0.8,
                                            transition: 'all 0.2s ease',
                                            fontSize: '11px',
                                            fontWeight: 500
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.opacity = '1';
                                            e.currentTarget.style.color = '#14b8a6';
                                            e.currentTarget.style.background = darkMode ? 'rgba(20, 184, 166, 0.12)' : 'rgba(20, 184, 166, 0.08)';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.opacity = '0.8';
                                            e.currentTarget.style.color = darkMode ? '#94a3b8' : '#64748b';
                                            e.currentTarget.style.background = 'transparent';
                                        }}
                                        title="Salin dan terapkan respons ini ke Catatan Tim (Document Pad)"
                                    >
                                        <FileText size={13} className="text-teal-400" />
                                        <span className="hidden sm:inline">Ke Catatan</span>
                                    </button>
                                )}

                                {timeFormatted && (
                                    <span
                                        style={{
                                            fontSize: '11px',
                                            color: theme.secondaryText || (darkMode ? '#64748b' : '#94a3b8'),
                                            marginLeft: '6px'
                                        }}
                                    >
                                        {timeFormatted}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
});

export default CollabChatBubble;
