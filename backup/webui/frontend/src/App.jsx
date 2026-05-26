// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "@/features/chat/ChatPage";
import LearningPage from "@/features/learning/LearningPage"; 

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat/guest" replace />} />
        <Route
          path="/chat/guest"
          element={<ChatPage key="guest" isGuest={true} />}
        />
        <Route
          path="/chat/new"
          element={<ChatPage key="new" isGuest={false} />}
        />
        <Route
          path="/chat/:sessionId"
          element={<ChatPage key="session" isGuest={false} />}
        />
        
        {/* Tambahkan route standalone di sini, tidak mengganggu yang atas */}
        <Route path="/learning" element={<LearningPage />} /> 
        
      </Routes>
    </BrowserRouter>
  );
}