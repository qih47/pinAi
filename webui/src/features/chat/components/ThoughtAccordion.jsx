import React, { useState } from 'react';
import { translations, resolveStatusMessage } from '../../../utils/translations';

const ThoughtAccordion = ({ thought, darkMode, theme, statusMessage, isStreaming, language = 'id' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  if (!thought || !thought.trim()) return null;

  const toggleOpen = () => setIsOpen(prev => !prev);

  // Bersihkan sisa tag jika ada kebocoran string pembungkus
  const cleanThought = thought
    .replace(/<think>/g, '')
    .replace(/<\/think>/g, '')
    .trim();

  if (
    !cleanThought ||
    cleanThought.length < 5 ||
    cleanThought.includes("Gemma Agentic") ||
    cleanThought.includes("Mode:") ||
    cleanThought === "Sedang memproses..." ||
    cleanThought === "Thinking" ||
    cleanThought === "Thinking..." ||
    cleanThought === "Thinking Done"
  ) {
    return null;
  }

  const accordionStyle = {
    marginBottom: '14px',
    borderRadius: '12px',
    // background: darkMode ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
    overflow: 'hidden',
    transition: 'all 0.2s ease',
    // border: darkMode ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.03)'
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '12px 16px',
    cursor: 'pointer',
    // background: isHovered
    //   ? (darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)')
    //   : 'transparent',
    transition: 'background 0.2s ease',
    userSelect: 'none'
  };

  const iconStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: isOpen ? (theme?.accentColor || '#3b82f6') : (darkMode ? '#9ca3af' : '#6b7280'),
    transition: 'transform 0.2s ease, color 0.2s',
    transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)'
  };

  const titleStyle = {
    fontSize: '12px',
    fontWeight: 500,
    color: isOpen 
      ? (darkMode ? '#f3f4f6' : '#1f2937')
      : (theme?.secondaryText || (darkMode ? '#9ca3af' : '#6b7280')),
    letterSpacing: '0.3px',
    transition: 'color 0.2s'
  };

  const contentStyle = {
    padding: isOpen ? '4px 16px 16px 16px' : '0 16px',
    maxHeight: isOpen ? '2000px' : '0',
    opacity: isOpen ? 1 : 0,
    overflow: 'hidden',
    transition: 'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease, padding 0.2s',
    fontSize: '12px',
    lineHeight: '1.6', 
    color: theme?.textColor || (darkMode ? '#94a3b8' : '#4b5563'),
    borderTop: isOpen ? (darkMode ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.03)') : 'none'
  };

  const sseDict = translations[language]?.sseStatus || translations.id.sseStatus || {};
  const titleText = !isStreaming 
    ? (sseDict.THINKING_DONE || 'Thinking Done') 
    : (statusMessage ? resolveStatusMessage(statusMessage, language) : (sseDict.THINKING_DEFAULT || 'Thinking'));

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
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleOpen();
          }
        }}
      >
        <span style={iconStyle}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </span>
        <span style={titleStyle}>🧠 {titleText} </span>
      </div>
      <div style={contentStyle}>
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', letterSpacing: '0.1px', fontStyle: 'italic' }}>
          {cleanThought}
        </div>
      </div>
    </div>
  );
};

export default ThoughtAccordion;