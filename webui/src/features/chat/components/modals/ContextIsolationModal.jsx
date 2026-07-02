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
          maxWidth: "550px",
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
            }}
            className="custom-scroll-gemini"
          >
            {isLoadingDocuments ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "20px",
                  color: theme.secondaryText,
                }}
              >
                Memuat dokumen...
              </div>
            ) : (!documents || documents.length === 0) ? (
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
              documents.map((doc) => {
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
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
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
                    </div>
                    <button
                      onClick={() => {
                        onSelectDocument(doc.id, doc.title);
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
    </div>
  );
}
