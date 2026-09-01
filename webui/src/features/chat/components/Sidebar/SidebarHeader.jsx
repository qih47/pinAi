import React from "react";
import SessionExpiryStatus from "../../../../components/SessionExpiryStatus";
import { Plus, Search } from "lucide-react";
import { translations } from "../../../../utils/translations";

export default function SidebarHeader({
  isOpen,
  setIsOpen,
  isMobile,
  isHovered,
  setIsHovered,
  cakraLogo,
  theme,
  darkMode,
  clearChat,
  showDocumentList,
  setShowDocumentList,
  userData,
  navigate,
  setIsSearchModalOpen,
  language
}) {
  const t = translations[language]?.sidebar || translations.id.sidebar;

  return (
    <>
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`relative flex flex-col justify-center transition-all duration-300 ${isOpen ? "p-5" : "p-3"}`}
      >
        <div className={`flex items-center ${isOpen ? "" : "justify-center w-full"}`}>
          <img
            src={cakraLogo}
            alt="CAKRA AI Logo"
            className={`transition-all duration-300 flex-shrink-0 object-contain ${isOpen ? "w-10 h-10" : "w-7 h-7"
              } ${!isOpen && isHovered ? "opacity-0" : "opacity-100"}`}
          />
          <h1
            className={`font-bold text-lg whitespace-nowrap transition-all duration-300 overflow-hidden ${!isOpen ? "opacity-0 pointer-events-none w-0 m-0" : "opacity-100 ml-2"
              }`}
            style={{ color: theme?.textColor }}
          >
            CAKRA
          </h1>
        </div>

        {(!isMobile || isOpen) && (
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={`absolute transition-all duration-300 p-1.5 rounded-lg ${darkMode ? 'hover:bg-gray-800 active:bg-gray-700' : 'hover:bg-gray-200 active:bg-gray-300'}`}
            style={{
              color: theme?.iconColor,
              top: isOpen ? "20px" : "12px",
              right: isOpen ? "12px" : "auto",
              left: isOpen ? "auto" : "50%",
              transform: isOpen ? "none" : "translateX(-50%)",
              opacity: isOpen ? 1 : isHovered ? 1 : 0,
              pointerEvents: isOpen ? "auto" : isHovered ? "auto" : "none",
            }}
            title={isOpen ? t.collapse : t.expand}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="4" width="18" height="16" rx="2.5" />
              <rect x="3" y="4" width="6" height="16" rx="2.5" />
            </svg>
          </button>
        )}
      </div>

      <div
        className={`p-3 space-y-0 ${!isOpen && "flex flex-col items-center"}`}
      >
        <SessionExpiryStatus />

        {/* ── TOMBOL: NEW CHAT ── */}
        <button
          onClick={clearChat}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.newChat}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <Plus size={18} strokeWidth={2.5} className="group-hover:text-blue-500 transition-colors" style={{ color: theme?.iconColor || "currentColor" }} />
          </span>
          <span
            className={`font-semibold whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            {t.newChat}
          </span>
        </button>

        {/* ── TOMBOL: SEARCH (CTRL+K) ── */}
        <button
          onClick={() => setIsSearchModalOpen(true)}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title={t.searchChat}
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <Search size={16} strokeWidth={2.5} className="group-hover:text-blue-500 transition-colors" style={{ color: theme?.iconColor || "currentColor" }} />
          </span>
          <span
            className={`font-semibold whitespace-nowrap transition-opacity duration-300 flex-1 text-left ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            {t.searchChat}
          </span>
          {isOpen && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded border opacity-60 ml-auto"
              style={{
                borderColor: darkMode ? "#4B5563" : "#D1D5DB",
                color: darkMode ? "#9CA3AF" : "#6B7280"
              }}
            >
              Ctrl K
            </span>
          )}
        </button>
      </div>
    </>
  );
}