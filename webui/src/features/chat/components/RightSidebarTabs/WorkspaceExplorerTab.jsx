import React from "react";
import { IconLightning, IconDownload, IconFolder, IconFileText, getArtifactFileIcon } from "./RightSidebarIcons";
import { getUploadUrl } from "../../../../stores/chatStore";

export default function WorkspaceExplorerTab({
  theme,
  darkMode,
  artifacts,
  sessionAttachments,
  handleOpenArtifact,
  handleDownloadArtifact,
  handleDownloadAllArtifacts,
  setPreviewImage,
  setPreviewDoc,
  borderStyleColor,
  t
}) {
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
    <>
      <div style={{ padding: "18px 20px" }}>
        <h3 style={{ margin: 0, color: theme.textColor, fontSize: "14px", fontWeight: 600, letterSpacing: '0.5px', textTransform: "uppercase", opacity: 0.9 }}>{t.workspace}</h3>
      </div>

      <div className="premium-scroll" style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "24px" }}>
        
        {/* ARTIFACTS LIST SECTION */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, color: darkMode ? "#94a3b8" : "#475569" }}>
              <span style={{ color: "#eab308", display: "flex" }}><IconLightning /></span>
              <span>{t.artifacts}</span>
            </div>
            {artifacts.length > 0 && (
              <button
                className="download-btn-hover"
                onClick={() => {
                  if (handleDownloadAllArtifacts) {
                    handleDownloadAllArtifacts(artifacts);
                  }
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: darkMode ? "#94a3b8" : "#475569",
                  fontSize: "12px",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  cursor: "pointer",
                  padding: "4px 8px",
                  borderRadius: "6px"
                }}
              >
                <IconDownload size={14} /> {t.downloadAll}
              </button>
            )}
          </div>

          {artifacts.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "#64748b", fontSize: "12px", background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)", borderRadius: "10px", border: `1px dashed ${borderStyleColor}` }}>
              {t.noArtifacts}
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
                          {art.lines_count ? art.lines_count : (art.code || '').split('\n').length} {t.lines}
                        </div>
                      </div>
                    </div>

                    {/* TOMBOL DOWNLOAD PINDAH KE SINI (SISI KANAN KARTU BARIS ARTIFACT) */}
                    <button
                      className="download-btn-hover"
                      onClick={(e) => {
                        e.stopPropagation(); // Mencegah terbukanya pratinjau file saat mendownload
                        if (handleDownloadArtifact) {
                            handleDownloadArtifact(art.filename, art.file_path, art.code);
                        } else {
                            executeDownload(art.filename, art.code);
                        }
                      }}
                      title={`${t.download} ${art.filename}`}
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
            <span>{t.attachments}</span>
          </div>

          {sessionAttachments.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "#64748b", fontSize: "12px", background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)", borderRadius: "10px", border: `1px dashed ${borderStyleColor}` }}>
              {t.noAttachments}
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
  );
}
