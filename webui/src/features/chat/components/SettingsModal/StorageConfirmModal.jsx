import React, { useState, useEffect } from "react";
import { AlertTriangle, Trash2, ShieldAlert, X, Loader2, Sparkles } from "lucide-react";

export default function StorageConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  actionType, // 'purge_attachments' | 'purge_artifacts' | 'clear_chats' | 'clear_collabs' | 'wipe_all'
  isLoading = false,
  darkMode = true,
  language = "id"
}) {
  const [typedKeyword, setTypedKeyword] = useState("");

  useEffect(() => {
    if (isOpen) {
      setTypedKeyword("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const isWipeAll = actionType === "wipe_all";
  const isDanger = ["clear_chats", "clear_collabs", "wipe_all"].includes(actionType);

  const getModalConfig = () => {
    switch (actionType) {
      case "purge_attachments":
        return {
          title: language === "en" ? "Clear File Attachments?" : "Bersihkan Lampiran Berkas?",
          description: language === "en"
            ? "This will delete uploaded images, PDFs, and files from server storage. Your entire chat message text history remains completely intact."
            : "Tindakan ini akan menghapus file fisik foto, PDF, dan dokumen lama dari disk server. Seluruh isi teks percakapan chat Anda tetap tersimpan utuh dan dapat dibaca.",
          confirmBtnText: language === "en" ? "Yes, Clear Attachments" : "Ya, Bersihkan Lampiran",
          confirmBtnClass: "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/20",
          iconBg: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
        };
      case "purge_artifacts":
        return {
          title: language === "en" ? "Clear AI Artifacts?" : "Bersihkan Artefak AI?",
          description: language === "en"
            ? "This will delete AI-generated draft documents and temporary artifact files from storage."
            : "Tindakan ini akan menghapus berkas draf dokumen hasil buatan AI dan file artefak sementara dari penyimpanan.",
          confirmBtnText: language === "en" ? "Yes, Clear Artifacts" : "Ya, Bersihkan Artefak",
          confirmBtnClass: "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20",
          iconBg: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        };
      case "clear_chats":
        return {
          title: language === "en" ? "Delete All Private Chats?" : "Hapus Semua Percakapan Pribadi?",
          description: language === "en"
            ? "WARNING: All your private conversation history and messages will be permanently deleted. This action cannot be undone."
            : "PERINGATAN: Seluruh riwayat obrolan dan pesan percakapan pribadi Anda akan dihapus secara permanen. Tindakan ini tidak dapat dibatalkan.",
          confirmBtnText: language === "en" ? "Delete All Chats" : "Hapus Semua Chat",
          confirmBtnClass: "bg-red-600 hover:bg-red-500 text-white shadow-red-600/20",
          iconBg: "bg-red-500/15 text-red-400 border-red-500/30",
        };
      case "clear_collabs":
        return {
          title: language === "en" ? "Delete Collab Rooms?" : "Hapus Ruang Kolaborasi Tim?",
          description: language === "en"
            ? "WARNING: All collaboration rooms you created will be deleted, and you will leave any rooms you joined."
            : "PERINGATAN: Semua ruang diskusi tim yang Anda buat akan dihapus dan Anda akan keluar dari seluruh ruang kolaborasi lain.",
          confirmBtnText: language === "en" ? "Delete Collab Rooms" : "Hapus Ruang Collab",
          confirmBtnClass: "bg-red-600 hover:bg-red-500 text-white shadow-red-600/20",
          iconBg: "bg-red-500/15 text-red-400 border-red-500/30",
        };
      case "wipe_all":
        return {
          title: language === "en" ? "Total Data Wipe (Reset)?" : "Pembersihan Total Data (Reset)?",
          description: language === "en"
            ? "CRITICAL WARNING: This will permanently delete ALL your private chats, attached files, artifacts, and collaboration rooms. Your account will be reset like brand new. Type 'HAPUS' below to proceed."
            : "PERINGATAN KRUSIAL: Ini akan menghapus SELURUH percakapan chat, berkas fisik lampiran, artefak AI, dan ruang kolaborasi Anda. Akun Anda akan di-reset bersih seperti baru. Ketik 'HAPUS' di bawah untuk melanjutkan.",
          confirmBtnText: language === "en" ? "Wipe All Data Permanently" : "Reset & Hapus Seluruh Data",
          confirmBtnClass: "bg-red-600 hover:bg-red-500 text-white shadow-red-600/30",
          iconBg: "bg-red-500/20 text-red-500 border-red-500/40",
        };
      default:
        return {
          title: "Konfirmasi Tindakan",
          description: "Apakah Anda yakin ingin melanjutkan?",
          confirmBtnText: "Lanjutkan",
          confirmBtnClass: "bg-blue-600 text-white",
          iconBg: "bg-blue-500/15 text-blue-400 border-blue-500/30",
        };
    }
  };

  const config = getModalConfig();
  const canConfirm = isWipeAll ? typedKeyword.trim().toUpperCase() === "HAPUS" : true;

  const handleConfirmClick = () => {
    if (!canConfirm || isLoading) return;
    onConfirm(actionType);
  };

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div
        className={`w-full max-w-md rounded-2xl p-6 shadow-2xl border relative flex flex-col gap-4 animate-scale-up ${
          darkMode
            ? "bg-[#1e1e24] text-gray-100 border-gray-700/60 shadow-black/60"
            : "bg-white text-gray-800 border-gray-200 shadow-xl"
        }`}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isLoading}
          className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-gray-500/20 text-gray-400 hover:text-gray-200 transition-colors"
        >
          <X size={18} />
        </button>

        {/* Header Icon & Title */}
        <div className="flex items-start gap-3.5 pr-6">
          <div className={`p-3 rounded-xl border flex-shrink-0 ${config.iconBg}`}>
            {isDanger ? <ShieldAlert size={24} /> : <Sparkles size={24} />}
          </div>
          <div>
            <h3 className={`text-base font-bold leading-tight ${isDanger ? "text-red-400" : "text-gray-100"}`}>
              {config.title}
            </h3>
            <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">
              {config.description}
            </p>
          </div>
        </div>

        {/* Input Confirmation for Total Wipe Out */}
        {isWipeAll && (
          <div className="space-y-1.5 pt-1">
            <label className="text-[11px] font-semibold text-gray-300">
              {language === "en" ? "Type 'HAPUS' to confirm:" : "Ketik 'HAPUS' untuk mengonfirmasi:"}
            </label>
            <input
              type="text"
              value={typedKeyword}
              onChange={(e) => setTypedKeyword(e.target.value)}
              placeholder="HAPUS"
              className={`w-full px-3.5 py-2 text-sm rounded-xl font-mono border focus:outline-none transition-colors ${
                darkMode
                  ? "bg-[#141416] border-red-500/40 text-white placeholder-gray-600 focus:border-red-500"
                  : "bg-gray-50 border-red-300 text-gray-900 placeholder-gray-400 focus:border-red-500"
              }`}
            />
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5 pt-3 border-t dark:border-gray-800 border-gray-200">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className={`px-4 py-2 rounded-xl text-xs font-medium border transition-colors ${
              darkMode
                ? "bg-gray-800/80 hover:bg-gray-700/80 border-gray-700 text-gray-300"
                : "bg-gray-100 hover:bg-gray-200 border-gray-300 text-gray-700"
            }`}
          >
            {language === "en" ? "Cancel" : "Batal"}
          </button>
          <button
            type="button"
            onClick={handleConfirmClick}
            disabled={!canConfirm || isLoading}
            className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed ${config.confirmBtnClass}`}
          >
            {isLoading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>{language === "en" ? "Processing..." : "Memproses..."}</span>
              </>
            ) : (
              <>
                <Trash2 size={14} />
                <span>{config.confirmBtnText}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
