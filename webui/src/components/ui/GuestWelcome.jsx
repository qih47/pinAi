import React, { useState, useEffect } from "react";
import cakraLogo from '../../assets/cakra.png';

const GREETING_TEMPLATES = [
  "Tugas apa yang mau dikerjakan hari ini",
  "Ada yang bisa saya bantu hari ini",
  "Mari selesaikan pekerjaan anda hari ini",
  "Fokus mengerjakan apa hari ini",
  "Siap membantu menyelesaikan target anda",
  "Apa prioritas utama anda saat ini",
  "Mari kita buat hari ini lebih produktif",
  "Butuh bantuan menganalisis sesuatu hari ini",
  "Siap mengeksekusi tugas terbaru anda",
  "Target apa yang ingin diselesaikan sekarang"
];

export default function GuestWelcome({
  isLoggedIn,
  userData,
  getGreeting, // Not used anymore for logged in, but kept for signature compatibility
  theme,
  isMobile,
}) {
  const [randomGreeting, setRandomGreeting] = useState("");

  useEffect(() => {
    if (isLoggedIn) {
      const randomIndex = Math.floor(Math.random() * GREETING_TEMPLATES.length);
      setRandomGreeting(GREETING_TEMPLATES[randomIndex]);
    }
  }, [isLoggedIn]);

  const rawFirstName = userData?.fullname?.split(" ")[0] || "Guest";
  const firstName = rawFirstName.charAt(0).toUpperCase() + rawFirstName.slice(1).toLowerCase();

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
        gap: '7px',
        // marginBottom: '3px',
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
              // 🔥 JALUR DINAMIS MOBILE: Kalau mobile kita perkecil ukurannya biar proporsional
              width: isMobile ? '36px' : '49px',
              height: isMobile ? '32px' : '44px',
              borderRadius: isMobile ? '7px' : '10px',
              filter: 'drop-shadow(0 4px 12px rgba(99, 102, 241, 0.35))',
              transition: 'all 0.3s ease' // Biar pas di-resize smooth perpindahannya
            }}
          />
        </div>

        {/* Teks Judul dengan Gradasi Kuning ke Biru Murni Tanpa Clip (Bebas Bug Balok) */}
        <h2 style={{
          fontSize: isMobile ? '18px' : '28px',
          fontWeight: '600',
          margin: '0',
          letterSpacing: '-0.8px',
          lineHeight: '1.2',
          display: 'inline-block',
          whiteSpace: isMobile ? 'normal' : 'nowrap',
          // 🔥 GRADASI KUNING KE BIRU: Langsung pakai standard text gradient style
          background: 'linear-gradient(to right, #facc15 0%, #2563eb 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          color: 'transparent'
        }}>
          {isLoggedIn
            ? `${randomGreeting}, ${firstName}?`
            : "Halo, saya CAKRA"}
        </h2>
      </div>

      {/* Teks Abu-Abu Subtitle di Bawah (Hanya untuk Guest) */}
      {!isLoggedIn && (
        <p style={{
          fontSize: isMobile ? '14px' : '16px',
          margin: '0',
          color: theme.secondaryText,
          fontWeight: '400',
          maxWidth: '500px',
          transition: 'color 0.3s ease',
          textAlign: 'center',
          lineHeight: '1.5'
        }}>
          Mau cari informasi apa hari ini?
        </p>
      )}
    </div>
  );
}