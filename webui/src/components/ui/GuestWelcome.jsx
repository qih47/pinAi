import React from "react";
import cakraLogo from '../../assets/cakra.png';

export default function GuestWelcome({
  isLoggedIn,
  userData,
  getGreeting,
  theme,
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center',
      padding: '20px',
      width: '100%'
    }}>
      
      {/* ── KUNCI SAKTI ALIGNMENT: Kontainer Baris Atas Otomatis Center Sejajar dengan Teks Bawah ── */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        gap: '14px', 
        marginBottom: '16px',
        maxWidth: '100%',
        width: 'auto'
      }}>
        
        {/* Logo Cakra */}
        <div style={{ 
          animation: 'logoFloat 4s ease-in-out infinite', 
          display: 'flex', 
          alignItems: 'center',
          flexShrink: 0
        }}>
          <img
            src={cakraLogo}
            alt="CAKRA"
            style={{
              width: '49px',
              height: '44px',
              borderRadius: '10px',
              filter: 'drop-shadow(0 4px 12px rgba(99, 102, 241, 0.35))'
            }}
          />
        </div>

        {/* Teks Judul dengan Gradasi Kuning ke Biru Murni Tanpa Clip (Bebas Bug Balok) */}
        <h2 style={{
          fontSize: '32px',
          fontWeight: '600',
          margin: '0',
          letterSpacing: '-0.8px',
          lineHeight: '1.2',
          display: 'inline-block',
          whiteSpace: 'nowrap',
          // 🔥 GRADASI KUNING KE BIRU: Langsung pakai standard text gradient style
          background: 'linear-gradient(to right, #facc15 0%, #2563eb 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          color: 'transparent'
        }}>
          {isLoggedIn
            ? `${getGreeting()}, ${userData?.fullname}`
            : "Halo, saya CAKRA"}
        </h2>
      </div>

      {/* Teks Abu-Abu Subtitle di Bawah */}
      <p style={{
        fontSize: '16px',
        margin: '0',
        color: theme.secondaryText,
        fontWeight: '400',
        maxWidth: '500px',
        transition: 'color 0.3s ease',
        textAlign: 'center',
        lineHeight: '1.5'
      }}>
        {isLoggedIn
          ? "Ada yang bisa saya bantu hari ini?"
          : "Asisten AI PT Pindad siap membantu Anda"}
      </p>
    </div>
  );
}