import React, { useState, useRef, useEffect } from 'react';
import { getHeaderDropdownMenuStyles } from '../chatPage.styles';

export default function HeaderDropdownMenu({ isGuest, onLogin, darkMode, setDarkMode, theme }) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const menuStyles = getHeaderDropdownMenuStyles(darkMode);

  return (
    <div ref={menuRef} style={menuStyles.container}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={menuStyles.button}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = darkMode
            ? 'rgba(255,255,255,0.05)'
            : 'rgba(0,0,0,0.05)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
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
          <circle cx="12" cy="12" r="1" />
          <circle cx="12" cy="5" r="1" />
          <circle cx="12" cy="19" r="1" />
        </svg>
      </button>

      {isOpen && (
        <div style={menuStyles.menu}>
          {isGuest && (
            <button
              type="button"
              onClick={() => {
                onLogin();
                setIsOpen(false);
              }}
              style={menuStyles.loginItem}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = darkMode
                  ? 'rgba(255,255,255,0.05)'
                  : 'rgba(0,0,0,0.03)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <span>🔑</span> Masuk
            </button>
          )}

          {isGuest && <div style={menuStyles.divider} />}

          <button
            type="button"
            onClick={() => {
              setDarkMode(!darkMode);
              setIsOpen(false);
            }}
            style={menuStyles.themeItem}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = darkMode
                ? 'rgba(255,255,255,0.05)'
                : 'rgba(0,0,0,0.03)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>{darkMode ? '☀️' : '🌙'}</span>
              <span>{darkMode ? 'Terang' : 'Gelap'}</span>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
