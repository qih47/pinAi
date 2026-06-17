import React from "react";
import { useSessionExpiry } from "../hooks/useSessionExpiry";
import { useChatAuthStore } from "../stores/authStore";

export default function SessionExpiryStatus() {
  const { isAuthenticated } = useChatAuthStore();
  const { expiresIn, extendSession } = useSessionExpiry();

  if (!isAuthenticated || !expiresIn) {
    return null;
  }

  const shouldShow = () => {
    const timeStr = expiresIn.toLowerCase();
    if (timeStr.includes("h")) {
      return false;
    }
    const match = timeStr.match(/(\d+)\s*m/);
    if (match) {
      const minutesLeft = parseInt(match[1], 10);
      return minutesLeft < 1;
    }
    if (timeStr.includes("s") && !timeStr.includes("m")) {
      return true;
    }
    return false;
  };

  if (!shouldShow()) {
    return null;
  }

  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      background: 'rgba(239, 68, 68, 0.08)',
      backdropFilter: 'blur(8px)',
      WebkitBackdropFilter: 'blur(8px)',
      border: '1px solid rgba(239, 68, 68, 0.2)',
      animation: 'fadeInSlide 0.4s ease-out forwards',
      width: '100%',
    }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        width: '100%'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: '#ef4444',
            boxShadow: '0 0 8px #ef4444',
            display: 'inline-block',
            animation: 'pulse 1.5s infinite ease-in-out'
          }} />
          <span style={{
            fontSize: '12px',
            fontWeight: '500',
            color: '#f87171',
            letterSpacing: '0.2px'
          }}>
            Sesi hampir habis
          </span>
        </div>
        <span style={{
          fontSize: '13px',
          fontWeight: '600',
          fontFamily: 'monospace',
          color: '#ef4444',
          background: 'rgba(239, 68, 68, 0.15)',
          padding: '2px 8px',
          borderRadius: '6px',
          letterSpacing: '0.5px'
        }}>
          {expiresIn}
        </span>
      </div>

      <button
        onClick={() => extendSession(8)}
        style={{
          width: '100%',
          padding: '8px',
          borderRadius: '8px',
          border: 'none',
          background: '#2563eb',
          color: '#ffffff',
          fontSize: '12px',
          fontWeight: '600',
          cursor: 'pointer',
          transition: 'background 0.2s ease, transform 0.1s ease',
          boxShadow: '0 4px 12px rgba(37, 99, 235, 0.2)',
          outline: 'none'
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = '#1d4ed8'}
        onMouseLeave={(e) => e.currentTarget.style.background = '#2563eb'}
        onMouseDown={(e) => e.currentTarget.style.transform = 'scale(0.98)'}
        onMouseUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
      >
        Perpanjang Sesi
      </button>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.9); }
        }
        @keyframes fadeInSlide {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}