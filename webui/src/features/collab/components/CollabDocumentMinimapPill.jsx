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
import { useDocWriterStore } from '../../../stores/docWriterStore';
import { getUploadUrl } from '../../../services/endpoints';
import { translations } from '../../../utils/translations';

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
    const t = translations[language]?.collab || translations.id.collab;
    const [isOpen, setIsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const closeTimeoutRef = useRef(null);
    const containerRef = useRef(null);

    const isSplitScreen = useChatStore(state => state.isSplitScreen);
    const setSplitScreen = useChatStore(state => state.setSplitScreen);
    const isTemplateModalOpen = useDocWriterStore(state => state.isTemplateModalOpen);

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

    // Helper kategori & format badge dokumen
    const getDocBadge = (docOrTitle, fallbackDoc = null) => {
        const doc = (typeof docOrTitle === 'object' && docOrTitle !== null) 
            ? docOrTitle 
            : (fallbackDoc || {});
        const rawTitle = typeof docOrTitle === 'string' ? docOrTitle : (doc.title || doc.filename || doc.name || '');
        const lower = rawTitle.toLowerCase();
        const explicitJenis = doc.jenis || doc.category;

        // 1. Deteksi Format File Presentasi / Slide
        if (/\.(pptx?|ppsx?|key)$/i.test(lower) || lower.includes('slide') || lower.includes('presentasi')) {
            return { label: 'SLIDE', color: darkMode ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-800 border-amber-300' };
        }

        // 2. Deteksi Format Spreadsheet / Excel
        if (/\.(xlsx?|csv|ods)$/i.test(lower) || lower.includes('spreadsheet') || lower.includes('rekapitulasi')) {
            return { label: 'EXCEL', color: darkMode ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-emerald-50 text-emerald-800 border-emerald-300' };
        }

        // 3. Deteksi Format Word / Dokumen Teks
        if (/\.(docx?|rtf|odt|txt)$/i.test(lower)) {
            return { label: 'WORD', color: darkMode ? 'bg-blue-500/15 text-blue-300 border-blue-500/30' : 'bg-blue-50 text-blue-800 border-blue-300' };
        }

        // 4. Deteksi Gambar
        if (/\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(lower)) {
            return { label: 'GAMBAR', color: darkMode ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30' : 'bg-cyan-50 text-cyan-800 border-cyan-300' };
        }

        // 5. Jika memiliki jenis/kategori resmi dari database
        if (explicitJenis && explicitJenis !== 'Regulasi' && explicitJenis !== 'Dokumen') {
            return { label: explicitJenis, color: darkMode ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30' : 'bg-indigo-50 text-indigo-800 border-indigo-300' };
        }

        // 6. Deteksi Regulasi Resmi Pindad dengan Batas Kata (Word Boundary) yang Ketat
        if (/\bpkb\b/i.test(lower)) return { label: 'PKB', color: darkMode ? 'bg-teal-500/15 text-teal-300 border-teal-500/30' : 'bg-teal-50 text-teal-800 border-teal-300' };
        if (/\bsop\b|\bprosedur\b/i.test(lower)) return { label: 'SOP', color: darkMode ? 'bg-blue-500/15 text-blue-300 border-blue-500/30' : 'bg-blue-50 text-blue-800 border-blue-300' };
        if (/\b(sk|skep)\b|\bdireksi\b|\bkeputusan\b/i.test(lower)) return { label: 'SK Direksi', color: darkMode ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-800 border-amber-300' };
        if (/\bse\b|\bedaran\b/i.test(lower)) return { label: 'Surat Edaran', color: darkMode ? 'bg-purple-500/15 text-purple-300 border-purple-500/30' : 'bg-purple-50 text-purple-800 border-purple-300' };

        // 7. Format PDF standar
        if (lower.endsWith('.pdf')) {
            return { label: 'PDF', color: darkMode ? 'bg-rose-500/15 text-rose-300 border-rose-500/30' : 'bg-rose-50 text-rose-800 border-rose-300' };
        }

        return { label: 'REGULASI', color: darkMode ? 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30' : 'bg-slate-100 text-slate-700 border-slate-300' };
    };

    if (!sessionDocs || sessionDocs.length === 0 || isSplitScreen || isTemplateModalOpen) {
        return null;
    }

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
                zIndex: 30,
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
                            title={`${sessionDocs.length} ${t.docMinimapTitle || 'Dokumen Rujukan Tim'}`}
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
                        <div className={`flex items-center justify-between pb-2 mb-2 border-b ${darkMode ? 'border-zinc-700/40' : 'border-slate-200'}`}>
                            <div className="flex items-center gap-1.5">
                                <BookOpen size={14} className={darkMode ? "text-amber-400" : "text-amber-600"} />
                                <span className={`text-xs font-semibold ${darkMode ? 'text-zinc-100' : 'text-slate-800'}`}>
                                    {t.docMinimapTitle || 'Dokumen Rujukan Tim'}
                                </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full border ${darkMode ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-800 border-amber-300'}`}>
                                    {sessionDocs.length}
                                </span>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setIsOpen(false);
                                    }}
                                    className={`p-1 rounded-md transition-colors ${darkMode ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800' : 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'}`}
                                >
                                    <X size={13} />
                                </button>
                            </div>
                        </div>

                        {/* Search Input (jika dokumen >= 4) */}
                        {sessionDocs.length >= 4 && (
                            <div className="relative mb-2">
                                <Search size={13} className={`absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none ${darkMode ? 'text-zinc-400' : 'text-slate-400'}`} />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder={t.docMinimapSearch || 'Cari dokumen...'}
                                    className={`w-full text-[11px] pl-7 pr-3 py-1.5 rounded-lg border outline-none ${
                                        darkMode
                                            ? 'bg-zinc-900 border-zinc-700/70 text-zinc-200 placeholder-zinc-500 focus:border-amber-500'
                                            : 'bg-slate-50 border-slate-200 text-slate-800 placeholder-slate-400 focus:border-amber-500'
                                    }`}
                                />
                            </div>
                        )}

                        {/* List Dokumen */}
                        <div className="flex flex-col gap-1.5 max-h-[340px] overflow-y-auto custom-scrollbar pr-0.5">
                            {filteredDocs.map((doc, idx) => {
                                const badge = getDocBadge(doc);
                                return (
                                    <div
                                        key={doc.rawKey || idx}
                                        className={`p-2 rounded-xl border transition-all ${
                                            darkMode
                                                ? 'bg-zinc-900/60 hover:bg-zinc-800/80 border-zinc-800/80 hover:border-zinc-700'
                                                : 'bg-slate-50/90 hover:bg-slate-100/90 border-slate-200 shadow-sm'
                                        }`}
                                    >
                                        <div className="flex items-start gap-2 mb-1.5">
                                            <div className={`p-1 rounded-lg shrink-0 mt-0.5 border ${darkMode ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-amber-50 border-amber-200 text-amber-600'}`}>
                                                <FileText size={12} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-1.5 mb-0.5">
                                                    <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${badge.color}`}>
                                                        {badge.label}
                                                    </span>
                                                </div>
                                                <div className={`text-[11px] font-semibold line-clamp-2 leading-snug ${darkMode ? 'text-zinc-100' : 'text-slate-800'}`}>
                                                    {doc.title}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Action buttons */}
                                        <div className={`flex items-center justify-end gap-1.5 mt-1 pt-1.5 border-t ${darkMode ? 'border-white/5' : 'border-slate-200/80'}`}>
                                            {typeof doc.messageIndex === 'number' && (
                                                <button
                                                    type="button"
                                                    onClick={(e) => handleJumpToChat(e, doc)}
                                                    className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-colors ${darkMode ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60'}`}
                                                    title="Lihat pesan di ruang obrolan"
                                                >
                                                    <MessageSquare size={11} />
                                                    <span>{t.docMinimapInChat || 'Di Chat'}</span>
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                onClick={(e) => handleOpenInInterrogator(e, doc)}
                                                className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold transition-colors border ${darkMode ? 'text-amber-300 bg-amber-500/15 hover:bg-amber-500/25 border-amber-500/30' : 'text-amber-800 bg-amber-100/80 hover:bg-amber-200/80 border-amber-300'}`}
                                                title="Buka berkas di Document Interrogator"
                                            >
                                                <Eye size={11} />
                                                <span>{t.docMinimapInterrogator || 'Interrogator →'}</span>
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
