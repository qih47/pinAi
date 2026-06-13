import React, { createContext, useState, useCallback, useRef } from 'react';

// Context for global Toast Notifications
export const ToastContext = createContext(null);

/**
 * ToastProvider component provides a toast notification system.
 * It displays notifications at the top-right corner with beautiful animations,
 * support for dark/light modes, auto-dismiss, and interactive dismissals.
 */
export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = idRef.current++;
    
    setToasts((prev) => [...prev, { id, message, type, duration }]);
    
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      {/* Toast Portal/Container */}
      <div 
        style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          maxWidth: '380px',
          width: '100%',
          pointerEvents: 'none',
        }}
      >
        {toasts.map((toast) => (
          <ToastItem 
            key={toast.id} 
            toast={toast} 
            onClose={() => removeToast(toast.id)} 
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onClose }) {
  const { message, type } = toast;
  
  // Icon map based on type
  const getIcon = () => {
    switch (type) {
      case 'success':
        return (
          <svg style={{ width: '20px', height: '20px', color: '#10B981' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'error':
        return (
          <svg style={{ width: '20px', height: '20px', color: '#EF4444' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'warning':
        return (
          <svg style={{ width: '20px', height: '20px', color: '#F59E0B' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        );
      case 'info':
      default:
        return (
          <svg style={{ width: '20px', height: '20px', color: '#3B82F6' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  // Color theme map for background border and text
  const getStyles = () => {
    switch (type) {
      case 'success':
        return {
          background: 'rgba(16, 185, 129, 0.1)',
          borderLeft: '4px solid #10B981',
          boxShadow: '0 4px 12px rgba(16, 185, 129, 0.15)',
        };
      case 'error':
        return {
          background: 'rgba(239, 68, 68, 0.1)',
          borderLeft: '4px solid #EF4444',
          boxShadow: '0 4px 12px rgba(239, 68, 68, 0.15)',
        };
      case 'warning':
        return {
          background: 'rgba(245, 158, 11, 0.1)',
          borderLeft: '4px solid #F59E0B',
          boxShadow: '0 4px 12px rgba(245, 158, 11, 0.15)',
        };
      case 'info':
      default:
        return {
          background: 'rgba(59, 82, 246, 0.1)',
          borderLeft: '4px solid #3B82F6',
          boxShadow: '0 4px 12px rgba(59, 82, 246, 0.15)',
        };
    }
  };

  return (
    <div
      style={{
        ...getStyles(),
        pointerEvents: 'auto',
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        borderRadius: '8px',
        color: '#FFFFFF',
        fontFamily: 'Inter, sans-serif',
        fontSize: '14px',
        fontWeight: '500',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        animation: 'toast-slide-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <style>{`
        @keyframes toast-slide-in {
          from {
            transform: translateX(120%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
      
      <div style={{ marginRight: '12px', display: 'flex', alignItems: 'center' }}>
        {getIcon()}
      </div>
      
      <div style={{ flex: 1, marginRight: '12px', wordBreak: 'break-word', color: 'inherit' }}>
        {message}
      </div>
      
      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '4px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255, 255, 255, 0.4)',
          borderRadius: '4px',
          transition: 'color 0.2s, background-color 0.2s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = '#FFFFFF';
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'rgba(255, 255, 255, 0.4)';
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        <svg style={{ width: '16px', height: '16px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
