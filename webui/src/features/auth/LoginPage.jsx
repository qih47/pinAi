import React, { useState, useEffect } from 'react';
import { useChatAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState('');
  const navigate = useNavigate();

  const { login, isLoading, error: storeError, isAuthenticated, user, systemStatus, clearError } = useChatAuthStore();

  useEffect(() => {
    if (clearError) clearError();
  }, [clearError]);

  useEffect(() => {
    if (isAuthenticated) {
      if (user?.npp === '06652') {
        window.location.href = import.meta.env.VITE_ANALYTICS_URL || `${window.location.protocol}//${window.location.hostname}:5174/analytics`;
        return;
      }
      const storeSessionId = useChatStore.getState().sessionUuid;
      const localSessionId = localStorage.getItem("cakra_last_session");
      const guestSessionId = (storeSessionId && storeSessionId !== "new") ? storeSessionId : localSessionId;
      
      if (guestSessionId && guestSessionId !== "new") {
        navigate(`/chat/${guestSessionId}`);
      } else {
        navigate('/chat/new'); 
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setLocalError('');

    if (!identifier.trim() || !password.trim()) {
      setLocalError('Harap isi semua bidang input yang diperlukan. ⚠️');
      return;
    }

    const guestSessionId = useChatStore.getState().sessionUuid;
    const result = await login(identifier, password, guestSessionId);
    if (result && result.success) {
      await useChatStore.getState().fetchSettings();
    }
  };

  return (
    <div style={{
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100dvh',
      background: '#0c0a09', // Latar belakang gelap slate yang lembut & premium
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", // Font profesional
      padding: '24px',
      position: 'relative'
    }}>
      
      {/* Container Form Elegan Minimalis */}
      <div style={{ 
        width: '100%', 
        maxWidth: '400px', 
        background: '#1c1917', // Kontras kontainer yang smooth
        borderRadius: '12px', // Sudut membulat modern yang profesional
        padding: '40px 32px', 
        border: '1px solid rgba(255, 255, 255, 0.04)',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)'
      }}>
        
        {/* Branding & Header */}
        <div style={{ marginBottom: '32px', textAlign: 'center' }}>
          <h2 style={{ 
            color: '#f5f5f4', 
            fontSize: '24px', 
            fontWeight: 600, 
            margin: '0 0 8px 0',
            letterSpacing: '-0.025em'
          }}>
            Selamat Datang Kembali
          </h2>
          <p style={{ color: '#a8a29e', fontSize: '14px', margin: 0, lineHeight: '1.5' }}>
            Masuk untuk mengakses sistem asisten virtual cerdas CAKRA AI.
          </p>
        </div>

        {/* Banner Notifikasi Error Bersih */}
        {(localError || storeError) && (
          <div style={{ 
            background: 'rgba(239, 68, 68, 0.08)', 
            border: '1px solid rgba(239, 68, 68, 0.15)', 
            color: '#f87171', 
            padding: '12px 14px', 
            borderRadius: '6px',
            fontSize: '13px', 
            marginBottom: '24px',
            lineHeight: '1.5'
          }}>
            {localError || storeError}
          </div>
        )}

        {/* Input Form Sektor */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Input Identifier */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ color: '#e7e5e4', fontSize: '13px', fontWeight: 500, letterSpacing: '0.01em' }}>
              Email atau NPP Pegawai
            </label>
            <input 
              type="text" 
              disabled={isLoading} 
              value={identifier} 
              onChange={(e) => setIdentifier(e.target.value)} 
              placeholder="contoh@pindad.com" 
              style={{ 
                background: '#141210', 
                border: '1px solid rgba(255, 255, 255, 0.08)', 
                borderRadius: '6px', 
                padding: '12px 14px', 
                color: '#f5f5f4', 
                fontSize: '14px', 
                outline: 'none', 
                fontFamily: 'inherit',
                transition: 'all 0.15s ease-in-out'
              }} 
              onFocus={(e) => { 
                e.target.style.borderColor = '#6366f1'; 
                e.target.style.boxShadow = '0 0 0 2px rgba(99, 102, 241, 0.2)';
              }}
              onBlur={(e) => { 
                e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)'; 
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Input Password */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ color: '#e7e5e4', fontSize: '13px', fontWeight: 500, letterSpacing: '0.01em' }}>
              Kata Sandi
            </label>
            <input 
              type="password" 
              disabled={isLoading} 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              placeholder="Masukkan kata sandi Anda" 
              style={{ 
                background: '#141210', 
                border: '1px solid rgba(255, 255, 255, 0.08)', 
                borderRadius: '6px', 
                padding: '12px 14px', 
                color: '#f5f5f4', 
                fontSize: '14px', 
                outline: 'none', 
                fontFamily: 'inherit',
                transition: 'all 0.15s ease-in-out'
              }} 
              onFocus={(e) => { 
                e.target.style.borderColor = '#6366f1'; 
                e.target.style.boxShadow = '0 0 0 2px rgba(99, 102, 241, 0.2)';
              }}
              onBlur={(e) => { 
                e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)'; 
                e.target.style.boxShadow = 'none';
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()} 
            />
          </div>

          {/* Tombol Submit Modern */}
          <button 
            type="submit" 
            disabled={isLoading} 
            style={{ 
              background: isLoading ? 'rgba(99, 102, 241, 0.6)' : '#6366f1', 
              color: '#ffffff', 
              border: 'none', 
              borderRadius: '6px', 
              padding: '12px 14px', 
              fontSize: '14px', 
              fontWeight: 500, 
              cursor: isLoading ? 'not-allowed' : 'pointer', 
              fontFamily: 'inherit',
              marginTop: '8px',
              boxShadow: '0 4px 6px -1px rgba(99, 102, 241, 0.2), 0 2px 4px -1px rgba(99, 102, 241, 0.1)',
              transition: 'background 0.15s ease-in-out'
            }} 
            onMouseEnter={(e) => { if(!isLoading) e.target.style.background = '#4f46e5'; }}
            onMouseLeave={(e) => { if(!isLoading) e.target.style.background = '#6366f1'; }}
          >
            {isLoading ? 'Memverifikasi...' : 'Masuk ke Akun'}
          </button>

        </form>
      </div>
    </div>
  );
}