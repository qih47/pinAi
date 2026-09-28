import React from "react";
import { AlertTriangle, HardDrive, Trash2, Settings, X, Loader2 } from "lucide-react";
import { translations } from "../../../utils/translations";
import useStorageStore from "../../../stores/useStorageStore";

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function StorageQuotaModal({
  isOpen,
  onClose,
  onOpenSettings,
  darkMode = true,
  language = "id"
}) {
  const t = translations[language]?.settings || translations.id.settings;
  const { storageStats, isPurging, purgeAttachments, fetchStorageStats } = useStorageStore();

  if (!isOpen) return null;

  const used = storageStats?.used_bytes || 0;
  const total = storageStats?.quota_bytes || 5368709120;
  const pct = storageStats?.used_percentage || 98.0;
  const formattedUsed = formatBytes(used);
  const formattedTotal = formatBytes(total);

  const handleQuickPurge = async () => {
    try {
      await purgeAttachments();
      await fetchStorageStats(true);
      onClose();
    } catch (err) {
      alert((t.cleanFailed || "Gagal membersihkan: ") + err.message);
    }
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div 
        className={`w-full max-w-md rounded-2xl p-6 shadow-2xl border relative flex flex-col gap-4 ${
          darkMode 
            ? "bg-[#1e1e24] text-gray-100 border-red-500/30 shadow-red-950/30" 
            : "bg-white text-gray-800 border-red-200 shadow-red-200/50"
        }`}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isPurging}
          className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-gray-500/20 text-gray-400 hover:text-gray-200 transition-colors"
        >
          <X size={18} />
        </button>

        {/* Header Icon & Title */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-red-500/15 text-red-500 flex-shrink-0 animate-pulse">
            <AlertTriangle size={24} />
          </div>
          <div>
            <h3 className="text-base font-bold text-red-500">
              {t.storageQuotaExceededTitle}
            </h3>
            <p className="text-xs text-gray-400">
              {t.storageSubtitle}
            </p>
          </div>
        </div>

        {/* Description */}
        <p className="text-xs leading-relaxed opacity-90">
          {t.storageQuotaExceededDesc.replace("{pct}", pct)}
        </p>

        {/* Visual Storage Meter */}
        <div className={`p-3.5 rounded-xl border ${darkMode ? "bg-black/30 border-gray-800" : "bg-gray-50 border-gray-200"}`}>
          <div className="flex justify-between items-center text-xs font-semibold mb-2">
            <span className="flex items-center gap-1.5">
              <HardDrive size={13} className="text-red-400" />
              <span>{t.storageQuota}</span>
            </span>
            <span className="text-red-400 font-mono">
              {formattedUsed} / {formattedTotal} ({pct}%)
            </span>
          </div>

          <div className="w-full h-2 rounded-full overflow-hidden bg-gray-700/40">
            <div 
              className="h-full bg-gradient-to-r from-amber-500 to-red-500 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(5, pct))}%` }}
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2.5 pt-1">
          {/* 1-Click Fast Cleanup: Purge Attachments only */}
          <button
            onClick={handleQuickPurge}
            disabled={isPurging}
            className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white shadow-lg shadow-red-600/30 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {isPurging ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                <span>Membersihkan ruang...</span>
              </>
            ) : (
              <>
                <Trash2 size={15} />
                <span>{t.quickPurgeAttachmentsBtn}</span>
              </>
            )}
          </button>

          {/* Open Detailed Settings */}
          <button
            onClick={() => {
              onClose();
              if (onOpenSettings) onOpenSettings();
            }}
            disabled={isPurging}
            className={`w-full py-2 px-4 rounded-xl text-xs font-medium flex items-center justify-center gap-2 border transition-all ${
              darkMode 
                ? "bg-gray-800/60 hover:bg-gray-800 border-gray-700 text-gray-300" 
                : "bg-gray-100 hover:bg-gray-200 border-gray-300 text-gray-700"
            }`}
          >
            <Settings size={14} />
            <span>{t.manageStorageBtn}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
