// src/features/chat/components/SourceCitation.jsx
import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';

import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl } from '../../../services/endpoints';
import { translations } from '../../../utils/translations';

const ModeHintIcon = ({ title, hintText, icon, darkMode }) => {
  const [show, setShow] = useState(false);
  const triggerRef = useRef(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const handleMouseEnter = (e) => {
    e.stopPropagation();
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setCoords({
        top: rect.top - 6,
        left: rect.left + rect.width / 2,
      });
    }
    setShow(true);
  };

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => { e.stopPropagation(); setShow(false); }}
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'absolute',
          right: '4px',
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
            width: '220px',
            padding: '8px 10px',
            borderRadius: '8px',
            fontSize: '11px',
            lineHeight: '1.4',
            textAlign: 'left',
            pointerEvents: 'none',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5), 0 8px 10px -6px rgba(0,0,0,0.4)',
            background: darkMode ? '#1e293b' : '#ffffff',
            color: darkMode ? '#f1f5f9' : '#0f172a',
            border: `1px solid ${darkMode ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)'}`,
            backdropFilter: 'blur(10px)',
          }}
        >
          {title && (
            <div style={{ fontWeight: 700, marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '4px', color: darkMode ? '#93c5fd' : '#2563eb' }}>
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

const SourceCitation = ({ sources, darkMode, theme, language = 'id', onPreview, onActivateIsolation, activeIsolatedDocId }) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const setSplitScreen = useChatStore(state => state.setSplitScreen);
  const t = translations[language]?.chat || translations.id.chat;

  if (!sources || sources.length === 0) return null;

  const handleView = (e, source) => {
    e.stopPropagation();
    const rawPath = source.url || source.file_path;
    const fileUrl = rawPath ? getUploadUrl(rawPath) : null;

    if (fileUrl) {
      setSplitScreen(true, fileUrl);
    } else if (onPreview) {
      onPreview(source);
    }
  };

  const handleChatIsolation = (e, source) => {
    e.stopPropagation();
    if (onActivateIsolation) {
      useChatStore.setState({ chatMode: 'focus' });
      onActivateIsolation(source);
    }
  };

  const handleComplianceIsolation = (e, source) => {
    e.stopPropagation();
    if (onActivateIsolation) {
      useChatStore.setState({ chatMode: 'compliance' });
      onActivateIsolation(source);
    }
  };

  const handleRedTeamIsolation = (e, source) => {
    e.stopPropagation();
    if (onActivateIsolation) {
      useChatStore.setState({ chatMode: 'redteam' });
      onActivateIsolation(source);
    }
  };

  // Sasis utama grid layout responsif penampung kartu dokumen
  const containerStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '12px',
    marginTop: '16px',
    marginBottom: '20px',
    width: '100%'
  };

  const cardStyle = (isHovered, isCurrentlyIsolated) => ({
    display: 'flex',
    flexDirection: 'column',
    padding: '12px 14px',
    background: darkMode
      ? isCurrentlyIsolated ? 'rgba(99, 102, 241, 0.2)' : (isHovered ? 'rgba(255, 255, 255, 0.06)' : '#1E1E20')
      : isCurrentlyIsolated ? 'rgba(99, 102, 241, 0.1)' : (isHovered ? 'rgba(0, 0, 0, 0.04)' : '#F3F4F6'),
    borderRadius: '16px',
    border: `1px solid ${isCurrentlyIsolated
      ? '#6366f1'
      : (darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)')
      }`,
    transition: 'all 0.2s cubic-bezier(0.2, 0.9, 0.4, 1.1)',
    transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
    boxShadow: isHovered ? (darkMode ? '0 6px 16px rgba(0,0,0,0.4)' : '0 4px 12px rgba(0,0,0,0.06)') : 'none',
    position: 'relative',
    overflow: 'visible'
  });

  const headerRowStyle = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    width: '100%',
    marginBottom: '6px'
  };

  const iconStyle = {
    fontSize: '16px',
    flexShrink: 0,
    marginTop: '2px'
  };

  const infoWrapStyle = {
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
    flex: 1
  };

  const titleStyle = {
    fontSize: '13px',
    fontWeight: 600,
    color: theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937'),
    whiteSpace: 'normal',
    wordBreak: 'break-word',
    lineHeight: '1.4'
  };

  const metaStyle = {
    fontSize: '11px',
    color: theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280'),
    marginTop: '2px',
    fontWeight: 500
  };

  const dividerStyle = {
    height: '1px',
    background: darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
    width: '100%',
    margin: '10px 0'
  };

  const actionsWrapStyle = {
    display: 'flex',
    gap: '6px',
    width: '100%',
    flexWrap: 'nowrap'
  };

  const btnStyle = (isPrimary, isHovered, hasHint = false, flexRatio = 1) => ({
    flex: flexRatio,
    minWidth: 0,
    position: 'relative',
    padding: hasHint ? '4px 13px 4px 6px' : '4px 5px',
    borderRadius: '12px',
    fontSize: '10px',
    fontWeight: 600,
    textAlign: 'center',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: isPrimary ? 'none' : `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)'}`,
    background: isPrimary
      ? (darkMode ? '#6366f1' : '#2563eb')
      : (darkMode ? 'rgba(255,255,255,0.02)' : '#ffffff'),
    color: isPrimary
      ? '#ffffff'
      : (theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937')),
    transition: 'opacity 0.15s ease',
    opacity: isHovered ? 0.85 : 1
  });

  return (
    <div style={containerStyle}>
      {sources.map((src, idx) => {
        const title = src.title || src.filename || src.name || 'Dokumen';
        const docId = src.id || src.dokumen_id;
        const regNomor = src.nomor || 'No Regulasi ----';
        const page = src.page || src.page_number || src.halaman;
        const isHovered = hoveredIndex === idx;

        const isCurrentlyIsolated = activeIsolatedDocId && (
          String(activeIsolatedDocId) === String(docId) ||
          String(activeIsolatedDocId) === String(src.doc_id) ||
          (src.title && activeIsolatedDocId === src.title)
        );

        return (
          <div
            key={`source-card-${idx}`}
            style={cardStyle(isHovered, isCurrentlyIsolated)}
            onMouseEnter={() => setHoveredIndex(idx)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            {/* Informasi Utama Dokumen */}
            <div style={headerRowStyle}>
              <span style={iconStyle}>📄</span>
              <div style={infoWrapStyle}>
                <span style={titleStyle} title={title}>
                  {title}
                </span>
                <span style={{
                  ...metaStyle,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  flexWrap: 'wrap'
                }}>
                  <span style={{
                    background: darkMode ? 'rgba(99, 102, 241, 0.2)' : 'rgba(37, 99, 235, 0.1)',
                    color: darkMode ? '#a5b4fc' : '#1e40af',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '9px',
                    fontWeight: 700,
                    textTransform: 'uppercase'
                  }}>
                    {src.jenis || 'Regulasi'}
                  </span>
                  <span>{regNomor} {src.total_pages ? `• ${src.total_pages} ${t.pages}` : (page ? `• ${t.pageAbbrev} ${page}` : '')}</span>
                </span>

                {/* Tampilkan Daftar BAB/Pasal jika ada */}
                {src.sections && src.sections.length > 0 && (
                  <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '4px',
                    marginTop: '6px'
                  }}>
                    {src.sections.slice(0, 3).map((sec, sIdx) => (
                      <span key={sIdx} style={{
                        background: darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '9px',
                        color: theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937')
                      }}>
                        {sec}
                      </span>
                    ))}
                    {src.sections.length > 3 && (
                      <span style={{ fontSize: '9px', color: metaStyle.color, alignSelf: 'center' }}>
                        +{src.sections.length - 3} lagi
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Garis Sekat Pembatas */}
            <div style={dividerStyle} />

            {/* Barisan Tombol Aksi Mandiri (Proporsional Lebar Teks) */}
            <div style={actionsWrapStyle}>
              <button
                type="button"
                onClick={(e) => handleView(e, src)}
                style={btnStyle(false, isHovered, false, 0.7)}
              >
                👁️ PDF
              </button>
              <button
                type="button"
                onClick={(e) => handleChatIsolation(e, src)}
                style={btnStyle(true, isHovered, true, 0.85)}
              >
                <span>{isCurrentlyIsolated && useChatStore.getState().chatMode !== 'compliance' ? '🔒 Fokus' : `💬 ${t.tanyaBtn}`}</span>
                <ModeHintIcon 
                  title={t.tanyaHintTitle} 
                  hintText={t.tanyaHint} 
                  icon="💬" 
                  darkMode={darkMode} 
                />
              </button>
              <button
                type="button"
                onClick={(e) => handleComplianceIsolation(e, src)}
                style={{
                  ...btnStyle(true, isHovered, true, 1.35),
                  background: isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ef4444' : (darkMode ? 'rgba(239, 68, 68, 0.15)' : 'rgba(239, 68, 68, 0.1)'),
                  color: isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ffffff' : (darkMode ? '#fca5a5' : '#b91c1c'),
                  border: `1px solid ${isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ef4444' : (darkMode ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.2)')}`,
                }}
              >
                <span>{isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? `🔒 ${t.kepatuhanBtn}` : `⚖️ ${t.kepatuhanBtn}`}</span>
                <ModeHintIcon 
                  title={t.kepatuhanHintTitle} 
                  hintText={t.kepatuhanHint} 
                  icon="⚖️" 
                  darkMode={darkMode} 
                />
              </button>
              <button
                type="button"
                onClick={(e) => handleRedTeamIsolation(e, src)}
                style={{
                  ...btnStyle(true, isHovered, true, 1.15),
                  background: isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#f97316' : (darkMode ? 'rgba(249, 115, 22, 0.15)' : 'rgba(249, 115, 22, 0.1)'),
                  color: isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#ffffff' : (darkMode ? '#fdba74' : '#c2410c'),
                  border: `1px solid ${isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#f97316' : (darkMode ? 'rgba(249, 115, 22, 0.3)' : 'rgba(249, 115, 22, 0.2)')}`,
                }}
              >
                <span>{isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '🔒 Red-Team' : `🕵️ ${t.bedahBtn}`}</span>
                <ModeHintIcon 
                  title={t.bedahHintTitle} 
                  hintText={t.bedahHint} 
                  icon="🕵️" 
                  darkMode={darkMode} 
                />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SourceCitation;