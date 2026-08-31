import React, { useState, useEffect } from "react";
import {
  BookOpen,
  MessageSquare,
  Paperclip,
  UserCheck,
  X,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  FileText,
  Search,
  CheckCircle2
} from "lucide-react";
import cakraLogo from "../../../../assets/cakra.png";
import { useChatAuthStore } from "../../../../stores/authStore";

export default function QuickTipsModal({ darkMode, language = "id", isOpen: externalIsOpen, onClose: externalOnClose, isGuest = false }) {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const [currentSlide, setCurrentSlide] = useState(0);
  const user = useChatAuthStore((state) => state.user);
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);

  const isGuestUser = Boolean(
    isGuest || 
    !isAuthenticated || 
    !user || 
    user?.npp === "GUEST" || 
    user?.role === "GUEST" || 
    user?.isGuest === true
  );

  const isOpen = (externalIsOpen !== undefined ? externalIsOpen : internalIsOpen) && !isGuestUser;

  const handleClose = () => {
    sessionStorage.removeItem("cakra_show_quick_tips");
    localStorage.setItem("cakra_tour_seen", "true");
    if (externalOnClose) {
      externalOnClose();
    } else {
      setInternalIsOpen(false);
    }
  };

  useEffect(() => {
    // Jangan pernah buka otomatis jika user adalah Guest / Belum login
    if (isGuestUser) return;

    // Cek apakah ada sinyal eksplisit dari onboarding wizard atau user belum pernah melihat tour
    const mustShowQuickTips = sessionStorage.getItem("cakra_show_quick_tips") === "true";
    const tourSeen = localStorage.getItem("cakra_tour_seen");

    if ((mustShowQuickTips || !tourSeen) && externalIsOpen === undefined) {
      // Tampilkan popup tips dengan delay halus 600ms agar halaman siap
      const timer = setTimeout(() => {
        setInternalIsOpen(true);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [externalIsOpen, isGuestUser]);

  // Listener untuk membuka kembali tips secara manual dari menu bantuan / sidebar
  useEffect(() => {
    if (isGuestUser) return;
    const handleOpenManual = () => {
      setCurrentSlide(0);
      setInternalIsOpen(true);
    };
    window.addEventListener("cakra_open_quick_tips", handleOpenManual);
    return () => window.removeEventListener("cakra_open_quick_tips", handleOpenManual);
  }, [isGuestUser]);

  if (!isOpen || isGuestUser) return null;

  const preferredName = user?.preferred_name || (user?.fullname ? user.fullname.split(" ")[0] : "Rekan");


  const slides = {
    id: [
      {
        title: "Eksplorasi Katalog Dokumen & Regulasi",
        badge: "Sidebar Kiri → Dokumen",
        icon: <BookOpen className="w-8 h-8 text-blue-500" />,
        desc: "Klik menu Dokumen di Sidebar sebelah kiri untuk menelusuri seluruh arsip regulasi, SKEP Direksi, Surat Edaran, dan SOP internal PT Pindad secara terstruktur.",
        highlight: "Tersedia fitur pencarian cepat untuk menemukan nomor dokumen dan regulasi yang Anda butuhkan."
      },
      {
        title: "Tanya Regulasi di Chat (Mode Dokumen)",
        badge: "Kotak Chat → Pilih Mode Dokumen",
        icon: <FileText className="w-8 h-8 text-emerald-500" />,
        desc: "Saat ingin menanyakan isi regulasi, ketentuan operasional, atau kebijakan perusahaan, pilih Mode Dokumen di bawah kotak pesan sebelum mengirim pertanyaan.",
        highlight: "Cakra AI akan otomatis menjawab berdasarkan isi regulasi resmi dan menyertakan sitasi sumber dokumennya."
      },
      {
        title: "Lampirkan Dokumen & Analisis Cerdas",
        badge: "Tombol '+' → Upload File",
        icon: <Paperclip className="w-8 h-8 text-indigo-500" />,
        desc: "Anda dapat melampirkan file dokumen (PDF, Word, Excel) maupun gambar ke dalam percakapan untuk diringkas, diekstrak datanya, atau dianalisis langsung oleh AI.",
        highlight: "Mendukung drag-and-drop file langsung ke area chat."
      },
      {
        title: `Asisten Pribadi Anda, ${preferredName}`,
        badge: "Menu Pengaturan → Gaya Bahasa",
        icon: <UserCheck className="w-8 h-8 text-purple-500" />,
        desc: `Cakra AI telah dipersonalisasi untuk memanggil Anda sebagai "${preferredName}". Anda dapat menyesuaikan gaya komunikasi (Formal, Santai, Akrab, atau Adaptif) kapan saja melalui menu Pengaturan.`,
        highlight: "Cakra AI siap mendampingi dan meningkatkan produktivitas harian Anda di PT Pindad!"
      }
    ],
    en: [
      {
        title: "Explore Document & Regulation Catalog",
        badge: "Left Sidebar → Documents",
        icon: <BookOpen className="w-8 h-8 text-blue-500" />,
        desc: "Click on Documents in the left sidebar to explore the full repository of corporate regulations, decrees, policies, and standard operating procedures.",
        highlight: "Includes quick search to locate official regulations and document numbers instantly."
      },
      {
        title: "Ask Regulations in Chat (Document Mode)",
        badge: "Chat Area → Select Document Mode",
        icon: <FileText className="w-8 h-8 text-emerald-500" />,
        desc: "When asking about internal regulations, operating policies, or corporate governance, select Document Mode below the message box.",
        highlight: "Cakra AI automatically answers using official regulatory sources and provides exact document citations."
      },
      {
        title: "Attach Files & Smart Document Analysis",
        badge: "'+' Button → Upload Files",
        icon: <Paperclip className="w-8 h-8 text-indigo-500" />,
        desc: "Attach document files (PDF, Word, Excel) or images directly into the conversation to summarize, extract data, and generate analytical insights on demand.",
        highlight: "Supports drag-and-drop file uploading directly into the chat canvas."
      },
      {
        title: `Personalized Assistant for You, ${preferredName}`,
        badge: "Settings Menu → Tone & Name",
        icon: <UserCheck className="w-8 h-8 text-purple-500" />,
        desc: `Cakra AI is configured to address you as "${preferredName}". You can adjust your preferred communication style (Formal, Casual, Friendly, or Adaptive) anytime in Settings.`,
        highlight: "Ready to support your daily corporate workflow and productivity at PT Pindad!"
      }
    ]
  }[language === "en" ? "en" : "id"];

  if (!isOpen) return null;

  const current = slides[currentSlide];
  const isLast = currentSlide === slides.length - 1;

  return (
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className={`relative w-full max-w-lg rounded-2xl shadow-2xl border overflow-hidden transition-all duration-300 ${darkMode
            ? "bg-[#18181b] border-gray-700/80 text-gray-100 shadow-black/80"
            : "bg-white border-gray-200 text-gray-900 shadow-gray-400/30"
          }`}
      >
        {/* Header Bar */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${darkMode ? "border-gray-800 bg-[#121215]" : "border-gray-100 bg-gray-50/80"}`}>
          <div className="flex items-center space-x-2.5">
            <img src={cakraLogo} alt="Cakra AI" className="w-6 h-6 object-contain" />
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm tracking-tight">CAKRA AI</span>
              <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-blue-500/10 text-blue-500 border border-blue-500/20">
                {language === "en" ? "Quick Tips" : "Panduan Cepat"}
              </span>
            </div>
          </div>
          <button
            onClick={handleClose}
            className={`p-1.5 rounded-lg transition-colors ${darkMode ? "text-gray-400 hover:text-white hover:bg-gray-800" : "text-gray-500 hover:text-gray-900 hover:bg-gray-200"}`}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Slide Content Body */}
        <div className="p-6 md:p-8">
          {/* Badge & Icon */}
          <div className="flex items-start justify-between mb-4">
            <div className={`p-3.5 rounded-2xl ${darkMode ? "bg-gray-800/80 border border-gray-700" : "bg-blue-50/80 border border-blue-100"}`}>
              {current.icon}
            </div>
            <span className={`text-[11px] font-semibold px-3 py-1 rounded-full border ${darkMode ? "bg-gray-800 border-gray-700 text-gray-300" : "bg-gray-100 border-gray-200 text-gray-700"}`}>
              {current.badge}
            </span>
          </div>

          {/* Title */}
          <h3 className="text-lg md:text-xl font-bold tracking-tight mb-2.5">
            {current.title}
          </h3>

          {/* Description */}
          <p className={`text-sm leading-relaxed mb-4 ${darkMode ? "text-gray-300" : "text-gray-600"}`}>
            {current.desc}
          </p>

          {/* Highlight Box */}
          <div className={`flex items-center space-x-2.5 p-3 rounded-xl text-xs font-medium ${darkMode ? "bg-blue-500/10 border border-blue-500/20 text-blue-300" : "bg-blue-50 border border-blue-200 text-blue-700"}`}>
            <Sparkles size={16} className="flex-shrink-0 text-blue-500" />
            <span>{current.highlight}</span>
          </div>
        </div>

        {/* Footer Navigation Bar */}
        <div className={`flex items-center justify-between px-6 py-4 border-t ${darkMode ? "border-gray-800 bg-[#121215]" : "border-gray-100 bg-gray-50/80"}`}>
          {/* Step Dots */}
          <div className="flex items-center space-x-1.5">
            {slides.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentSlide(idx)}
                className={`h-2 rounded-full transition-all duration-300 ${currentSlide === idx
                    ? "w-6 bg-blue-500"
                    : `w-2 ${darkMode ? "bg-gray-700 hover:bg-gray-600" : "bg-gray-300 hover:bg-gray-400"}`
                  }`}
                aria-label={`Slide ${idx + 1}`}
              />
            ))}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center space-x-2.5">
            {currentSlide > 0 && (
              <button
                type="button"
                onClick={() => setCurrentSlide(prev => Math.max(0, prev - 1))}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${darkMode
                    ? "border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700"
                    : "border-gray-300 bg-white text-gray-700 hover:bg-gray-100"
                  }`}
              >
                {language === "en" ? "Back" : "Kembali"}
              </button>
            )}

            {!isLast ? (
              <button
                type="button"
                onClick={() => setCurrentSlide(prev => Math.min(slides.length - 1, prev + 1))}
                className="flex items-center space-x-1 px-4 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm shadow-blue-500/20 transition-all"
              >
                <span>{language === "en" ? "Next" : "Lanjut"}</span>
                <ChevronRight size={14} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleClose}
                className="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-md shadow-blue-500/25 transition-all"
              >
                <CheckCircle2 size={14} />
                <span>{language === "en" ? "Start Chatting" : "Mulai Percakapan"}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
