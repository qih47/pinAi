import React from "react";
import { IconChevronLeft, IconCopy, IconClose } from "./RightSidebarIcons";

export default function DocumentPreviewTab({
  previewDoc,
  setPreviewDoc,
  docContent,
  isDocLoading,
  theme,
  darkMode,
  setShowRightSidebar,
  toast,
  borderStyleColor,
  baseBgColor,
  containerBgColor
}) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${borderStyleColor}`, background: darkMode ? "rgba(255,255,255,0.02)" : "#fafafa" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", overflow: "hidden" }}>
          <button
            onClick={() => setPreviewDoc(null)}
            style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#fff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", alignItems: "center" }}
          >
            <IconChevronLeft />
          </button>
          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <span style={{ fontSize: "13px", fontWeight: 600, color: darkMode ? "#f8fafc" : "#0f172a", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {previewDoc.name}
            </span>
            <span style={{ fontSize: "11px", color: "#64748b" }}>
              {previewDoc.size ? `${parseFloat((previewDoc.size / 1024).toFixed(2))} KB • ` : ''}
              {docContent ? `${docContent.split('\n').length} baris` : 'Memuat...'}
            </span>
          </div>
        </div>
        
        <div style={{ display: "flex", gap: "6px", alignItems: 'center' }}>
          {docContent && (
            <button
              onClick={async () => {
                try {
                  if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(docContent);
                  } else {
                    const textArea = document.createElement("textarea");
                    textArea.value = docContent; document.body.appendChild(textArea);
                    textArea.focus(); textArea.select(); document.execCommand('copy');
                    document.body.removeChild(textArea);
                  }
                  toast.success("Konten berhasil disalin!");
                } catch (err) { toast.error("Gagal menyalin teks"); }
              }}
              style={{ background: "transparent", border: "none", color: "#64748b", padding: "8px", borderRadius: "8px", cursor: "pointer", display: "flex", transition: "all 0.2s" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"; e.currentTarget.style.color = theme.textColor; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#64748b"; }}
              title="Copy Konten"
            >
              <IconCopy size={16} />
            </button>
          )}
          
          <button
            onClick={() => {
              if (setShowRightSidebar) setShowRightSidebar(false);
              setTimeout(() => setPreviewDoc(null), 300);
            }}
            style={{ background: darkMode ? "rgba(239,68,68,0.1)" : "rgba(239,68,68,0.05)", border: `1px solid ${darkMode ? "rgba(239,68,68,0.2)" : "rgba(239,68,68,0.15)"}`, color: "#ef4444", padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", flexShrink: 0, marginLeft: "4px" }}
            title="Tutup Panel"
          >
            <IconClose />
          </button>
        </div>
      </div>

      <div style={{ flex: 1, padding: "16px", background: baseBgColor }}>
        <div className="premium-scroll" style={{ height: "100%", overflow: "auto", background: containerBgColor, borderRadius: "12px", border: `1px solid ${borderStyleColor}`, padding: "20px" }}>
          {isDocLoading ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: "10px", color: "#64748b" }}>
              <div style={{ width: "20px", height: "20px", border: "2px solid rgba(99,102,241,0.2)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "rotate-spin 0.8s linear infinite" }} />
              <span style={{ fontSize: "12px", animation: "custom-pulse 1.5s infinite" }}>Membaca file dokumen...</span>
            </div>
          ) : (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: darkMode ? "#a6adba" : "#334155", fontFamily: '"JetBrains Mono", monospace', fontSize: "12.5px", lineHeight: "1.6" }}>
              {docContent}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
