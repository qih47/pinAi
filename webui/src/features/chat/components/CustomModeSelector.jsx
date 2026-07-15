import React, { useState, useRef, useEffect } from 'react';
import { getCustomModeSelectorStyles } from '../chatPage.styles';
import { translations } from '../../../utils/translations';

export default function CustomModeSelector({ 
  value, 
  onChange, 
  disabled, 
  darkMode,
  thinking,           
  onThinkingChange,
  language
}) {
  const t = translations[language]?.chatInput || translations.id.chatInput;
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const options = [
    { value: 'auto', label: t.autoMode },
    { value: 'flash', label: t.flashMode },
    { value: 'documents', label: t.docMode }
  ];

  const selectedOption = options.find((opt) => opt.value === value);
  const selectorStyles = getCustomModeSelectorStyles(darkMode, disabled);

  return (
    <div ref={dropdownRef} style={selectorStyles.container}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        style={selectorStyles.button}
        onMouseEnter={(e) => {
          if (!disabled) {
            e.currentTarget.style.background = darkMode
              ? 'rgba(255,255,255,0.08)'
              : 'rgba(0,0,0,0.05)';
          }
        }}
        onMouseLeave={(e) => {
          if (!disabled) {
            e.currentTarget.style.background = darkMode
              ? 'rgba(255,255,255,0.03)'
              : 'rgba(0,0,0,0.02)';
          }
        }}
      >
        <span>{selectedOption?.label}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s'
          }}
        >
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>

      {isOpen && (
        <div style={{...selectorStyles.dropdown, minWidth: '220px'}}>
          {/* List Options */}
          {options.map((option) => {
            const isSelected = value === option.value;
            const itemStyle = selectorStyles.item(isSelected);
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                style={itemStyle}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = darkMode
                      ? 'rgba(255,255,255,0.05)'
                      : 'rgba(0,0,0,0.03)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = isSelected
                    ? (darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.1)')
                    : 'transparent';
                }}
              >
                <span>{option.label}</span>
                {isSelected && (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="3"
                  >
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                )}
              </button>
            );
          })}

          {/* Garis Pemisah */}
          <div style={{ 
            height: '1px', 
            backgroundColor: darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)', 
            margin: '4px 8px' 
          }} />

          {/* Thinking Toggle Section */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            padding: '8px 12px',
            opacity: disabled ? 0.5 : 1
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <span style={{ 
                fontSize: '13px', 
                fontWeight: 600, 
                color: darkMode ? '#e5e7eb' : '#374151' 
              }}>
                {t.thinkingToggle}
              </span>
            </div>
            
            <button
              type="button"
              disabled={disabled}
              onClick={(e) => {
                e.stopPropagation(); 
                if (!disabled && onThinkingChange) {
                  onThinkingChange(!thinking);
                }
              }}
              style={{
                position: 'relative',
                width: '36px',
                height: '20px',
                borderRadius: '9999px',
                backgroundColor: thinking ? '#6366f1' : (darkMode ? '#4b5563' : '#d1d5db'),
                border: 'none',
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
                padding: 0,
                flexShrink: 0
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: '2px',
                  left: thinking ? '18px' : '2px',
                  width: '16px',
                  height: '16px',
                  backgroundColor: '#ffffff',
                  borderRadius: '50%',
                  transition: 'left 0.2s',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
                }}
              />
            </button>
          </div>
          
        </div>
      )}
    </div>
  );
}