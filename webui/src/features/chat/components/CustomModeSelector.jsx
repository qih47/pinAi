import React from 'react';
import { Brain } from 'lucide-react';
import { translations } from '../../../utils/translations';

/**
 * ThinkButton (replacing legacy CustomModeSelector)
 * ChatGPT-style Deep Thinking toggle button (Brain icon + 'Think' text).
 * Sits cleanly alongside VoiceButton & SendButton.
 */
export default function CustomModeSelector({ 
  disabled = false, 
  darkMode = true,
  thinking = true,           
  onThinkingChange,
  language = 'id'
}) {
  const isThinkingActive = Boolean(thinking);
  const t = translations[language]?.chatInput || translations.id.chatInput;

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && onThinkingChange) {
      onThinkingChange(!isThinkingActive);
    }
  };

  const titleText = t.thinkTooltip || "Dapatkan jawaban yang lebih cerdas";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      title={titleText}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "6px",
        height: "36px",
        padding: "0 12px",
        borderRadius: "9999px",
        fontSize: "13px",
        fontWeight: isThinkingActive ? "600" : "500",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all 0.18s cubic-bezier(0.4, 0, 0.2, 1)",
        userSelect: "none",
        outline: "none",
        border: "none",
        boxShadow: "none",
        background: "transparent",
        color: isThinkingActive
          ? (darkMode ? "#38bdf8" : "#0284c7")
          : (darkMode ? "#9ca3af" : "#6b7280"),
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = darkMode 
            ? "rgba(255, 255, 255, 0.06)" 
            : "rgba(0, 0, 0, 0.05)";
          e.currentTarget.style.color = isThinkingActive 
            ? (darkMode ? "#7dd3fc" : "#0369a1") 
            : (darkMode ? "#e5e7eb" : "#1f2937");
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = isThinkingActive 
            ? (darkMode ? "#38bdf8" : "#0284c7") 
            : (darkMode ? "#9ca3af" : "#6b7280");
        }
      }}
    >
      <Brain 
        size={16} 
        strokeWidth={isThinkingActive ? 2.2 : 1.8}
        style={{
          transition: "transform 0.2s ease, color 0.2s ease",
          transform: isThinkingActive ? "scale(1.06)" : "scale(1)",
          color: isThinkingActive 
            ? (darkMode ? "#38bdf8" : "#0284c7") 
            : (darkMode ? "#9ca3af" : "#6b7280"),
          flexShrink: 0
        }} 
      />
      <span style={{ letterSpacing: "-0.01em", lineHeight: "1" }}>
        {t.thinkButton || "Think"}
      </span>
    </button>
  );
}

export { CustomModeSelector as ThinkButton };