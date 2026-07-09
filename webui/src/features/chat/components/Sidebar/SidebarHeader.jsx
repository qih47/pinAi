import React from "react";
import SessionExpiryStatus from "../../../../components/SessionExpiryStatus";

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
  navigate
}) {
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
            CAKRA AI
          </h1>
        </div>

        {!isMobile && (
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={`absolute transition-all duration-300 p-1 rounded ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
            style={{
              color: theme?.iconColor,
              top: isOpen ? "20px" : "12px",
              right: isOpen ? "12px" : "auto",
              left: isOpen ? "auto" : "50%",
              transform: isOpen ? "none" : "translateX(-50%)",
              opacity: isOpen ? 1 : isHovered ? 1 : 0,
              pointerEvents: isOpen ? "auto" : isHovered ? "auto" : "none",
            }}
            title={isOpen ? "Ciutkan" : "Lebarkan"}
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
          title="New Chat"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 group-hover:text-blue-500 flex-shrink-0"
            style={{ color: theme?.iconColor }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span
            className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            New Chat
          </span>
        </button>

        {/* ── TOMBOL: DOCUMENTS (DULU EMOJI 📄, SEKARANG SVG) ── */}
        <button
          onClick={() => setShowDocumentList(!showDocumentList)}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="Documents"
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
            className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            Documents
          </span>
        </button>

        {/* ── CORPORATE TOOLS SECTION ── */}
        <div className={`pt-4 pb-1 transition-all duration-300 ${!isOpen ? "opacity-0 h-0 overflow-hidden" : "opacity-100 h-auto"}`}>
          <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color: theme?.secondaryText || "#9ca3af", paddingLeft: "12px" }}>
            Corporate Tools
          </p>
        </div>

        {/* 1. Smart Mail */}
        <button
          onClick={() => navigate('/corporate/mail')}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="Smart Mail"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme?.iconColor || "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-blue-500 transition-colors">
              <rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect>
              <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
            </svg>
          </span>
          <span className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: theme?.textColor }}>
            Smart Mail
          </span>
        </button>

        {/* 2. Nota Dinas Gen */}
        <button
          onClick={() => navigate('/corporate/notadinas')}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="Nota Dinas Gen"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme?.iconColor || "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-emerald-500 transition-colors">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
            </svg>
          </span>
          <span className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: theme?.textColor }}>
            Nota Dinas Gen
          </span>
        </button>

        {/* 3. Vendor Analyzer */}
        <button
          onClick={() => navigate('/corporate/vendor')}
          className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="Vendor Analyzer"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme?.iconColor || "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:text-purple-500 transition-colors">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
          </span>
          <span className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"}`} style={{ color: theme?.textColor }}>
            Vendor Analyzer
          </span>
        </button>

        {/* ── TOMBOL: ANALYTICS (HANYA UNTUK 06652) ── */}
        {userData?.npp === '06652' && (
          <button
            onClick={() => navigate('/analytics')}
            className={`flex items-center rounded-full transition-colors group overflow-hidden text-[14px] ${darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-200'}`}
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title="Analytics"
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
                className="group-hover:text-cyan-500 transition-colors"
              >
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
              </svg>
            </span>
            <span
              className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: theme?.textColor }}
            >
              Analytics
            </span>
          </button>
        )}

        {/* ── TOMBOL: AUDIT LOGS (DULU EMOJI 🛡️, SEKARANG SVG) ── */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/audit-logs')}
            className="flex items-center rounded-full hover:bg-red-100/10 transition-colors group overflow-hidden text-[14px]"
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title="Audit Logs (Admin)"
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
              className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: '#ef4444', fontSize: '13px' }}
            >
              Audit Logs
            </span>
          </button>
        )}

        {/* ── TOMBOL: CACHE & INDEX (DULU EMOJI ⚡, SEKARANG SVG) ── */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/cache-stats')}
            className="flex items-center rounded-full hover:bg-indigo-100/10 transition-colors group overflow-hidden text-[14px]"
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title="Cache & Performance (Admin)"
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
              className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: '#818cf8', fontSize: '13px' }}
            >
              Cache & Index
            </span>
          </button>
        )}
      </div>
    </>
  );
}