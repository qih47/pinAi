import React from "react";

export default function NotificationToast({ notification }) {
  return (
    <div className="fixed top-0 left-0 right-0 z-[100] flex justify-center pointer-events-none">
      <div
        className={`
          mt-6 px-6 py-3 rounded-2xl shadow-2xl text-white font-semibold
          flex items-center gap-3
          transform transition-all duration-500 ease-out
          animate-in fade-in slide-in-from-top-8
          ${
            notification.type === "success"
              ? "bg-emerald-600/90 backdrop-blur-md border border-emerald-400/20"
              : notification.type === "error"
              ? "bg-rose-600/90 backdrop-blur-md border border-rose-400/20"
              : "bg-blue-600/90 backdrop-blur-md border border-blue-400/20"
          }
        `}
        style={{
          animation: "slideDown 0.4s ease-out forwards",
        }}
      >
        {notification.type === "success" && (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
        )}

        <span className="text-sm tracking-wide">{notification.message}</span>
      </div>

      <style
        dangerouslySetInnerHTML={{
          __html: `
            @keyframes slideDown {
              from { transform: translateY(-100%); opacity: 0; }
              to { transform: translateY(0); opacity: 1; }
            }
          `,
        }}
      />
    </div>
  );
}