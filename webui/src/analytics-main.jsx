import './index.css';
import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from '@/features/analytics/DashboardLayout';
import ToastProvider from './components/ui/ToastProvider';
import Loading from './components/Loading';
import { useChatAuthStore } from "@/stores/authStore";
import { useTokenRefresh } from "./hooks/useTokenRefresh";

function AnalyticsApp() {
  const [isInitializing, setIsInitializing] = useState(true);
  const checkSession = useChatAuthStore((state) => state.checkSession);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        await checkSession();
      } catch (e) {
        console.error("Gagal menginisiasi session awal:", e);
      } finally {
        setIsInitializing(false);
      }
    };
    initializeAuth();
  }, [checkSession]);

  if (isInitializing) {
    return <Loading text="CAKRA ANALYTICS" />;
  }

  return (
    <ToastProvider>
      <BrowserRouter>
        <AnalyticsContent />
      </BrowserRouter>
    </ToastProvider>
  );
}

function AnalyticsContent() {
  useTokenRefresh();
  
  return (
    <Routes>
      <Route path="/analytics" element={<DashboardLayout />} />
      {/* Catch all to redirect to analytics */}
      <Route path="*" element={<Navigate to="/analytics" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AnalyticsApp />
  </React.StrictMode>
);
