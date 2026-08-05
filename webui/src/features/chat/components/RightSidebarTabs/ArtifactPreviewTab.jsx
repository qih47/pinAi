import React, { useState } from "react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CakraResponseRenderer from "../CakraResponseRenderer";
import { IconChevronLeft, IconCopy, IconClose, getArtifactFileIcon } from "./RightSidebarIcons";

const CodeSandboxViewer = React.lazy(() => import('../CodeSandboxViewer'));

export default function ArtifactPreviewTab({
  previewArtifact,
  setPreviewArtifact,
  artifactContent,
  isArtifactLoading,
  theme,
  darkMode,
  toast,
  containerBgColor,
  setShowRightSidebar,
  rightSidebarWidth,
  setRightSidebarWidth,
  isMobile,
  t
}) {
  const ext = previewArtifact?.filename?.split('.').pop()?.toLowerCase();
  const isMarkdownOrText = ext === 'md' || ext === 'txt';
  const isUIPreviewable = ext === 'jsx' || ext === 'js' || ext === 'html';
  const content = artifactContent || previewArtifact.code || '// Void Content';

  // Default buka Code. Biarkan user klik View UI (Mata) manual
  const [viewMode, setViewMode] = useState('code');

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", background: containerBgColor, gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", overflow: "hidden", flex: 1 }}>
          <button
            onClick={() => setPreviewArtifact(null)}
            style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#fff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", flexShrink: 0 }}
            title="Kembali"
          >
            <IconChevronLeft />
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
            {getArtifactFileIcon(ext, theme.iconColor)}
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

        <div style={{ display: "flex", gap: "6px", flexShrink: 0, alignItems: 'center' }}>

          <button
            onClick={() => {
              const codeToCopy = artifactContent || previewArtifact.code || '';
              navigator.clipboard.writeText(codeToCopy).then(() => toast.success("Kode disalin!"));
            }}
            style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#ffffff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "12px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}
          >
            <IconCopy size={13} /> {t.copy}
          </button>

          <button
            onClick={() => {
              // Gunakan magic number 9999 sebagai state mode full expand dinamis
              if (rightSidebarWidth === 9999) {
                setRightSidebarWidth(600);
              } else {
                setRightSidebarWidth(9999);
              }
            }}
            style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#ffffff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", flexShrink: 0, marginLeft: "4px" }}
            title="Expand"
          >
            {rightSidebarWidth === 9999 ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" /></svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></svg>
            )}
          </button>

          <button
            onClick={() => {
              if (setShowRightSidebar) setShowRightSidebar(false);
              setTimeout(() => setPreviewArtifact(null), 300);
            }}
            style={{ background: darkMode ? "rgba(239,68,68,0.1)" : "rgba(239,68,68,0.05)", border: `1px solid ${darkMode ? "rgba(239,68,68,0.2)" : "rgba(239,68,68,0.15)"}`, color: "#ef4444", padding: "6px", borderRadius: "8px", cursor: "pointer", display: "flex", flexShrink: 0, marginLeft: "4px" }}
            title={t.closePanel}
          >
            <IconClose />
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", background: darkMode ? '#1a1b1d' : '#ffffff', display: 'flex', flexDirection: 'column' }} className="premium-scroll">
        {isArtifactLoading ? (
          <div style={{ padding: "60px 24px", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", color: "#64748b" }}>
            <div style={{ width: "24px", height: "24px", border: "2px solid rgba(99,102,241,0.1)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "rotate-spin 0.6s linear infinite" }} />
            <span style={{ fontSize: "12px" }}>{t.loadingArtifact}</span>
          </div>
        ) : (
          isMarkdownOrText ? (
            <div style={{ padding: "24px", color: theme.textColor }}>
              <CakraResponseRenderer rawContent={content} thinkingContent="" isStreaming={false} darkMode={darkMode} theme={theme} searchQuery="" statusMessage="" />
            </div>
          ) : (
            <div style={{ padding: "20px", display: "flex", flexDirection: "column", height: "100%", minHeight: "600px" }}>
              <div style={{
                background: '#1e1e1e',
                borderRadius: '12px',
                overflow: 'hidden',
                boxShadow: darkMode ? '0 8px 30px rgba(0,0,0,0.4)' : '0 10px 40px rgba(0,0,0,0.15)',
                border: darkMode ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.05)',
                display: 'flex',
                flexDirection: 'column',
                flex: 1
              }}>
                {/* MAC OS HEADER */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#2d2d2d', padding: '10px 16px', position: 'relative' }}>
                  {/* TAB TOGGLE: VIEW UI & SOURCE CODE (Dipindah ke kiri) */}
                  {isUIPreviewable ? (
                    <div style={{ display: 'flex', background: '#1e1e1e', borderRadius: '6px', padding: '3px' }}>
                      <button
                        onClick={() => setViewMode('preview')}
                        style={{
                          background: viewMode === 'preview' ? '#3b82f6' : 'transparent',
                          color: viewMode === 'preview' ? '#ffffff' : '#94a3b8',
                          padding: '4px 12px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, cursor: 'pointer', border: 'none',
                          display: 'flex', alignItems: 'center', gap: '6px',
                          transition: 'all 0.2s',
                          boxShadow: viewMode === 'preview' ? '0 1px 2px rgba(0,0,0,0.2)' : 'none'
                        }}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>

                      </button>
                      <button
                        onClick={() => setViewMode('code')}
                        style={{
                          background: viewMode === 'code' ? '#3b82f6' : 'transparent',
                          color: viewMode === 'code' ? '#ffffff' : '#94a3b8',
                          padding: '4px 12px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, cursor: 'pointer', border: 'none',
                          display: 'flex', alignItems: 'center', gap: '6px',
                          transition: 'all 0.2s',
                          boxShadow: viewMode === 'code' ? '0 1px 2px rgba(0,0,0,0.2)' : 'none'
                        }}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></svg>

                      </button>
                    </div>
                  ) : (
                    <div></div>
                  )}

                  {/* Nama File selalu di kanan */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <span style={{ fontSize: '11px', color: '#a0a0a0', fontFamily: 'monospace', fontWeight: 500, letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>{previewArtifact.filename}</span>
                  </div>
                </div>

                {/* CONTENT AREA */}
                <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', background: viewMode === 'preview' ? (darkMode ? '#1e1e1e' : '#ffffff') : '#1e1e1e' }}>
                  {isUIPreviewable && viewMode === 'preview' ? (
                    /* --- LIVE SANDBOX PREVIEW --- */
                    <div style={{ flex: 1, width: "100%", height: "100%" }}>
                      <React.Suspense fallback={<div style={{ padding: "40px", color: "#64748b", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                        <div style={{ width: "20px", height: "20px", border: "2px solid rgba(99,102,241,0.2)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "rotate-spin 0.6s linear infinite" }} />
                        <span>Loading Engine...</span>
                      </div>}>
                        <CodeSandboxViewer code={content} language={ext === 'html' ? 'html' : 'react'} darkMode={darkMode} />
                      </React.Suspense>
                    </div>
                  ) : (
                    /* --- SOURCE CODE HIGHLIGHTER --- */
                    <div style={{ padding: '16px 0', flex: 1 }}>
                      <SyntaxHighlighter
                        language={ext} style={vscDarkPlus}
                        customStyle={{ margin: 0, padding: '0 16px', background: 'transparent', fontSize: '12px', fontFamily: '"Fira Code", "JetBrains Mono", monospace', lineHeight: '1.6' }}
                        showLineNumbers={true} wrapLines={false}
                      >
                        {content}
                      </SyntaxHighlighter>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        )}
      </div>

      <div style={{ padding: "8px 20px", background: darkMode ? '#151618' : '#f8fafc', fontSize: "11px", color: "#64748b", fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between', borderTop: `1px solid ${darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` }}>
        <span>LINES: {previewArtifact.lines_count ? previewArtifact.lines_count : (artifactContent || previewArtifact.code || '').split('\n').length}</span>
        <span>CHARS: {(artifactContent || previewArtifact.code || '').length}</span>
      </div>
    </div>
  );
}
