import React from "react";

export default function LoginModal({
  setShowLoginModal,
  loginForm,
  setLoginForm,
  loginError,
  handleLoginSubmit,
  showPassword,
  setShowPassword,
  cakraLogo,
}) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#232326] rounded-2xl shadow-2xl p-8 relative border border-gray-100 dark:border-[#232326]">
        <button
          onClick={() => setShowLoginModal(false)}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          ✕
        </button>
        <div className="text-center mb-8">
          <div className="absolute top-4 left-4 flex items-center z-50">
            <img
              src={cakraLogo}
              alt="CAKRA AI Logo"
              className="w-10 h-10 object-cover rounded-full"
              style={{
                animation: "spin-once 2s cubic-bezier(0.4,0,0.2,1) 1",
              }}
            />
          </div>
          <h2 className="mt-2 text-2xl font-bold text-gray-800 dark:text-blue-200">
            Login CAKRA AI
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Gunakan NPP dan password ESS
          </p>
        </div>
        <form onSubmit={handleLoginSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              NPP
            </label>
            <input
              type="text"
              required
              className="w-full px-4 py-2 border border-gray-300 dark:border-[#232326] rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white dark:bg-[#1a1a1c] text-gray-900 dark:text-gray-100"
              value={loginForm.username}
              onChange={(e) =>
                setLoginForm({ ...loginForm, username: e.target.value })
              }
              placeholder="NPP"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                className="w-full px-4 py-2 border border-gray-300 dark:border-[#232326] rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white dark:bg-[#1a1a1c] text-gray-900 dark:text-gray-100 pr-12"
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                placeholder="••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-500 transition-colors"
              >
                {showPassword ? (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-5 h-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-5 h-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
                    />
                  </svg>
                )}
              </button>
            </div>
          </div>
          {loginError && (
            <p className="text-red-500 text-xs mt-1 animate-pulse">
              {loginError}
            </p>
          )}
          <button
            type="submit"
            className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-bold hover:opacity-90 transition-opacity mt-4"
          >
            Masuk Sekarang
          </button>
        </form>
      </div>
    </div>
  );
}