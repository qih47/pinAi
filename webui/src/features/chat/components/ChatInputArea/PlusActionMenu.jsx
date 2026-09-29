import React, { useState, useMemo, useRef, useEffect, forwardRef } from "react";
import {
  Paperclip, Cloud, Globe, FileText, Code2, Target,
  BarChart3, Workflow, FilePlus, Mail, Search, X, HardDrive
} from "lucide-react";
import { translations } from "../../../../utils/translations";
import useStorageStore from "../../../../stores/useStorageStore";

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

const PlusActionMenu = forwardRef(function PlusActionMenu({
  isOpen,
  onClose,
  fileInputRef,
  openNextcloudModal,
  isGuest = false,
  currentIsLoggedIn = true,
  darkMode = true,
  language = "id",
  setActiveModeTag,
  textareaRef
}, ref) {
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef(null);

  const t = translations[language]?.chatInput || translations.id.chatInput;
  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;

  const storageStats = useStorageStore((state) => state.storageStats);
  const fetchStorageStats = useStorageStore((state) => state.fetchStorageStats);

  // Auto focus search when menu opens
  useEffect(() => {
    if (isOpen) {
      setSearchQuery("");
      if (!isGuest && currentIsLoggedIn) {
        fetchStorageStats();
      }
      const timer = setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen, fetchStorageStats, isGuest, currentIsLoggedIn]);

  const menuItems = useMemo(() => {
    const items = [
      // ── UPLOAD & FILE ACTIONS ──
      {
        id: "upload_file",
        title: language === "en" ? "Add photos & files" : "Unggah foto & berkas",
        desc: language === "en" ? "Upload from computer" : "Unggah dari komputer",
        icon: Paperclip,
        color: "#9ca3af",
        action: () => {
          onClose();
          fileInputRef.current?.click();
        }
      },
    ];

    if (!isGuest && currentIsLoggedIn) {
      items.push({
        id: "upload_cloud",
        title: language === "en" ? "Add from library" : "Ambil dari PinCloud",
        desc: language === "en" ? "Browse and search your files" : "Jelajahi berkas PinCloud internal",
        icon: Cloud,
        color: "#9ca3af",
        action: () => {
          onClose();
          openNextcloudModal();
        }
      });
    }

    // ── PRESET / AI MODES (Horizontal Memanjang) ──
    const presets = [
      {
        id: "websearch",
        title: tHints.websearch || "Web search",
        desc: language === "en" ? "Find real-time news and info" : "Cari berita dan info realtime",
        icon: Globe,
        color: "#06b6d4",
      },
      ...(!isGuest ? [{
        id: "documents",
        title: tHints.documents || "Document search",
        desc: language === "en" ? "Search internal regulations and archives" : "Telusuri arsip dan regulasi internal",
        icon: FileText,
        color: "#10b981",
      }] : []),
      {
        id: "code",
        title: tHints.code || "Code",
        desc: language === "en" ? "Write scripts, functions and debug" : "Tulis skrip koding & perbaiki error",
        icon: Code2,
        color: "#8b5cf6",
      },
      {
        id: "create_file",
        title: tHints.createFile || "Create file",
        desc: language === "en" ? "Generate Excel, Word, Python, Markdown" : "Buat berkas Excel, Word, Markdown",
        icon: FilePlus,
        color: "#f59e0b",
      },
      {
        id: "diagram",
        title: tHints.diagram || "Diagram & Flow",
        desc: language === "en" ? "Visualize workflows and architectures" : "Visualisasi diagram alur Mermaid",
        icon: Workflow,
        color: "#ec4899",
      },
      {
        id: "chart",
        title: tHints.chart || "Chart & Data",
        desc: language === "en" ? "Interactive data visualization" : "Visualisasi grafik batang & tabel data",
        icon: BarChart3,
        color: "#3b82f6",
      },
      ...(!isGuest ? [
        {
          id: "smart_mail",
          title: tHints.smartMail || "Draft Letter",
          desc: language === "en" ? "Official memos, formal emails & letters" : "Nota dinas, memo resmi & email",
          icon: Mail,
          color: "#6366f1",
        },
        {
          id: "focus",
          title: tHints.focus || "Focus & Audit",
          desc: language === "en" ? "Deep document interrogation & audit" : "Interogasi & audit kepatuhan dokumen",
          icon: Target,
          color: "#ef4444",
        }
      ] : [])
    ];

    presets.forEach(p => {
      items.push({
        ...p,
        action: () => {
          onClose();
          setActiveModeTag(p.id);
          setTimeout(() => {
            textareaRef?.current?.focus();
          }, 50);
        }
      });
    });

    return items;
  }, [language, isGuest, currentIsLoggedIn, tHints, onClose, fileInputRef, openNextcloudModal, setActiveModeTag, textareaRef]);

  // Filter items based on search query
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return menuItems;
    const q = searchQuery.toLowerCase();
    return menuItems.filter(item =>
      item.title.toLowerCase().includes(q) ||
      item.desc.toLowerCase().includes(q)
    );
  }, [menuItems, searchQuery]);

  if (!isOpen) return null;

  return (
    <div
      ref={ref}
      style={{
        position: "absolute",
        bottom: "calc(100% + 14px)",
        left: 0,
        right: 0,
        width: "100%",
        boxSizing: "border-box",
        background: darkMode ? "#1e1e20" : "#ffffff",
        border: darkMode ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(0, 0, 0, 0.1)",
        borderRadius: "22px",
        boxShadow: darkMode
          ? "0 20px 50px -10px rgba(0,0,0,0.7), 0 0 1px 1px rgba(255,255,255,0.08)"
          : "0 20px 40px -10px rgba(0,0,0,0.18), 0 0 1px rgba(0,0,0,0.12)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        zIndex: 60,
        animation: "fadeInUp 0.16s cubic-bezier(0.16, 1, 0.3, 1)",
        maxHeight: "min(350px, calc(100vh - 160px))"
      }}
    >
      {/* ── LIST MENU ITEMS (MEMANJANG SATU BARIS, SEUKURAN INPUT, SCROLLABLE ELEGAN) ── */}
      <div
        className="custom-scrollbar"
        style={{
          padding: "8px 6px 8px 8px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
          maxHeight: "265px",
          overflowY: "auto",
          overscrollBehavior: "contain",
          flex: 1,
          minHeight: 0
        }}
      >
        {/* 🚨 MINI STORAGE METER PILL (Aktif jika terpakai >= 80%) */}
        {storageStats && storageStats.used_percentage >= 80 && (
          <div
            onClick={() => {
              onClose();
              useStorageStore.getState().openSettingsModal('storage');
            }}
            style={{
              margin: "4px 8px 8px 8px",
              padding: "7px 12px",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              background: storageStats.used_percentage >= 90 ? "rgba(239, 68, 68, 0.12)" : "rgba(245, 158, 11, 0.12)",
              border: `1px solid ${storageStats.used_percentage >= 90 ? "rgba(239, 68, 68, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
              color: storageStats.used_percentage >= 90 ? "#f87171" : "#fbbf24",
              fontSize: "11px",
              fontWeight: 600,
              transition: "opacity 0.15s ease"
            }}
            title={language === "en" ? "Click to manage storage in Settings" : "Klik untuk kelola penyimpanan di Pengaturan"}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <HardDrive size={13} />
              <span>
                {language === "en" ? "Storage: " : "Penyimpanan: "}
                {formatBytes(storageStats.used_bytes)} / {formatBytes(storageStats.quota_bytes)} ({storageStats.used_percentage}%)
              </span>
            </div>
            <span style={{ textDecoration: "underline", fontSize: "10px", fontWeight: "bold" }}>
              {language === "en" ? "Manage" : "Kelola"}
            </span>
          </div>
        )}

        {filteredItems.map((item) => {
          const IconComponent = item.icon;

          return (
            <button
              key={item.id}
              type="button"
              onClick={item.action}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                padding: "8px 14px",
                borderRadius: "12px",
                border: "none",
                background: "transparent",
                color: darkMode ? "#ffffff" : "#111827",
                textAlign: "left",
                cursor: "pointer",
                transition: "background 0.15s ease",
                width: "100%",
                minHeight: "36px"
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = darkMode ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.05)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {/* Icon */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: item.color,
                  flexShrink: 0,
                  width: "22px"
                }}
              >
                <IconComponent size={18} />
              </div>

              {/* Title & Desc berdampingan memanjang satu baris persis seperti di gambar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  minWidth: 0,
                  flex: 1,
                  whiteSpace: "nowrap",
                  overflow: "hidden"
                }}
              >
                <span
                  style={{
                    fontSize: "13.5px",
                    fontWeight: "600",
                    color: darkMode ? "#ececf1" : "#111827",
                    flexShrink: 0
                  }}
                >
                  {item.title}
                </span>
                <span
                  style={{
                    fontSize: "12.5px",
                    color: darkMode ? "#9ca3af" : "#6b7280",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap"
                  }}
                >
                  {item.desc}
                </span>
              </div>
            </button>
          );
        })}

        {filteredItems.length === 0 && (
          <div
            style={{
              padding: "16px",
              textAlign: "center",
              fontSize: "13px",
              color: darkMode ? "#9ca3af" : "#6b7280"
            }}
          >
            {language === "en" ? "No matching plugins or skills" : "Tidak ada opsi atau preset yang cocok"}
          </div>
        )}
      </div>

      {/* ── BOTTOM SEARCH BAR ── */}
      <div
        style={{
          borderTop: darkMode ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(0, 0, 0, 0.06)",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          background: darkMode ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.02)",
          flexShrink: 0
        }}
      >
        <Search size={15} color={darkMode ? "#6b7280" : "#9ca3af"} style={{ flexShrink: 0 }} />
        <input
          ref={searchInputRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={language === "en" ? "Type to search plugins, files, folders & skills" : "Ketik untuk mencari fitur, berkas, atau preset..."}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: darkMode ? "#ffffff" : "#111827",
            fontSize: "13px",
            lineHeight: "1.4"
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && filteredItems.length > 0) {
              e.preventDefault();
              filteredItems[0].action();
            } else if (e.key === "Escape") {
              onClose();
            }
          }}
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            style={{
              background: "transparent",
              border: "none",
              color: darkMode ? "#9ca3af" : "#6b7280",
              cursor: "pointer",
              padding: "2px",
              display: "flex",
              alignItems: "center"
            }}
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  );
});

export default PlusActionMenu;
