import React, { useState, useRef, useMemo, useEffect } from 'react';
import { 
    BookOpen, 
    FileText, 
    Search, 
    X, 
    Eye, 
    MessageSquare,
    ChevronRight
} from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl } from '../../../services/endpoints';

/**
 * 💊 CollabDocumentMinimapPill
 * Indikator Kapsul Tunggal (Document Minimap Rail) yang melayang di sebelah KIRI chat area Collab Space.
 * Mengumpulkan semua dokumen aktif dan rujukan yang dibahas di dalam ruangan obrolan.
 */
export default function CollabDocumentMinimapPill({
    messages = [],
    darkMode = true,
    language = 'id',
    isMobile = false,
    onNavigate,
    scrollContainerRef
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const closeTimeoutRef = useRef(null);
    const containerRef = useRef(null);

    const isSplitScreen = useChatStore(state => state.isSplitScreen);
    const setSplitScreen = useChatStore(state => state.setSplitScreen);

    // ── 1. Ekstrak Semua Dokumen Rujukan Unik dari Obrolan Collab ──
    const sessionDocs = useMemo(() => {
        if (!Array.isArray(messages) || messages.length === 0) return [];
        const seen = new Set();
        const docs = [];

        messages.forEach((msg, msgIndex) => {
            // A. Dari attachments (context_doc / PDF)
            if (Array.isArray(msg.attachments)) {
                msg.attachments.forEach(att => {
                    const isDoc = att.type === 'context_doc' || att.is_context || (att.name && att.name.toLowerCase().endsWith('.pdf'));
                    if (isDoc) {
                        const key = att.doc_id || att.id || att.filename || att.title || att.name;
                        if (key && !seen.has(String(key))) {
                            seen.add(String(key));
                            docs.push({
                                ...att,
                                messageIndex: msgIndex,
                                title: att.title || att.name || att.filename || 'Dokumen Rujukan Tim',
                                rawKey: key
                            });
                        }
                    }
                });
            }

            // B. Dari AI citations / sources
            const rawSources = msg.sources || msg.citations || [];
            if (Array.isArray(rawSources)) {
                rawSources.forEach(s => {
                    const key = s.id || s.dokumen_id || s.title || s.filename || s.name;
                    if (key && !seen.has(String(key))) {
                        seen.add(String(key));
                        docs.push({
                            ...s,
                            messageIndex: msgIndex,
                            title: s.title || s.filename || s.name || 'Dokumen Rujukan Pindad',
                            rawKey: key
                        });
                    }
                });
            }
        });

        return docs;
    }, [messages]);

    // ── 2. Filter Pencarian Dokumen Sesi ──
    const filteredDocs = useMemo(() => {
        if (!searchQuery.trim()) return sessionDocs;
        const q = searchQuery.toLowerCase().trim();
        return sessionDocs.filter(doc => {
            const titleMatch = (doc.title || '').toLowerCase().includes(q);
            const nomorMatch = (doc.nomor || '').toLowerCase().includes(q);
            const filenameMatch = (doc.filename || '').toLowerCase().includes(q);
            return titleMatch || nomorMatch || filenameMatch;
        });
    }, [sessionDocs, searchQuery]);

    // Tutup jika klik di luar
    useEffect(() => {
        const handlePointerDown = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('pointerdown', handlePointerDown);
        return () => document.removeEventListener('pointerdown', handlePointerDown);
    }, []);

    // Jangan tampilkan jika tidak ada dokumen atau Document Interrogator sedang terbuka
    if (sessionDocs.length === 0 || isSplitScreen) return null;

    const handleMouseEnter = () => {
        if (isMobile) return;
        if (closeTimeoutRef.current) {
            clearTimeout(closeTimeoutRef.current);
            closeTimeoutRef.current = null;
        }
        setIsOpen(true);
    };

    const handleMouseLeave = () => {
        if (isMobile) return;
        if (closeTimeoutRef.current) {
            clearTimeout(closeTimeoutRef.current);
            closeTimeoutRef.current = null;
        }
        setIsOpen(false);
        setSearchQuery('');
    };

    // Helper preview file URL
    const getDocFileUrl = (doc) => {
        if (doc.file_url) return doc.file_url;
        if (doc.url) return doc.url;
        if (doc.file_path) {
            const cleanPath = doc.file_path.replace(/\\/g, '/');
            return getUploadUrl(cleanPath);
        }
        if (doc.filename) {
            return getUploadUrl(`file_peraturan/${doc.filename}`);
        }
        return null;
    };

    // Buka di Document Interrogator
    const handleOpenInInterrogator = (e, doc) => {
        e.stopPropagation();
        setIsOpen(false);
        const fileUrl = getDocFileUrl(doc);
        if (fileUrl) {
            setSplitScreen(true, fileUrl);
        } else {
            const docId = doc.id || doc.dokumen_id || doc.doc_id;
            if (docId) {
                window.open(`https://peraturan.pindad.com/content/detail/${docId}`, '_blank', 'noopener,noreferrer');
            }
        }
    };

    // Lompat ke chat yang menautkan dokumen ini
    const handleJumpToChat = (e, doc) => {
        e.stopPropagation();
        setIsOpen(false);
        if (typeof onNavigate === 'function' && typeof doc.messageIndex === 'number') {
            onNavigate(doc.messageIndex);
        }
    };

    // Kategori badge
    const getDocBadge = (title = '') => {
        const lower = title.toLowerCase();
        if (lower.includes('pkb')) return { label: 'PKB', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' };
        if (lower.includes('sop') || lower.includes('prosedur')) return { label: 'SOP', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30' };
        if (lower.includes('sk') || lower.includes('direksi') || lower.includes('keputusan')) return { label: 'SK Direksi', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' };
        if (lower.includes('se') || lower.includes('edaran')) return { label: 'Surat Edaran', color: 'bg-purple-500/15 text-purple-300 border-purple-500/30' };
        return { label: 'Regulasi', color: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30' };
    };

    return (
        <div
            ref={containerRef}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            style={{
                position: 'absolute',
                left: '16px',
                top: '50%',
                transform: 'translateY(-50%)',
                zIndex: 40,
                display: 'flex',
                alignItems: 'center',
            }}
        >
            <div
                onClick={() => isMobile && setIsOpen(!isOpen)}
                style={{
                    background: darkMode ? 'rgba(24, 24, 27, 0.88)' : 'rgba(255, 255, 255, 0.95)',
                    backdropFilter: 'blur(16px)',
                    border: `1px solid ${darkMode ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.8)'}`,
                    boxShadow: darkMode 
                        ? '0 12px 32px -4px rgba(0, 0, 0, 0.45), 0 4px 12px rgba(0, 0, 0, 0.25)' 
                        : '0 12px 32px -4px rgba(0, 0, 0, 0.1), 0 4px 12px rgba(0, 0, 0, 0.05)',
                    borderRadius: isOpen ? '16px' : '999px',
                    padding: isOpen ? '12px' : '10px 8px',
                    width: isOpen ? (isMobile ? 'calc(100vw - 32px)' : '320px') : 'auto',
                    maxWidth: isOpen ? '360px' : 'auto',
                    minWidth: isOpen ? '280px' : '36px',
                    maxHeight: isOpen ? '460px' : 'auto',
                    cursor: isOpen ? 'default' : 'pointer',
                    transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isOpen ? 'stretch' : 'center',
                    gap: isOpen ? '8px' : '6px',
                    overflow: 'hidden'
                }}
            >
                {!isOpen ? (
                    // ── 💊 TAMPILAN PILL RAMPING (DEFAULT) ──
                    <div className="flex flex-col items-center gap-2 select-none">
                        <div 
                            className="w-7 h-7 rounded-full flex items-center justify-center bg-amber-500/15 border border-amber-500/30 text-amber-400"
                            title={`${sessionDocs.length} Dokumen Rujukan Tim`}
                        >
                            <BookOpen size={14} />
                        </div>
                        <span className="text-[10px] font-extrabold text-amber-400">
                            {sessionDocs.length}
                        </span>
                        {/* Dot indicators */}
                        <div className="flex flex-col gap-1 items-center">
                            {sessionDocs.slice(0, 4).map((_, i) => (
                                <span
                                    key={i}
                                    className="w-1.5 h-1.5 rounded-full bg-zinc-500/60"
                                />
                            ))}
                        </div>
                    </div>
                ) : (
                    // ── 🗂️ TAMPILAN EXPANDED POPOVER ──
                    <div className="flex flex-col w-full">
                        {/* Header */}
                        <div className="flex items-center justify-between pb-2 border-b border-zinc-700/40 mb-2">
                            <div className="flex items-center gap-1.5">
                                <BookOpen size={14} className="text-amber-400" />
                                <span className="text-xs font-semibold text-zinc-100">
                                    Dokumen Rujukan Tim
                                </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                    {sessionDocs.length}
                                </span>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setIsOpen(false);
                                    }}
                                    className="p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                                >
                                    <X size={13} />
                                </button>
                            </div>
                        </div>

                        {/* Search Input (jika dokumen >= 4) */}
                        {sessionDocs.length >= 4 && (
                            <div className="relative mb-2">
                                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Cari dokumen..."
                                    className={`w-full text-[11px] pl-7 pr-3 py-1.5 rounded-lg border outline-none ${
                                        darkMode
                                            ? 'bg-zinc-900 border-zinc-700/70 text-zinc-200 placeholder-zinc-500 focus:border-amber-500'
                                            : 'bg-zinc-50 border-zinc-200 text-zinc-800 placeholder-zinc-400 focus:border-amber-500'
                                    }`}
                                />
                            </div>
                        )}

                        {/* List Dokumen */}
                        <div className="flex flex-col gap-1.5 max-h-[340px] overflow-y-auto custom-scrollbar pr-0.5">
                            {filteredDocs.map((doc, idx) => {
                                const badge = getDocBadge(doc.title);
                                return (
                                    <div
                                        key={doc.rawKey || idx}
                                        className={`p-2 rounded-xl border transition-all ${
                                            darkMode
                                                ? 'bg-zinc-900/60 hover:bg-zinc-800/80 border-zinc-800/80 hover:border-zinc-700'
                                                : 'bg-zinc-50 hover:bg-zinc-100/90 border-zinc-200'
                                        }`}
                                    >
                                        <div className="flex items-start gap-2 mb-1.5">
                                            <div className="p-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0 mt-0.5">
                                                <FileText size={12} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-1.5 mb-0.5">
                                                    <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${badge.color}`}>
                                                        {badge.label}
                                                    </span>
                                                </div>
                                                <div className="text-[11px] font-semibold line-clamp-2 text-zinc-100 leading-snug">
                                                    {doc.title}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Action buttons */}
                                        <div className="flex items-center justify-end gap-1.5 mt-1 pt-1.5 border-t border-white/5">
                                            {typeof doc.messageIndex === 'number' && (
                                                <button
                                                    type="button"
                                                    onClick={(e) => handleJumpToChat(e, doc)}
                                                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                                                    title="Lihat pesan di ruang obrolan"
                                                >
                                                    <MessageSquare size={11} />
                                                    <span>Di Chat</span>
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                onClick={(e) => handleOpenInInterrogator(e, doc)}
                                                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold text-amber-300 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 transition-colors"
                                                title="Buka berkas di Document Interrogator"
                                            >
                                                <Eye size={11} />
                                                <span>Interrogator →</span>
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
