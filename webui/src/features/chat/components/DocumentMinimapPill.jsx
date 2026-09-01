import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { 
    FileText, 
    BookOpen, 
    Sparkles, 
    Search, 
    X, 
    Scale, 
    ShieldCheck, 
    Eye, 
    MessageSquare, 
    MoreVertical, 
    Check,
    Globe,
    ChevronDown,
    Loader2
} from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl, fetchAllDocuments } from '../../../services/endpoints';
import { translations } from '../../../utils/translations';

/**
 * 💊 DocumentMinimapPill
 * Indikator Kapsul Tunggal (Session Document Minimap Rail) yang melayang di sebelah KIRI chat area.
 * Desain ultra-compact dengan:
 * 1. Filter Pencarian Cepat di bagian atas popover (dokumen sesi).
 * 2. Tampilan list dokumen sesi yang ringkas & responsif.
 * 3. Menu Micro-Flyout 4 Mode via Portal (Anti-Clipping & Auto-Hide on Unfocus).
 * 4. 🌐 Collapsible Section: "Cari di Seluruh Database Regulasi Pindad" (di luar sesi ini).
 */
export default function DocumentMinimapPill({
    messages = [],
    darkMode = true,
    language = 'id',
    isMobile = false,
    sidebarOpen = false,
    hasSidebar = false,
    onNavigate,
    scrollContainerRef
}) {
    const t = translations[language]?.documentPill || translations.id.documentPill;
    const [isOpen, setIsOpen] = useState(false);
    const [hoveredDocIndex, setHoveredDocIndex] = useState(null);
    const [activeActionDoc, setActiveActionDoc] = useState(null);
    const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
    const [searchQuery, setSearchQuery] = useState('');
    
    // ── State untuk Expand/Collapse Pencarian Regulasi Global ──
    const [isGlobalExpanded, setIsGlobalExpanded] = useState(false);
    const [globalSearchQuery, setGlobalSearchQuery] = useState('');
    const [globalDocs, setGlobalDocs] = useState([]);
    const [isLoadingGlobal, setIsLoadingGlobal] = useState(false);

    const closeTimeoutRef = useRef(null);
    const actionMenuTimeoutRef = useRef(null);
    const globalSearchDebounceRef = useRef(null);
    const containerRef = useRef(null);
    const pillRef = useRef(null);

    const isSplitScreen = useChatStore(state => state.isSplitScreen);
    const setSplitScreen = useChatStore(state => state.setSplitScreen);
    const setContextIsolation = useChatStore(state => state.setContextIsolation);
    const activeIsolatedDocId = useChatStore(state => state.activeIsolatedDocId);
    const chatMode = useChatStore(state => state.chatMode || 'auto');

    // ── 1. Ekstrak Semua Dokumen Rujukan Unik dari Seluruh Sesi ──
    const sessionDocs = useMemo(() => {
        if (!Array.isArray(messages) || messages.length === 0) return [];
        const seen = new Set();
        const docs = [];

        messages.forEach((msg, msgIndex) => {
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
                            rawKey: key,
                            isSessionDoc: true
                        });
                    }
                });
            }
        });

        return docs;
    }, [messages]);

    // Set of session doc IDs/keys untuk menghindari duplikasi di list global
    const sessionDocKeys = useMemo(() => {
        const set = new Set();
        sessionDocs.forEach(d => {
            if (d.id) set.add(String(d.id));
            if (d.dokumen_id) set.add(String(d.dokumen_id));
            if (d.title) set.add(d.title.toLowerCase().trim());
            if (d.filename) set.add(d.filename.toLowerCase().trim());
        });
        return set;
    }, [sessionDocs]);

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

    // ── 3. Fetch Dokumen Global saat Section Dibuka atau Search Berubah ──
    const fetchGlobal = useCallback(async (query = '') => {
        setIsLoadingGlobal(true);
        try {
            const res = await fetchAllDocuments({ limit: 8, search: query.trim() });
            let items = [];
            if (res && Array.isArray(res.items)) {
                items = res.items;
            } else if (Array.isArray(res)) {
                items = res;
            }

            const formatted = items.map(item => ({
                ...item,
                title: item.title || item.filename || item.name || 'Regulasi PT Pindad',
                rawKey: `global_${item.id || item.dokumen_id || item.filename}`,
                isGlobalDoc: true
            }));

            setGlobalDocs(formatted);
        } catch (err) {
            console.error("Gagal memuat dokumen global:", err);
            setGlobalDocs([]);
        } finally {
            setIsLoadingGlobal(false);
        }
    }, []);

    // Fetch instan saat pertama kali dibuka jika belum ada data
    const handleToggleGlobal = () => {
        const nextState = !isGlobalExpanded;
        setIsGlobalExpanded(nextState);
        if (nextState && globalDocs.length === 0) {
            fetchGlobal(globalSearchQuery);
        }
    };

    // Debounce search hanya saat user mengetik query baru
    useEffect(() => {
        if (!isGlobalExpanded) return;

        if (globalSearchDebounceRef.current) {
            clearTimeout(globalSearchDebounceRef.current);
        }

        globalSearchDebounceRef.current = setTimeout(() => {
            fetchGlobal(globalSearchQuery);
        }, 300);

        return () => {
            if (globalSearchDebounceRef.current) {
                clearTimeout(globalSearchDebounceRef.current);
            }
        };
    }, [globalSearchQuery]);

    // ── Auto Close saat Scroll atau Click Outside ──
    useEffect(() => {
        if (!isOpen && !activeActionDoc) return;

        const handlePointerDown = (e) => {
            const portalEl = document.getElementById('cakra-document-mode-portal');
            if (portalEl && !portalEl.contains(e.target)) {
                setActiveActionDoc(null);
            }
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                if (!portalEl || !portalEl.contains(e.target)) {
                    setIsOpen(false);
                    setActiveActionDoc(null);
                    setIsGlobalExpanded(false);
                    setHoveredDocIndex(null);
                }
            }
        };

        const handleScroll = (e) => {
            if (containerRef.current && containerRef.current.contains(e.target)) {
                return;
            }
            setActiveActionDoc(null);
            if (isMobile) {
                setIsOpen(false);
            }
        };

        window.addEventListener('scroll', handleScroll, true);
        document.addEventListener('pointerdown', handlePointerDown);

        return () => {
            window.removeEventListener('scroll', handleScroll, true);
            document.removeEventListener('pointerdown', handlePointerDown);
        };
    }, [activeActionDoc, isOpen, isMobile]);

    // Jika tidak ada dokumen di sesi ini atau Document Interrogator sedang terbuka (isSplitScreen), jangan tampilkan minimap pill
    if (sessionDocs.length === 0 || isSplitScreen) return null;

    // ── 4. Handle Hover Main Container ──
    const handleMouseEnter = () => {
        if (isMobile) return; // Pada mobile, gunakan click/tap
        if (closeTimeoutRef.current) {
            clearTimeout(closeTimeoutRef.current);
            closeTimeoutRef.current = null;
        }
        setIsOpen(true);
    };

    const handleMouseLeave = () => {
        if (isMobile) return; // Pada mobile, jangan gunakan mouseleave
        if (closeTimeoutRef.current) {
            clearTimeout(closeTimeoutRef.current);
            closeTimeoutRef.current = null;
        }
        setIsOpen(false);
        setHoveredDocIndex(null);
        setActiveActionDoc(null);
        setIsGlobalExpanded(false);
        setGlobalSearchQuery('');
        setSearchQuery('');
    };

    // ── 5. Handle Action Menu Hover Debounce & Portal Positioning ──
    const handleActionMenuEnter = (e, doc) => {
        if (actionMenuTimeoutRef.current) {
            clearTimeout(actionMenuTimeoutRef.current);
            actionMenuTimeoutRef.current = null;
        }
        if (closeTimeoutRef.current) {
            clearTimeout(closeTimeoutRef.current);
            closeTimeoutRef.current = null;
        }

        const rect = e.currentTarget.getBoundingClientRect();
        const popupWidth = 180;
        const popupHeight = 160;

        let left = rect.right + 6;
        if (left + popupWidth > window.innerWidth) {
            left = Math.max(10, rect.left - popupWidth - 6);
        }

        let top = rect.top - 8;
        if (top + popupHeight > window.innerHeight) {
            top = Math.max(10, window.innerHeight - popupHeight - 10);
        }

        setMenuPosition({ top, left });
        setActiveActionDoc(doc);
    };

    const handleActionMenuLeave = () => {
        actionMenuTimeoutRef.current = setTimeout(() => {
            setActiveActionDoc(null);
        }, 180);
    };

    // ── 6. Handler Split-Screen PDF View ──
    const handlePdfClick = (e, doc) => {
        if (e) e.stopPropagation();
        setActiveActionDoc(null);
        setIsGlobalExpanded(false);

        // 1. Scroll chat jika merupakan dokumen sesi
        if (onNavigate && typeof doc.messageIndex === 'number') {
            onNavigate(doc.messageIndex);
        }

        // 2. Prioritaskan file_path lokal PDF untuk Split-Screen Interrogator
        const rawPath = doc.file_path || (doc.filename && doc.filename.endsWith('.pdf') ? doc.filename : null);
        const fileUrl = rawPath ? getUploadUrl(rawPath) : (doc.url && doc.url.endsWith('.pdf') ? doc.url : null);
        
        if (fileUrl) {
            setSplitScreen(true, fileUrl);
        } else {
            const docId = doc.id || doc.dokumen_id || doc.doc_id;
            if (docId) {
                window.open(`https://peraturan.pindad.com/content/detail/${docId}`, '_blank', 'noopener,noreferrer');
            }
        }
    };

    // ── 7. Handler 3 Mode Aksi (Fokus, Kepatuhan, Bedah) ──
    const handleModeClick = (e, doc, targetMode) => {
        if (e) e.stopPropagation();
        setActiveActionDoc(null);
        setIsGlobalExpanded(false);

        const docId = doc.id || doc.dokumen_id || doc.doc_id;
        const docTitle = doc.title || doc.filename || doc.name;

        const isCurrentlyActive = activeIsolatedDocId && (
            String(activeIsolatedDocId) === String(docId) ||
            String(activeIsolatedDocId) === String(doc.doc_id) ||
            activeIsolatedDocId === docTitle
        ) && (chatMode === targetMode || (targetMode === 'focus' && chatMode === 'auto'));

        if (isCurrentlyActive) {
            setContextIsolation(null, null, 'auto');
        } else {
            setContextIsolation(docId, docTitle, targetMode);
        }
    };

    // Helper kategori badge dokumen Pindad
    const getDocBadge = (title = '') => {
        const lower = title.toLowerCase();
        if (lower.includes('pkb')) return { label: 'PKB Pindad', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' };
        if (lower.includes('sop') || lower.includes('prosedur')) return { label: 'SOP', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30' };
        if (lower.includes('sk') || lower.includes('direksi') || lower.includes('keputusan')) return { label: 'SK Direksi', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' };
        if (lower.includes('se') || lower.includes('edaran')) return { label: 'Surat Edaran', color: 'bg-purple-500/15 text-purple-300 border-purple-500/30' };
        return { label: 'Regulasi', color: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30' };
    };

    // ── 8. Render Portal 4 Mode Action Popup Menu ──
    const renderActionPortal = () => {
        if (!activeActionDoc || typeof document === 'undefined') return null;

        const doc = activeActionDoc;
        const docId = doc.id || doc.dokumen_id || doc.doc_id;
        const docTitle = doc.title || doc.filename || doc.name;

        const isDocIsolated = activeIsolatedDocId && (
            String(activeIsolatedDocId) === String(docId) ||
            String(activeIsolatedDocId) === String(doc.doc_id) ||
            activeIsolatedDocId === docTitle
        );

        const isFocusActive = isDocIsolated && (chatMode === 'focus' || chatMode === 'auto');
        const isComplianceActive = isDocIsolated && chatMode === 'compliance';
        const isRedTeamActive = isDocIsolated && chatMode === 'redteam';

        return createPortal(
            <div
                id="cakra-document-mode-portal"
                style={{
                    position: 'fixed',
                    top: `${menuPosition.top}px`,
                    left: `${menuPosition.left}px`,
                    zIndex: 99999,
                    boxShadow: '0 16px 36px -4px rgba(0, 0, 0, 0.75), 0 0 1px 1px rgba(255, 255, 255, 0.12)'
                }}
                onMouseEnter={() => {
                    if (actionMenuTimeoutRef.current) {
                        clearTimeout(actionMenuTimeoutRef.current);
                        actionMenuTimeoutRef.current = null;
                    }
                    if (closeTimeoutRef.current) {
                        clearTimeout(closeTimeoutRef.current);
                        closeTimeoutRef.current = null;
                    }
                }}
                onMouseLeave={handleActionMenuLeave}
                className={`w-44 rounded-xl border backdrop-blur-2xl p-1.5 flex flex-col gap-0.5 animate-in fade-in zoom-in-95 ${
                    darkMode
                        ? 'bg-[#18181b]/98 border-zinc-700/90 text-zinc-200'
                        : 'bg-white/98 border-gray-200 text-gray-800'
                }`}
            >
                {/* 1. 👁️ Lihat PDF */}
                <button
                    type="button"
                    onClick={(e) => handlePdfClick(e, doc)}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-left ${
                        darkMode ? 'hover:bg-zinc-800 hover:text-white' : 'hover:bg-gray-100 hover:text-gray-900'
                    }`}
                >
                    <Eye className="w-3.5 h-3.5 text-zinc-400" />
                    <span>{t.openPdf || 'Lihat PDF'}</span>
                </button>

                {/* 2. 💬 Mode Fokus / Tanya */}
                <button
                    type="button"
                    onClick={(e) => handleModeClick(e, doc, 'focus')}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-left ${
                        isFocusActive
                            ? 'bg-indigo-600/25 text-indigo-300 font-semibold'
                            : darkMode ? 'hover:bg-indigo-600/15 hover:text-indigo-300' : 'hover:bg-indigo-50 hover:text-indigo-600'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                        <span>{t.modeFocus || 'Fokus / Tanya'}</span>
                    </div>
                    {isFocusActive && <Check className="w-3 h-3 text-indigo-400" />}
                </button>

                {/* 3. ⚖️ Mode Kepatuhan (Compliance) */}
                <button
                    type="button"
                    onClick={(e) => handleModeClick(e, doc, 'compliance')}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-left ${
                        isComplianceActive
                            ? 'bg-amber-600/25 text-amber-300 font-semibold'
                            : darkMode ? 'hover:bg-amber-600/15 hover:text-amber-300' : 'hover:bg-amber-50 hover:text-amber-600'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <Scale className="w-3.5 h-3.5 text-amber-400" />
                        <span>{t.modeCompliance || 'Kepatuhan'}</span>
                    </div>
                    {isComplianceActive && <Check className="w-3 h-3 text-amber-400" />}
                </button>

                {/* 4. 🛡️ Mode Bedah Dokumen (Red Team) */}
                <button
                    type="button"
                    onClick={(e) => handleModeClick(e, doc, 'redteam')}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-left ${
                        isRedTeamActive
                            ? 'bg-rose-600/25 text-rose-300 font-semibold'
                            : darkMode ? 'hover:bg-rose-600/15 hover:text-rose-300' : 'hover:bg-rose-50 hover:text-rose-600'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="w-3.5 h-3.5 text-rose-400" />
                        <span>{t.modeRedTeam || 'Bedah Dokumen'}</span>
                    </div>
                    {isRedTeamActive && <Check className="w-3 h-3 text-rose-400" />}
                </button>
            </div>,
            document.body
        );
    };

    const isShiftedMobile = Boolean(isMobile && hasSidebar && sidebarOpen);

    return (
        <>
            {/* ── 📱 Mobile Backdrop saat Popover Terbuka ── */}
            {isOpen && isMobile && (
                <div
                    onClick={(e) => {
                        e.stopPropagation();
                        setIsOpen(false);
                        setActiveActionDoc(null);
                        setIsGlobalExpanded(false);
                    }}
                    className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px] transition-opacity animate-in fade-in duration-200"
                />
            )}

            <div
                ref={containerRef}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                style={{
                    position: 'absolute',
                    left: isShiftedMobile ? 'calc(16rem + 16px)' : '16px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    zIndex: 100,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    padding: '10px 0',
                    userSelect: 'none',
                    transition: 'left 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
            >
                {/* ── 🗂️ SINGLE IN-PLACE EXPANDING CONTAINER ── */}
                <div
                    onClick={() => {
                        if (!isOpen) {
                            setIsOpen(true);
                        }
                    }}
                    className={`custom-scrollbar ${
                        isOpen
                            ? darkMode
                                ? 'bg-[#18181b]/95 border-zinc-800/90 text-zinc-100 p-2.5 backdrop-blur-xl'
                                : 'bg-white/95 border-gray-200 text-gray-900 p-2.5 backdrop-blur-xl'
                            : darkMode
                                ? 'bg-zinc-900/90 border-zinc-700/90 px-1 py-2 hover:border-zinc-500'
                                : 'bg-white/90 border-gray-300 px-1 py-2 hover:border-gray-400'
                    }`}
                    style={{
                        width: isOpen ? (isMobile ? 'min(340px, calc(100vw - 32px))' : '340px') : '20px',
                        borderRadius: isOpen ? '16px' : '99px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: isOpen ? 'stretch' : 'center',
                        justifyContent: 'flex-start',
                        gap: isOpen ? '0px' : '6px',
                        cursor: isOpen ? 'default' : 'pointer',
                        maxHeight: 'min(86vh, calc(100vh - 40px))',
                        boxShadow: isOpen
                            ? darkMode
                                ? '0 20px 35px -5px rgba(0, 0, 0, 0.7), 0 0 1px 1px rgba(255, 255, 255, 0.08)'
                                : '0 20px 35px -5px rgba(0, 0, 0, 0.15), 0 0 1px 1px rgba(0, 0, 0, 0.05)'
                            : darkMode
                                ? '0 4px 12px rgba(0,0,0,0.4)'
                                : '0 4px 12px rgba(0,0,0,0.1)',
                        border: `1px solid ${
                            isOpen
                                ? darkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.1)'
                                : darkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)'
                        }`,
                        transition: 'width 0.2s cubic-bezier(0.16, 1, 0.3, 1), background 0.15s ease',
                        overflowY: isOpen ? 'auto' : 'hidden',
                        overflowX: 'hidden',
                    }}
                >
                    {!isOpen ? (
                        // ── 💊 STRIP KAPSUL MINIMAP (SAAT TIDAK DI-HOVER) ──
                        sessionDocs.map((doc, idx) => (
                            <div
                                key={idx}
                                style={{
                                    width: '10px',
                                    height: '2px',
                                    borderRadius: '99px',
                                    background: darkMode ? '#71717a' : '#9ca3af',
                                    transition: 'all 0.15s ease',
                                    flexShrink: 0,
                                }}
                            />
                        ))
                    ) : (
                        // ── 🗂️ KONTEN LENGKAP POPOVER (SAAT DI-HOVER) ──
                        <div className="flex flex-col w-full">
                            {/* Header Popover */}
                            <div className="flex items-center justify-between px-2 py-1.5 mb-1.5 border-b border-zinc-700/40">
                                <div className="flex items-center gap-1.5 min-w-0 pr-2">
                                    <BookOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                                    <span className="text-[12px] font-semibold tracking-tight truncate">
                                        {t.title || 'Dokumen Rujukan PT Pindad'}
                                    </span>
                                </div>
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                                        {sessionDocs.length}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setIsOpen(false);
                                            setActiveActionDoc(null);
                                            setIsGlobalExpanded(false);
                                        }}
                                        className="p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors"
                                        title="Tutup"
                                    >
                                        <X className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>

                        {/* 🔍 Search Input Box Dokumen Sesi (Muncul jika dokumen >= 20) */}
                        {sessionDocs.length >= 20 && (
                            <div className="relative mb-2 px-0.5">
                                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder={t.searchPlaceholder || "Cari dokumen rujukan..."}
                                    className={`w-full text-[11px] pl-7 pr-6 py-1.5 rounded-lg border outline-none transition-all ${
                                        darkMode 
                                            ? 'bg-zinc-900/90 border-zinc-700/70 text-zinc-200 placeholder-zinc-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40' 
                                            : 'bg-gray-50 border-gray-200 text-gray-800 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30'
                                    }`}
                                />
                                {searchQuery && (
                                    <button
                                        type="button"
                                        onClick={() => setSearchQuery('')}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-zinc-400 hover:text-zinc-200 transition-colors"
                                    >
                                        <X className="w-3 h-3" />
                                    </button>
                                )}
                            </div>
                        )}

                        {/* ── 📚 Document Items List (Dokumen Sesi) — Memanjang penuh tanpa dipotong ── */}
                        <div className="flex flex-col gap-1 pr-0.5">
                            {filteredDocs.length === 0 ? (
                                <div className="py-5 text-center text-[11px] text-zinc-400">
                                    {t.noResults || 'Dokumen tidak ditemukan'}
                                </div>
                            ) : (
                                filteredDocs.map((doc, idx) => {
                                    const isHovered = hoveredDocIndex === idx;
                                    const docId = doc.id || doc.dokumen_id || doc.doc_id;
                                    const docTitle = doc.title || doc.filename || doc.name;

                                    const isDocIsolated = activeIsolatedDocId && (
                                        String(activeIsolatedDocId) === String(docId) ||
                                        String(activeIsolatedDocId) === String(doc.doc_id) ||
                                        activeIsolatedDocId === docTitle
                                    );

                                    const isFocusActive = isDocIsolated && (chatMode === 'focus' || chatMode === 'auto');
                                    const isComplianceActive = isDocIsolated && chatMode === 'compliance';
                                    const isRedTeamActive = isDocIsolated && chatMode === 'redteam';

                                    const badge = getDocBadge(doc.title);
                                    const isActionActive = activeActionDoc?.rawKey === doc.rawKey;

                                    return (
                                        <div
                                            key={idx}
                                            onMouseEnter={() => {
                                                setHoveredDocIndex(idx);
                                                if (activeActionDoc && activeActionDoc.rawKey !== doc.rawKey) {
                                                    setActiveActionDoc(null);
                                                }
                                            }}
                                            onMouseLeave={() => setHoveredDocIndex(null)}
                                            className={`group relative flex items-center justify-between p-2 rounded-xl transition-all duration-150 border ${
                                                isDocIsolated
                                                    ? 'border-indigo-500/80 bg-indigo-500/10 shadow-sm'
                                                    : isHovered
                                                    ? darkMode
                                                        ? 'border-zinc-700 bg-zinc-800/80'
                                                        : 'border-gray-300 bg-gray-100'
                                                    : 'border-transparent hover:border-zinc-800/60'
                                            }`}
                                        >
                                            {/* Bagian Kiri: Icon + Judul + Kategori (Klik untuk Buka PDF) */}
                                            <div 
                                                onClick={(e) => handlePdfClick(e, doc)}
                                                className="flex items-start gap-2 min-w-0 flex-1 pr-1.5 cursor-pointer"
                                                title="Klik untuk membuka dokumen PDF"
                                            >
                                                <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500 group-hover:text-white transition-colors">
                                                    <FileText className="w-3.5 h-3.5" />
                                                </div>

                                                <div className="flex flex-col min-w-0">
                                                    <p className="text-[12px] font-medium leading-tight truncate group-hover:text-indigo-400 transition-colors" title={doc.title}>
                                                        {doc.title}
                                                    </p>
                                                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                                        <span className={`text-[9px] font-semibold px-1.5 py-0.2 rounded border ${badge.color}`}>
                                                            {badge.label}
                                                        </span>
                                                        {doc.halaman && (
                                                            <span className="text-[10px] text-zinc-400">
                                                                Hal. {doc.halaman}
                                                            </span>
                                                        )}
                                                        {isDocIsolated && (
                                                            <span className={`text-[9px] font-bold px-1 rounded flex items-center gap-0.5 ${
                                                                isComplianceActive ? 'bg-amber-500/20 text-amber-300' :
                                                                isRedTeamActive ? 'bg-rose-500/20 text-rose-300' :
                                                                'bg-indigo-500/20 text-indigo-300'
                                                            }`}>
                                                                <Check className="w-2.5 h-2.5" />
                                                                {isComplianceActive ? 'Kepatuhan' : isRedTeamActive ? 'Bedah' : 'Fokus'}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* ── 🔘 Bagian Kanan: Trigger Popover 4 Mode (Hover/Klik Titik 3) ── */}
                                            <div className="relative flex items-center flex-shrink-0">
                                                <button
                                                    type="button"
                                                    onMouseEnter={(e) => handleActionMenuEnter(e, doc)}
                                                    onMouseLeave={handleActionMenuLeave}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        if (activeActionDoc?.rawKey === doc.rawKey) {
                                                            setActiveActionDoc(null);
                                                        } else {
                                                            handleActionMenuEnter(e, doc);
                                                        }
                                                    }}
                                                    className={`p-1 rounded-lg transition-all ${
                                                        isActionActive || isHovered
                                                            ? darkMode ? 'bg-zinc-700/80 text-white' : 'bg-gray-200 text-gray-900'
                                                            : 'text-zinc-500 hover:text-zinc-200'
                                                    }`}
                                                    title="Opsi Mode Analisis & Pratinjau Dokumen"
                                                >
                                                    <MoreVertical className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>

                        {/* ── 📊 Footer Info Dokumen Sesi ── */}
                        <div className="mt-2 pt-2 border-t border-zinc-800/60 flex items-center justify-between px-1 text-[10px] text-zinc-400">
                            <span className="flex items-center gap-1">
                                <Sparkles className="w-2.5 h-2.5 text-indigo-400" />
                                <span>{t.sessionDocs || 'Dokumen di Sesi Ini'}</span>
                            </span>
                            <span className="text-zinc-500 text-[9.5px]">
                                {filteredDocs.length} / {sessionDocs.length}
                            </span>
                        </div>

                        {/* ── 🌐 COLLAPSIBLE SECTION: PENCARIAN DATABASE REGULASI GLOBAL ── */}
                        <div className="mt-2 pt-2 border-t border-zinc-800/60 flex flex-col gap-1.5">
                            <button
                                type="button"
                                onClick={handleToggleGlobal}
                                className={`w-full flex items-center justify-between px-2 py-1.5 rounded-xl border text-[11px] font-medium transition-colors duration-150 ${
                                    isGlobalExpanded
                                        ? 'bg-indigo-600/15 border-indigo-500/40 text-indigo-300'
                                        : darkMode
                                        ? 'bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/60 text-zinc-300'
                                        : 'bg-gray-50 border-gray-200 hover:bg-gray-100 text-gray-700'
                                }`}
                            >
                                <div className="flex items-center gap-1.5 truncate">
                                    <Globe className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                                    <span className="truncate">{t.exploreGlobal || 'Cari di Seluruh Regulasi Pindad'}</span>
                                </div>
                                <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 transition-transform duration-200 ${isGlobalExpanded ? 'rotate-180 text-indigo-400' : 'text-zinc-400'}`} />
                            </button>

                            {isGlobalExpanded && (
                                <div className="flex flex-col gap-1.5 p-1.5 rounded-xl bg-zinc-950/40 border border-zinc-800/50 transition-all duration-150">
                                    {/* Search Box Global Regulations */}
                                    <div className="relative">
                                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
                                        <input
                                            type="text"
                                            value={globalSearchQuery}
                                            onChange={(e) => setGlobalSearchQuery(e.target.value)}
                                            placeholder={t.searchGlobalPlaceholder || "Ketik judul/nomor (misal: PKB, Cuti, SOP)..."}
                                            className={`w-full text-[11px] pl-7 pr-6 py-1.5 rounded-lg border outline-none transition-all ${
                                                darkMode 
                                                    ? 'bg-zinc-900/90 border-zinc-700/70 text-zinc-200 placeholder-zinc-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40' 
                                                    : 'bg-white border-gray-300 text-gray-800 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30'
                                            }`}
                                        />
                                        {isLoadingGlobal ? (
                                            <Loader2 className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-indigo-400 animate-spin" />
                                        ) : globalSearchQuery ? (
                                            <button
                                                type="button"
                                                onClick={() => setGlobalSearchQuery('')}
                                                className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-zinc-400 hover:text-zinc-200 transition-colors"
                                            >
                                                <X className="w-3 h-3" />
                                            </button>
                                        ) : null}
                                    </div>

                                    {/* List Hasil Dokumen Global */}
                                    <div className="flex flex-col gap-1 pr-0.5">
                                        {isLoadingGlobal ? (
                                            <div className="py-4 flex items-center justify-center gap-1.5 text-[11px] text-zinc-400">
                                                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                                                <span>{t.loadingGlobal || 'Mencari regulasi di database...'}</span>
                                            </div>
                                        ) : globalDocs.length === 0 ? (
                                            <div className="py-4 text-center text-[10.5px] text-zinc-400">
                                                {t.emptyGlobal || 'Tidak ada regulasi yang cocok'}
                                            </div>
                                        ) : (
                                            globalDocs.map((gDoc, gIdx) => {
                                                const docId = gDoc.id || gDoc.dokumen_id || gDoc.doc_id;
                                                const docTitle = gDoc.title || gDoc.filename || gDoc.name;
                                                const badge = getDocBadge(gDoc.title);
                                                const isActionActive = activeActionDoc?.rawKey === gDoc.rawKey;

                                                const isDocIsolated = activeIsolatedDocId && (
                                                    String(activeIsolatedDocId) === String(docId) ||
                                                    String(activeIsolatedDocId) === String(gDoc.doc_id) ||
                                                    activeIsolatedDocId === docTitle
                                                );

                                                return (
                                                    <div
                                                        key={gIdx}
                                                        onMouseEnter={() => {
                                                            if (activeActionDoc && activeActionDoc.rawKey !== gDoc.rawKey) {
                                                                setActiveActionDoc(null);
                                                            }
                                                        }}
                                                        className={`group relative flex items-center justify-between p-1.5 rounded-lg transition-all duration-150 border ${
                                                            isDocIsolated
                                                                ? 'border-indigo-500/80 bg-indigo-500/10'
                                                                : darkMode
                                                                ? 'border-zinc-800/70 hover:border-zinc-700 bg-zinc-900/50 hover:bg-zinc-850'
                                                                : 'border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50'
                                                        }`}
                                                    >
                                                        {/* Bagian Kiri: Title & Badge (Klik untuk Buka PDF) */}
                                                        <div
                                                            onClick={(e) => handlePdfClick(e, gDoc)}
                                                            className="flex items-start gap-1.5 min-w-0 flex-1 pr-1 cursor-pointer"
                                                            title="Klik untuk membuka dokumen PDF"
                                                        >
                                                            <div className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5 bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500 group-hover:text-white transition-colors">
                                                                <FileText className="w-3 h-3" />
                                                            </div>

                                                            <div className="flex flex-col min-w-0">
                                                                <p className="text-[11px] font-medium leading-tight truncate group-hover:text-indigo-400 transition-colors" title={gDoc.title}>
                                                                    {gDoc.title}
                                                                </p>
                                                                <div className="flex items-center gap-1 mt-0.5">
                                                                    <span className={`text-[8.5px] font-semibold px-1 py-0.1 rounded border ${badge.color}`}>
                                                                        {badge.label}
                                                                    </span>
                                                                    {gDoc.nomor && (
                                                                        <span className="text-[9px] text-zinc-400 truncate">
                                                                            {gDoc.nomor}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* Bagian Kanan: Trigger 4 Mode Popover */}
                                                        <div className="relative flex items-center flex-shrink-0">
                                                            <button
                                                                type="button"
                                                                onMouseEnter={(e) => handleActionMenuEnter(e, gDoc)}
                                                                onMouseLeave={handleActionMenuLeave}
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    if (activeActionDoc?.rawKey === gDoc.rawKey) {
                                                                        setActiveActionDoc(null);
                                                                    } else {
                                                                        handleActionMenuEnter(e, gDoc);
                                                                    }
                                                                }}
                                                                className={`p-1 rounded transition-all ${
                                                                    isActionActive
                                                                        ? darkMode ? 'bg-zinc-700/80 text-white' : 'bg-gray-200 text-gray-900'
                                                                        : 'text-zinc-500 hover:text-zinc-200'
                                                                }`}
                                                                title="Opsi Mode Analisis & Pratinjau Dokumen"
                                                            >
                                                                <MoreVertical className="w-3 h-3" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                );
                                            })
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* ── 🚀 RENDER POPUP 4 MODE DI ATAS SEMUA ELEMEN (PORTAL document.body) ── */}
            {renderActionPortal()}
        </div>
        </>
    );
}
