import React from "react";

export default function IsolatedDocBanner({
  activeIsolatedTitle,
  setContextIsolation,
  darkMode
}) {
  if (!activeIsolatedTitle) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: darkMode
          ? "rgba(99, 102, 241, 0.15)"
          : "rgba(37, 99, 235, 0.08)",
        border: `1px solid ${darkMode ? "#6366f1" : "#2563eb"}`,
        borderRadius: "12px",
        padding: "8px 16px",
        marginBottom: "10px",
        fontSize: "13px",
        fontWeight: 500,
        color: darkMode ? "#a5b4fc" : "#1e3a8a",
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
          Mode Fokus: Menanyai isi <strong>{activeIsolatedTitle}</strong>
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
