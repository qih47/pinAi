import React, { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { isToday, isYesterday, isThisWeek, isThisMonth } from "date-fns";
import { translations } from "../../../../utils/translations";
import { useSessionTitle } from "../../../../hooks/useSessionTitle";
import { useChatStore } from "../../../../stores/chatStore";

const TypewriterTitle = ({ text, onDone }) => {
  const [displayedText, setDisplayedText] = React.useState("");
  const [isTyping, setIsTyping] = React.useState(true);

  React.useEffect(() => {
    let i = 0;
    setDisplayedText("");
    setIsTyping(true);
    const timer = setInterval(() => {
      setDisplayedText(text.substring(0, i + 1));
      i++;
      if (i >= text.length) {
        clearInterval(timer);
        // Hilangkan kursor berkedip setelah 1.5 detik agar terlihat rapi
        setTimeout(() => {
          setIsTyping(false);
          if (onDone) onDone(); // beritahu parent animasi selesai
        }, 1500);
      }
    }, 50);
    return () => clearInterval(timer);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      <span>{displayedText}</span>
      {isTyping && (
        <span style={{
          display: 'inline-block',
          width: '6px',
          height: '1.1em',
          background: '#10b981',
          marginLeft: '2px',
          verticalAlign: 'text-bottom',
          animation: 'cakraCursorBlink 1s step-end infinite',
        }} />
      )}
    </span>
  );
};

export default function SessionList({
  isOpen,
  chatHistory,
  setChatHistory,
  currentSessionId,
  loadChatSession,
  theme,
  darkMode,
  pinChat,
  renameChat,
  deleteChat,
  menuRef,
  activeMenuId,
  setActiveMenuId,
  sessionSearchQuery,
  setSessionSearchQuery,
  sidebarSearchInputRef,
  confirmDelete,
  isDeletingId,
  language,
  showDocumentList,
  setShowDocumentList,
  userData,
  navigate
}) {
  const location = useLocation();
  const t = translations[language]?.sidebar || translations.id.sidebar;
  const [hoveredChatId, setHoveredChatId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [tempTitle, setTempTitle] = useState("");

  // Track session yang sudah pernah dianimasikan — jangan animasi ulang
  const animatedTitles = React.useRef(new Set());

  const activeStreams = useChatStore((state) => state.activeStreams || {});
  const { isTitleGenerating } = useSessionTitle(
    chatHistory,
    setChatHistory,
    currentSessionId,
    true
  );

  const togglePinChat = async (e, sessionUuid) => {
    e.stopPropagation();
    try {
      const currentChat = chatHistory.find(
        (c) => c.session_uuid === sessionUuid,
      );
      const isPinnedCurrentValue = currentChat ? currentChat.is_pinned : false;

      const result = await pinChat(sessionUuid, isPinnedCurrentValue);

      if (result.status === "success") {
        setChatHistory((prev) => {
          const newHistory = prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, is_pinned: !chat.is_pinned }
              : chat,
          );
          return [...newHistory].sort(
            (a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0),
          );
        });
        setActiveMenuId(null);
      }
    } catch (err) {
      console.error("Gagal menyematkan chat:", err);
    }
  };

  const handleRename = async (sessionUuid) => {
    if (!tempTitle.trim()) return;
    try {
      const result = await renameChat(sessionUuid, tempTitle);
      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, judul: tempTitle }
              : chat,
          ),
        );
        setEditingSessionId(null);
      }
    } catch (err) {
      console.error("Gagal rename chat:", err);
    }
  };

  return (
    <div
      className="flex-1 overflow-y-auto px-2 pt-2 space-y-0.5"
      style={{
        scrollbarWidth: "thin",
      }}
    >
      {/* ── MENUS THAT SCROLL ALONG WITH CHATS ── */}
      <div className="space-y-0 mb-4 px-1">
        {/* ── TOMBOL: DOCUMENTS (DULU EMOJI 📄, SEKARANG SVG) ── */}
        <button
          onClick={() => setShowDocumentList(!showDocumentList)}
          className={`flex items-center transition-all group overflow-hidden text-[14px] ${
            showDocumentList
              ? "bg-blue-500/10 text-blue-500 font-semibold border-l-2 border-blue-500 rounded-r-full"
              : `rounded-full font-medium ${darkMode ? 'hover:bg-white/5' : 'hover:bg-gray-200/50'}`
          }`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.documents}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke={theme?.iconColor || "currentColor"}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="group-hover:text-blue-500 transition-colors"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
          </span>
          <span
            className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: showDocumentList ? '' : theme?.textColor }}
          >
            {t.documents}
          </span>
        </button>

        {/* ── CORPORATE TOOLS SECTION ── */}
        <div className={`pt-4 pb-1 transition-all duration-300 ${!isOpen ? "opacity-0 h-0 overflow-hidden" : "opacity-100 h-auto"}`}>
          <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color: theme?.secondaryText || "#9ca3af", paddingLeft: "12px" }}>
            {t.corporateTools}
          </p>
        </div>

        {/* 1. Smart Mail */}
        <button
          onClick={() => navigate('/corporate/mail')}
          className={`flex items-center transition-all group overflow-hidden text-[14px] ${
            location.pathname === '/corporate/mail'
              ? "bg-blue-500/10 text-blue-500 font-semibold border-l-2 border-blue-500 rounded-r-full"
              : `rounded-full font-medium ${darkMode ? 'hover:bg-white/5' : 'hover:bg-gray-200/50'}`
          }`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.smartMail}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={location.pathname === '/corporate/mail' ? "currentColor" : (theme?.iconColor || "currentColor")} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-blue-500 transition-colors">
              <rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect>
              <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
            </svg>
          </span>
          <span className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: location.pathname === '/corporate/mail' ? '' : theme?.textColor }}>
            {t.smartMail}
          </span>
        </button>

        {/* 2. Nota Dinas Gen */}
        <button
          onClick={() => navigate('/corporate/notadinas')}
          className={`flex items-center transition-all group overflow-hidden text-[14px] ${
            location.pathname === '/corporate/notadinas'
              ? "bg-blue-500/10 text-blue-500 font-semibold border-l-2 border-blue-500 rounded-r-full"
              : `rounded-full font-medium ${darkMode ? 'hover:bg-white/5' : 'hover:bg-gray-200/50'}`
          }`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.notaDinasGen}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={location.pathname === '/corporate/notadinas' ? "currentColor" : (theme?.iconColor || "currentColor")} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-emerald-500 transition-colors">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
            </svg>
          </span>
          <span className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: location.pathname === '/corporate/notadinas' ? '' : theme?.textColor }}>
            {t.notaDinasGen}
          </span>
        </button>

        {/* 3. Vendor Analyzer */}
        <button
          onClick={() => navigate('/corporate/vendor')}
          className={`flex items-center transition-all group overflow-hidden text-[14px] ${
            location.pathname === '/corporate/vendor'
              ? "bg-blue-500/10 text-blue-500 font-semibold border-l-2 border-blue-500 rounded-r-full"
              : `rounded-full font-medium ${darkMode ? 'hover:bg-white/5' : 'hover:bg-gray-200/50'}`
          }`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.vendorAnalyzer}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={location.pathname === '/corporate/vendor' ? "currentColor" : (theme?.iconColor || "currentColor")} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-purple-500 transition-colors">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
          </span>
          <span className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: location.pathname === '/corporate/vendor' ? '' : theme?.textColor }}>
            {t.vendorAnalyzer}
          </span>
        </button>

        {/* ── TOMBOL: ANALYTICS (HANYA UNTUK 06652) ── */}
        {userData?.npp === '06652' && (
          <button
            onClick={() => navigate('/analytics')}
            className={`flex items-center transition-all group overflow-hidden text-[14px] ${
              location.pathname === '/analytics'
                ? "bg-blue-500/10 text-blue-500 font-semibold border-l-2 border-blue-500 rounded-r-full"
                : `rounded-full font-medium ${darkMode ? 'hover:bg-white/5' : 'hover:bg-gray-200/50'}`
            }`}
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title={t.analytics}
          >
            <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke={location.pathname === '/analytics' ? "currentColor" : (theme?.iconColor || "currentColor")}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="group-hover:text-cyan-500 transition-colors"
              >
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
              </svg>
            </span>
            <span
              className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: location.pathname === '/analytics' ? '' : theme?.textColor }}
            >
              {t.analytics}
            </span>
          </button>
        )}

        {/* ── TOMBOL: AUDIT LOGS (DULU EMOJI 🛡️, SEKARANG SVG) ── */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/audit-logs')}
            className={`flex items-center transition-all group overflow-hidden text-[14px] ${
              location.pathname === '/admin/audit-logs'
                ? "bg-red-500/10 text-red-500 font-semibold border-l-2 border-red-500 rounded-r-full"
                : `rounded-full font-medium ${darkMode ? 'hover:bg-red-900/10' : 'hover:bg-red-50/50'}`
            }`}
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title={t.auditLogs}
          >
            <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#ef4444"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
            </span>
            <span
              className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: location.pathname === '/admin/audit-logs' ? '' : '#ef4444', fontSize: '13px' }}
            >
              {t.auditLogs}
            </span>
          </button>
        )}

        {/* ── TOMBOL: CACHE & INDEX (DULU EMOJI ⚡, SEKARANG SVG) ── */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/cache-stats')}
            className={`flex items-center transition-all group overflow-hidden text-[14px] ${
              location.pathname === '/admin/cache-stats'
                ? "bg-indigo-500/10 text-indigo-500 font-semibold border-l-2 border-indigo-500 rounded-r-full"
                : `rounded-full font-medium ${darkMode ? 'hover:bg-indigo-900/10' : 'hover:bg-indigo-50/50'}`
            }`}
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title={t.cacheIndex}
          >
            <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#818cf8"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
            </span>
            <span
              className={`whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: location.pathname === '/admin/cache-stats' ? '' : '#818cf8', fontSize: '13px' }}
            >
              {t.cacheIndex}
            </span>
          </button>
        )}
      </div>

      <div className={`transition-opacity duration-300 ${!isOpen ? "opacity-0 pointer-events-none hidden" : "opacity-100"}`}>
        <div
          className="px-3 py-1 text-[11px] font-bold uppercase tracking-widest mb-1"
          style={{ color: theme?.secondaryText || "#6b7280" }}
        >
          {t.chats}
        </div>

      {(() => {
        if (chatHistory.length === 0) {
          return (
            <div className="text-[11px] text-gray-400 px-3 py-4 italic">
              {t.emptyHistory}
            </div>
          );
        }

        // Group the chats
        const groups = {
          starred: [],
          today: [],
          yesterday: [],
          pastWeek: [],
          pastMonth: [],
          older: []
        };

        chatHistory.forEach(chat => {
          if (chat.is_pinned) {
            groups.starred.push(chat);
            return;
          }

          const updatedAt = chat.updated_at || chat.created_at || chat.started_at;
          if (!updatedAt) {
            groups.older.push(chat);
            return;
          }

          const date = new Date(updatedAt);
          if (isToday(date)) {
            groups.today.push(chat);
          } else if (isYesterday(date)) {
            groups.yesterday.push(chat);
          } else if (isThisWeek(date)) {
            groups.pastWeek.push(chat);
          } else if (isThisMonth(date)) {
            groups.pastMonth.push(chat);
          } else {
            groups.older.push(chat);
          }
        });

        const groupConfigs = [
          { key: "starred", label: t.starred, items: groups.starred },
          { key: "today", label: t.today, items: groups.today },
          { key: "yesterday", label: t.yesterday, items: groups.yesterday },
          { key: "pastWeek", label: t.pastWeek, items: groups.pastWeek },
          { key: "pastMonth", label: t.pastMonth, items: groups.pastMonth },
          { key: "older", label: t.older, items: groups.older }
        ];

        return groupConfigs.map((group) => {
          if (group.items.length === 0) return null;

          return (
            <div key={group.key} className="mb-4">
              <div
                className="px-3 py-1 text-[8px] font-bold uppercase tracking-widest mb-1"
                style={{ color: theme?.secondaryText || "#9CA3AF" }}
              >
                {group.label}
              </div>
              {group.items
                .sort((a, b) => new Date(b.updated_at || b.created_at || b.started_at) - new Date(a.updated_at || a.created_at || a.started_at))
                .map((chat) => (

                  <div
                    key={chat.session_uuid}
                    onMouseEnter={() => setHoveredChatId(chat.session_uuid)}
                    onMouseLeave={() => setHoveredChatId(null)}
                    onClick={() => {
                      loadChatSession(chat.session_uuid);
                      setActiveMenuId(null);
                    }}
                    className={`group relative flex items-center px-3 py-1.5 text-[13px] rounded-xl cursor-pointer transition-all hover:translate-x-1 ${currentSessionId === chat.session_uuid
                      ? "bg-blue-500/10 text-blue-400 font-semibold border-l-2 border-blue-500"
                      : `font-medium ${darkMode ? "hover:bg-white/5" : "hover:bg-gray-200/50"}`
                      } ${isDeletingId === chat.session_uuid ? "animate-delete" : ""
                      } ${activeMenuId === chat.session_uuid ? "z-50" : "z-10"}`}
                    style={{
                      color:
                        currentSessionId === chat.session_uuid
                          ? darkMode
                            ? "#60a5fa"
                            : "#2563eb"
                          : darkMode
                            ? "#94a3b8"
                            : "#4b5563",
                    }}
                    title={chat.judul}
                  >
                    {/* 🔥 SVG GANTI EMOJI PIN/CHAT UTAMA LIST */}
                    <span className="mr-2.5 opacity-60 flex-shrink-0">
                      {chat.is_pinned ? (
                        /* SVG Pushpin Modern Simetris */
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1">
                          <path d="M21 12c-1.42 0-3.37-1.12-4-2.28V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5.72C6.37 10.88 4.42 12 3 12a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1h8v6l1 2 1-2v-6h8a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1z"></path>
                        </svg>
                      ) : (
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                      )}
                    </span>

                    <span className="flex-1 text-left pr-4 text-[13px] leading-relaxed min-w-0 flex items-center">
                      {editingSessionId === chat.session_uuid ? (
                        <input
                          autoFocus
                          className="w-full bg-white border border-blue-400 rounded px-1 outline-none text-black text-xs py-0 dark:bg-gray-800 dark:text-white"
                          value={tempTitle}
                          onChange={(e) => setTempTitle(e.target.value)}
                          onBlur={() => handleRename(chat.session_uuid)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRename(chat.session_uuid);
                            if (e.key === "Escape") setEditingSessionId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="flex items-center gap-1 min-w-0 flex-1">
                          <span className="truncate" title={chat.judul || t.newChatTitle}>
                            {chat._titleUpdated && !animatedTitles.current.has(chat.session_uuid) ? (
                              <TypewriterTitle
                                text={chat.judul}
                                onDone={() => {
                                  // Tandai sudah dianimasi — jangan ulang lagi
                                  animatedTitles.current.add(chat.session_uuid);
                                }}
                              />
                            ) : (
                              chat.judul || t.newChatTitle
                            )}
                          </span>
                          {activeStreams[chat.session_uuid]?.isStreaming && (
                            <svg className="animate-spin text-blue-500 flex-shrink-0" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          )}
                          {isTitleGenerating(chat.session_uuid) && (
                            <span
                              title="Generating better title..."
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '2px',
                                fontSize: '9px',
                                color: '#a78bfa',
                                background: 'rgba(139,92,246,0.12)',
                                border: '1px solid rgba(139,92,246,0.25)',
                                borderRadius: '8px',
                                padding: '1px 5px',
                                flexShrink: 0,
                                animation: 'pulse 1.5s ease-in-out infinite',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                              </svg>
                            </span>
                          )}
                        </span>
                      )}
                    </span>

                    {(hoveredChatId === chat.session_uuid ||
                      activeMenuId === chat.session_uuid) && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(
                              activeMenuId === chat.session_uuid
                                ? null
                                : chat.session_uuid,
                            );
                          }}
                          className={`absolute right-1 p-1 rounded transition-colors ${darkMode ? "hover:bg-gray-700" : "hover:bg-gray-300"}`}
                        >
                          <svg className="h-4 w-4" style={{ color: theme?.secondaryText || "currentColor" }} fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                          </svg>
                        </button>
                      )}

                    {activeMenuId === chat.session_uuid && (
                      <div
                        ref={menuRef}
                        onClick={(e) => e.stopPropagation()}
                        className={`absolute right-0 top-7 w-32 rounded-md shadow-lg z-[100] py-1 text-[11px] border`}
                        style={{ backgroundColor: darkMode ? '#1f2937' : '#ffffff', borderColor: darkMode ? '#374151' : '#e5e7eb' }}
                      >
                        {/* 🔥 DROPDOWN ITEM 1: PIN (SVG VECTOR) */}
                        <button
                          onClick={(e) => togglePinChat(e, chat.session_uuid)}
                          className={`w-full text-left px-3 py-2 flex justify-between items-center ${darkMode ? "hover:bg-gray-700 text-gray-200" : "hover:bg-gray-100"}`}
                        >
                          <span>{chat.is_pinned ? t.unpin : t.pin}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-60">
                            <line x1="12" y1="2" x2="12" y2="22"></line>
                            <polyline points="5 12 12 5 19 12"></polyline>
                          </svg>
                        </button>

                        {/* 🔥 DROPDOWN ITEM 2: RENAME (SVG VECTOR) */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingSessionId(chat.session_uuid);
                            setTempTitle(chat.judul || "");
                            setActiveMenuId(null);
                          }}
                          className={`w-full text-left px-3 py-2 flex justify-between items-center ${darkMode ? "hover:bg-gray-700 text-gray-200" : "hover:bg-gray-100"}`}
                        >
                          <span>{t.rename}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-60">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4Z"></path>
                          </svg>
                        </button>

                        {/* 🔥 DROPDOWN ITEM 3: HAPUS (SVG VECTOR) */}
                        <button
                          onClick={(e) => confirmDelete(e, chat.session_uuid)}
                          className={`w-full text-left px-3 py-2 text-red-600 flex justify-between items-center font-semibold ${darkMode ? "hover:bg-red-900/20" : "hover:bg-red-50"}`}
                        >
                          <span>{t.delete}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <polyline points="3 6 5 3 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                ))}
            </div>
          );
        });
      })()}
      </div>
    </div>
  );
}