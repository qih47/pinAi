import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { translations } from "../../../../utils/translations";
import { getApiBase } from "../../../../services/endpoints";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

const ModeHintIcon = ({ title, hintText, icon, darkMode }) => {
  const [show, setShow] = useState(false);
  const triggerRef = useRef(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const updateCoords = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const safeLeft = Math.min(window.innerWidth - 125, Math.max(125, rect.left + rect.width / 2));
      setCoords({
        top: rect.top - 6,
        left: safeLeft,
      });
    }
  };

  const handleMouseEnter = (e) => {
    e.stopPropagation();
    updateCoords();
    setShow(true);
  };

  const handleClick = (e) => {
    e.stopPropagation();
    updateCoords();
    setShow(prev => !prev);
  };

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => { e.stopPropagation(); setShow(false); }}
        onClick={handleClick}
        style={{
          position: 'absolute',
          right: '6px',
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'help',
          flexShrink: 0,
          opacity: 0.65,
          transition: 'all 0.15s ease',
        }}
        onMouseOver={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(-50%) scale(1.2)'; }}
        onMouseOut={(e) => { e.currentTarget.style.opacity = '0.65'; e.currentTarget.style.transform = 'translateY(-50%) scale(1)'; }}
      >
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </span>
      {show && createPortal(
        <div
          style={{
            position: 'fixed',
            top: `${coords.top}px`,
            left: `${coords.left}px`,
            transform: 'translate(-50%, -100%)',
            zIndex: 999999,
            width: 'min(230px, calc(100vw - 32px))',
            padding: '8px 11px',
            borderRadius: '8px',
            fontSize: '11px',
            lineHeight: '1.45',
            textAlign: 'left',
            pointerEvents: 'none',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.4), 0 8px 10px -6px rgba(0,0,0,0.3)',
            background: darkMode ? '#1e293b' : '#ffffff',
            color: darkMode ? '#f1f5f9' : '#0f172a',
            border: `1px solid ${darkMode ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)'}`,
            backdropFilter: 'blur(10px)',
          }}
        >
          {title && (
            <div style={{ fontWeight: 700, marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '5px', color: darkMode ? '#93c5fd' : '#2563eb' }}>
              {icon && <span>{icon}</span>}
              <span>{title}</span>
            </div>
          )}
          <div style={{ color: darkMode ? '#cbd5e1' : '#475569', fontWeight: 400 }}>
            {hintText}
          </div>
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              borderTop: `5px solid ${darkMode ? '#1e293b' : '#ffffff'}`,
            }}
          />
        </div>,
        document.body
      )}
    </>
  );
};

export default function ContextIsolationModal({
  showModal,
  onClose,
  documents,
  documentsTotal,
  fetchDocumentsList,
  isLoadingDocuments,
  activeIsolatedDocId,
  onSelectDocument,
  handleChatModeChange,
  theme,
  darkMode,
  language
}) {
  const t = translations[language]?.contextModal || translations.id.contextModal;
  const tChat = translations[language]?.chat || translations.id.chat;

  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [previewPdfUrl, setPreviewPdfUrl] = useState(null);
  const [previewPdfBlobUrl, setPreviewPdfBlobUrl] = useState(null);
  const [isLoadingPdf, setIsLoadingPdf] = useState(false);
  const [previewNumPages, setPreviewNumPages] = useState(null);
  const [previewPageNumber, setPreviewPageNumber] = useState(1);
  const [previewScale, setPreviewScale] = useState(1.0);
  const [previewViewMode, setPreviewViewMode] = useState('scroll');

  const [expandedLineageDocId, setExpandedLineageDocId] = useState(null);
  const [lineageData, setLineageData] = useState(null);
  const [isLoadingLineage, setIsLoadingLineage] = useState(false);

  const [expandedInsightDocId, setExpandedInsightDocId] = useState(null);
  const [insightData, setInsightData] = useState(null);
  const [isLoadingInsight, setIsLoadingInsight] = useState(false);

  const [expandedActions, setExpandedActions] = useState({});
  const [eyeDropdownDocId, setEyeDropdownDocId] = useState(null);

  const formatDocDate = (dateVal) => {
    if (!dateVal) return "-";
    try {
      const d = new Date(dateVal);
      if (isNaN(d.getTime())) return String(dateVal);
      return d.toLocaleDateString(language === 'en' ? 'en-US' : 'id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      });
    } catch {
      return String(dateVal);
    }
  };

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
    if (showModal) {
      fetchDocumentsList({ offset: (currentPage - 1) * limit, limit, search: debouncedSearch });
      setExpandedLineageDocId(null);
      setExpandedInsightDocId(null);
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
        padding: "10px",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
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
          maxHeight: "92vh",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "14px 16px",
            borderBottom: `1px solid ${theme.borderColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 600 }}>
            {t.title}
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
              padding: "4px 8px",
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        <div
          style={{
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            flex: 1,
            overflowY: "auto",
          }}
        >
          <input
            type="text"
            placeholder={t.searchPlaceholder}
            value={docSearchQuery}
            onChange={(e) => setDocSearchQuery(e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: "8px",
              border: `1px solid ${theme.inputBorder}`,
              background: theme.inputBg,
              color: theme.textColor,
              outline: "none",
              fontSize: "13px",
              width: "100%",
              boxSizing: "border-box",
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
            className="custom-scrollbar"
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
                {t.loading}
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
                {t.noDocs}
              </div>
            ) : (
              (documents || []).map((doc) => {
                const isIsolated = activeIsolatedDocId === doc.id;
                return (
                  <div
                    key={doc.id}
                    style={{
                      padding: "12px 14px",
                      borderRadius: "10px",
                      background: isIsolated
                        ? darkMode
                          ? "rgba(99, 102, 241, 0.15)"
                          : "rgba(37, 99, 235, 0.08)"
                        : darkMode
                          ? "#2a2a2d"
                          : "#f9fafb",
                      border: `1px solid ${isIsolated ? (darkMode ? "#6366f1" : "#2563eb") : theme.borderColor
                        }`,
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div
                      style={{ display: "flex", flexDirection: "column", gap: "10px" }}
                    >
                      <div style={{ minWidth: 0, flex: 1, textAlign: "left" }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: "13.5px",
                            lineHeight: "1.4",
                            overflowWrap: "anywhere",
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
                            marginTop: "3px",
                            lineHeight: "1.4",
                            overflowWrap: "break-word",
                            wordBreak: "break-word",
                          }}
                        >
                          {t.number}: {doc.nomor || "-"} | {t.type}: {doc.jenis_dokumen || "-"} | {t.date || "Tanggal"}: {formatDocDate(doc.tgl_tetap || doc.tanggal || doc.created_at)}
                        </div>
                        {doc.snippet && (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "12px",
                              color: theme.secondaryText,
                              background: darkMode ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
                              padding: "8px 10px",
                              borderRadius: "6px",
                              borderLeft: `2px solid ${theme.borderColor}`,
                              lineHeight: "1.5",
                              fontStyle: "italic",
                              overflowWrap: "break-word",
                              wordBreak: "break-word",
                            }}
                            dangerouslySetInnerHTML={{ __html: doc.snippet }}
                          />
                        )}
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: "8px",
                            marginTop: "10px",
                            paddingTop: "6px",
                          }}
                        >
                          {/* Sisi Kiri: Status Dokumen + Alat Ekstra (Eye, Download, Lineage, Insight, Chevron) */}
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                            <div
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                padding: "2px 8px",
                                borderRadius: "12px",
                                fontSize: "10px",
                                fontWeight: 600,
                                backgroundColor:
                                  doc.stataktif === "batal" ? "rgba(239, 68, 68, 0.15)" :
                                    doc.stataktif === "obsolete" ? "rgba(245, 158, 11, 0.15)" :
                                      "rgba(10, 185, 129, 0.15)",
                                color:
                                  doc.stataktif === "batal" ? "#ef4444" :
                                    doc.stataktif === "obsolete" ? "#f59e0b" :
                                      "#10b981",
                              }}
                            >
                              {doc.stataktif === "batal" ? t.revokedStatus :
                                doc.stataktif === "obsolete" ? t.obsoleteStatus :
                                  t.validStatus}
                            </div>

                            {doc.filename && !isIsolated && expandedActions[doc.id] && (
                              <>
                                {/* Tombol Eye dengan dropdown PDF / Portal */}
                                <div
                                  style={{ position: 'relative', display: 'inline-flex' }}
                                  onMouseEnter={() => setEyeDropdownDocId(doc.id)}
                                  onMouseLeave={() => setEyeDropdownDocId(null)}
                                >
                                  <button
                                    title={t.viewDoc}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setEyeDropdownDocId(prev => prev === doc.id ? null : doc.id);
                                    }}
                                    style={{
                                      background: eyeDropdownDocId === doc.id ? (darkMode ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.06)") : "transparent",
                                      border: "none",
                                      color: theme.textColor,
                                      cursor: "pointer",
                                      padding: "4px",
                                      borderRadius: "6px",
                                      display: 'flex',
                                      alignItems: 'center',
                                      transition: "background 0.15s ease",
                                    }}
                                  >
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                      <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                  </button>
                                  {/* Dropdown menu dengan hover bridge mulus */}
                                  {eyeDropdownDocId === doc.id && (
                                    <div
                                      style={{
                                        position: 'absolute',
                                        top: '100%',
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        paddingTop: '6px',
                                        zIndex: 9999,
                                      }}
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <div style={{
                                        background: darkMode ? '#1e293b' : '#ffffff',
                                        border: `1px solid ${darkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.10)'}`,
                                        borderRadius: '10px',
                                        boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                                        overflow: 'hidden',
                                        minWidth: '145px',
                                        backdropFilter: 'blur(12px)',
                                      }}>
                                        {/* Opsi 1: Buka PDF */}
                                        <button
                                          onClick={async (e) => {
                                            e.stopPropagation();
                                            setEyeDropdownDocId(null);
                                            setPreviewPdfUrl(`${getApiBase()}/api/documents/preview/${doc.filename}`);
                                            setIsLoadingPdf(true);
                                            try {
                                              const encodedFilename = btoa(doc.filename);
                                              const res = await fetch(`${getApiBase()}/api/documents/preview_b64/${encodedFilename}`);
                                              const rawBlob = await res.blob();
                                              const pdfBlob = new Blob([rawBlob], { type: "application/pdf" });
                                              setPreviewPdfBlobUrl(URL.createObjectURL(pdfBlob));
                                            } catch (err) {
                                              console.error("Error loading PDF", err);
                                            } finally {
                                              setIsLoadingPdf(false);
                                            }
                                          }}
                                          style={{
                                            display: 'flex', alignItems: 'center', gap: '8px',
                                            width: '100%', padding: '8px 12px',
                                            background: 'transparent', border: 'none',
                                            color: darkMode ? '#e2e8f0' : '#1f2937',
                                            cursor: 'pointer', fontSize: '12px', fontWeight: 500,
                                            textAlign: 'left',
                                            transition: 'background 0.12s',
                                          }}
                                          onMouseOver={(e) => e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'}
                                          onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                                        >
                                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                          </svg>
                                          Buka PDF
                                        </button>
                                        {/* Opsi 2: Buka Portal */}
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setEyeDropdownDocId(null);
                                            window.open(`https://peraturan.pindad.com/content/detail/${doc.id}`, '_blank', 'noopener,noreferrer');
                                          }}
                                          style={{
                                            display: 'flex', alignItems: 'center', gap: '8px',
                                            width: '100%', padding: '8px 12px',
                                            background: 'transparent', border: 'none',
                                            borderTop: `1px solid ${darkMode ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'}`,
                                            color: darkMode ? '#a5b4fc' : '#2563eb',
                                            cursor: 'pointer', fontSize: '12px', fontWeight: 500,
                                            textAlign: 'left',
                                            transition: 'background 0.12s',
                                          }}
                                          onMouseOver={(e) => e.currentTarget.style.background = darkMode ? 'rgba(99,102,241,0.12)' : 'rgba(37,99,235,0.06)'}
                                          onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                                        >
                                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                            <polyline points="15 3 21 3 21 9"/>
                                            <line x1="10" y1="14" x2="21" y2="3"/>
                                          </svg>
                                          Buka di Portal
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>

                                {/* Tombol Download */}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    const link = document.createElement("a");
                                    link.href = `${getApiBase()}/file_peraturan/${doc.filename}`;
                                    link.download = doc.filename;
                                    link.target = "_blank";
                                    document.body.appendChild(link);
                                    link.click();
                                    document.body.removeChild(link);
                                  }}
                                  title={t.downloadDoc}
                                  style={{
                                    padding: "4px",
                                    background: "transparent",
                                    border: "none",
                                    color: theme.textColor,
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                  }}
                                >
                                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                    <polyline points="7 10 12 15 17 10"></polyline>
                                    <line x1="12" y1="15" x2="12" y2="3"></line>
                                  </svg>
                                </button>

                                {/* Tombol Riwayat (Lineage) */}
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (expandedLineageDocId === doc.id) {
                                      setExpandedLineageDocId(null);
                                      setLineageData(null);
                                      return;
                                    }
                                    setExpandedLineageDocId(doc.id);
                                    setIsLoadingLineage(true);
                                    setLineageData(null);
                                    try {
                                      const res = await fetch(`${getApiBase()}/api/documents/${doc.id}/lineage`);
                                      if (res.ok) {
                                        const data = await res.json();
                                        setLineageData(data);
                                      }
                                    } catch (err) {
                                      console.error("Error loading lineage", err);
                                    } finally {
                                      setIsLoadingLineage(false);
                                    }
                                  }}
                                  title={t.lineageDoc}
                                  style={{
                                    background: expandedLineageDocId === doc.id ? "rgba(99, 102, 241, 0.15)" : "transparent",
                                    border: "none",
                                    color: expandedLineageDocId === doc.id ? "#6366f1" : theme.textColor,
                                    cursor: "pointer",
                                    padding: "4px 8px",
                                    borderRadius: "6px",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    transition: "all 0.2s ease",
                                  }}
                                >
                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                                  </svg>
                                  {t.lineageBtn}
                                </button>

                                {/* Tombol AI Smart Insight */}
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (expandedInsightDocId === doc.id) {
                                      setExpandedInsightDocId(null);
                                      setInsightData(null);
                                      return;
                                    }
                                    setExpandedInsightDocId(doc.id);
                                    setIsLoadingInsight(true);
                                    setInsightData(null);
                                    try {
                                      const res = await fetch(`${getApiBase()}/api/documents/${doc.id}/insight`);
                                      if (res.ok) {
                                        const data = await res.json();
                                        setInsightData(data.insight);
                                      }
                                    } catch (err) {
                                      console.error("Error loading insight", err);
                                    } finally {
                                      setIsLoadingInsight(false);
                                    }
                                  }}
                                  title="AI Smart Insight"
                                  style={{
                                    background: expandedInsightDocId === doc.id ? "rgba(245, 158, 11, 0.15)" : "transparent",
                                    border: "none",
                                    color: expandedInsightDocId === doc.id ? "#f59e0b" : theme.textColor,
                                    cursor: "pointer",
                                    padding: "4px 8px",
                                    borderRadius: "6px",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    transition: "all 0.2s ease",
                                  }}
                                >
                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                                  </svg>
                                  {t.insightBtn}
                                </button>
                              </>
                            )}

                            {doc.filename && !isIsolated && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedActions(prev => ({ ...prev, [doc.id]: !prev[doc.id] }));
                                }}
                                title={expandedActions[doc.id] ? "Sembunyikan aksi" : "Tampilkan aksi lainnya"}
                                style={{
                                  padding: "4px 6px",
                                  background: expandedActions[doc.id] ? (darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.06)") : "transparent",
                                  border: `1px solid ${expandedActions[doc.id] ? (darkMode ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)") : "transparent"}`,
                                  color: theme.textColor,
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  borderRadius: "6px",
                                  transition: "all 0.2s ease"
                                }}
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: expandedActions[doc.id] ? 'rotate(0deg)' : 'rotate(180deg)', transition: 'transform 0.2s' }}>
                                  <polyline points="9 18 15 12 9 6"></polyline>
                                </svg>
                              </button>
                            )}
                          </div>

                          {/* Sisi Kanan: Tombol Mode Chat (Tanya, Kepatuhan, Bedah, atau Unfocus) */}
                          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
                            {isIsolated ? (
                              <button
                                onClick={() => {
                                  onSelectDocument(null, "");
                                  if (handleChatModeChange) handleChatModeChange('auto');
                                  onClose();
                                }}
                                style={{
                                  padding: "4px 10px",
                                  borderRadius: "20px",
                                  border: "none",
                                  background: "#ef4444",
                                  color: "#ffffff",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                  transition: "all 0.15s ease",
                                  flexShrink: 0,
                                }}
                              >
                                {t.unfocus}
                              </button>
                            ) : (
                              <>
                                <button
                                  onClick={() => {
                                    onSelectDocument(doc.id, doc.title);
                                    if (handleChatModeChange) handleChatModeChange('focus');
                                    onClose();
                                  }}
                                  style={{
                                    position: "relative",
                                    padding: "4px 22px 4px 10px",
                                    borderRadius: "20px",
                                    border: "none",
                                    background: "#6366f1",
                                    color: "#ffffff",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    cursor: "pointer",
                                    transition: "all 0.15s ease",
                                    flexShrink: 0,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px"
                                  }}
                                >
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                                  </svg>
                                  <span>{tChat.tanyaBtn}</span>
                                  <ModeHintIcon 
                                    title={tChat.tanyaHintTitle} 
                                    hintText={tChat.tanyaHint} 
                                    icon="💬" 
                                    darkMode={darkMode} 
                                  />
                                </button>
                                <button
                                  onClick={() => {
                                    onSelectDocument(doc.id, doc.title);
                                    if (handleChatModeChange) handleChatModeChange('compliance');
                                    onClose();
                                  }}
                                  style={{
                                    position: "relative",
                                    padding: "4px 22px 4px 10px",
                                    borderRadius: "20px",
                                    border: "1px solid rgba(239, 68, 68, 0.3)",
                                    background: "rgba(239, 68, 68, 0.1)",
                                    color: "#ef4444",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    cursor: "pointer",
                                    transition: "all 0.15s ease",
                                    flexShrink: 0,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px"
                                  }}
                                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.2)" }}
                                  onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.1)" }}
                                >
                                  <span style={{ fontSize: "10px" }}>⚖️</span> 
                                  <span>{tChat.kepatuhanBtn}</span>
                                  <ModeHintIcon 
                                    title={tChat.kepatuhanHintTitle} 
                                    hintText={tChat.kepatuhanHint} 
                                    icon="⚖️" 
                                    darkMode={darkMode} 
                                  />
                                </button>
                                <button
                                  onClick={() => {
                                    onSelectDocument(doc.id, doc.title);
                                    if (handleChatModeChange) handleChatModeChange('redteam');
                                    onClose();
                                  }}
                                  style={{
                                    position: "relative",
                                    padding: "4px 22px 4px 10px",
                                    borderRadius: "20px",
                                    border: "1px solid rgba(217, 119, 6, 0.3)",
                                    background: "rgba(217, 119, 6, 0.1)",
                                    color: "#d97706",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    cursor: "pointer",
                                    transition: "all 0.15s ease",
                                    flexShrink: 0,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px"
                                  }}
                                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(217, 119, 6, 0.2)" }}
                                  onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(217, 119, 6, 0.1)" }}
                                >
                                  <span style={{ fontSize: "10px" }}>🕵️</span> 
                                  <span>{tChat.bedahBtn}</span>
                                  <ModeHintIcon 
                                    title={tChat.bedahHintTitle} 
                                    hintText={tChat.bedahHint} 
                                    icon="🕵️" 
                                    darkMode={darkMode} 
                                  />
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Expandable Lineage Section */}
                    {expandedLineageDocId === doc.id && (
                      <div
                        style={{
                          padding: "12px 16px",
                          borderTop: `1px dashed ${theme.borderColor}`,
                          background: darkMode ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.01)",
                          borderBottomLeftRadius: "10px",
                          borderBottomRightRadius: "10px",
                          animation: "fadeIn 0.2s ease-out",
                        }}
                      >
                        {isLoadingLineage ? (
                          <div style={{ color: theme.secondaryText, fontSize: "12px", textAlign: "center" }}>{t.trackingLineage}</div>
                        ) : lineageData ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "12px" }}>
                            {/* Yg dicabut oleh doc ini */}
                            {lineageData.revokes && lineageData.revokes.length > 0 && (
                              <div style={{ marginBottom: "12px" }}>
                                <div style={{ color: theme.secondaryText, marginBottom: "4px" }}>{t.revokes}</div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                  {lineageData.revokes.map(r => (
                                    <div key={r.id} style={{ padding: "6px 10px", background: darkMode ? "#2a2a2d" : "#f1f5f9", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                      <div style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1, paddingRight: "10px" }}>
                                        <span style={{ fontWeight: 500, color: theme.textColor }}>{r.noper || t.noNumber} - {r.judul}</span>
                                        <span style={{ color: "#ef4444", fontSize: "11px", fontWeight: 600 }}>{t.inactive}</span>
                                      </div>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          onSelectDocument(r.id, r.judul);
                                          onClose();
                                        }}
                                        style={{
                                          padding: "4px 10px",
                                          borderRadius: "16px",
                                          border: "none",
                                          background: "#6366f1",
                                          color: "#ffffff",
                                          fontSize: "11px",
                                          fontWeight: 600,
                                          cursor: "pointer",
                                          flexShrink: 0,
                                        }}
                                      >
                                        {t.focus}
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Current Doc Highlight */}
                            <div style={{ padding: "8px 12px", background: darkMode ? "rgba(255,255,255,0.03)" : "#f8fafc", borderRadius: "8px", border: `1px solid ${theme.borderColor}`, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ color: "#10b981", display: "flex" }}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></span>
                              <div style={{ fontWeight: 600, color: "#10b981" }}>{t.currentDoc}</div>
                            </div>

                            {/* Yg mencabut doc ini */}
                            {lineageData.revoked_by && lineageData.revoked_by.length > 0 && (
                              <div style={{ marginBottom: lineageData.latest_active && !lineageData.revoked_by.some(r => r.id === lineageData.latest_active.id) ? "12px" : "0px" }}>
                                <div style={{ color: theme.secondaryText, marginBottom: "4px" }}>{t.revokedBy}</div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                  {lineageData.revoked_by.map(r => {
                                    const statLower = String(r.stataktif || "").trim().toLowerCase();
                                    const isRActive = !(statLower === "obsolete" || statLower === "0" || statLower === "2");
                                    return (
                                      <div
                                        key={r.id}
                                        style={{
                                          padding: "6px 10px",
                                          background: isRActive
                                            ? (darkMode ? "rgba(16, 185, 129, 0.15)" : "#d1fae5")
                                            : (darkMode ? "rgba(245, 158, 11, 0.12)" : "#fef3c7"),
                                          border: isRActive
                                            ? "1px solid #10b981"
                                            : "1px solid rgba(245, 158, 11, 0.5)",
                                          borderRadius: "6px",
                                          display: "flex",
                                          justifyContent: "space-between",
                                          alignItems: "center"
                                        }}
                                      >
                                        <div style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1, paddingRight: "10px" }}>
                                          <span style={{ fontWeight: 500, color: theme.textColor }}>{r.noper || t.noNumber} - {r.judul}</span>
                                          <span
                                            style={{
                                              color: isRActive ? "#10b981" : "#f59e0b",
                                              fontSize: "11px",
                                              fontWeight: 600
                                            }}
                                          >
                                            {isRActive ? t.active : t.inactive}
                                          </span>
                                        </div>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            onSelectDocument(r.id, r.judul);
                                            onClose();
                                          }}
                                          style={{
                                            padding: "4px 10px",
                                            borderRadius: "16px",
                                            border: "none",
                                            background: isRActive ? "#10b981" : "#6366f1",
                                            color: "#ffffff",
                                            fontSize: "11px",
                                            fontWeight: 600,
                                            cursor: "pointer",
                                            flexShrink: 0,
                                          }}
                                        >
                                          {t.focus}
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Regulasi Terkini yang Berlaku Saat Ini (Ujung Rantai Silsilah) */}
                            {lineageData.latest_active && !lineageData.revoked_by?.some(r => r.id === lineageData.latest_active.id) && lineageData.latest_active.id !== doc.id && (
                              <div style={{ marginTop: "10px" }}>
                                <div style={{ color: "#10b981", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}>
                                  🌟 {t.latestActiveSuccessor}
                                </div>
                                <div
                                  style={{
                                    padding: "8px 12px",
                                    background: darkMode ? "rgba(16, 185, 129, 0.18)" : "#d1fae5",
                                    border: "1.5px solid #10b981",
                                    borderRadius: "8px",
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    boxShadow: "0 2px 8px rgba(16, 185, 129, 0.15)"
                                  }}
                                >
                                  <div style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1, paddingRight: "10px" }}>
                                    <span style={{ fontWeight: 600, color: theme.textColor, fontSize: "12.5px" }}>
                                      {lineageData.latest_active.noper || t.noNumber} - {lineageData.latest_active.judul}
                                    </span>
                                    <span style={{ color: "#10b981", fontSize: "11px", fontWeight: 700 }}>
                                      {t.active}
                                    </span>
                                  </div>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onSelectDocument(lineageData.latest_active.id, lineageData.latest_active.judul);
                                      onClose();
                                    }}
                                    style={{
                                      padding: "5px 12px",
                                      borderRadius: "16px",
                                      border: "none",
                                      background: "#10b981",
                                      color: "#ffffff",
                                      fontSize: "11px",
                                      fontWeight: 700,
                                      cursor: "pointer",
                                      flexShrink: 0,
                                      boxShadow: "0 2px 6px rgba(16, 185, 129, 0.3)"
                                    }}
                                  >
                                    {t.focus}
                                  </button>
                                </div>
                              </div>
                            )}

                            {(!lineageData.revokes?.length && !lineageData.revoked_by?.length && !lineageData.latest_active) && (
                              <div style={{ color: theme.secondaryText, fontStyle: "italic", textAlign: "center" }}>
                                {t.noLineage}
                              </div>
                            )}
                          </div>

                        ) : null}
                      </div>
                    )}

                    {/* Expandable Insight Section */}
                    {expandedInsightDocId === doc.id && (
                      <div
                        style={{
                          padding: "16px",
                          borderTop: `1px dashed ${theme.borderColor}`,
                          background: darkMode ? "rgba(245, 158, 11, 0.05)" : "rgba(245, 158, 11, 0.05)",
                          borderBottomLeftRadius: "10px",
                          borderBottomRightRadius: "10px",
                          animation: "fadeIn 0.2s ease-out",
                        }}
                      >
                        {isLoadingInsight ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f59e0b", fontSize: "12px", justifyContent: "center" }}>
                            <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" />
                              <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeLinecap="round" />
                            </svg>
                            <span>{t.readingInsight}</span>
                          </div>
                        ) : insightData ? (
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px", color: "#f59e0b", fontWeight: 600, fontSize: "13px" }}>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                              </svg>
                              CAKRA Smart Insight
                            </div>
                            <div
                              style={{
                                color: theme.textColor,
                                fontSize: "12.5px",
                                lineHeight: "1.6",
                              }}
                              className="insight-markdown-content"
                            >
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkMath]}
                                rehypePlugins={[rehypeKatex]}
                                components={{
                                  p: ({ node, ...props }) => <p style={{ margin: "0 0 8px 0" }} {...props} />,
                                  ul: ({ node, ...props }) => <ul style={{ margin: "0 0 8px 0", paddingLeft: "20px" }} {...props} />,
                                  ol: ({ node, ...props }) => <ol style={{ margin: "0 0 8px 0", paddingLeft: "20px" }} {...props} />,
                                  li: ({ node, ...props }) => <li style={{ marginBottom: "4px" }} {...props} />,
                                  strong: ({ node, ...props }) => <strong style={{ fontWeight: 600, color: theme.textColor }} {...props} />
                                }}
                              >
                                {insightData}
                              </ReactMarkdown>
                            </div>
                          </div>
                        ) : (
                          <div style={{ color: theme.secondaryText, fontSize: "12px", textAlign: "center" }}>{t.insightFailed}</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Pagination UI */}
        <div
          style={{
            padding: "10px 16px",
            borderTop: `1px solid ${theme.borderColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
            background: darkMode ? "#1e1e20" : "#ffffff",
            flexShrink: 0,
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
            {t.prev}
          </button>

          <div style={{ fontSize: "12px", color: theme.secondaryText }}>
            {t.page} {totalPages > 0 ? currentPage : 0} {t.of} {totalPages}
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
            {t.next}
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
            background: "rgba(0,0,0,0.85)",
            backdropFilter: "blur(6px)",
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
              background: darkMode ? "#18181b" : "#f1f5f9",
              position: "relative",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Top Toolbar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 16px",
                background: darkMode ? "#1f1f23" : "#ffffff",
                borderBottom: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`,
                zIndex: 10,
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
                <span style={{ fontSize: "13px", fontWeight: "600", color: darkMode ? "#f3f4f6" : "#1f2937", whiteSpace: "nowrap" }}>
                  Pratinjau Dokumen
                </span>
                {previewNumPages && (
                  <span style={{ fontSize: "12px", color: darkMode ? "#9ca3af" : "#6b7280", whiteSpace: "nowrap" }}>
                    {previewViewMode === 'page' ? `Hal. ${previewPageNumber}/${previewNumPages}` : `${previewNumPages} Halaman`}
                  </span>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                {/* Zoom Controls */}
                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <button
                    onClick={() => setPreviewScale(s => Math.max(0.6, s - 0.15))}
                    style={{
                      padding: "4px 8px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 600,
                      background: darkMode ? "#27272a" : "#f1f5f9",
                      border: `1px solid ${darkMode ? "#3f3f46" : "#cbd5e1"}`,
                      color: darkMode ? "#e4e4e7" : "#334155",
                      cursor: "pointer",
                    }}
                    title="Perkecil"
                  >
                    -
                  </button>
                  <span style={{ fontSize: "11px", fontWeight: 600, width: "36px", textAlign: "center", color: darkMode ? "#a1a1aa" : "#4b5563" }}>
                    {Math.round(previewScale * 100)}%
                  </span>
                  <button
                    onClick={() => setPreviewScale(s => Math.min(2.5, s + 0.15))}
                    style={{
                      padding: "4px 8px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 600,
                      background: darkMode ? "#27272a" : "#f1f5f9",
                      border: `1px solid ${darkMode ? "#3f3f46" : "#cbd5e1"}`,
                      color: darkMode ? "#e4e4e7" : "#334155",
                      cursor: "pointer",
                    }}
                    title="Perbesar"
                  >
                    +
                  </button>
                </div>

                {/* Mode Scroll / Page */}
                {previewNumPages && (
                  <button
                    onClick={() => setPreviewViewMode(prev => prev === 'scroll' ? 'page' : 'scroll')}
                    style={{
                      padding: "5px 10px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 500,
                      background: darkMode ? "#27272a" : "#f1f5f9",
                      border: `1px solid ${darkMode ? "#3f3f46" : "#cbd5e1"}`,
                      color: darkMode ? "#e4e4e7" : "#334155",
                      cursor: "pointer",
                    }}
                  >
                    {previewViewMode === 'scroll' ? "Gulir" : "Halaman"}
                  </button>
                )}

                {/* Open in New Tab */}
                {previewPdfBlobUrl && (
                  <button
                    onClick={() => window.open(previewPdfBlobUrl, '_blank')}
                    style={{
                      padding: "5px 8px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 500,
                      background: darkMode ? "#27272a" : "#f1f5f9",
                      border: `1px solid ${darkMode ? "#3f3f46" : "#cbd5e1"}`,
                      color: darkMode ? "#e4e4e7" : "#334155",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                    }}
                    title="Buka di tab baru"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                      <polyline points="15 3 21 3 21 9"></polyline>
                      <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                  </button>
                )}

                {/* Close Button */}
                <button
                  onClick={() => {
                    setPreviewPdfUrl(null);
                    if (previewPdfBlobUrl) URL.revokeObjectURL(previewPdfBlobUrl);
                    setPreviewPdfBlobUrl(null);
                  }}
                  style={{
                    background: "rgba(239,68,68,0.15)",
                    border: "1px solid rgba(239,68,68,0.3)",
                    borderRadius: "6px",
                    color: "#ef4444",
                    cursor: "pointer",
                    padding: "5px 10px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "12px",
                    fontWeight: 600,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                  <span>Tutup</span>
                </button>
              </div>
            </div>

            {/* Document Content with Touch Scrolling */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                overflowX: "hidden",
                WebkitOverflowScrolling: "touch",
                position: "relative",
                padding: "12px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
              className="custom-scrollbar"
            >
              {isLoadingPdf ? (
                <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", gap: "8px", color: darkMode ? "#9ca3af" : "#64748b" }}>
                  <div style={{ width: "24px", height: "24px", border: "2px solid rgba(99,102,241,0.2)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "rotate-spin 0.8s linear infinite" }} />
                  <span style={{ fontSize: "13px" }}>{t.loadingPdf || "Memuat dokumen..."}</span>
                </div>
              ) : previewPdfBlobUrl ? (
                <Document
                  file={previewPdfBlobUrl}
                  onLoadSuccess={({ numPages }) => {
                    setPreviewNumPages(numPages);
                    setPreviewPageNumber(1);
                  }}
                  loading={
                    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", color: darkMode ? "#9ca3af" : "#64748b" }}>
                      Memuat halaman PDF...
                    </div>
                  }
                  error={
                    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", color: "#ef4444" }}>
                      Gagal memuat PDF.
                    </div>
                  }
                  className="flex flex-col items-center w-full"
                >
                  {previewViewMode === 'scroll' && previewNumPages ? (
                    <div className="flex flex-col items-center gap-4 w-full">
                      {Array.from(new Array(previewNumPages), (_, index) => (
                        <div key={`page_${index + 1}`} className="shadow-xl bg-white max-w-full overflow-hidden">
                          <Page
                            pageNumber={index + 1}
                            scale={previewScale}
                            width={Math.min(window.innerWidth - 24, 750)}
                            renderTextLayer={true}
                            renderAnnotationLayer={true}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    previewNumPages && (
                      <div className="flex flex-col items-center gap-3">
                        <div className="shadow-xl bg-white max-w-full overflow-hidden">
                          <Page
                            pageNumber={previewPageNumber}
                            scale={previewScale}
                            width={Math.min(window.innerWidth - 24, 750)}
                            renderTextLayer={true}
                            renderAnnotationLayer={true}
                          />
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <button
                            disabled={previewPageNumber <= 1}
                            onClick={() => setPreviewPageNumber(p => Math.max(1, p - 1))}
                            className="px-3 py-1.5 rounded bg-gray-200 dark:bg-gray-700 text-xs font-semibold disabled:opacity-40"
                          >
                            Prev
                          </button>
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                            {previewPageNumber} / {previewNumPages}
                          </span>
                          <button
                            disabled={previewPageNumber >= previewNumPages}
                            onClick={() => setPreviewPageNumber(p => Math.min(previewNumPages, p + 1))}
                            className="px-3 py-1.5 rounded bg-gray-200 dark:bg-gray-700 text-xs font-semibold disabled:opacity-40"
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    )
                  )}
                </Document>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
