import React from "react";

export default function IsolatedDocBanner({
  activeIsolatedTitle,
  setContextIsolation,
  darkMode,
  chatMode
}) {
  if (!activeIsolatedTitle) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: chatMode === 'compliance' 
          ? (darkMode ? "rgba(239, 68, 68, 0.2)" : "rgba(239, 68, 68, 0.1)") 
          : chatMode === 'redteam'
            ? (darkMode ? "rgba(249, 115, 22, 0.2)" : "rgba(249, 115, 22, 0.1)")
            : (darkMode ? "rgba(99, 102, 241, 0.15)" : "rgba(37, 99, 235, 0.08)"),
        border: `1px solid ${
          chatMode === 'compliance'
            ? (darkMode ? "#ef4444" : "#dc2626")
            : chatMode === 'redteam'
              ? (darkMode ? "#f97316" : "#ea580c")
              : (darkMode ? "#6366f1" : "#2563eb")
        }`,
        borderRadius: "12px",
        padding: "8px 16px",
        marginBottom: "10px",
        fontSize: "13px",
        fontWeight: 500,
        color: chatMode === 'compliance'
          ? (darkMode ? "#fca5a5" : "#991b1b")
          : chatMode === 'redteam'
            ? (darkMode ? "#fdba74" : "#9a3412")
            : (darkMode ? "#a5b4fc" : "#1e3a8a"),
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          minWidth: 0,
        }}
      >
        <span>🔒</span>
        <span
          style={{
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {chatMode === 'compliance' 
            ? 'Mode Uji Kepatuhan: Uji Skenario pada ' 
            : chatMode === 'redteam'
              ? 'Mode Red-Team: Membedah celah hukum pada '
              : 'Mode Fokus: Menanyai isi '} 
          <strong>{activeIsolatedTitle}</strong>
        </span>
      </div>
      <button
        type="button"
        onClick={() => setContextIsolation(null, null)}
        style={{
          background: "transparent",
          border: "none",
          color: darkMode ? "#9ca3af" : "#4b5563",
          cursor: "pointer",
          fontWeight: "bold",
        }}
      >
        ✕
      </button>
    </div>
  );
}
