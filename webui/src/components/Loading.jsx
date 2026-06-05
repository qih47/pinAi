import React from 'react';
import cakraLogo from '../assets/cakra.png';

export default function Loading({ text = "CAKRA AI ASSISTANT", darkMode = true }) {
  const isDark = darkMode;

  const theme = {
    containerBg: isDark ? '#151517' : '#f8fafc',
    statusColor: isDark ? '#38bdf8' : '#0284c7',
    terminalIconColor: isDark ? '#cbd5e1' : '#64748b',
    trackBg: isDark ? '#2a2a2d' : '#e2e8f0',
    footerColor: isDark ? '#475569' : '#94a3b8',
    // Progress bar gradient tetap oke di kedua mode, tapi bisa disesuaikan
  };

  return (
    <div style={{ ...styles.container, background: theme.containerBg }}>
      {/* Inject Style Animasi Khusus Loading */}
      <style>{`
        @keyframes logoPulse {
          0%, 100% { 
            transform: scale(1);
            filter: drop-shadow(0 0 15px rgba(99, 102, 241, 0.2));
          }
          50% { 
            transform: scale(1.04);
            filter: drop-shadow(0 0 35px rgba(56, 189, 248, 0.5));
          }
        }
        @keyframes terminalText {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
        @keyframes progressBar {
          0% { width: 0%; }
          50% { width: 70%; }
          100% { width: 100%; }
        }
        * { box-sizing: border-box; }
      `}</style>

      <div style={styles.wrapper}>
        {/* Logo Cakra Berdenyut Sinematik */}
        <div style={styles.logoBox}>
          <img 
            src={cakraLogo} 
            alt="CAKRA AI" 
            style={styles.logo} 
          />
        </div>

        {/* Teks Status Bergaya Cyber Terminal */}
        <div style={styles.statusText}>
          <span style={{ ...styles.terminalIcon, color: theme.terminalIconColor }}>⚡</span>{' '}
          <span style={{ color: theme.statusColor, animation: 'terminalText 1.8s ease-in-out infinite' }}>
            {text.toUpperCase()}
          </span>
        </div>

        {/* Bar Indikator Proses Tipis Minimalis */}
        <div style={{ ...styles.trackBar, background: theme.trackBg }}>
          <div style={styles.progressBar} />
        </div>
        
        {/* Footer Amankan Enkripsi */}
        <div style={{ ...styles.secureFooter, color: theme.footerColor }}>
          RAG SYSTEM PINDAD
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    width: '100vw',
    height: '100vh',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Inter', 'Segoe UI', monospace",
    overflow: 'hidden',
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 9999,
  },
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    maxWidth: 400,
    width: '100%',
    padding: '0 24px'
  },
  logoBox: {
    marginBottom: 32,
    animation: 'logoPulse 2.5s ease-in-out infinite',
  },
  logo: {
    width: 84,
    height: 84,
    borderRadius: 22,
    objectFit: 'cover',
  },
  statusText: {
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: '1.5px',
    lineHeight: 1.6,
    marginBottom: 20,
  },
  terminalIcon: {
    // warna diatur inline
  },
  trackBar: {
    width: 180,
    height: 3,
    borderRadius: 4,
    overflow: 'hidden',
    position: 'relative',
    marginBottom: 40
  },
  progressBar: {
    height: '100%',
    background: 'linear-gradient(90deg, #6366f1, #38bdf8)',
    borderRadius: 4,
    animation: 'progressBar 2s cubic-bezier(0.4, 0, 0.2, 1) infinite',
  },
  secureFooter: {
    fontSize: 9,
    letterSpacing: '2px',
    fontWeight: 500
  }
};