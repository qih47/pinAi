import React from "react";

export default function PreviewImageModal({ previewImage, onClose }) {
  if (!previewImage) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.85)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
      onClick={onClose}
    >
      <button
        style={{
          position: "absolute",
          top: "24px",
          right: "24px",
          background: "rgba(255,255,255,0.1)",
          border: "none",
          color: "#fff",
          padding: "8px",
          borderRadius: "50%",
          cursor: "pointer",
          zIndex: 101,
        }}
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      <img
        src={previewImage}
        alt="Preview"
        style={{
          maxWidth: "100%",
          maxHeight: "100%",
          objectFit: "contain",
          borderRadius: "8px",
        }}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}
