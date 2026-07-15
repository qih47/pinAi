import React from "react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CakraResponseRenderer from "../CakraResponseRenderer";
import { IconChevronLeft, IconCopy, IconClose, getArtifactFileIcon } from "./RightSidebarIcons";

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
  t
}) {
  const ext = previewArtifact?.filename?.split('.').pop()?.toLowerCase();
  const isMarkdownOrText = ext === 'md' || ext === 'txt';
  const content = artifactContent || previewArtifact.code || '// Void Content';

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
              const code = artifactContent || previewArtifact.code || '';
              navigator.clipboard.writeText(code).then(() => toast.success("Kode disalin!"));
            }}
            style={{ background: darkMode ? "rgba(255,255,255,0.04)" : "#ffffff", border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`, color: theme.textColor, padding: "6px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "12px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}
          >
            <IconCopy size={13} /> {t.copy}
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

      <div style={{ flex: 1, overflow: "auto", background: darkMode ? '#1a1b1d' : '#ffffff' }} className="premium-scroll">
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
            <div style={{ padding: "20px" }}>
              <div style={{ 
                  background: '#1e1e1e',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  boxShadow: darkMode ? '0 8px 30px rgba(0,0,0,0.4)' : '0 10px 40px rgba(0,0,0,0.15)',
                  border: darkMode ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.05)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#2d2d2d', padding: '10px 16px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span style={{ width: '11px', height: '11px', borderRadius: '50%', background: '#ff5f56' }} />
                    <span style={{ width: '11px', height: '11px', borderRadius: '50%', background: '#ffbd2e' }} />
                    <span style={{ width: '11px', height: '11px', borderRadius: '50%', background: '#27c93f' }} />
                  </div>
                  <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#a0a0a0', fontFamily: 'monospace', fontWeight: 500, letterSpacing: '0.5px' }}>{previewArtifact.filename}</span>
                </div>
                <div style={{ padding: '16px 0' }}>
                  <SyntaxHighlighter
                    language={ext} style={vscDarkPlus}
                    customStyle={{ margin: 0, padding: '0 16px', background: 'transparent', fontSize: '12px', fontFamily: '"Fira Code", "JetBrains Mono", monospace', lineHeight: '1.6' }}
                    showLineNumbers={true} wrapLines={false}
                  >
                    {content}
                  </SyntaxHighlighter>
                </div>
              </div>
            </div>
          )
        )}
      </div>

      <div style={{ padding: "8px 20px", background: darkMode ? '#151618' : '#f8fafc', fontSize: "11px", color: "#64748b", fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between' }}>
        <span>LINES: {previewArtifact.lines_count ? previewArtifact.lines_count : (artifactContent || previewArtifact.code || '').split('\n').length}</span>
        <span>CHARS: {(artifactContent || previewArtifact.code || '').length}</span>
      </div>
    </div>
  );
}
