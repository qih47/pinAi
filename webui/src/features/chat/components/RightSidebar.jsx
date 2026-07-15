import React, { useState } from "react";
import useToast from "../../../hooks/useToast";
import DocumentPreviewTab from "./RightSidebarTabs/DocumentPreviewTab";
import ArtifactPreviewTab from "./RightSidebarTabs/ArtifactPreviewTab";
import WorkspaceExplorerTab from "./RightSidebarTabs/WorkspaceExplorerTab";
import { translations } from "../../../utils/translations";

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
  handleDownloadArtifact,
  handleDownloadAllArtifacts,
  setPreviewImage,
  setShowRightSidebar,
  language
}) {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState("workspace");
  const t = translations[language]?.rightSidebar || translations.id.rightSidebar;
  const isPreviewMode = !!(previewDoc || previewArtifact);

  const baseBgColor = darkMode ? "#1e1f22" : "#ffffff";
  const containerBgColor = darkMode ? "#161719" : "#f8fafc";
  const borderStyleColor = darkMode ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.08)";

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
        .premium-scroll::-webkit-scrollbar-button { display: none !important; width: 0 !important; height: 0 !important; -webkit-appearance: none !important; }
        .premium-scroll::-webkit-scrollbar-thumb { background: ${darkMode ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)"}; border-radius: 10px; }
        .premium-scroll::-webkit-scrollbar-thumb:hover { background: ${darkMode ? "rgba(255,255,255,0.25)" : "rgba(0,0,0,0.25)"}; }
        .premium-scroll::-webkit-scrollbar-corner { background: transparent; }
        .premium-scroll::-webkit-scrollbar-corner { background: transparent; }
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
        <DocumentPreviewTab
          previewDoc={previewDoc}
          setPreviewDoc={setPreviewDoc}
          docContent={docContent}
          isDocLoading={isDocLoading}
          setActiveTab={setActiveTab}
          theme={theme}
          language={language}
          t={t}
          darkMode={darkMode}
          setShowRightSidebar={setShowRightSidebar}
          toast={toast}
          borderStyleColor={borderStyleColor}
          baseBgColor={baseBgColor}
          containerBgColor={containerBgColor}
        />
      ) : previewArtifact ? (
        // ── MODE 2: ARTIFACT CODE VIEW ──
        <ArtifactPreviewTab
          previewArtifact={previewArtifact}
          setPreviewArtifact={setPreviewArtifact}
          artifactContent={artifactContent}
          isArtifactLoading={isArtifactLoading}
          theme={theme}
          language={language}
          t={t}
          darkMode={darkMode}
          toast={toast}
          containerBgColor={containerBgColor}
          setShowRightSidebar={setShowRightSidebar}
        />
      ) : (
        // ── MODE 3: WORKSPACE FILE HUB ──
        <WorkspaceExplorerTab
          theme={theme}
          darkMode={darkMode}
          artifacts={artifacts}
          sessionAttachments={sessionAttachments}
          handleOpenArtifact={handleOpenArtifact}
          handleDownloadArtifact={handleDownloadArtifact}
          handleDownloadAllArtifacts={handleDownloadAllArtifacts}
          setPreviewImage={setPreviewImage}
          setPreviewDoc={setPreviewDoc}
          borderStyleColor={borderStyleColor}
          language={language}
          t={t}
        />
      )}
    </aside>
  );
}