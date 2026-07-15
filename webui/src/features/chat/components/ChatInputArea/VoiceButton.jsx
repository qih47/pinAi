import React, { useState, useRef } from "react";
import { Mic, Square } from "lucide-react";

export default function VoiceButton({ onTranscriptionSuccess, darkMode, disabled }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        // Stop all tracks to release microphone
        stream.getTracks().forEach((track) => track.stop());
        await handleTranscription(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Error accessing microphone:", error);
      alert(`Gagal mengakses mikrofon: ${error.name} - ${error.message}\n\nPastikan Anda telah memberikan izin dan mic terpasang.`);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleTranscription = async (audioBlob) => {
    setIsTranscribing(true);
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    try {
      const token = localStorage.getItem("cakra_token");
      const res = await fetch("/api/voice/transcribe", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Transcription failed");
      }

      const data = await res.json();
      if (data.status === "success" && data.text) {
        onTranscriptionSuccess(data.text);
      }
    } catch (error) {
      console.error("Transcription error:", error);
      alert("Gagal memproses suara. Coba lagi.");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleClick = () => {
    if (disabled || isTranscribing) return;
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // UI styling
  const buttonStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "36px",
    height: "36px",
    borderRadius: "18px",
    border: "none",
    background: isRecording
      ? (darkMode ? "rgba(239, 68, 68, 0.2)" : "rgba(239, 68, 68, 0.1)")
      : "transparent",
    color: isRecording 
      ? "#ef4444" 
      : (darkMode ? "#9ca3af" : "#6b7280"),
    cursor: disabled || isTranscribing ? "not-allowed" : "pointer",
    transition: "all 0.2s ease",
    position: "relative",
  };

  return (
    <button 
      type="button" 
      onClick={handleClick} 
      style={buttonStyle}
      title="Voice Typing"
      onMouseEnter={(e) => {
        if (!isRecording && !disabled && !isTranscribing) {
          e.currentTarget.style.background = darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
          e.currentTarget.style.color = darkMode ? "#d1d5db" : "#374151";
        }
      }}
      onMouseLeave={(e) => {
        if (!isRecording && !disabled && !isTranscribing) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = darkMode ? "#9ca3af" : "#6b7280";
        }
      }}
    >
      {/* Ripple effect when recording */}
      {isRecording && (
        <span 
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            border: "1.5px solid #ef4444",
            animation: "ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite",
            opacity: 0.75
          }}
        />
      )}
      
      {isTranscribing ? (
        <span style={{ fontSize: "14px", animation: "pulse 1s infinite" }}>⏳</span>
      ) : isRecording ? (
        <Square size={16} fill="currentColor" />
      ) : (
        <Mic size={20} />
      )}
      
      <style>{`
        @keyframes ping {
          75%, 100% {
            transform: scale(1.5);
            opacity: 0;
          }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </button>
  );
}
