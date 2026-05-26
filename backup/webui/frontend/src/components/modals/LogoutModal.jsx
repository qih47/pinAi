import React from "react";

export default function LogoutModal({
  setIsLogoutModalOpen,
  handleLogout,
}) {
  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-[#18181e] rounded-3xl p-6 max-w-sm w-full mx-4 shadow-2xl animate-zoom-in border border-gray-100 dark:border-[#232326]">
        <div className="text-center">
          <div className="w-16 h-16 bg-red-50 dark:bg-red-900/30 text-red-500 dark:text-red-400 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
            ⚠️
          </div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
            Konfirmasi Keluar
          </h3>
          <p className="text-gray-500 dark:text-gray-300 mt-2 text-sm leading-relaxed">
            Anda yakin ingin keluar? dalam mode guest anda tidak bisa
            melihat dokumen peraturan PT Pindad.
          </p>
        </div>
        <div className="flex space-x-3 mt-8">
          <button
            onClick={() => setIsLogoutModalOpen(false)}
            className="flex-1 px-4 py-3 bg-gray-100 dark:bg-[#232326] text-gray-700 dark:text-gray-200 rounded-2xl font-semibold hover:bg-gray-200 dark:hover:bg-[#29293a] transition-all active:scale-95"
          >
            Batal
          </button>
          <button
            onClick={handleLogout}
            className="flex-1 px-4 py-3 bg-red-600 text-white rounded-2xl font-semibold hover:bg-red-700 transition-all shadow-lg shadow-red-200 active:scale-95"
          >
            Ya, Keluar
          </button>
        </div>
      </div>
    </div>
  );
}