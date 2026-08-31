import React, { useState, useEffect, useRef } from 'react';
import { 
  X, 
  User, 
  Lock, 
  Eye, 
  EyeOff, 
  AlertCircle, 
  Loader2,
  ShieldCheck,
  Sparkles,
  KeyRound,
  ArrowRight
} from 'lucide-react';
import cakraLogo from '../../assets/cakra.png';
import { useChatAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useNavigate } from 'react-router-dom';

export default function LoginModal({ 
  isOpen: externalIsOpen, 
  onClose: externalOnClose, 
  darkMode = true,
  language = 'id'
}) {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const [npp, setNpp] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isShaking, setIsShaking] = useState(false);

  const inputRef = useRef(null);
  const navigate = useNavigate();
  const { login, error: storeError, clearError } = useChatAuthStore();

  const isOpen = externalIsOpen !== undefined ? externalIsOpen : internalIsOpen;

  const handleClose = () => {
    setLocalError('');
    if (clearError) clearError();
    if (externalOnClose) {
      externalOnClose();
    } else {
      setInternalIsOpen(false);
    }
  };

  // Global listener: bisa dibuka dari mana saja lewat event atau redirect /login
  useEffect(() => {
    const handleOpen = () => {
      setNpp('');
      setPassword('');
      setLocalError('');
      setInternalIsOpen(true);
    };

    if (sessionStorage.getItem('cakra_open_login_modal') === 'true') {
      sessionStorage.removeItem('cakra_open_login_modal');
      handleOpen();
    }

    window.addEventListener('cakra_open_login', handleOpen);
    return () => window.removeEventListener('cakra_open_login', handleOpen);
  }, []);

  // Auto focus input NPP saat modal dibuka
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        if (inputRef.current) inputRef.current.focus();
      }, 100);
    }
  }, [isOpen]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setLocalError('');

    if (!npp.trim() || !password.trim()) {
      setLocalError(language === 'en' ? 'NPP dan kata sandi wajib diisi.' : 'NPP dan kata sandi wajib diisi.');
      triggerShake();
      return;
    }

    setIsSubmitting(true);
    try {
      const guestSessionId = useChatStore.getState().sessionUuid;
      const result = await login(npp.trim(), password, guestSessionId);

      if (result && result.success) {
        await useChatStore.getState().fetchSettings();
        const currentUser = useChatAuthStore.getState().user;

        handleClose();

        if (currentUser && currentUser.is_onboarded === false) {
          navigate('/welcome', { replace: true });
        } else {
          const localSessionId = localStorage.getItem("cakra_last_session");
          const targetSession = (guestSessionId && guestSessionId !== "new") ? guestSessionId : localSessionId;
          if (targetSession && targetSession !== "new") {
            navigate(`/chat/${targetSession}`);
          } else {
            navigate('/chat/new');
          }
        }
      } else {
        setLocalError(result?.message || (language === 'en' ? 'NPP atau kata sandi salah.' : 'NPP atau kata sandi salah.'));
        triggerShake();
      }
    } catch (err) {
      setLocalError(language === 'en' ? 'Terjadi kesalahan sistem.' : 'Terjadi kesalahan saat masuk.');
      triggerShake();
    } finally {
      setIsSubmitting(false);
    }
  };

  const triggerShake = () => {
    setIsShaking(true);
    setTimeout(() => setIsShaking(false), 400);
  };

  if (!isOpen) return null;

  // Fluent Tokens (Matching Welcome Wizard OOBE)
  const isDark = darkMode;
  const winBlue = '#0067C5';
  const winBlueHover = '#005FB8';
  const canvasBg = isDark ? '#1e293b' : '#ffffff';
  const canvasBorder = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)';
  const textColor = isDark ? '#f8fafc' : '#1e293b';
  const textMuted = isDark ? '#94a3b8' : '#64748b';
  const inputBg = isDark ? 'rgba(255, 255, 255, 0.03)' : '#f8fafc';
  const inputBorder = isDark ? 'rgba(255, 255, 255, 0.12)' : '#e2e8f0';

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        backgroundColor: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif',
        animation: 'fadeIn 0.2s ease'
      }}
    >
      {/* ── 2-COLUMN FLUENT OOBE MODAL CANVAS (MATCHING WELCOME WIZARD) ── */}
      <div 
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '740px',
          minHeight: '440px',
          background: canvasBg,
          borderRadius: '18px',
          border: `1px solid ${canvasBorder}`,
          boxShadow: isDark
            ? '0 30px 70px -12px rgba(0, 0, 0, 0.8), 0 0 35px rgba(0, 103, 197, 0.2)'
            : '0 25px 60px -12px rgba(0, 0, 0, 0.15), 0 0 30px rgba(0, 103, 197, 0.1)',
          display: 'flex',
          overflow: 'hidden',
          transition: 'all 0.25s ease',
          animation: isShaking ? 'shake 0.4s ease-in-out' : 'none'
        }}
      >
        {/* Close Button */}
        <button 
          onClick={handleClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            padding: '7px',
            borderRadius: '8px',
            border: 'none',
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
            color: textMuted,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.15s ease',
            zIndex: 20
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)';
            e.currentTarget.style.color = textColor;
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
            e.currentTarget.style.color = textMuted;
          }}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        {/* ── LEFT COLUMN: 3D HERO ILLUSTRATION & BRAND (42%) ── */}
        <div style={{
          width: '42%',
          background: isDark ? 'rgba(0, 0, 0, 0.25)' : 'rgba(0, 103, 197, 0.03)',
          borderRight: `1px solid ${canvasBorder}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '36px 28px',
          position: 'relative',
          textAlign: 'center',
          boxSizing: 'border-box'
        }}>
          {/* Logo Pindad Cakra di Kiri Atas */}
          <div style={{ position: 'absolute', top: '20px', left: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src={cakraLogo} alt="CAKRA AI" style={{ width: '24px', height: '24px', objectFit: 'contain' }} />
            <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.05em', color: textColor }}>
              CAKRA AI
            </span>
          </div>

          {/* 3D Hero Graphic Container */}
          <div style={{
            position: 'relative',
            width: '150px',
            height: '150px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px'
          }}>
            {/* Ambient Glowing Halo */}
            <div style={{
              position: 'absolute',
              width: '120px',
              height: '120px',
              borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(0, 103, 197, 0.4) 0%, rgba(99, 102, 241, 0.2) 50%, transparent 70%)',
              filter: 'blur(16px)'
            }} />

            {/* 3D Floating Graphic Card */}
            <div style={{
              position: 'relative',
              width: '96px',
              height: '96px',
              borderRadius: '24px',
              background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 50%, #4f46e5 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 16px 35px rgba(37, 99, 235, 0.45), inset 0 2px 4px rgba(255, 255, 255, 0.4)',
              transform: 'rotate(-4deg)'
            }}>
              <img src={cakraLogo} alt="CAKRA" style={{ width: '56px', height: '56px', objectFit: 'contain', filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.3))' }} />
            </div>

            {/* Floating Mini Badge */}
            <div style={{
              position: 'absolute',
              bottom: '4px',
              right: '-6px',
              padding: '6px 10px',
              borderRadius: '12px',
              background: isDark ? '#0f172a' : '#ffffff',
              border: `1px solid ${inputBorder}`,
              boxShadow: '0 8px 18px rgba(0,0,0,0.18)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transform: 'rotate(4deg)'
            }}>
              <ShieldCheck size={14} color="#0284c7" />
              <span style={{ fontSize: '10px', fontWeight: 700, color: textColor, letterSpacing: '0.02em' }}>
                HRIS SSO
              </span>
            </div>
          </div>

          {/* Left Column Brand Text */}
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: textColor, margin: '0 0 3px 0', letterSpacing: '-0.01em' }}>
            {language === 'en' ? 'Corporate AI Assistant' : 'Asisten AI Korporat'}
          </h3>
          <p style={{ fontSize: '12px', color: textMuted, margin: 0 }}>
            PT Pindad (Persero)
          </p>
        </div>

        {/* ── RIGHT COLUMN: AUTHENTICATION FORM (58%) ── */}
        <div style={{
          width: '58%',
          padding: '38px 36px 36px 36px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          boxSizing: 'border-box'
        }}>
          {/* Title & Subtitle */}
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: textColor, margin: '0 0 6px 0', letterSpacing: '-0.01em' }}>
            {language === 'en' ? 'Sign In' : 'Masuk'}
          </h2>
          <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 20px 0', lineHeight: 1.4 }}>
            {language === 'en'
              ? 'Enter your NPP and HRIS password.'
              : 'Gunakan NPP dan kata sandi HRIS Anda.'}
          </p>

          {/* Error Alert */}
          {(localError || storeError) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 14px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              color: '#ef4444',
              fontSize: '12px',
              marginBottom: '16px',
              animation: 'fadeIn 0.15s ease'
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{localError || storeError}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {/* Field: NPP */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: textColor, marginBottom: '6px' }}>
                NPP (Nomor Pokok Pegawai)
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <div style={{ position: 'absolute', left: '12px', color: textMuted, display: 'flex', alignItems: 'center', pointerEvents: 'none' }}>
                  <User size={16} />
                </div>
                <input
                  ref={inputRef}
                  type="text"
                  value={npp}
                  onChange={(e) => setNpp(e.target.value)}
                  placeholder="00000"
                  autoComplete="username"
                  disabled={isSubmitting}
                  style={{
                    width: '100%',
                    padding: '10px 14px 10px 38px',
                    borderRadius: '8px',
                    border: `1px solid ${inputBorder}`,
                    background: inputBg,
                    color: textColor,
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'all 0.15s ease',
                    boxSizing: 'border-box'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = winBlue;
                    e.target.style.boxShadow = '0 0 0 2px rgba(0, 103, 197, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = inputBorder;
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
            </div>

            {/* Field: Kata Sandi */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, color: textColor }}>
                  {language === 'en' ? 'Password' : 'Kata Sandi'}
                </label>
                <span style={{ fontSize: '11px', color: textMuted }}>
                  {language === 'en' ? 'HRIS Account' : 'Akun HRIS'}
                </span>
              </div>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <div style={{ position: 'absolute', left: '12px', color: textMuted, display: 'flex', alignItems: 'center', pointerEvents: 'none' }}>
                  <Lock size={16} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  style={{
                    width: '100%',
                    padding: '10px 40px 10px 38px',
                    borderRadius: '8px',
                    border: `1px solid ${inputBorder}`,
                    background: inputBg,
                    color: textColor,
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'all 0.15s ease',
                    boxSizing: 'border-box'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = winBlue;
                    e.target.style.boxShadow = '0 0 0 2px rgba(0, 103, 197, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = inputBorder;
                    e.target.style.boxShadow = 'none';
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    background: 'transparent',
                    border: 'none',
                    color: textMuted,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px'
                  }}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                width: '100%',
                marginTop: '6px',
                padding: '10px 24px',
                borderRadius: '6px',
                border: 'none',
                background: winBlue,
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 6px rgba(0, 103, 197, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'all 0.15s ease'
              }}
              onMouseOver={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = winBlueHover;
              }}
              onMouseOut={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = winBlue;
              }}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>{language === 'en' ? 'Signing in...' : 'Memverifikasi...'}</span>
                </>
              ) : (
                <>
                  <span>{language === 'en' ? 'Sign In' : 'Masuk ke Sistem'}</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
