// src/features/chat/components/SourceCitation.jsx
import React, { useState } from 'react';

const SourceCitation = ({ sources, darkMode, theme, onPreview }) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (!sources || sources.length === 0) return null;

  const handleClick = (source, idx) => {
    if (onPreview) {
      onPreview(source);
    } else {
      // fallback: open in new tab if source has url
      if (source.url) window.open(source.url, '_blank');
    }
  };

  const containerStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '10px',
    marginTop: '16px',
    marginBottom: '8px'
  };

  const cardStyle = (isHovered) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 14px',
    background: darkMode
      ? isHovered ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.04)'
      : isHovered ? 'rgba(99, 102, 241, 0.08)' : 'rgba(0, 0, 0, 0.03)',
    borderRadius: '40px',
    border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)'}`,
    fontSize: '12px',
    fontWeight: 500,
    color: theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937'),
    cursor: 'pointer',
    transition: 'all 0.2s cubic-bezier(0.2, 0.9, 0.4, 1.1)',
    transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
    boxShadow: isHovered ? (darkMode ? '0 4px 12px rgba(0,0,0,0.3)' : '0 2px 8px rgba(0,0,0,0.08)') : 'none'
  });

  const iconStyle = {
    width: '14px',
    height: '14px',
    opacity: 0.7
  };

  const textStyle = {
    maxWidth: '200px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  };

  const pageBadge = (page) => page ? ` (hal. ${page})` : '';

  return (
    <div style={containerStyle}>
      {sources.map((src, idx) => {
        const title = src.title || src.filename || src.name || 'Dokumen';
        const page = src.page || src.page_number;
        const isHovered = hoveredIndex === idx;
        return (
          <div
            key={`source-${idx}`}
            style={cardStyle(isHovered)}
            onClick={() => handleClick(src, idx)}
            onMouseEnter={() => setHoveredIndex(idx)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <span style={iconStyle}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </span>
            <span style={textStyle} title={title + pageBadge(page)}>
              {title}{pageBadge(page)}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default SourceCitation;