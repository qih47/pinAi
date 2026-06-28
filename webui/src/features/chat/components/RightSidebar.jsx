import React from "react";
import CakraResponseRenderer from "./CakraResponseRenderer";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getUploadUrl } from "../../../stores/chatStore";
import useToast from "../../../hooks/useToast";

// ── VEKTOR SVG PREMIUM & MINIMALIS ─────────────────────────────────────────
const IconChevronLeft = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
);

const IconClose = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
);

const IconCopy = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
);

const IconDownload = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
);

const IconLightning = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
);

const IconFolder = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
);

const IconFileText = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4M10 9H8M16 13H8M16 17H8"/></svg>
);

const getArtifactFileIcon = (ext, defaultColor) => {
  const colors = {
    jsx: '#00d8ff', tsx: '#2f74c0', js: '#f7e018', ts: '#2f74c0',
    py: '#366f9b', md: '#f97316', css: '#2062af', html: '#e34c26',
    json: '#10b981', sh: '#4caf50', sql: '#f43f5e'
  };
  const strokeColor = colors[ext?.toLowerCase()] || defaultColor || '#94a3b8';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={strokeColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4M8 12h8M8 16h6"/>
    </svg>
  );
};

export default function RightSidebar({
  isMobile,
  theme,
  darkMode,
  previewDoc,
  setPreviewDoc,
  docContent,
  isDocLoading,
  previewArtifact,
  setPreviewArtifact,
  artifactContent,
  isArtifactLoading,
  rightSidebarWidth,
  showRightSidebar,
  isResizingRightSidebar,
  startResizingRightSidebar,
  artifacts,
  sessionAttachments,
  handleOpenArtifact,
  setPreviewImage,
  setShowRightSidebar,
}) {
  const toast = useToast();
  const isPreviewMode = !!(previewDoc || previewArtifact);

  const baseBgColor = darkMode ? "#1e1f22" : "#ffffff";
  const containerBgColor = darkMode ? "#161719" : "#f8fafc";
  const borderStyleColor = darkMode ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.08)";

  // Helper fungsi download blob agar kode di bawah lebih rapi
  const executeDownload = (filename, codeString) => {
    const blob = new Blob([codeString || ''], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <aside
      style={{
        position: "absolute",
        right: 0,
        top: isPreviewMode ? 0 : "56px",
        bottom: 0,
        width: isMobile ? "100%" : (isPreviewMode ? `${rightSidebarWidth}px` : "325px"),
        maxWidth: "100vw",
        background: baseBgColor,
        borderLeft: `1px solid ${borderStyleColor}`,
        borderTopLeftRadius: (isPreviewMode || isMobile) ? "0" : "20px",
        transform: showRightSidebar ? "translateX(0)" : "translateX(100%)",
        transition: isResizingRightSidebar.current ? "none" : "transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), width 0.4s cubic-bezier(0.16, 1, 0.3, 1), border-radius 0.2s",
        zIndex: isPreviewMode ? 40 : 35,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        boxShadow: showRightSidebar ? (darkMode ? "-8px 0 40px rgba(0,0,0,0.4)" : "-8px 0 40px rgba(0,0,0,0.04)") : "none",
      }}
    >
      <style>{`
        @keyframes custom-pulse { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }
        @keyframes rotate-spin { 100% { transform: rotate(360deg); } }
        .premium-scroll::-webkit-scrollbar { width: 5px; height: 5px; }
        .premium-scroll::-webkit-scrollbar-track { background: transparent; }
        .premium-scroll::-webkit-scrollbar-thumb { background: ${darkMode ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)"}; border-radius: 10px; }
        .premium-scroll::-webkit-scrollbar-thumb:hover { background: ${darkMode ? "rgba(255,255,255,0.25)" : "rgba(0,0,0,0.25)"}; }
        .download-btn-hover { transition: all 0.2s ease; }
        .download-btn-hover:hover { background: ${darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'} !important; color: #6366f1 !important; }
      `}</style>

      {isPreviewMode && !isMobile && (
        <div
          onMouseDown={startResizingRightSidebar}
          style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '4px', cursor: 'col-resize', zIndex: 50, transition: 'background 0.2s' }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#6366f1'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        />
      )}

      {/* ── MODE 1: DOCUMENT PREVIEW ── */}
      {previewDoc ? (
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
            
            <div style={{ display: "flex", gap: "6px" }}>
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
                >
                  <IconCopy size={16} />
                </button>
              )}
              <button
                onClick={() => { setShowRightSidebar(false); setTimeout(() => setPreviewDoc(null), 300); }}
                style={{ background: "transparent", border: "none", color: "#64748b", padding: "8px", borderRadius: "8px", cursor: "pointer", display: "flex", transition: "all 0.2s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(239,68,68,0.1)"; e.currentTarget.style.color = "#ef4444"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#64748b"; }}
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
      ) : previewArtifact ? (
        // ── MODE 2: ARTIFACT CODE VIEW ──
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${borderStyleColor}`, background: containerBgColor, gap: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", overflow: "hidden", flex: 1 }}>
              <button
                onClick={() => setPreviewArtifact(null)}
                style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#fff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", flexShrink: 0 }}
              >
                <IconChevronLeft />
              </button>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                {getArtifactFileIcon(previewArtifact.filename?.split('.').pop(), theme.iconColor)}
                <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <span style={{ fontSize: "13px", fontWeight: 600, color: theme.textColor, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {previewArtifact.filename}
                  </span>
                  <span style={{ fontSize: "10px", color: "#64748b", fontWeight: 500, letterSpacing: "0.3px" }}>
                    {previewArtifact.language?.toUpperCase()} • ARTIFACT
                  </span>
                </div>
              </div>
            </div>
            
            <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
              <button
                onClick={() => {
                  const code = artifactContent || previewArtifact.code || '';
                  navigator.clipboard.writeText(code).then(() => toast.success("Kode disalin!"));
                }}
                style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#ffffff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "12px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}
              >
                <IconCopy size={13} /> Copy
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflow: "auto", background: darkMode ? '#1a1b1d' : '#ffffff' }} className="premium-scroll">
            {isArtifactLoading ? (
              <div style={{ padding: "60px 24px", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", color: "#64748b" }}>
                <div style={{ width: "24px", height: "24px", border: "2px solid rgba(99,102,241,0.1)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "rotate-spin 0.6s linear infinite" }} />
                <span style={{ fontSize: "12px" }}>Menyusun arsitektur kode...</span>
              </div>
            ) : (
              (() => {
                const ext = previewArtifact?.filename?.split('.').pop()?.toLowerCase();
                const isMarkdownOrText = ext === 'md' || ext === 'txt';
                const content = artifactContent || previewArtifact.code || '// Void Content';

                if (isMarkdownOrText) {
                  return (
                    <div style={{ padding: "24px", color: theme.textColor }}>
                      <CakraResponseRenderer rawContent={content} thinkingContent="" isStreaming={false} darkMode={darkMode} theme={theme} searchQuery="" statusMessage="" />
                    </div>
                  );
                }

                return (
                  <div style={{ padding: "20px" }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'between', marginBottom: '14px', background: darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)', padding: '6px 12px', borderRadius: '6px' }}>
                      <div style={{ display: 'flex', gap: '5px' }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ef4444' }} />
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f59e0b' }} />
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
                      </div>
                      <span style={{ marginLeft: 'auto', fontSize: '10px', color: '#64748b', fontFamily: 'monospace' }}>{previewArtifact.filename}</span>
                    </div>
                    <SyntaxHighlighter
                      language={ext} style={vscDarkPlus}
                      customStyle={{ margin: 0, padding: 0, background: 'transparent', fontSize: '12px', fontFamily: '"Fira Code", "JetBrains Mono", monospace', lineHeight: '1.6' }}
                      showLineNumbers={true} wrapLines={false}
                    >
                      {content}
                    </SyntaxHighlighter>
                  </div>
                );
              })()
            )}
          </div>

          <div style={{ padding: "8px 20px", borderTop: `1px solid ${borderStyleColor}`, background: darkMode ? '#151618' : '#f8fafc', fontSize: "11px", color: "#64748b", fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between' }}>
            <span>LINES: {previewArtifact.lines_count ? previewArtifact.lines_count : (artifactContent || previewArtifact.code || '').split('\n').length}</span>
            <span>CHARS: {(artifactContent || previewArtifact.code || '').length}</span>
          </div>
        </div>
      ) : (
        // ── MODE 3: WORKSPACE FILE HUB (DETEKSI LIST MAP DISINI) ──
        <>
          <div style={{ padding: "18px 20px", borderBottom: `1px solid ${borderStyleColor}` }}>
            <h3 style={{ margin: 0, color: theme.textColor, fontSize: "14px", fontWeight: 600, letterSpacing: '0.5px', textTransform: "uppercase", opacity: 0.9 }}>Workspace Explorer</h3>
          </div>

          <div className="premium-scroll" style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "24px" }}>
            
            {/* ARTIFACTS LIST SECTION */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, color: darkMode ? "#94a3b8" : "#475569" }}>
                  <span style={{ color: "#eab308", display: "flex" }}><IconLightning /></span>
                  <span>GENERATED ARTIFACTS</span>
                </div>
                {artifacts.length > 0 && (
                  <span style={{ fontSize: "10px", fontWeight: 600, color: "#6366f1", background: "rgba(99,102,241,0.1)", borderRadius: "6px", padding: "1px 6px" }}>
                    {artifacts.length}
                  </span>
                )}
              </div>

              {artifacts.length === 0 ? (
                <div style={{ padding: "24px 16px", textAlign: "center", color: "#64748b", fontSize: "12px", background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)", borderRadius: "10px", border: `1px dashed ${borderStyleColor}` }}>
                  Tidak ada sistem eksekusi kode terdeteksi.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {artifacts.map((art, artIdx) => {
                    const ext = art.filename?.split('.').pop()?.toLowerCase();
                    return (
                      <div
                        key={art.filename + artIdx}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 12px",
                          background: darkMode ? "rgba(255,255,255,0.02)" : "#f8fafc",
                          borderRadius: "8px",
                          border: `1px solid ${borderStyleColor}`,
                          transition: "all 0.2s ease"
                        }}
                      >
                        {/* Area Klik Kiri Utama untuk Buka Preview File */}
                        <div 
                          onClick={() => handleOpenArtifact(art.filename, art.code || '', art.file_path || null)}
                          style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: 0, cursor: "pointer" }}
                          onMouseEnter={(e) => {
                            e.currentTarget.parentElement.style.borderColor = '#6366f1';
                            e.currentTarget.parentElement.style.background = darkMode ? 'rgba(99,102,241,0.04)' : 'rgba(79,70,229,0.03)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.parentElement.style.borderColor = borderStyleColor;
                            e.currentTarget.parentElement.style.background = darkMode ? "rgba(255,255,255,0.02)" : "#f8fafc";
                          }}
                        >
                          <span style={{ display: "flex", flexShrink: 0 }}>{getArtifactFileIcon(ext, theme.iconColor)}</span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: "12.5px", fontWeight: 500, color: theme.textColor, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              {art.filename}
                            </div>
                            <div style={{ fontSize: "10px", color: "#64748b", marginTop: "1px" }}>
                              {art.lines_count ? art.lines_count : (art.code || '').split('\n').length} baris kode
                            </div>
                          </div>
                        </div>

                        {/* TOMBOL DOWNLOAD PINDAH KE SINI (SISI KANAN KARTU BARIS ARTIFACT) */}
                        <button
                          className="download-btn-hover"
                          onClick={(e) => {
                            e.stopPropagation(); // Mencegah terbukanya pratinjau file saat mendownload
                            executeDownload(art.filename, art.code);
                          }}
                          title={`Unduh ${art.filename}`}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "#64748b",
                            padding: "6px",
                            borderRadius: "6px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            marginLeft: "8px",
                            flexShrink: 0
                          }}
                        >
                          <IconDownload size={14} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* UPLOADED ATTACHMENTS SECTION */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, color: darkMode ? "#94a3b8" : "#475569", marginBottom: "12px" }}>
                <span style={{ color: "#3b82f6", display: "flex" }}><IconFolder /></span>
                <span>UPLOADED ATTACHMENTS</span>
              </div>

              {sessionAttachments.length === 0 ? (
                <div style={{ padding: "24px 16px", textAlign: "center", color: "#64748b", fontSize: "12px", background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)", borderRadius: "10px", border: `1px dashed ${borderStyleColor}` }}>
                  Belum ada aset data eksternal.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  {sessionAttachments.map((att, idx) => {
                    const fullUrl = getUploadUrl(att.file_path);
                    const isImg = /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(att.file_name);
                    const isPdf = /\.pdf$/i.test(att.file_name);

                    return (
                      <div
                        key={idx}
                        onClick={() => {
                          if (isImg) setPreviewImage(fullUrl);
                          else setPreviewDoc({ url: fullUrl, name: att.file_name, type: isPdf ? 'pdf' : 'text', path: att.file_path, size: att.file_size || att.size || 0 });
                        }}
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          background: darkMode ? "rgba(255,255,255,0.02)" : "#ffffff",
                          borderRadius: "10px",
                          border: `1px solid ${borderStyleColor}`,
                          overflow: "hidden",
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                          boxShadow: "0 2px 4px rgba(0,0,0,0.02)"
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = "#6366f1";
                          e.currentTarget.style.transform = "translateY(-2px)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = borderStyleColor;
                          e.currentTarget.style.transform = "none";
                        }}
                      >
                        <div style={{ aspectRatio: "16/11", width: "100%", background: darkMode ? "rgba(0,0,0,0.2)" : "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                          {isImg ? (
                            <img src={fullUrl} alt={att.file_name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                          ) : (
                            <div style={{ color: darkMode ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.25)" }}>
                              <IconFileText />
                            </div>
                          )}
                        </div>
                        <div style={{ padding: "6px 8px", background: darkMode ? "rgba(0,0,0,0.1)" : "#fafafa", borderTop: `1px solid ${borderStyleColor}` }}>
                          <div style={{ fontSize: "11px", color: theme.textColor, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            {att.file_name}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}