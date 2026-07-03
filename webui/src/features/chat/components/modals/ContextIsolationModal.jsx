import React, { useState, useEffect } from "react";

export default function ContextIsolationModal({
  showModal,
  onClose,
  documents,
  documentsTotal,
  fetchDocumentsList,
  isLoadingDocuments,
  activeIsolatedDocId,
  onSelectDocument,
  theme,
  darkMode,
}) {
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [previewPdfUrl, setPreviewPdfUrl] = useState(null);
  const [previewPdfBlobUrl, setPreviewPdfBlobUrl] = useState(null);
  const [isLoadingPdf, setIsLoadingPdf] = useState(false);
  const limit = 15;

  useEffect(() => {
    const handler = setTimeout(() => {
      if (debouncedSearch !== docSearchQuery) {
        setDebouncedSearch(docSearchQuery);
        setCurrentPage(1); // Reset page on new search
      }
    }, 500);
    return () => clearTimeout(handler);
  }, [docSearchQuery, debouncedSearch]);

  useEffect(() => {
    if (showModal && fetchDocumentsList) {
      const offset = (currentPage - 1) * limit;
      fetchDocumentsList({ offset, limit, search: debouncedSearch });
    }
  }, [showModal, currentPage, debouncedSearch, fetchDocumentsList]);

  if (!showModal) return null;

  const totalPages = Math.ceil((documentsTotal || 0) / limit);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.5)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        animation: "fadeInUp 0.2s ease-out",
        padding: "20px",
      }}
    >
      <div
        style={{
          background: darkMode ? "#1e1e20" : "#ffffff",
          color: theme.textColor,
          width: "100%",
          maxWidth: "850px",
          borderRadius: "16px",
          border: `1px solid ${theme.borderColor}`,
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.3)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "85vh",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            borderBottom: `1px solid ${theme.borderColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
            Daftar Dokumen Regulasi
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: theme.secondaryText,
              cursor: "pointer",
              fontSize: "18px",
              fontWeight: "bold",
            }}
          >
            ✕
          </button>
        </div>

        <div
          style={{
            padding: "16px 20px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            flex: 1,
            overflowY: "auto",
          }}
        >
          <input
            type="text"
            placeholder="Cari nama dokumen atau nomor..."
            value={docSearchQuery}
            onChange={(e) => setDocSearchQuery(e.target.value)}
            style={{
              padding: "10px 14px",
              borderRadius: "8px",
              border: `1px solid ${theme.inputBorder}`,
              background: theme.inputBg,
              color: theme.textColor,
              outline: "none",
              fontSize: "14px",
              width: "100%",
            }}
          />

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              marginTop: "4px",
              position: "relative",
              minHeight: documents && documents.length > 0 ? "400px" : "auto",
            }}
            className="custom-scroll-gemini"
          >
            {isLoadingDocuments && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: darkMode ? "rgba(30, 30, 32, 0.6)" : "rgba(255, 255, 255, 0.6)",
                  backdropFilter: "blur(2px)",
                  zIndex: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "10px",
                  color: theme.textColor,
                  fontWeight: 600,
                }}
              >
                Memuat dokumen...
              </div>
            )}

            {(!documents || documents.length === 0) && !isLoadingDocuments ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "20px",
                  color: theme.secondaryText,
                }}
              >
                Tidak ada dokumen ditemukan.
              </div>
            ) : (
              (documents || []).map((doc) => {
                const isIsolated = activeIsolatedDocId === doc.id;
                return (
                  <div
                    key={doc.id}
                    style={{
                      padding: "12px 16px",
                      borderRadius: "10px",
                      background: isIsolated
                        ? darkMode
                          ? "rgba(99, 102, 241, 0.15)"
                          : "rgba(37, 99, 235, 0.08)"
                        : darkMode
                          ? "#2a2a2d"
                          : "#f9fafb",
                      border: `1px solid ${
                        isIsolated ? (darkMode ? "#6366f1" : "#2563eb") : theme.borderColor
                      }`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "12px",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div
                      style={{ minWidth: 0, flex: 1, textAlign: "left" }}
                    >
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: "13.5px",
                          lineHeight: "1.4",
                          overflowWrap: "break-word",
                          wordBreak: "break-word",
                          color: theme.textColor,
                        }}
                      >
                        {doc.title}
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: theme.secondaryText,
                          marginTop: "2px",
                        }}
                      >
                        No: {doc.nomor || "-"} | Tipe: {doc.jenis_dokumen || "-"}
                      </div>
                      <div
                        style={{
                          display: "inline-block",
                          marginTop: "6px",
                          padding: "2px 8px",
                          borderRadius: "12px",
                          fontSize: "10px",
                          fontWeight: 600,
                          backgroundColor:
                            doc.stataktif === "batal" ? "rgba(239, 68, 68, 0.15)" :
                            doc.stataktif === "obsolete" ? "rgba(245, 158, 11, 0.15)" :
                            "rgba(16, 185, 129, 0.15)",
                          color:
                            doc.stataktif === "batal" ? "#ef4444" :
                            doc.stataktif === "obsolete" ? "#f59e0b" :
                            "#10b981",
                        }}
                      >
                        {doc.stataktif === "batal" ? "Dicabut" :
                         doc.stataktif === "obsolete" ? "Tidak Berlaku" :
                         "Berlaku"}
                      </div>
                    </div>
                    
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      {doc.filename && (
                        <>
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              setPreviewPdfUrl(`${import.meta.env.VITE_API_BASE_URL || "http://192.168.11.80:5000"}/api/documents/preview/${doc.filename}`);
                              setIsLoadingPdf(true);
                              try {
                                const encodedFilename = btoa(doc.filename);
                                const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || "http://192.168.11.80:5000"}/api/documents/preview_b64/${encodedFilename}`);
                                const rawBlob = await res.blob();
                                const pdfBlob = new Blob([rawBlob], { type: "application/pdf" });
                                setPreviewPdfBlobUrl(URL.createObjectURL(pdfBlob));
                              } catch (err) {
                                console.error("Error loading PDF", err);
                              } finally {
                                setIsLoadingPdf(false);
                              }
                            }}
                            title="Lihat Dokumen"
                            style={{
                              padding: "6px",
                              borderRadius: "6px",
                              border: `1px solid ${theme.borderColor}`,
                              background: "transparent",
                              color: theme.primaryText,
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                              <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              const link = document.createElement("a");
                              link.href = `${import.meta.env.VITE_API_BASE_URL || "http://192.168.11.80:5000"}/file_peraturan/${doc.filename}`;
                              link.download = doc.filename;
                              link.target = "_blank";
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                            }}
                            title="Download Dokumen"
                            style={{
                              padding: "6px",
                              borderRadius: "6px",
                              border: `1px solid ${theme.borderColor}`,
                              background: "transparent",
                              color: theme.primaryText,
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                              <polyline points="7 10 12 15 17 10"></polyline>
                              <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                          </button>
                        </>
                      )}
                      <button
                      onClick={() => {
                        if (isIsolated) {
                          onSelectDocument(null, "");
                        } else {
                          onSelectDocument(doc.id, doc.title);
                        }
                        onClose();
                      }}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "20px",
                        border: "none",
                        background: isIsolated ? "#ef4444" : "#6366f1",
                        color: "#ffffff",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                        flexShrink: 0,
                      }}
                    >
                        {isIsolated ? "Batal Fokus" : "Fokus"}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Pagination UI */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: `1px solid ${theme.borderColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: darkMode ? "#1e1e20" : "#ffffff",
          }}
        >
          <button
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage <= 1 || isLoadingDocuments}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              background: (currentPage <= 1 || isLoadingDocuments) ? (darkMode ? "#3a3a3d" : "#e5e7eb") : (darkMode ? "#3b82f6" : "#2563eb"),
              color: (currentPage <= 1 || isLoadingDocuments) ? (darkMode ? "#6b7280" : "#9ca3af") : "#ffffff",
              border: "none",
              fontSize: "12px",
              fontWeight: 600,
              cursor: (currentPage <= 1 || isLoadingDocuments) ? "not-allowed" : "pointer",
            }}
          >
            &laquo; Sebelumnya
          </button>
          
          <div style={{ fontSize: "12px", color: theme.secondaryText }}>
            Halaman {totalPages > 0 ? currentPage : 0} dari {totalPages}
          </div>

          <button
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage >= totalPages || isLoadingDocuments}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              background: (currentPage >= totalPages || isLoadingDocuments) ? (darkMode ? "#3a3a3d" : "#e5e7eb") : (darkMode ? "#3b82f6" : "#2563eb"),
              color: (currentPage >= totalPages || isLoadingDocuments) ? (darkMode ? "#6b7280" : "#9ca3af") : "#ffffff",
              border: "none",
              fontSize: "12px",
              fontWeight: 600,
              cursor: (currentPage >= totalPages || isLoadingDocuments) ? "not-allowed" : "pointer",
            }}
          >
            Selanjutnya &raquo;
          </button>
        </div>
      </div>

      {/* PDF Preview Modal Overlay */}
      {previewPdfUrl && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            animation: "fadeIn 0.2s ease-out",
          }}
          onClick={() => {
            setPreviewPdfUrl(null);
            if (previewPdfBlobUrl) URL.revokeObjectURL(previewPdfBlobUrl);
            setPreviewPdfBlobUrl(null);
          }}
        >
          <div
            style={{
              width: "100%",
              height: "100%",
              background: "#000000",
              position: "relative",
              display: "flex",
              flexDirection: "column",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Floating Close Button */}
            <button
              onClick={() => {
                setPreviewPdfUrl(null);
                if (previewPdfBlobUrl) URL.revokeObjectURL(previewPdfBlobUrl);
                setPreviewPdfBlobUrl(null);
              }}
              style={{
                position: "absolute",
                top: "20px",
                right: "20px",
                zIndex: 1001,
                background: "rgba(0,0,0,0.5)",
                border: "none",
                borderRadius: "50%",
                color: "#ffffff",
                cursor: "pointer",
                padding: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backdropFilter: "blur(4px)",
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(239,68,68,0.8)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(0,0,0,0.5)")}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            
            {/* PDF Viewer */}
            <div style={{ flex: 1, position: "relative", width: "100%", height: "100%" }}>
              {isLoadingPdf ? (
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", color: theme.secondaryText }}>
                  Memuat dokumen...
                </div>
              ) : previewPdfBlobUrl ? (
                <iframe
                  src={`${previewPdfBlobUrl}#view=FitH`}
                  title="Preview Dokumen"
                  width="100%"
                  height="100%"
                  style={{ border: "none", display: "block" }}
                />
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
