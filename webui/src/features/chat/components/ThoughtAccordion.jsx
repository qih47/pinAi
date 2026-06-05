// src/features/chat/components/ThoughtAccordion.jsx
import React, { useState } from 'react';

const ThoughtAccordion = ({ thought, darkMode, theme }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  if (!thought) return null;

  const toggleOpen = () => setIsOpen(prev => !prev);

  const accordionStyle = {
    marginBottom: '16px',
    borderRadius: '12px',
    background: darkMode ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
    border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)'}`,
    overflow: 'hidden',
    transition: 'all 0.2s ease'
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 16px',
    cursor: 'pointer',
    background: isHovered
      ? darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)'
      : 'transparent',
    transition: 'background 0.2s',
    userSelect: 'none'
  };

  const iconStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'transform 0.25s ease',
    transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)'
  };

  const titleStyle = {
    fontSize: '13px',
    fontWeight: 500,
    color: theme?.secondaryText || (darkMode ? '#9ca3af' : '#6b7280'),
    letterSpacing: '0.3px'
  };

  const contentStyle = {
    padding: isOpen ? '0 16px 16px 16px' : '0 16px',
    maxHeight: isOpen ? '1000px' : '0',
    opacity: isOpen ? 1 : 0,
    overflow: 'hidden',
    transition: 'max-height 0.35s cubic-bezier(0.33, 1, 0.68, 1), opacity 0.25s ease, padding 0.2s',
    fontSize: '13.5px',
    lineHeight: '1.6',
    color: theme?.textColor || (darkMode ? '#cbd5e1' : '#374151'),
    borderTop: isOpen ? `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)'}` : 'none',
    marginTop: isOpen ? '8px' : '0'
  };

  return (
    <div style={accordionStyle}>
      <div
        style={headerStyle}
        onClick={toggleOpen}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
      >
        <span style={iconStyle}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </span>
        <span style={titleStyle}>🧠 Proses berpikir CAKRA</span>
      </div>
      <div style={contentStyle}>
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {thought}
        </div>
      </div>
    </div>
  );
};

export default ThoughtAccordion;