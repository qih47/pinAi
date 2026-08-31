import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Globe,
  Sun,
  Moon,
  Monitor,
  Sparkles,
  User,
  Mail,
  Cloud,
  ArrowRight,
  ArrowLeft,
  Check,
  Bot,
  Briefcase,
  Layers,
  ShieldCheck,
  MessageSquare
} from 'lucide-react';
import { useChatAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import apiClient from '../../services/apiClient';
import cakraLogo from '../../assets/cakra.png';

export default function WelcomeWizardPage() {
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useChatAuthStore();

  // 🛡️ SENSOR PENCEGAT:
  // - JIKA TIDAK ADA SESI / BELUM LOGIN -> TENDANG KE /login
  // - JIKA SUDAH PERNAH ONBOARDING (is_onboarded === true) -> TENDANG BALIK KE /chat
  useEffect(() => {
    const localToken = localStorage.getItem('cakra_token');
    if (!isAuthenticated && !token && !localToken) {
      navigate('/login', { replace: true });
      return;
    }
    if (user && user.is_onboarded === true) {
      const lastSession = localStorage.getItem("cakra_last_session");
      navigate(lastSession ? `/chat/${lastSession}` : '/chat/new', { replace: true });
    }
  }, [isAuthenticated, token, user, navigate]);

  // Wizard States
  const [step, setStep] = useState(1); // 1: Language, 2: Theme, 3: Persona, 4: Integrations, 5: Finish
  const [language, setLanguage] = useState(localStorage.getItem('cakra_language') || user?.preferred_language || 'id');
  const [themeMode, setThemeMode] = useState(() => {
    return localStorage.getItem('cakra-theme-setting') || user?.theme_preference || 'light';
  });
  const [commStyle, setCommStyle] = useState(user?.communication_style || 'formal_saya_anda');
  const [preferredName, setPreferredName] = useState(user?.preferred_name || (user?.fullname ? user.fullname.split(' ')[0] : ''));

  // Sinkronisasi kelas tema DOM seketika saat user berada di Welcome Wizard
  useEffect(() => {
    if (themeMode === 'light') {
      document.documentElement.classList.remove('dark');
    } else if (themeMode === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.classList.toggle('dark', isDark);
    }
  }, [themeMode]);

  // Integrations state
  const [mailUser, setMailUser] = useState('');
  const [mailPass, setMailPass] = useState('');
  const [cloudUser, setCloudUser] = useState('');
  const [cloudPass, setCloudPass] = useState('');

  // Loading & Splash States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSplash, setShowSplash] = useState(false);
  const [splashPhase, setSplashPhase] = useState(1);

  // Multilingual Configuration
  const t = {
    id: {
      step1: {
        title: 'Pilih bahasa tampilan Anda',
        subtitle: 'Pilih bahasa utama untuk pengalaman antarmuka Cakra AI.',
        options: [
          { id: 'id', title: 'Bahasa Indonesia', desc: 'Pengalaman penuh dalam Bahasa Indonesia baku & natural.', flag: 'id' },
          { id: 'en', title: 'English', desc: 'Full experience in English for international communication.', flag: 'en' }
        ]
      },
      step2: {
        title: 'Pilih tema tampilan yang Anda sukai',
        subtitle: 'Sesuaikan nuansa visual yang paling nyaman untuk mata Anda.',
        options: [
          { id: 'dark', title: 'Mode Gelap (Dark)', desc: 'Tampilan obsidian kontras tinggi yang ramah di mata.', icon: 'moon' },
          { id: 'light', title: 'Mode Terang (Light)', desc: 'Tampilan bersih, cerah, dan tajam untuk siang hari.', icon: 'sun' },
          { id: 'system', title: 'Ikuti Pengaturan Sistem', desc: 'Otomatis menyesuaikan dengan preferensi perangkat Anda.', icon: 'monitor' }
        ]
      },
      step3: {
        title: 'Bagaimana Cakra AI harus memanggil Anda?',
        subtitle: 'Tentukan nama panggilan dan gaya komunikasi asisten Anda.',
        namePlaceholder: 'Ketik nama panggilan (contoh: Boss, Mas Dadang, Pak Budi)',
        styles: [
          { id: 'formal_saya_anda', title: 'Formal & Santun', desc: 'Menggunakan sapaan Saya / Anda yang profesional.' },
          { id: 'informal_gue_lo', title: 'Santai & Kasual', desc: 'Menggunakan gaya akrab Gue / Lo yang dinamis.' },
          { id: 'familiar_aku_kamu', title: 'Akrab & Hangat', desc: 'Menggunakan gaya hangat Aku / Kamu.' },
          { id: 'adaptive_mirroring', title: 'Adaptif / Cermin Gaya Anda', desc: 'Otomatis menyesuaikan gaya bahasa mengikuti cara Anda mengetik.' }
        ],
        previewGreeting: (name, style) => {
          const n = name || 'Rekan';
          if (style === 'informal_gue_lo') {
            return `Halo ${n}! Salam kenal bro/sis. Gue siap bantu kelarin koding, riset data, sampai kerjaan harian lo hari ini! ⚡`;
          }
          if (style === 'familiar_aku_kamu') {
            return `Halo ${n}! Senang banget bisa kenal sama kamu. Aku siap nemenin dan bantu semua aktivitas kerjamu hari ini ya! 🤝`;
          }
          if (style === 'adaptive_mirroring') {
            return `Halo ${n}! Saya akan otomatis menyesuaikan gaya bahasa & sapaan mengikuti bagaimana cara Anda mengetik di setiap chat. 🪞✨`;
          }
          return `Halo ${n}! Senang berkenalan dengan Anda. Saya siap membantu tugas, analisis data, hingga riset internal PT Pindad hari ini! 👔`;
        }
      },
      step4: {
        title: 'Hubungkan akun korporat Pindad',
        subtitle: 'Integrasikan email Zimbra dan Cloud Pindad untuk asisten yang lebih pintar (Opsional).',
        mailTitle: 'Pindad Smart Mail (Zimbra)',
        cloudTitle: 'Pindad Cloud (Nextcloud WebDAV)',
        username: 'Username NPP / Akun',
        password: 'Password',
        skipBtn: 'Lewati langkah ini'
      },
      step5: {
        title: 'Semuanya sudah siap!',
        subtitle: 'Preferensi Anda telah tersimpan. Mari mulai revolusi produktivitas bersama Cakra AI.',
        finishBtn: 'Mulai'
      },
      splash: {
        preparing: 'Menyiapkan ruang kerja cerdas Anda...',
        welcome: (name) => `Halo, ${name || 'Pegawai'}! Selamat datang di Cakra AI PT Pindad.`
      },
      buttons: {
        next: 'Next',
        back: 'Back',
        skip: 'Skip'
      }
    },
    en: {
      step1: {
        title: 'Choose your preferred language',
        subtitle: 'Select the primary language for Cakra AI interface.',
        options: [
          { id: 'id', title: 'Bahasa Indonesia', desc: 'Full experience in standard and natural Indonesian.', flag: 'id' },
          { id: 'en', title: 'English', desc: 'Full experience in English for international communication.', flag: 'en' }
        ]
      },
      step2: {
        title: 'How would you like to view this app?',
        subtitle: 'Select the color theme that is most comfortable for your eyes.',
        options: [
          { id: 'dark', title: 'Dark Mode', desc: 'High contrast obsidian look that is easy on the eyes.', icon: 'moon' },
          { id: 'light', title: 'Light Mode', desc: 'Clean, bright, and crisp appearance for daytime.', icon: 'sun' },
          { id: 'system', title: 'Match System Default', desc: 'Automatically adapts to your device theme.', icon: 'monitor' }
        ]
      },
      step3: {
        title: 'How should Cakra AI address you?',
        subtitle: 'Set your preferred nickname and conversation style.',
        namePlaceholder: 'Type your nickname (e.g. Boss, Alex, Mr. Smith)',
        styles: [
          { id: 'formal_saya_anda', title: 'Formal & Professional', desc: 'Uses professional and respectful corporate language.' },
          { id: 'informal_gue_lo', title: 'Casual & Modern', desc: 'Uses modern and energetic conversational tone.' },
          { id: 'familiar_aku_kamu', title: 'Warm & Friendly', desc: 'Uses friendly and approachable companion tone.' },
          { id: 'adaptive_mirroring', title: 'Adaptive (Tone Mirroring)', desc: 'Automatically adapts tone to match how you type in chat.' }
        ],
        previewGreeting: (name, style) => {
          const n = name || 'Friend';
          if (style === 'informal_gue_lo') {
            return `Hey ${n}! Awesome to meet you. I'm all set to help you crush your tasks and workflows today! ⚡`;
          }
          if (style === 'familiar_aku_kamu') {
            return `Hi ${n}! So glad to be your assistant. I'm here to support and guide you through your work today! 🤝`;
          }
          if (style === 'adaptive_mirroring') {
            return `Hello ${n}! I will automatically mirror your language tone and conversational pacing dynamically. 🪞✨`;
          }
          return `Hello ${n}! It is a pleasure to meet you. I am ready to assist with your corporate tasks and research today! 👔`;
        }
      },
      step4: {
        title: 'Connect corporate accounts',
        subtitle: 'Integrate Zimbra Mail and Pindad Cloud for an even smarter assistant (Optional).',
        mailTitle: 'Pindad Smart Mail (Zimbra)',
        cloudTitle: 'Pindad Cloud (Nextcloud WebDAV)',
        username: 'Username / Account NPP',
        password: 'Password',
        skipBtn: 'Skip for now'
      },
      step5: {
        title: 'You are all set!',
        subtitle: 'Your personal preferences have been saved. Let us begin with Cakra AI.',
        finishBtn: 'Get Started'
      },
      splash: {
        preparing: 'Setting up your intelligent workspace...',
        welcome: (name) => `Hello, ${name || 'Employee'}! Welcome to Cakra AI PT Pindad.`
      },
      buttons: {
        next: 'Next',
        back: 'Back',
        skip: 'Skip'
      }
    }
  }[language];

  // Colors & Theme Tokens (Windows 11 OOBE Style)
  const isDark = themeMode === 'dark' || (themeMode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  // Windows 11 Signature Colors
  const winBlue = '#0067C5';
  const winBlueHover = '#005FB8';

  const outerBg = isDark
    ? 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)'
    : 'linear-gradient(135deg, #dbeafe 0%, #ede9fe 50%, #f1f5f9 100%)';

  const canvasBg = isDark ? '#1e293b' : '#ffffff';
  const canvasBorder = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)';
  const textColor = isDark ? '#f8fafc' : '#1e293b';
  const textMuted = isDark ? '#94a3b8' : '#64748b';
  const cardInactiveBg = isDark ? 'rgba(255, 255, 255, 0.03)' : '#ffffff';
  const cardInactiveBorder = isDark ? 'rgba(255, 255, 255, 0.1)' : '#e2e8f0';

  const handleFinish = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        token: token || localStorage.getItem('cakra_token'),
        preferred_language: language,
        theme_preference: themeMode,
        communication_style: commStyle,
        preferred_name: preferredName.trim() || user?.fullname?.split(' ')[0] || 'Pegawai',
        mail_username: mailUser.trim() || null,
        mail_password: mailPass || null,
        cloud_username: cloudUser.trim() || null,
        cloud_password: cloudPass || null
      };

      const res = await apiClient.post('/user/onboarding', payload);

      if (res.data?.data) {
        const updatedUser = { ...user, ...res.data.data, is_onboarded: true };
        localStorage.setItem('cakra_user', JSON.stringify(updatedUser));
        useChatAuthStore.setState({ user: updatedUser });
      }

      localStorage.setItem('cakra_language', language);
      localStorage.setItem('cakra-theme-setting', themeMode);
      localStorage.setItem('cakra_theme', themeMode);
      sessionStorage.setItem('cakra_show_quick_tips', 'true');
      localStorage.removeItem('cakra_tour_seen');

      // Terapkan class DOM seketika
      if (themeMode === 'dark') {
        document.documentElement.classList.add('dark');
      } else if (themeMode === 'light') {
        document.documentElement.classList.remove('dark');
      } else {
        const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.classList.toggle('dark', isDark);
      }

      await useChatStore.getState().fetchSettings();

      setShowSplash(true);
      setTimeout(() => {
        setSplashPhase(2);
      }, 1800);

      setTimeout(() => {
        navigate('/chat/new', { replace: true });
      }, 4000);

    } catch (err) {
      console.error('Failed to complete onboarding:', err);
      setShowSplash(true);
      setTimeout(() => {
        navigate('/chat/new', { replace: true });
      }, 2500);
    }
  };

  return (
    <div style={{
      minHeight: '100dvh',
      width: '100vw',
      background: outerBg,
      color: textColor,
      fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      padding: '20px',
      boxSizing: 'border-box',
      overflow: 'hidden',
      transition: 'background 0.4s ease'
    }}>

      {/* 🖥️ CENTRAL FLOATING OOBE CANVAS */}
      <div style={{
        width: '100%',
        maxWidth: '920px',
        minHeight: '540px',
        background: canvasBg,
        borderRadius: '16px',
        border: `1px solid ${canvasBorder}`,
        boxShadow: isDark
          ? '0 30px 60px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(0, 103, 197, 0.15)'
          : '0 25px 50px -12px rgba(0, 0, 0, 0.12), 0 0 25px rgba(0, 103, 197, 0.08)',
        display: 'flex',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 1,
        transition: 'all 0.3s ease'
      }}>

        {/* ── LEFT COLUMN: 3D HERO ILLUSTRATION & BRAND (40%) ── */}
        <div style={{
          width: '40%',
          background: isDark ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 103, 197, 0.03)',
          borderRight: `1px solid ${canvasBorder}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 32px',
          position: 'relative'
        }}>
          {/* Logo Pindad Cakra di Kiri Atas */}
          <div style={{ position: 'absolute', top: '24px', left: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src={cakraLogo} alt="CAKRA AI" style={{ width: '28px', height: '28px', objectFit: 'contain' }} />
            <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.05em', color: textColor }}>
              CAKRA AI
            </span>
          </div>

          {/* Dynamic 3D Hero Graphic Based on Current Step */}
          <div style={{
            width: '180px',
            height: '180px',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {/* Ambient Glowing Halo */}
            <div style={{
              position: 'absolute',
              width: '140px',
              height: '140px',
              borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(0, 103, 197, 0.35) 0%, rgba(99, 102, 241, 0.15) 50%, transparent 70%)',
              filter: 'blur(16px)'
            }} />

            {/* Step 1 Graphic (Globe & Flags) */}
            {step === 1 && (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{
                  width: '100px',
                  height: '100px',
                  borderRadius: '24px',
                  background: 'linear-gradient(135deg, #0284c7, #2563eb)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 15px 30px rgba(37, 99, 235, 0.4)',
                  transform: 'rotate(-6deg)'
                }}>
                  <Globe size={52} color="#ffffff" />
                </div>
                {/* Floating Flag Badge */}
                <div style={{
                  position: 'absolute',
                  bottom: '-10px',
                  right: '-15px',
                  padding: '6px 12px',
                  borderRadius: '12px',
                  background: '#ffffff',
                  boxShadow: '0 8px 16px rgba(0,0,0,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transform: 'rotate(6deg)'
                }}>
                  <div style={{ width: '18px', height: '12px', borderRadius: '2px', overflow: 'hidden', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ height: '50%', background: '#EF4444' }} />
                    <div style={{ height: '50%', background: '#FFFFFF' }} />
                  </div>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#1e293b' }}>ID / EN</span>
                </div>
              </div>
            )}

            {/* Step 2 Graphic (Theme Display & Sun/Moon) */}
            {step === 2 && (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{
                  width: '110px',
                  height: '80px',
                  borderRadius: '16px',
                  background: isDark ? '#0f172a' : '#f8fafc',
                  border: '3px solid #3b82f6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 15px 30px rgba(59, 130, 246, 0.35)',
                  transform: 'rotate(-4deg)'
                }}>
                  {isDark ? <Moon size={38} color="#38bdf8" /> : <Sun size={38} color="#eab308" />}
                </div>
              </div>
            )}

            {/* Step 3 Graphic (AI Chat Persona) */}
            {step === 3 && (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{
                  width: '100px',
                  height: '100px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 15px 30px rgba(139, 92, 246, 0.4)'
                }}>
                  <Bot size={52} color="#ffffff" />
                </div>
                {/* Floating Chat Bubble */}
                <div style={{
                  position: 'absolute',
                  top: '-10px',
                  right: '-20px',
                  padding: '8px 12px',
                  borderRadius: '14px',
                  background: '#ffffff',
                  boxShadow: '0 8px 20px rgba(0,0,0,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <MessageSquare size={14} color="#3b82f6" />
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#1e293b' }}>
                    {preferredName ? `Hi, ${preferredName}!` : 'Hi!'}
                  </span>
                </div>
              </div>
            )}

            {/* Step 4 Graphic (Corporate Tools) */}
            {step === 4 && (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{
                  width: '100px',
                  height: '100px',
                  borderRadius: '24px',
                  background: 'linear-gradient(135deg, #0284c7, #0ea5e9)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 15px 30px rgba(2, 132, 199, 0.4)',
                  transform: 'rotate(-4deg)'
                }}>
                  <Cloud size={48} color="#ffffff" />
                </div>
                <div style={{
                  position: 'absolute',
                  bottom: '-8px',
                  right: '-12px',
                  width: '42px',
                  height: '42px',
                  borderRadius: '12px',
                  background: '#3b82f6',
                  boxShadow: '0 8px 16px rgba(0,0,0,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                  transform: 'rotate(8deg)'
                }}>
                  <Mail size={22} />
                </div>
              </div>
            )}

            {/* Step 5 Graphic (Sparkles & Finish) */}
            {step === 5 && (
              <div style={{
                width: '110px',
                height: '110px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #0067C5, #7c3aed)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 15px 35px rgba(0, 103, 197, 0.45)',
                animation: 'pulse 2s infinite'
              }}>
                <Sparkles size={56} color="#ffffff" />
              </div>
            )}
          </div>

          {/* Stepper Dots di Bawah Grafis */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '36px' }}>
            {[1, 2, 3, 4, 5].map((s) => (
              <div
                key={s}
                style={{
                  width: step === s ? '24px' : '8px',
                  height: '8px',
                  borderRadius: '4px',
                  background: step === s ? winBlue : (step > s ? '#10b981' : (isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)')),
                  transition: 'all 0.3s ease'
                }}
              />
            ))}
          </div>
        </div>

        {/* ── RIGHT COLUMN: SELECTION AREA & CONTROLS (60%) ── */}
        <div style={{
          width: '60%',
          padding: '44px 40px 36px 40px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative'
        }}>

          {/* Content Area */}
          <div>
            {/* STEP 1: LANGUAGE SELECTION */}
            {step === 1 && (
              <div>
                <h2 style={{ fontSize: '24px', fontWeight: 600, margin: '0 0 6px 0', color: textColor, letterSpacing: '-0.01em' }}>
                  {t.step1.title}
                </h2>
                <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 24px 0', lineHeight: 1.4 }}>
                  {t.step1.subtitle}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {t.step1.options.map((opt) => {
                    const isSelected = language === opt.id;
                    return (
                      <div
                        key={opt.id}
                        onClick={() => setLanguage(opt.id)}
                        style={{
                          padding: '16px 20px',
                          borderRadius: '8px',
                          border: isSelected ? `2px solid ${winBlue}` : `1px solid ${cardInactiveBorder}`,
                          background: isSelected ? winBlue : cardInactiveBg,
                          color: isSelected ? '#ffffff' : textColor,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '16px',
                          transition: 'all 0.15s ease',
                          boxShadow: isSelected ? '0 6px 14px rgba(0, 103, 197, 0.3)' : 'none'
                        }}
                      >
                        {/* Flag Badge */}
                        <div style={{
                          width: '38px',
                          height: '26px',
                          borderRadius: '4px',
                          overflow: 'hidden',
                          boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          flexShrink: 0,
                          display: 'flex',
                          flexDirection: 'column'
                        }}>
                          {opt.flag === 'id' ? (
                            <>
                              <div style={{ height: '50%', background: '#EF4444' }} />
                              <div style={{ height: '50%', background: '#FFFFFF' }} />
                            </>
                          ) : (
                            <svg viewBox="0 0 60 30" width="100%" height="100%">
                              <clipPath id="uk-clip-oobe">
                                <path d="M0,0 v30 h60 v-30 z" />
                              </clipPath>
                              <g clipPath="url(#uk-clip-oobe)">
                                <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
                                <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
                                <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="3" />
                                <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
                                <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
                              </g>
                            </svg>
                          )}
                        </div>

                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '15px', fontWeight: 600, color: isSelected ? '#ffffff' : textColor }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: '12px', color: isSelected ? 'rgba(255,255,255,0.85)' : textMuted, marginTop: '2px' }}>
                            {opt.desc}
                          </div>
                        </div>

                        {isSelected && (
                          <div style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: winBlue }}>
                            <Check size={13} strokeWidth={3} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 2: THEME SELECTION */}
            {step === 2 && (
              <div>
                <h2 style={{ fontSize: '24px', fontWeight: 600, margin: '0 0 6px 0', color: textColor, letterSpacing: '-0.01em' }}>
                  {t.step2.title}
                </h2>
                <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 24px 0', lineHeight: 1.4 }}>
                  {t.step2.subtitle}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {t.step2.options.map((opt) => {
                    const isSelected = themeMode === opt.id;
                    return (
                      <div
                        key={opt.id}
                        onClick={() => setThemeMode(opt.id)}
                        style={{
                          padding: '16px 20px',
                          borderRadius: '8px',
                          border: isSelected ? `2px solid ${winBlue}` : `1px solid ${cardInactiveBorder}`,
                          background: isSelected ? winBlue : cardInactiveBg,
                          color: isSelected ? '#ffffff' : textColor,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '16px',
                          transition: 'all 0.15s ease',
                          boxShadow: isSelected ? '0 6px 14px rgba(0, 103, 197, 0.3)' : 'none'
                        }}
                      >
                        <div style={{
                          width: '36px',
                          height: '36px',
                          borderRadius: '8px',
                          background: isSelected ? 'rgba(255,255,255,0.2)' : (isDark ? '#334155' : '#f1f5f9'),
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: isSelected ? '#ffffff' : (isDark ? '#38bdf8' : '#0284c7'),
                          flexShrink: 0
                        }}>
                          {opt.icon === 'moon' && <Moon size={20} />}
                          {opt.icon === 'sun' && <Sun size={20} />}
                          {opt.icon === 'monitor' && <Monitor size={20} />}
                        </div>

                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '15px', fontWeight: 600, color: isSelected ? '#ffffff' : textColor }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: '12px', color: isSelected ? 'rgba(255,255,255,0.85)' : textMuted, marginTop: '2px' }}>
                            {opt.desc}
                          </div>
                        </div>

                        {isSelected && (
                          <div style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: winBlue }}>
                            <Check size={13} strokeWidth={3} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 3: NICKNAME & PERSONA */}
            {step === 3 && (
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: '0 0 6px 0', color: textColor, letterSpacing: '-0.01em' }}>
                  {t.step3.title}
                </h2>
                <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 18px 0', lineHeight: 1.4 }}>
                  {t.step3.subtitle}
                </p>

                {/* Nickname Input */}
                <div style={{ marginBottom: '16px' }}>
                  <input
                    type="text"
                    value={preferredName}
                    onChange={(e) => setPreferredName(e.target.value)}
                    placeholder={t.step3.namePlaceholder}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      borderRadius: '8px',
                      border: `1px solid ${cardInactiveBorder}`,
                      background: isDark ? '#0f172a' : '#f8fafc',
                      color: textColor,
                      fontSize: '14px',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                {/* Style Options */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                  {t.step3.styles.map((style) => {
                    const isSelected = commStyle === style.id;
                    return (
                      <div
                        key={style.id}
                        onClick={() => setCommStyle(style.id)}
                        style={{
                          padding: '10px 16px',
                          borderRadius: '8px',
                          border: isSelected ? `2px solid ${winBlue}` : `1px solid ${cardInactiveBorder}`,
                          background: isSelected ? winBlue : cardInactiveBg,
                          color: isSelected ? '#ffffff' : textColor,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: isSelected ? '#ffffff' : textColor }}>
                            {style.title}
                          </div>
                          <div style={{ fontSize: '11px', color: isSelected ? 'rgba(255,255,255,0.85)' : textMuted }}>
                            {style.desc}
                          </div>
                        </div>
                        {isSelected && (
                          <div style={{ width: '18px', height: '18px', borderRadius: '50%', background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: winBlue }}>
                            <Check size={12} strokeWidth={3} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Live Preview Bubble */}
                <div style={{
                  background: isDark ? 'rgba(0, 103, 197, 0.08)' : '#eff6ff',
                  border: `1px solid ${isDark ? 'rgba(0, 103, 197, 0.25)' : '#bfdbfe'}`,
                  borderRadius: '8px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px'
                }}>
                  <Bot size={18} color={winBlue} style={{ flexShrink: 0 }} />
                  <div style={{ fontSize: '12px', color: textColor, lineHeight: 1.4 }}>
                    "{t.step3.previewGreeting(preferredName, commStyle)}"
                  </div>
                </div>
              </div>
            )}

            {/* STEP 4: CORPORATE INTEGRATIONS */}
            {step === 4 && (
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: '0 0 6px 0', color: textColor, letterSpacing: '-0.01em' }}>
                  {t.step4.title}
                </h2>
                <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 20px 0', lineHeight: 1.4 }}>
                  {t.step4.subtitle}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Zimbra */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <Mail size={16} color={winBlue} />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: textColor }}>{t.step4.mailTitle}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                      <input
                        type="text"
                        value={mailUser}
                        onChange={(e) => setMailUser(e.target.value)}
                        placeholder="NPP / email@pindad.com"
                        style={{ padding: '8px 12px', borderRadius: '6px', border: `1px solid ${cardInactiveBorder}`, background: canvasBg, color: textColor, fontSize: '12px', outline: 'none' }}
                      />
                      <input
                        type="password"
                        value={mailPass}
                        onChange={(e) => setMailPass(e.target.value)}
                        placeholder={t.step4.password}
                        style={{ padding: '8px 12px', borderRadius: '6px', border: `1px solid ${cardInactiveBorder}`, background: canvasBg, color: textColor, fontSize: '12px', outline: 'none' }}
                      />
                    </div>
                  </div>

                  {/* Nextcloud */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <Cloud size={16} color="#0284c7" />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: textColor }}>{t.step4.cloudTitle}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                      <input
                        type="text"
                        value={cloudUser}
                        onChange={(e) => setCloudUser(e.target.value)}
                        placeholder="Username Nextcloud"
                        style={{ padding: '8px 12px', borderRadius: '6px', border: `1px solid ${cardInactiveBorder}`, background: canvasBg, color: textColor, fontSize: '12px', outline: 'none' }}
                      />
                      <input
                        type="password"
                        value={cloudPass}
                        onChange={(e) => setCloudPass(e.target.value)}
                        placeholder={t.step4.password}
                        style={{ padding: '8px 12px', borderRadius: '6px', border: `1px solid ${cardInactiveBorder}`, background: canvasBg, color: textColor, fontSize: '12px', outline: 'none' }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STEP 5: SUMMARY & FINISH */}
            {step === 5 && (
              <div>
                <h2 style={{ fontSize: '24px', fontWeight: 600, margin: '0 0 6px 0', color: textColor, letterSpacing: '-0.01em' }}>
                  {t.step5.title}
                </h2>
                <p style={{ fontSize: '13px', color: textMuted, margin: '0 0 24px 0', lineHeight: 1.4 }}>
                  {t.step5.subtitle}
                </p>

                {/* Summary Tiles */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  {/* Bahasa */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <span style={{ fontSize: '11px', color: textMuted, textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
                      {language === 'id' ? 'Bahasa' : 'Language'}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                      <div style={{
                        width: '24px',
                        height: '16px',
                        borderRadius: '3px',
                        overflow: 'hidden',
                        boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
                        border: '1px solid rgba(0,0,0,0.1)',
                        flexShrink: 0,
                        display: 'flex',
                        flexDirection: 'column'
                      }}>
                        {language === 'id' ? (
                          <>
                            <div style={{ height: '50%', background: '#EF4444' }} />
                            <div style={{ height: '50%', background: '#FFFFFF' }} />
                          </>
                        ) : (
                          <svg viewBox="0 0 60 30" width="100%" height="100%">
                            <clipPath id="uk-clip-sum">
                              <path d="M0,0 v30 h60 v-30 z"/>
                            </clipPath>
                            <g clipPath="url(#uk-clip-sum)">
                              <path d="M0,0 v30 h60 v-30 z" fill="#012169"/>
                              <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6"/>
                              <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="3"/>
                              <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10"/>
                              <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6"/>
                            </g>
                          </svg>
                        )}
                      </div>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: textColor }}>
                        {language === 'id' ? 'Bahasa Indonesia' : 'English'}
                      </span>
                    </div>
                  </div>

                  {/* Tema */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <span style={{ fontSize: '11px', color: textMuted, textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
                      {language === 'id' ? 'Tema' : 'Theme'}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                      {themeMode === 'dark' && <Moon size={16} color="#38bdf8" />}
                      {themeMode === 'light' && <Sun size={16} color="#eab308" />}
                      {themeMode === 'system' && <Monitor size={16} color="#0284c7" />}
                      <span style={{ fontSize: '13px', fontWeight: 600, color: textColor }}>
                        {themeMode === 'dark' ? 'Dark Mode' : (themeMode === 'light' ? 'Light Mode' : 'System')}
                      </span>
                    </div>
                  </div>

                  {/* Panggilan */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <span style={{ fontSize: '11px', color: textMuted, textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
                      {language === 'id' ? 'Panggilan' : 'Nickname'}
                    </span>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: textColor, marginTop: '6px' }}>
                      "{preferredName || (language === 'id' ? 'Rekan' : 'Friend')}"
                    </div>
                  </div>

                  {/* Gaya Bicara */}
                  <div style={{ padding: '14px 16px', borderRadius: '8px', border: `1px solid ${cardInactiveBorder}`, background: cardInactiveBg }}>
                    <span style={{ fontSize: '11px', color: textMuted, textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
                      {language === 'id' ? 'Gaya Bicara' : 'Voice Tone'}
                    </span>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: textColor, marginTop: '6px' }}>
                      {commStyle === 'formal_saya_anda' && (language === 'id' ? 'Formal & Santun' : 'Formal & Polite')}
                      {commStyle === 'informal_gue_lo' && (language === 'id' ? 'Santai & Kasual' : 'Casual & Modern')}
                      {commStyle === 'familiar_aku_kamu' && (language === 'id' ? 'Akrab & Hangat' : 'Warm & Friendly')}
                      {commStyle === 'adaptive_mirroring' && (language === 'id' ? 'Adaptif (Mirroring)' : 'Adaptive (Mirror)')}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── BOTTOM ACTION BUTTONS (Right-Aligned Windows 11 Style) ── */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '12px',
            marginTop: '32px',
            paddingTop: '16px'
          }}>
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                style={{
                  padding: '8px 24px',
                  borderRadius: '6px',
                  border: `1px solid ${cardInactiveBorder}`,
                  background: canvasBg,
                  color: textColor,
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {t.buttons.back}
              </button>
            )}

            {step === 4 && (
              <button
                type="button"
                onClick={() => setStep(5)}
                style={{
                  padding: '8px 20px',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'transparent',
                  color: textMuted,
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textDecoration: 'underline'
                }}
              >
                {t.step4.skipBtn}
              </button>
            )}

            {step < 5 ? (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                style={{
                  padding: '8px 28px',
                  borderRadius: '6px',
                  border: 'none',
                  background: winBlue,
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 2px 6px rgba(0, 103, 197, 0.3)',
                  transition: 'all 0.15s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = winBlueHover}
                onMouseOut={(e) => e.currentTarget.style.background = winBlue}
              >
                {t.buttons.next}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                disabled={isSubmitting}
                style={{
                  padding: '8px 32px',
                  borderRadius: '6px',
                  border: 'none',
                  background: winBlue,
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  boxShadow: '0 2px 8px rgba(0, 103, 197, 0.4)',
                  transition: 'all 0.15s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = winBlueHover}
                onMouseOut={(e) => e.currentTarget.style.background = winBlue}
              >
                {t.step5.finishBtn}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 🎬 CINEMATIC WELCOME SPLASH OVERLAY */}
      {showSplash && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100dvh',
          background: isDark ? '#0b1120' : '#f8fafc',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          animation: 'fadeIn 0.5s ease forwards'
        }}>
          <style>{`
            @keyframes pulseScale {
              0%, 100% { transform: scale(1); opacity: 0.9; }
              50% { transform: scale(1.06); opacity: 1; }
            }
            @keyframes fadeIn {
              from { opacity: 0; }
              to { opacity: 1; }
            }
            @keyframes slideUp {
              from { transform: translateY(16px); opacity: 0; }
              to { transform: translateY(0); opacity: 1; }
            }
          `}</style>

          <div style={{
            width: '100px',
            height: '100px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(0, 103, 197, 0.25), rgba(99, 102, 241, 0.25))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '28px',
            animation: 'pulseScale 2s infinite ease-in-out',
            boxShadow: '0 0 50px rgba(0, 103, 197, 0.3)'
          }}>
            <img
              src={cakraLogo}
              alt="Cakra AI"
              style={{ width: '54px', height: '54px', objectFit: 'contain' }}
            />
          </div>

          {splashPhase === 1 ? (
            <div style={{ textAlign: 'center', animation: 'slideUp 0.4s ease forwards' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 500, color: textMuted, margin: '0 0 12px 0' }}>
                {t.splash.preparing}
              </h2>
              <div style={{
                width: '140px',
                height: '3px',
                background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                borderRadius: '3px',
                margin: '0 auto',
                overflow: 'hidden',
                position: 'relative'
              }}>
                <div style={{
                  width: '50px',
                  height: '100%',
                  background: winBlue,
                  borderRadius: '3px',
                  position: 'absolute',
                  animation: 'pulseScale 1.2s infinite ease-in-out'
                }} />
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', animation: 'slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards' }}>
              <h1 style={{
                fontSize: '26px',
                fontWeight: 700,
                background: 'linear-gradient(135deg, #0284c7, #8b5cf6)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                margin: '0 0 10px 0',
                letterSpacing: '-0.01em'
              }}>
                {t.splash.welcome(preferredName)}
              </h1>
              <p style={{ fontSize: '14px', color: textMuted, margin: 0 }}>
                {language === 'id' ? 'Membuka lembar percakapan baru Anda...' : 'Launching your new workspace session...'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
