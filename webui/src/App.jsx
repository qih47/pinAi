import React, { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";
import ChatPage from "@/features/chat/ChatPage";
import LoginPage from "@/features/auth/LoginPage"; // 👈 IMPORT LOGIN ENGINE
import CacheStatsPage from "@/features/admin/CacheStatsPage"; // 👈 W13 & W15: Cache & Search Stats Dashboard
import { useChatAuthStore } from "@/stores/authStore"; // 👈 IMPORT AUTH STORE
import { useChatStore } from "@/stores/chatStore";
import Loading from "./components/Loading";
import Layout from "./components/Layout";
import ToastProvider from "./components/ui/ToastProvider";
import { useTokenRefresh } from "./hooks/useTokenRefresh"; // 👈 W18: Token auto-refresh
import OllamaThinkTest from '@/features/chat/components/OllamaThinkTest';

// Komponen redirect: jika analytics dibuka di port 5173, arahkan ke port 5174
function AnalyticsRedirect() {
  React.useEffect(() => {
    const analyticsUrl = `${window.location.protocol}//${window.location.hostname}:5174/analytics`;
    window.location.replace(analyticsUrl);
  }, []);
  return null;
}

function SessionRouteWrapper({ isGuest, corporateMode = null }) {
  const { sessionId } = useParams();
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);

  // 🛡️ SENSOR PENCEGAT OTENTIKASI PEGAWAI
  // Kalau mau masuk sektor non-guest tapi jimat tokennya kosong, sepak balik ke /login!
  if (!isGuest && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isGuest && isAuthenticated) {
    const lastSession = localStorage.getItem("cakra_last_session");
    return (
      <Navigate
        to={lastSession ? `/chat/${lastSession}` : "/chat/new"}
        replace
      />
    );
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

  return <ChatPage isGuest={isGuest} corporateMode={corporateMode} />;
}

export default function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const checkSession = useChatAuthStore((state) => state.checkSession);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Beneran hit DB verify-session asinkronus, bolo!
        const isValid = await checkSession();
        if (isValid) {
          await useChatStore.getState().fetchSettings();
        }
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
        <AppContent />
      </BrowserRouter>
    </ToastProvider>
  );
}

/**
 * AppContent: Wrapper to use hooks inside BrowserRouter
 * Enables useTokenRefresh hook which runs globally for authenticated users
 */
function AppContent() {
  // 👇 W18: Token auto-refresh every 30min + on user activity + emergency refresh
  useTokenRefresh();

  return (
    <Routes>
      {/* 🔐 DAFTARKAN RUTE LOGIN CYBERPUNK DI LUAR BUNGKUSAN LAYOUT */}
      <Route path="/login" element={<LoginPage />} />

      {/* ⚡ W13 & W15: Admin Cache & Performance Dashboard */}
      <Route path="/admin/cache-stats" element={<CacheStatsPage />} />
      
      <Route path="/test-think" element={<OllamaThinkTest />} />
      <Route path="/" element={<Navigate to="/chat/guest" replace />} />

      {/* 🔒 /analytics di port ini tidak valid — redirect ke port 5174 */}
      <Route
        path="/analytics"
        element={
          <AnalyticsRedirect />
        }
      />
      <Route
        path="/analytics/*"
        element={
          <AnalyticsRedirect />
        }
      />

      <Route element={<Layout />}>
        <Route
          path="/chat/guest"
          element={<SessionRouteWrapper isGuest={true} />}
        />
        <Route
          path="/chat/new"
          element={<SessionRouteWrapper isGuest={false} />}
        />
        <Route
          path="/chat/:sessionId"
          element={<SessionRouteWrapper isGuest={false} />}
        />
        <Route
          path="/corporate/mail"
          element={<SessionRouteWrapper isGuest={false} corporateMode="mail" />}
        />
        <Route
          path="/corporate/notadinas"
          element={<SessionRouteWrapper isGuest={false} corporateMode="notadinas" />}
        />
        <Route
          path="/corporate/vendor"
          element={<SessionRouteWrapper isGuest={false} corporateMode="vendor" />}
        />
      </Route>
    </Routes>
  );
}
