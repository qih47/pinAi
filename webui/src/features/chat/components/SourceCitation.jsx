// src/features/chat/components/SourceCitation.jsx
import React, { useState } from 'react';

import { useChatStore } from '../../../stores/chatStore';
import { getUploadUrl } from '../../../services/endpoints';

const SourceCitation = ({ sources, darkMode, theme, onPreview, onActivateIsolation, activeIsolatedDocId }) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const setSplitScreen = useChatStore(state => state.setSplitScreen);

  if (!sources || sources.length === 0) return null;

  const handleView = (e, source) => {
    e.stopPropagation(); // Mencegah trigger click card utama
    const rawPath = source.url || source.file_path;
    const fileUrl = rawPath ? getUploadUrl(rawPath) : null;
    
    // Aktifkan Split Screen Mode
    if (fileUrl) {
      setSplitScreen(true, fileUrl);
    } else if (onPreview) {
      onPreview(source);
    }
  };

  const handleChatIsolation = (e, source) => {
    e.stopPropagation(); // Mencegah trigger click card utama
    if (onActivateIsolation) {
      // Pemicu callback menuju chatStore untuk mengunci context ke id dokumen ini
      // Harus menggunakan setState({ chatMode: 'focus' })
      useChatStore.setState({ chatMode: 'focus' });
      onActivateIsolation(source);
    }
  };

  const handleComplianceIsolation = (e, source) => {
    e.stopPropagation(); 
    if (onActivateIsolation) {
      // Set mode ke compliance sebelum isolasi
      useChatStore.setState({ chatMode: 'compliance' });
      onActivateIsolation(source);
    }
  };

  const handleRedTeamIsolation = (e, source) => {
    e.stopPropagation(); 
    if (onActivateIsolation) {
      // Set mode ke redteam sebelum isolasi
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
    marginBottom: '50px',
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
    border: `1px solid ${
      isCurrentlyIsolated 
        ? '#6366f1' 
        : (darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)')
    }`,
    transition: 'all 0.2s cubic-bezier(0.2, 0.9, 0.4, 1.1)',
    transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
    boxShadow: isHovered ? (darkMode ? '0 6px 16px rgba(0,0,0,0.4)' : '0 4px 12px rgba(0,0,0,0.06)') : 'none',
    position: 'relative',
    overflow: 'hidden'
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
    gap: '8px',
    width: '100%'
  };

  const btnStyle = (isPrimary, isHovered) => ({
    flex: 1,
    padding: '4px 6px',
    borderRadius: '12px',
    fontSize: '10px',
    fontWeight: 600,
    textAlign: 'center',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
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
        const page = src.page || src.page_number;
        const isHovered = hoveredIndex === idx;
        
        // Cek apakah kartu ini adalah dokumen yang sedang dikunci/diisolasi mode chat-nya
        const isCurrentlyIsolated = activeIsolatedDocId === docId;

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
                  <span>{regNomor} {page ? `• Hal. ${page}` : ''} {src.jumlah_halaman ? `• Total ${src.jumlah_halaman} Hal` : ''}</span>
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

            {/* Barisan Tombol Aksi Mandiri */}
            <div style={actionsWrapStyle}>
              <button
                type="button"
                onClick={(e) => handleView(e, src)}
                style={btnStyle(false, isHovered)}
              >
                👁️ PDF
              </button>
              <button
                type="button"
                onClick={(e) => handleChatIsolation(e, src)}
                style={btnStyle(true, isHovered)}
              >
                {isCurrentlyIsolated && useChatStore.getState().chatMode !== 'compliance' ? '🔒 Fokus' : '💬 Tanya'}
              </button>
              <button
                type="button"
                onClick={(e) => handleComplianceIsolation(e, src)}
                style={{
                  ...btnStyle(true, isHovered),
                  background: isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ef4444' : (darkMode ? 'rgba(239, 68, 68, 0.15)' : 'rgba(239, 68, 68, 0.1)'),
                  color: isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ffffff' : (darkMode ? '#fca5a5' : '#b91c1c'),
                  border: `1px solid ${isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '#ef4444' : (darkMode ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.2)')}`,
                }}
              >
                {isCurrentlyIsolated && useChatStore.getState().chatMode === 'compliance' ? '🔒 Kepatuhan' : '⚖️ Kepatuhan'}
              </button>
              <button
                type="button"
                onClick={(e) => handleRedTeamIsolation(e, src)}
                style={{
                  ...btnStyle(true, isHovered),
                  background: isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#f97316' : (darkMode ? 'rgba(249, 115, 22, 0.15)' : 'rgba(249, 115, 22, 0.1)'),
                  color: isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#ffffff' : (darkMode ? '#fdba74' : '#c2410c'),
                  border: `1px solid ${isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '#f97316' : (darkMode ? 'rgba(249, 115, 22, 0.3)' : 'rgba(249, 115, 22, 0.2)')}`,
                }}
              >
                {isCurrentlyIsolated && useChatStore.getState().chatMode === 'redteam' ? '🔒 Red-Team' : '🕵️ Bedah'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SourceCitation;