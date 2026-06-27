/**
 * FileGenerationCard.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Komponen interaktif untuk Interceptor-Analyst Pipeline CAKRA AI.
 * Mengadopsi visual layout bertingkat saat streaming, dan berubah menjadi 
 * File Card Minimalis Premium saat Done sesuai gambar (image_c936bf.png).
 */

import React, { useState, useEffect, useRef } from 'react';

// ─── Sleek Loader UI ─────────────────────────────────────────────────────────
const PulseLoader = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  }}>
    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out' }} />
    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out 0.2s' }} />
    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out 0.4s' }} />
    <style>
      {`
        @keyframes cakraPulse {
          0%, 100% { transform: scale(0.8); opacity: 0.5; }
          50% { transform: scale(1.2); opacity: 1; }
        }
      `}
    </style>
  </div>
);

// ─── Deteksi Label Jenis Ekstensi Deskriptif ──────────────────────────────────
function getFileMeta(filename) {
  const ext = filename?.split('.').pop()?.toLowerCase();
  const meta = {
    jsx: { type: 'Component', label: 'JSX' },
    tsx: { type: 'Component', label: 'TSX' },
    js: { type: 'Script', label: 'JS' },
    ts: { type: 'Script', label: 'TS' },
    py: { type: 'Script', label: 'Python' },
    md: { type: 'Document', label: 'MD' },
    css: { type: 'Style', label: 'CSS' },
    html: { type: 'Web', label: 'HTML' },
    json: { type: 'Data', label: 'JSON' },
  };
  return meta[ext] || { type: 'File', label: ext?.toUpperCase() || 'TXT' };
}

export default function FileGenerationCard({
  filename,
  stage,           // "creating" | "streaming" | "done" | "error"
  liveCode,        // string kodingan yang mengalir real-time dari SSE
  darkMode = true,
  onOpenArtifact,  // callback(filename, code) -> trigger sidebar kanan
  file_path,       // path file di server
}) {
  const [copyDone, setCopyDone] = useState(false);

  const isDone = stage === 'done';
  const isError = stage === 'error';
  const isActive = stage === 'creating' || stage === 'streaming';

  if (!isDone) return null;

  const fileMeta = getFileMeta(filename);

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(liveCode || '');
    setCopyDone(true);
    setTimeout(() => setCopyDone(false), 2000);
  };

  const handleDownload = (e) => {
    e.stopPropagation();
    const blob = new Blob([liveCode || ''], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'file.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleOpenClick = (e) => {
    e.stopPropagation();
    if (onOpenArtifact) {
      onOpenArtifact(filename, liveCode || '', file_path || null);
    }
  };

  return (
    <div className="cakra-pipeline-card" style={{
      // margin: '12px 0',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      width: '100%',
    }}>
      {/* ── STAGE DONE: MORPHING PERSIS GAMBAR REFERENSI (image_c936bf.png) ── */}
      <div 
        onClick={handleOpenClick}
        style={{
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '10px',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
        boxSizing: 'border-box',
        cursor: onOpenArtifact ? 'pointer' : 'default',
        transition: 'background 0.2s'
      }}
      onMouseEnter={(e) => {
        if (onOpenArtifact) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
      }}
      onMouseLeave={(e) => {
        if (onOpenArtifact) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
      }}
      >
        {/* Bagian Kiri: Icon Skematis & Info Nama File */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', overflow: 'hidden' }}>
            {/* Box Icon Miring Transparan (Gaya image_c936bf.png) */}
            <div style={{
              width: '40px',
              height: '46px',
              borderRadius: '6px',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              background: 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.05) 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              flexShrink: 0,
              transform: 'perspective(100px) rotateY(-5deg)',
              boxShadow: '-4px 4px 10px rgba(0,0,0,0.3)'
            }}>
              {/* Mini Skema Garis Teks Dokumen */}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="2" strokeLinecap="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>

            {/* Teks Judul & Sub-metadata File */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', overflow: 'hidden' }}>
              <div style={{
                fontSize: '15px',
                fontWeight: '500',
                color: '#ffffff',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                letterSpacing: '-0.01em'
              }}>
                {filename}
              </div>
              <div style={{
                fontSize: '12px',
                color: 'rgba(255, 255, 255, 0.4)',
                fontFamily: 'monospace'
              }}>
                {fileMeta.type} · {fileMeta.label}
              </div>
            </div>
          </div>

          {/* Bagian Kanan: Aksi Kontrol Panel Minimalis */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>

            {/* Action Icon: Copy
            <button
              onClick={handleCopy}
              title="Copy Code"
              style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '6px', padding: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center',
                color: copyDone ? '#10b981' : 'rgba(255,255,255,0.5)', transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#ffffff'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = copyDone ? '#10b981' : 'rgba(255,255,255,0.5)'; e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button> */}



            {/* Tombol Utama: Download (Persis image_c936bf.png) */}
            <button
              onClick={handleDownload}
              style={{
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                padding: '8px 16px',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: '0 2px 6px rgba(0,0,0,0.2)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#ffffff';
                e.currentTarget.style.color = '#18181b';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = '#ffffff';
              }}
            >
              Download
            </button>
          </div>
        </div>
      {/* ERROR STATE */}
      {isError && (
        <div style={{ marginLeft: '32px', padding: '6px 10px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid #ef4444', color: '#ef4444', fontSize: '12px' }}>
          ⚠️ Pipeline Error: Gagal menulis file fisik ke disk server.
        </div>
      )}

      <style>{`
        @keyframes cakraCursorBlink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}