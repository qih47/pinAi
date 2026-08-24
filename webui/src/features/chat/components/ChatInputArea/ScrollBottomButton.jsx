import React from "react";

export default function ScrollBottomButton({
  isBottom,
  showScrollBottom,
  showWelcome,
  messages,
  messagesContainerRef,
  darkMode
}) {
  if (!(isBottom && showScrollBottom && !showWelcome && messages.length > 0)) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        top: "-46px",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        zIndex: 40,
        animation: "fadeSlideIn 0.25s ease-out forwards",
      }}
    >
      <button
        onClick={() => {
          if (messagesContainerRef.current) {
            messagesContainerRef.current.scrollTo({
              top: 9999999,
              behavior: "smooth",
            });
          }
        }}
        style={{
          pointerEvents: "auto",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "6px",
          padding: "8px 14px",
          borderRadius: "20px",
          fontSize: "13px",
          fontWeight: "500",
          border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}`,
          background: darkMode ? "#202123" : "#ffffff",
          color: darkMode ? "#f3f4f6" : "#1f2937",
          boxShadow: darkMode
            ? "0 4px 12px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.2)"
            : "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
          cursor: "pointer",
          transition: "all 0.2s ease-in-out",
          outline: "none",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = darkMode ? "#2d2d30" : "#f9fafb";
          e.currentTarget.style.transform = "translateY(-2px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = darkMode ? "#202123" : "#ffffff";
          e.currentTarget.style.transform = "translateY(0)";
        }}
        title="Lihat pesan baru di bawah"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <polyline points="19 12 12 19 5 12"></polyline>
        </svg>
      </button>
    </div>
  );
}
