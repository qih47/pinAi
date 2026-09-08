import React from "react";

export default function AttachmentPreview({
  selectedFiles,
  removeFilePreview,
  darkMode,
  theme
}) {
  if (!selectedFiles || selectedFiles.length === 0) return null;

  const secondaryTextColor = theme?.secondaryText || (darkMode ? "#9ca3af" : "#6b7280");
  const textColor = theme?.text || (darkMode ? "#ffffff" : "#111827");

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "10px",
        marginBottom: "12px",
        padding: "4px 6px",
        width: "100%",
      }}
    >
      {selectedFiles.map((file, idx) => {
        const fileName = (file?.name || "file").toLowerCase();
        const fileType = file?.type || "";
        const isImage = fileType.startsWith("image/");
        const extSplit = fileName.split(".");
        const ext = extSplit.length > 1 ? extSplit.pop().toUpperCase() : "FILE";

        let imageSrc = null;
        if (isImage) {
          if (file.preview) {
            imageSrc = file.preview;
          } else if (file instanceof Blob) {
            imageSrc = URL.createObjectURL(file);
          } else if (file.file_obj instanceof Blob) {
            imageSrc = URL.createObjectURL(file.file_obj);
          }
        }

        const fileSizeText = file._lines !== undefined
          ? `${file._lines} lines`
          : (file?.size
            ? (file.size > 1024 * 1024
              ? (file.size / (1024 * 1024)).toFixed(1) + " MB"
              : (file.size / 1024).toFixed(1) + " KB")
            : "");

        return (
          <div
            key={idx}
            style={{
              position: "relative",
              width: "120px",
              height: "120px",
              borderRadius: "12px",
              overflow: "hidden",
              background: darkMode ? "#2a2b2d" : "#f3f4f6",
              border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            }}
          >
            {isImage && imageSrc ? (
              <img
                src={imageSrc}
                alt="preview"
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <div
                style={{
                  padding: "12px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  height: "100%",
                  width: "100%",
                  boxSizing: "border-box"
                }}
              >
                <div style={{ overflow: "hidden" }}>
                  <div style={{
                    color: textColor,
                    fontSize: "14px",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    marginBottom: "4px",
                    fontFamily: "'Inter', sans-serif"
                  }}>
                    {file?.name || "Dokumen"}
                  </div>
                  <div style={{
                    color: secondaryTextColor,
                    fontSize: "12px",
                    fontWeight: 500
                  }}>
                    {fileSizeText}
                  </div>
                </div>

                <div style={{
                  alignSelf: "flex-start",
                  border: `1px solid ${darkMode ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)"}`,
                  borderRadius: "6px",
                  padding: "2px 6px",
                  fontSize: "11px",
                  fontWeight: 700,
                  color: secondaryTextColor,
                  background: darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
                  letterSpacing: "0.5px"
                }}>
                  {ext}
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => removeFilePreview(idx)}
              style={{
                position: "absolute",
                top: "2px",
                right: "2px",
                background: "rgba(0,0,0,0.6)",
                border: "none",
                borderRadius: "50%",
                width: "16px",
                height: "16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                fontSize: "9px",
                cursor: "pointer",
                fontWeight: "bold",
                zIndex: 2,
              }}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
