import React from 'react';
import { getPlusButtonStyles } from '../chatPage.styles';

export default function PlusButton({ onClick, disabled, selectedFiles, darkMode, isStreaming }) {
  const buttonStyles = getPlusButtonStyles(darkMode, selectedFiles, disabled);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={buttonStyles.button}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = darkMode
            ? 'rgba(255,255,255,0.08)'
            : 'rgba(0,0,0,0.05)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background =
          selectedFiles.length > 0
            ? darkMode
              ? 'rgba(99, 102, 241, 0.2)'
              : 'rgba(37, 99, 235, 0.1)'
            : 'transparent';
      }}
      title="Lampirkan Berkas (PDF / Gambar) atau Paste (Ctrl+V) atau Drag-Drop"
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    </button>
  );
}
