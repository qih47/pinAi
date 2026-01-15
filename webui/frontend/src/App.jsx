// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatContent from "./components/ChatContent";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat/guest" replace />} />
        <Route
          path="/chat/guest"
          element={<ChatContent key="guest" isGuest={true} />}
        />
        <Route
          path="/chat/new"
          element={<ChatContent key="new" isGuest={false} />}
        />
        <Route
          path="/chat/:sessionId"
          element={<ChatContent key="session" isGuest={false} />}
        />
      </Routes>
    </BrowserRouter>
  );
}