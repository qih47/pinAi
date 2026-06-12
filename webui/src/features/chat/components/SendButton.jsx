import React from 'react';
import { getSendButtonStyles } from '../chatPage.styles';

export default function SendButton({ isStreaming, isUploadingFile, input, selectedFiles, theme }) {
  const buttonStyles = getSendButtonStyles(isStreaming, isUploadingFile, input, selectedFiles, theme);
  const isDisabled = isStreaming || isUploadingFile || (!input.trim() && selectedFiles.length === 0);

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
