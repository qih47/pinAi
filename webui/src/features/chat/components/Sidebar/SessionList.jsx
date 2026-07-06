import React, { useState, useEffect } from "react";
import { useSessionTitle } from "../../../../hooks/useSessionTitle";

const TypewriterTitle = ({ text }) => {
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
        setTimeout(() => setIsTyping(false), 1500);
      }
    }, 50);
    return () => clearInterval(timer);
  }, [text]);

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
  isDeletingId
}) {
  const [hoveredChatId, setHoveredChatId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [tempTitle, setTempTitle] = useState("");

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
      className={`flex-1 overflow-y-auto px-2 py-2 space-y-0.5 transition-opacity duration-300 no-scrollbar ${!isOpen ? "opacity-0 pointer-events-none hidden" : "opacity-100"
        }`}
      style={{
        msOverflowStyle: "none",
        scrollbarWidth: "none",
      }}
    >
      <div
        className="px-3 py-1 text-[11px] font-bold uppercase tracking-widest mb-1"
        style={{ color: theme?.secondaryText || "#6b7280" }}
      >
        Semua Chat
      </div>

      {isOpen && (
        <div className="px-3 mb-2 relative">
          <input
            ref={sidebarSearchInputRef}
            type="text"
            placeholder="Cari riwayat chat... (Ctrl+K)"
            value={sessionSearchQuery}
            onChange={(e) => setSessionSearchQuery(e.target.value)}
            className="w-full text-xs rounded-lg px-2.5 py-1.5 outline-none border transition-colors"
            style={{
              background: darkMode ? "#252528" : "#F3F4F6",
              borderColor: darkMode ? "#2A2A2D" : "#E5E7EB",
              color: theme?.textColor || (darkMode ? "#e2e8f0" : "#1f2937"),
            }}
          />
          {sessionSearchQuery && (
            <button
              onClick={() => setSessionSearchQuery("")}
              className="absolute right-5 top-1/2 -translate-y-1/2 text-[10px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          )}
        </div>
      )}

      {chatHistory.length > 0 ? (
        [...chatHistory]
          .filter((c) =>
            (c.judul || "Chat Baru")
              .toLowerCase()
              .includes(sessionSearchQuery.toLowerCase()),
          )
          .sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0))
          .map((chat) => (
            <div
              key={chat.session_uuid}
              onMouseEnter={() => setHoveredChatId(chat.session_uuid)}
              onMouseLeave={() => setHoveredChatId(null)}
              onClick={() => {
                loadChatSession(chat.session_uuid);
                setActiveMenuId(null);
              }}
              className={`group relative flex items-center px-3 py-2 text-sm rounded-xl cursor-pointer transition-all ${currentSessionId === chat.session_uuid
                ? "bg-blue-500/10 text-blue-400 font-semibold border-l-2 border-blue-500"
                : "hover:bg-gray-200/50 dark:hover:bg-white/5 font-medium"
                } ${isDeletingId === chat.session_uuid ? "animate-delete" : ""
                }`}
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

              <span className="truncate flex-1 text-left pr-4 text-[13px] leading-relaxed">
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
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span className="truncate">
                      {chat._titleUpdated ? (
                        <TypewriterTitle text={chat.judul} />
                      ) : (
                        chat.judul || "Chat Baru"
                      )}
                    </span>
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
                    className="absolute right-1 p-1 hover:bg-gray-300 rounded transition-colors dark:hover:bg-gray-700"
                  >
                    <svg className="h-4 w-4" style={{ color: theme?.secondaryText || "currentColor" }} fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                    </svg>
                  </button>
                )}

              {activeMenuId === chat.session_uuid && (
                <div
                  ref={menuRef}
                  className="absolute right-0 top-7 w-32 bg-white border border-gray-200 rounded-md shadow-lg z-[100] py-1 text-[11px] dark:bg-gray-800 dark:border-gray-700"
                >
                  {/* 🔥 DROPDOWN ITEM 1: PIN (SVG VECTOR) */}
                  <button
                    onClick={(e) => togglePinChat(e, chat.session_uuid)}
                    className="w-full text-left px-3 py-2 hover:bg-gray-100 flex justify-between items-center dark:hover:bg-gray-700 dark:text-gray-200"
                  >
                    <span>{chat.is_pinned ? "Lepas Pin" : "Pin Chat"}</span>
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
                    className="w-full text-left px-3 py-2 hover:bg-gray-100 flex justify-between items-center dark:hover:bg-gray-700 dark:text-gray-200"
                  >
                    <span>Rename</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-60">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4Z"></path>
                    </svg>
                  </button>

                  {/* 🔥 DROPDOWN ITEM 3: HAPUS (SVG VECTOR) */}
                  <button
                    onClick={(e) => confirmDelete(e, chat.session_uuid)}
                    className="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600 flex justify-between items-center font-semibold dark:hover:bg-red-900/20"
                  >
                    <span>Hapus</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="3 6 5 3 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))
      ) : (
        <div className="text-[11px] text-gray-400 px-3 py-4 italic">
          Belum ada history
        </div>
      )}
    </div>
  );
}