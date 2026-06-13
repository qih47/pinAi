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
      padding: '20px'
    }}>
      {/* Logo dengan animasi float */}
      <div style={{
        marginBottom: '24px',
        animation: 'logoFloat 4s ease-in-out infinite'
      }}>
        <img
          src={cakraLogo}
          alt="CAKRA"
          style={{
            width: '90px',
            height: '80px',
            borderRadius: '20px',
            filter: 'drop-shadow(0 8px 24px rgba(99, 102, 241, 0.25))'
          }}
        />
      </div>

      {/* Greeting */}
      <h2 style={{
        fontSize: '32px',
        fontWeight: '600',
        margin: '0 0 12px 0',
        letterSpacing: '-0.8px',
        background: 'linear-gradient(135deg, #111827 0%, #6366f1 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text'
      }}>
        {isLoggedIn
          ? `${getGreeting()}, ${userData?.fullname}`
          : "Halo, saya CAKRA"}
      </h2>

      {/* Subtitle */}
      <p style={{
        fontSize: '16px',
        margin: '0 0 8px 0',
        color: theme.secondaryText,
        fontWeight: '400',
        maxWidth: '500px',
        transition: 'color 0.3s ease'
      }}>
        {isLoggedIn
          ? "Ada yang bisa saya bantu hari ini?"
          : "Asisten AI PT Pindad siap membantu Anda"}
      </p>
    </div>
  );
}