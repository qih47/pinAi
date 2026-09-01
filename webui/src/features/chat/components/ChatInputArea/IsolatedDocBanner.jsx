import React, { useState, useRef } from "react";
import { ChevronDown, Check } from "lucide-react";
import { useChatStore } from "../../../../stores/chatStore";
import { translations } from "../../../../utils/translations";

export default function IsolatedDocBanner({
  activeIsolatedTitle,
  setContextIsolation,
  darkMode,
  chatMode,
  language = "id"
}) {
  const activeIsolatedDocId = useChatStore((state) => state.activeIsolatedDocId);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const hoverTimeoutRef = useRef(null);

  const tGlobal = translations[language]?.chat?.isolatedBanner || translations.id.chat.isolatedBanner;

  if (!activeIsolatedTitle) return null;

  const currentMode = chatMode === 'compliance' ? 'compliance' : chatMode === 'redteam' ? 'redteam' : 'focus';

  const modes = [
    {
      id: "focus",
      name: tGlobal.focus.name,
      badgeLabel: tGlobal.focus.badge,
      icon: "🎯",
      desc: tGlobal.focus.desc,
      badgeColor: darkMode ? "#c7d2fe" : "#3730a3",
      actionDesc: tGlobal.focus.action
    },
    {
      id: "compliance",
      name: tGlobal.compliance.name,
      badgeLabel: tGlobal.compliance.badge,
      icon: "⚖️",
      desc: tGlobal.compliance.desc,
      badgeColor: darkMode ? "#fca5a5" : "#b91c1c",
      actionDesc: tGlobal.compliance.action
    },
    {
      id: "redteam",
      name: tGlobal.redteam.name,
      badgeLabel: tGlobal.redteam.badge,
      icon: "🕵️",
      desc: tGlobal.redteam.desc,
      badgeColor: darkMode ? "#fdba74" : "#c2410c",
      actionDesc: tGlobal.redteam.action
    }
  ];

  const activeConfig = modes.find(m => m.id === currentMode) || modes[0];

  const bannerTheme = currentMode === 'compliance'
    ? {
        bg: darkMode ? "rgba(239, 68, 68, 0.14)" : "rgba(254, 226, 226, 0.7)",
        border: darkMode ? "rgba(239, 68, 68, 0.4)" : "rgba(239, 68, 68, 0.35)",
        textColor: darkMode ? "#fecaca" : "#991b1b",
        glow: darkMode ? "0 0 16px rgba(239, 68, 68, 0.12)" : "0 2px 8px rgba(239, 68, 68, 0.06)",
        badgeBg: darkMode ? "rgba(239, 68, 68, 0.28)" : "rgba(239, 68, 68, 0.15)",
        actionDesc: activeConfig.actionDesc
      }
    : currentMode === 'redteam'
    ? {
        bg: darkMode ? "rgba(249, 115, 22, 0.14)" : "rgba(255, 237, 213, 0.7)",
        border: darkMode ? "rgba(249, 115, 22, 0.4)" : "rgba(249, 115, 22, 0.35)",
        textColor: darkMode ? "#fed7aa" : "#9a3412",
        glow: darkMode ? "0 0 16px rgba(249, 115, 22, 0.12)" : "0 2px 8px rgba(249, 115, 22, 0.06)",
        badgeBg: darkMode ? "rgba(249, 115, 22, 0.28)" : "rgba(249, 115, 22, 0.15)",
        actionDesc: activeConfig.actionDesc
      }
    : {
        bg: darkMode ? "rgba(99, 102, 241, 0.14)" : "rgba(238, 242, 255, 0.8)",
        border: darkMode ? "rgba(99, 102, 241, 0.4)" : "rgba(99, 102, 241, 0.35)",
        textColor: darkMode ? "#e0e7ff" : "#1e3a8a",
        glow: darkMode ? "0 0 16px rgba(99, 102, 241, 0.12)" : "0 2px 8px rgba(99, 102, 241, 0.06)",
        badgeBg: darkMode ? "rgba(99, 102, 241, 0.28)" : "rgba(99, 102, 241, 0.12)",
        actionDesc: activeConfig.actionDesc
      };

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    hoverTimeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 180);
  };

  const handleSwitchMode = (modeId) => {
    setContextIsolation(activeIsolatedDocId, activeIsolatedTitle, modeId);
    setIsOpen(false);
  };

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: bannerTheme.bg,
        border: `1px solid ${bannerTheme.border}`,
        boxShadow: bannerTheme.glow,
        backdropFilter: "blur(12px)",
        borderRadius: "14px",
        padding: "6px 12px",
        marginBottom: "10px",
        fontSize: "13px",
        color: bannerTheme.textColor,
        transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          minWidth: 0,
          flex: 1,
        }}
      >
        <span style={{ fontSize: "15px", flexShrink: 0 }}>{activeConfig.icon}</span>

        {/* Kotak Kecil (Badge Ringkas) dengan Hover Dropdown */}
        <div
          ref={dropdownRef}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          style={{ position: "relative", display: "inline-block" }}
        >
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="group flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-bold tracking-wider uppercase transition-all duration-150 cursor-pointer shadow-sm"
            style={{
              background: bannerTheme.badgeBg,
              color: activeConfig.badgeColor,
              border: `1px solid ${bannerTheme.border}`,
              outline: "none"
            }}
            title={tGlobal.switchMode}
          >
            <span>{activeConfig.badgeLabel}</span>
            <ChevronDown
              size={12}
              className={`transition-transform duration-200 opacity-60 group-hover:opacity-100 ${
                isOpen ? "rotate-180" : ""
              }`}
            />
          </button>

          {/* 🔽 POPOVER MENU LENGKAP & DETAIL SAAT HOVER / CLICK */}
          {isOpen && (
            <div
              className={`absolute left-0 bottom-full mb-2.5 w-72 rounded-xl shadow-2xl p-1.5 z-50 transition-all duration-150 border ${
                darkMode
                  ? "bg-[#1c1c22]/95 border-gray-700/80 backdrop-blur-xl text-gray-200 shadow-black/70"
                  : "bg-white/95 border-gray-200/90 backdrop-blur-xl text-gray-800 shadow-indigo-500/10"
              }`}
            >
              <div className="px-2.5 py-1.5 border-b border-gray-200/40 dark:border-gray-700/50 mb-1 flex items-center justify-between">
                <span className="text-[10px] font-bold tracking-wider uppercase text-gray-400 dark:text-gray-500">
                  {tGlobal.switchMode}
                </span>
                <span className="text-[10px] text-indigo-400 font-medium">{tGlobal.isolatedDocCount}</span>
              </div>

              <div className="flex flex-col gap-1">
                {modes.map((mode) => {
                  const isActive = mode.id === currentMode;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => handleSwitchMode(mode.id)}
                      className={`w-full flex items-start gap-2.5 p-2 rounded-lg text-left transition-all duration-150 cursor-pointer ${
                        isActive
                          ? darkMode
                            ? "bg-white/10 text-white font-medium"
                            : "bg-indigo-50 text-indigo-900 font-medium"
                          : darkMode
                          ? "hover:bg-white/5 text-gray-300 hover:text-white"
                          : "hover:bg-gray-100/80 text-gray-700 hover:text-gray-900"
                      }`}
                    >
                      <span className="text-base flex-shrink-0 mt-0.5">{mode.icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-[12px] font-semibold tracking-tight">{mode.name}</span>
                          {isActive && <Check size={13} className="text-indigo-400 flex-shrink-0" />}
                        </div>
                        <p className="text-[10.5px] leading-tight text-gray-400 dark:text-gray-400 font-normal truncate mt-0.5">
                          {mode.desc}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Keterangan Aksi & Judul Dokumen */}
        <span
          style={{
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            fontSize: "12.5px",
            fontWeight: 400,
            opacity: 0.95
          }}
        >
          {bannerTheme.actionDesc} <strong style={{ fontWeight: 600 }}>{activeIsolatedTitle}</strong>
        </span>
      </div>

      {/* Tombol Close / Lepas Isolasi */}
      <button
        type="button"
        title={tGlobal.closeTitle}
        onClick={() => setContextIsolation(null, null, 'auto')}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "22px",
          height: "22px",
          borderRadius: "50%",
          background: darkMode ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)",
          border: "none",
          color: darkMode ? "#9ca3af" : "#4b5563",
          cursor: "pointer",
          fontSize: "11px",
          fontWeight: "bold",
          marginLeft: "8px",
          flexShrink: 0,
          transition: "all 0.15s ease",
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.background = darkMode ? "rgba(255, 255, 255, 0.2)" : "rgba(0, 0, 0, 0.12)";
          e.currentTarget.style.color = darkMode ? "#ffffff" : "#111827";
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.background = darkMode ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
          e.currentTarget.style.color = darkMode ? "#9ca3af" : "#4b5563";
        }}
      >
        ✕
      </button>
    </div>
  );
}
