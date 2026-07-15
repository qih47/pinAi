import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { formatDistanceToNow, isToday, isYesterday, isThisWeek, isThisMonth } from "date-fns";
import { id, enUS } from "date-fns/locale";
import { translations } from "../../../../utils/translations";

export default function SearchModal({ isOpen, onClose, chatHistory, loadChatSession, darkMode, theme, language = "id" }) {
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef(null);
  const modalRef = useRef(null);
  const t = translations[language]?.searchModal || translations.id.searchModal;
  const t_sidebar = translations[language]?.sidebar || translations.id.sidebar;

  useEffect(() => {
    if (isOpen) {
      setSearchQuery("");
      setTimeout(() => {
        if (inputRef.current) inputRef.current.focus();
      }, 100);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (modalRef.current && !modalRef.current.contains(e.target)) {
        onClose();
      }
    };
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter chats by search query
  const filteredChats = chatHistory.filter((c) =>
    (c.judul || "Chat Baru").toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Helper to format relative time like Claude (Past week, Past month, Today, etc)
  const getRelativeTime = (updatedAt) => {
    if (!updatedAt) return "";
    const date = new Date(updatedAt);

    if (isToday(date)) return t_sidebar.today;
    if (isYesterday(date)) return t_sidebar.yesterday;
    if (isThisWeek(date)) return t_sidebar.pastWeek;
    if (isThisMonth(date)) return t_sidebar.pastMonth;

    return formatDistanceToNow(date, { addSuffix: true, locale: language === "en" ? enUS : id });
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[10dvh] bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        ref={modalRef}
        className="w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-top-4 duration-200 border"
        style={{
          background: darkMode ? "#1E1E22" : "#FFFFFF",
          borderColor: darkMode ? "#333333" : "#E5E7EB",
        }}
      >
        {/* Header / Input */}
        <div className="flex items-center px-4 py-3 border-b" style={{ borderColor: darkMode ? "#333333" : "#E5E7EB" }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={darkMode ? "#9CA3AF" : "#6B7280"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-3">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent border-none outline-none text-lg"
            placeholder={t.placeholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ color: darkMode ? "#FFFFFF" : "#111827" }}
          />
          <button onClick={onClose} className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/10 transition-colors ml-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={darkMode ? "#9CA3AF" : "#6B7280"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-[60vh] overflow-y-auto no-scrollbar py-2">
          {filteredChats.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: darkMode ? "#9CA3AF" : "#6B7280" }}>
              {searchQuery ? t.empty : ""}
            </div>
          ) : (
            filteredChats.map((chat) => (
              <div
                key={chat.session_uuid}
                onClick={() => loadChatSession(chat.session_uuid)}
                className="group flex items-center px-4 py-3 mx-2 my-1 cursor-pointer rounded-xl transition-all"
                style={{
                  color: darkMode ? "#E2E8F0" : "#1F2937",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = darkMode ? "#2A2A2D" : "#F3F4F6";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={darkMode ? "#9CA3AF" : "#6B7280"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-3 flex-shrink-0 opacity-70">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <div className="flex-1 flex flex-col min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="flex-1 font-medium truncate pr-4 text-[15px]">
                      {chat.judul || t_sidebar.newChatTitle}
                    </span>
                    <span
                      className="text-[12px] whitespace-nowrap opacity-60"
                      style={{ color: darkMode ? "#9CA3AF" : "#6B7280" }}
                    >
                      {getRelativeTime(chat.updated_at || chat.created_at || chat.started_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
