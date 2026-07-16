import React from 'react';
import { getSendButtonStyles } from '../chatPage.styles';
import { translations } from '../../../utils/translations';

export default function SendButton({ isStreaming, isUploadingFile, input, selectedFiles, theme, onStop, language = 'id' }) {
  const tGlobal = translations[language] || translations.id;
  const buttonStyles = getSendButtonStyles(isStreaming, isUploadingFile, input, selectedFiles, theme);
  const isDisabled = isUploadingFile || (!isStreaming && !input.trim() && selectedFiles.length === 0);

  if (isStreaming) {
    return (
      <button
        type="button"
        onClick={onStop}
        style={{ ...buttonStyles.button, background: '#ef4444', opacity: 1, cursor: 'pointer' }}
        title={tGlobal.chat.stopResponse}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2" ry="2" />
        </svg>
      </button>
    );
  }

  return (
    <button
      type="submit"
      disabled={isDisabled}
      style={buttonStyles.button}
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
        <line x1="12" y1="19" x2="12" y2="5" />
        <polyline points="5 12 12 5 19 12" />
      </svg>
    </button>
  );
}
