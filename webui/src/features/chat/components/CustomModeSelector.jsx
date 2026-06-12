import React, { useState, useRef, useEffect } from 'react';
import { getCustomModeSelectorStyles } from '../chatPage.styles';

export default function CustomModeSelector({ value, onChange, disabled, darkMode }) {
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
    { value: 'auto', label: 'Auto' },
    { value: 'flash', label: 'Flash' },
    { value: 'documents', label: 'Documents' }
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
        <div style={selectorStyles.dropdown}>
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
        </div>
      )}
    </div>
  );
}
