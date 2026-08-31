import React from "react";

export default function IsolatedDocBanner({
  activeIsolatedTitle,
  setContextIsolation,
  darkMode,
  chatMode
}) {
  if (!activeIsolatedTitle) return null;

  // Tentukan styling dan label spesifik berdasarkan chatMode yang aktif
  const isCompliance = chatMode === 'compliance';
  const isRedTeam = chatMode === 'redteam';

  const config = isCompliance
    ? {
        icon: "⚖️",
        modeName: "Uji Kepatuhan Regulasi",
        actionDesc: "Uji skenario tindakan terhadap",
        bg: darkMode ? "rgba(239, 68, 68, 0.16)" : "rgba(254, 226, 226, 0.7)",
        border: darkMode ? "rgba(239, 68, 68, 0.45)" : "rgba(239, 68, 68, 0.35)",
        badgeBg: darkMode ? "rgba(239, 68, 68, 0.3)" : "rgba(239, 68, 68, 0.15)",
        badgeColor: darkMode ? "#fca5a5" : "#b91c1c",
        textColor: darkMode ? "#fecaca" : "#991b1b",
        glow: darkMode ? "0 0 15px rgba(239, 68, 68, 0.15)" : "0 2px 8px rgba(239, 68, 68, 0.08)"
      }
    : isRedTeam
    ? {
        icon: "🕵️",
        modeName: "Bedah Celah Hukum (Red-Team)",
        actionDesc: "Membedah ambiguitas & risiko pada",
        bg: darkMode ? "rgba(249, 115, 22, 0.16)" : "rgba(255, 237, 213, 0.7)",
        border: darkMode ? "rgba(249, 115, 22, 0.45)" : "rgba(249, 115, 22, 0.35)",
        badgeBg: darkMode ? "rgba(249, 115, 22, 0.3)" : "rgba(249, 115, 22, 0.15)",
        badgeColor: darkMode ? "#fdba74" : "#c2410c",
        textColor: darkMode ? "#fed7aa" : "#9a3412",
        glow: darkMode ? "0 0 15px rgba(249, 115, 22, 0.15)" : "0 2px 8px rgba(249, 115, 22, 0.08)"
      }
    : {
        icon: "🎯",
        modeName: "Mode Fokus Dokumen",
        actionDesc: "Menanyai isi",
        bg: darkMode ? "rgba(99, 102, 241, 0.16)" : "rgba(238, 242, 255, 0.8)",
        border: darkMode ? "rgba(99, 102, 241, 0.45)" : "rgba(99, 102, 241, 0.35)",
        badgeBg: darkMode ? "rgba(99, 102, 241, 0.3)" : "rgba(99, 102, 241, 0.12)",
        badgeColor: darkMode ? "#c7d2fe" : "#3730a3",
        textColor: darkMode ? "#e0e7ff" : "#1e3a8a",
        glow: darkMode ? "0 0 15px rgba(99, 102, 241, 0.15)" : "0 2px 8px rgba(99, 102, 241, 0.08)"
      };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: config.bg,
        border: `1px solid ${config.border}`,
        boxShadow: config.glow,
        backdropFilter: "blur(12px)",
        borderRadius: "14px",
        padding: "8px 14px",
        marginBottom: "10px",
        fontSize: "13px",
        color: config.textColor,
        transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          minWidth: 0,
          flex: 1,
        }}
      >
        <span style={{ fontSize: "16px", flexShrink: 0 }}>{config.icon}</span>

        {/* Badge Tipe Mode */}
        <span
          style={{
            background: config.badgeBg,
            color: config.badgeColor,
            padding: "2px 8px",
            borderRadius: "6px",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "0.3px",
            textTransform: "uppercase",
            flexShrink: 0,
          }}
        >
          {config.modeName}
        </span>

        {/* Keterangan Aksi & Judul Dokumen */}
        <span
          style={{
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            fontSize: "12.5px",
            fontWeight: 400,
          }}
        >
          {config.actionDesc} <strong style={{ fontWeight: 600 }}>{activeIsolatedTitle}</strong>
        </span>
      </div>

      {/* Tombol Close / Lepas Isolasi */}
      <button
        type="button"
        title="Tutup & kembali ke chat global"
        onClick={() => setContextIsolation(null, null, 'auto')}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "24px",
          height: "24px",
          borderRadius: "50%",
          background: darkMode ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)",
          border: "none",
          color: darkMode ? "#9ca3af" : "#4b5563",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "bold",
          marginLeft: "10px",
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
