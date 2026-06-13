import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import ChatPage from "@/features/chat/ChatPage";
import LoginPage from "@/features/auth/LoginPage"; // 👈 IMPORT LOGIN ENGINE
import { useChatAuthStore } from "@/stores/authStore"; // 👈 IMPORT AUTH STORE
import { useChatStore } from "@/stores/chatStore";
import Loading from "./components/Loading";
import Layout from "./components/Layout";
import ToastProvider from "./components/ui/ToastProvider";

function SessionRouteWrapper({ isGuest }) {
  const { sessionId } = useParams();
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);

  // 🛡️ SENSOR PENCEGAT OTENTIKASI PEGAWAI
  // Kalau mau masuk sektor non-guest tapi jimat tokennya kosong, sepak balik ke /login!
  if (!isGuest && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isGuest && isAuthenticated) {
    const lastSession = localStorage.getItem("cakra_last_session");
    return <Navigate to={lastSession ? `/chat/${lastSession}` : "/chat/new"} replace />;
  }

  useEffect(() => {
    if (isGuest) {
      useChatStore.setState({ sessionUuid: null, messages: [] });
    } else if (sessionId === "new") {
      // Hanya reset untuk halaman obrolan baru; UUID session ditangani ChatPage via URL
      useChatStore.setState({ sessionUuid: "new", messages: [] });
    }
    // Untuk /chat/:uuid — jangan timpa store di sini agar tidak bentrok dengan load sidebar
  }, [sessionId, isGuest]);

  return <ChatPage isGuest={isGuest} />;
}

export default function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const checkSession = useChatAuthStore((state) => state.checkSession);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Beneran hit DB verify-session asinkronus, bolo!
        await checkSession();
      } catch (e) {
        console.error("Gagal menginisiasi session awal:", e);
      } finally {
        // Matikan loading screen taktis lo setelah pengecekan kelar
        setIsInitializing(false);
      }
    };

    initializeAuth();
  }, [checkSession]);

  if (isInitializing) {
    return <Loading text="CAKRA AI ASSISTANT" />;
  }

  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          {/* 🔐 DAFTARKAN RUTE LOGIN CYBERPUNK DI LUAR BUNGKUSAN LAYOUT */}
          <Route path="/login" element={<LoginPage />} />

          <Route path="/" element={<Navigate to="/chat/guest" replace />} />
          
          <Route element={<Layout />}>
            <Route path="/chat/guest" element={<SessionRouteWrapper key="guest" isGuest={true} />} />
            <Route path="/chat/new" element={<SessionRouteWrapper key="new" isGuest={false} />} />
            <Route path="/chat/:sessionId" element={<SessionRouteWrapper key="session" isGuest={false} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}