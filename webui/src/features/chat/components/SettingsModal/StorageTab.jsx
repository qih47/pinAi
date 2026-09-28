import React, { useEffect, useState } from "react";
import { 
  HardDrive, RefreshCw, Trash2, Image, FileCode, MessageSquare, 
  Users, AlertTriangle, ShieldAlert, CheckCircle2, Loader2, Sparkles
} from "lucide-react";
import { translations } from "../../../../utils/translations";
import useStorageStore from "../../../../stores/useStorageStore";
import StorageConfirmModal from "./StorageConfirmModal";

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function StorageTab({ darkMode = true, language = "id" }) {
  const t = translations[language]?.settings || translations.id.settings;
  const {
    storageStats,
    isLoading,
    isPurging,
    fetchStorageStats,
    purgeAttachments,
    purgeArtifacts,
    clearPrivateChats,
    clearCollabs,
    wipeAllUserData
  } = useStorageStore();

  const [feedbackMsg, setFeedbackMsg] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // 'purge_attachments' | 'purge_artifacts' | 'clear_chats' | 'clear_collabs' | 'wipe_all' | null

  useEffect(() => {
    fetchStorageStats();
  }, [fetchStorageStats]);

  const showFeedback = (msg, isError = false) => {
    setFeedbackMsg({ text: msg, isError });
    setTimeout(() => setFeedbackMsg(null), 4000);
  };

  const handleExecuteConfirm = async (actionType) => {
    try {
      if (actionType === "purge_attachments") {
        const res = await purgeAttachments();
        showFeedback(`Berhasil membebaskan ${formatBytes(res.freed_bytes)} dari ${res.freed_files_count} berkas lampiran.`);
      } else if (actionType === "purge_artifacts") {
        const res = await purgeArtifacts();
        showFeedback(`Berhasil membersihkan ${formatBytes(res.freed_bytes)} artefak AI.`);
      } else if (actionType === "clear_chats") {
        const res = await clearPrivateChats();
        showFeedback(`Berhasil menghapus ${res.deleted_sessions_count} sesi percakapan pribadi.`);
      } else if (actionType === "clear_collabs") {
        const res = await clearCollabs();
        showFeedback(`Berhasil menghapus ${res.deleted_rooms_count} ruang kolaborasi tim.`);
      } else if (actionType === "wipe_all") {
        await wipeAllUserData();
        showFeedback("Pembersihan total data berhasil diselesaikan.");
      }
    } catch (err) {
      showFeedback((t.cleanFailed || "Gagal: ") + err.message, true);
    } finally {
      setConfirmAction(null);
    }
  };

  const handlePurgeAttachments = () => setConfirmAction("purge_attachments");
  const handlePurgeArtifacts = () => setConfirmAction("purge_artifacts");
  const handleClearChats = () => setConfirmAction("clear_chats");
  const handleClearCollabs = () => setConfirmAction("clear_collabs");
  const handleWipeAll = () => setConfirmAction("wipe_all");



  const quota = storageStats?.quota_bytes || 5368709120;
  const used = storageStats?.used_bytes || 0;
  const free = storageStats?.free_bytes || Math.max(0, quota - used);
  const pct = storageStats?.used_percentage || 0;
  const breakdown = storageStats?.breakdown || {};

  const attachBytes = breakdown.attachments?.bytes || 0;
  const artifactBytes = breakdown.artifacts?.bytes || 0;
  const chatBytes = breakdown.chats?.bytes || 0;
  const collabBytes = breakdown.collabs?.bytes || 0;

  const attachPct = quota > 0 ? (attachBytes / quota) * 100 : 0;
  const artifactPct = quota > 0 ? (artifactBytes / quota) * 100 : 0;
  const chatPct = quota > 0 ? (chatBytes / quota) * 100 : 0;
  const collabPct = quota > 0 ? (collabBytes / quota) * 100 : 0;

  return (
    <div className="space-y-6 pb-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4 dark:border-gray-800 border-gray-200">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2">
            <HardDrive size={20} className="text-blue-500" />
            <span>{t.storageTitle}</span>
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            {t.storageSubtitle}
          </p>
        </div>
        <button
          onClick={() => fetchStorageStats(true)}
          disabled={isLoading || isPurging}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors self-start sm:self-auto ${
            darkMode 
              ? "bg-gray-800/80 hover:bg-gray-700/80 border-gray-700 text-gray-300" 
              : "bg-gray-100 hover:bg-gray-200 border-gray-300 text-gray-700"
          }`}
          title={t.refreshStorage}
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          <span>{t.refreshStorage}</span>
        </button>
      </div>

      {/* Alert / Feedback Notification */}
      {feedbackMsg && (
        <div className={`p-3 rounded-xl text-xs flex items-center gap-2 transition-all ${
          feedbackMsg.isError 
            ? "bg-red-500/10 text-red-400 border border-red-500/20" 
            : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
        }`}>
          {feedbackMsg.isError ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* Quota Status Warning Card (if >= 80%) */}
      {pct >= 80 && (
        <div className={`p-3.5 rounded-xl border flex items-center gap-3 ${
          pct >= 90 
            ? "bg-red-500/10 border-red-500/30 text-red-400" 
            : "bg-amber-500/10 border-amber-500/30 text-amber-400"
        }`}>
          <AlertTriangle size={20} className="flex-shrink-0 animate-pulse" />
          <div className="text-xs">
            <span className="font-bold">
              {pct >= 90 ? t.storageCriticalQuotaWarning.replace("{pct}", pct) : t.storageNearQuotaWarning.replace("{pct}", pct)}
            </span>
          </div>
        </div>
      )}

      {/* Main Storage Capacity Overview Card */}
      <div className={`p-5 rounded-2xl border ${darkMode ? "bg-[#18181c] border-gray-800/80" : "bg-gray-50/80 border-gray-200"}`}>
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 mb-3">
          <div>
            <span className="text-2xl font-black tracking-tight">
              {formatBytes(used)}
            </span>
            <span className="text-xs text-gray-400 font-medium ml-2">
              dari {formatBytes(quota)} ({pct}%)
            </span>
          </div>
          <span className="text-xs font-medium text-emerald-400">
            {t.storageFreeLeft.replace("{free}", formatBytes(free))}
          </span>
        </div>

        {/* Multi-segmented Visual Storage Bar */}
        <div className="w-full h-3 rounded-full overflow-hidden flex bg-gray-800/40 p-0.5 border border-gray-700/30">
          {attachPct > 0 && (
            <div 
              className="h-full bg-indigo-500 rounded-l-full transition-all duration-500" 
              style={{ width: `${Math.max(1, attachPct)}%` }} 
              title={`Lampiran: ${formatBytes(attachBytes)} (${attachPct.toFixed(1)}%)`}
            />
          )}
          {artifactPct > 0 && (
            <div 
              className="h-full bg-emerald-500 transition-all duration-500" 
              style={{ width: `${Math.max(1, artifactPct)}%` }} 
              title={`Artefak AI: ${formatBytes(artifactBytes)} (${artifactPct.toFixed(1)}%)`}
            />
          )}
          {chatPct > 0 && (
            <div 
              className="h-full bg-amber-500 transition-all duration-500" 
              style={{ width: `${Math.max(0.5, chatPct)}%` }} 
              title={`Chat Pribadi: ${formatBytes(chatBytes)} (${chatPct.toFixed(1)}%)`}
            />
          )}
          {collabPct > 0 && (
            <div 
              className="h-full bg-cyan-500 transition-all duration-500" 
              style={{ width: `${Math.max(0.5, collabPct)}%` }} 
              title={`Diskusi Collab: ${formatBytes(collabBytes)} (${collabPct.toFixed(1)}%)`}
            />
          )}
        </div>

        {/* Legend / Category Breakdowns */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t dark:border-gray-800/60 border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 flex-shrink-0" />
            <div className="text-[11px] truncate">
              <p className="text-gray-400 truncate">{t.storageAttachments}</p>
              <p className="font-semibold">{formatBytes(attachBytes)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0" />
            <div className="text-[11px] truncate">
              <p className="text-gray-400 truncate">{t.storageArtifacts}</p>
              <p className="font-semibold">{formatBytes(artifactBytes)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500 flex-shrink-0" />
            <div className="text-[11px] truncate">
              <p className="text-gray-400 truncate">{t.storageChats}</p>
              <p className="font-semibold">{formatBytes(chatBytes)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-500 flex-shrink-0" />
            <div className="text-[11px] truncate">
              <p className="text-gray-400 truncate">{t.storageCollabs}</p>
              <p className="font-semibold">{formatBytes(collabBytes)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Smart Cleaners (Recommended) */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-emerald-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
            {t.smartCleanup}
          </h3>
        </div>
        <p className="text-xs text-gray-400 -mt-1">
          {t.smartCleanupDesc}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          {/* Card 1: Purge Attachments Only */}
          <div className={`p-4 rounded-xl border flex flex-col justify-between gap-3 ${
            darkMode ? "bg-[#18181c] border-gray-800/80" : "bg-gray-50 border-gray-200"
          }`}>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-indigo-500/15 text-indigo-400 flex-shrink-0">
                <Image size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold">{t.purgeAttachmentsBtn}</h4>
                <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                  {t.purgeAttachmentsDesc}
                </p>
              </div>
            </div>
            <button
              onClick={handlePurgeAttachments}
              disabled={isPurging || attachBytes === 0}
              className="w-full py-2 px-3 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPurging ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              <span>{t.purgeAttachmentsBtn} ({formatBytes(attachBytes)})</span>
            </button>
          </div>

          {/* Card 2: Purge AI Artifacts */}
          <div className={`p-4 rounded-xl border flex flex-col justify-between gap-3 ${
            darkMode ? "bg-[#18181c] border-gray-800/80" : "bg-gray-50 border-gray-200"
          }`}>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/15 text-emerald-400 flex-shrink-0">
                <FileCode size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold">{t.purgeArtifactsBtn}</h4>
                <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                  {t.purgeArtifactsDesc}
                </p>
              </div>
            </div>
            <button
              onClick={handlePurgeArtifacts}
              disabled={isPurging || artifactBytes === 0}
              className="w-full py-2 px-3 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPurging ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              <span>{t.purgeArtifactsBtn} ({formatBytes(artifactBytes)})</span>
            </button>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center gap-2">
          <ShieldAlert size={16} className="text-red-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-red-400">
            {t.dangerZone}
          </h3>
        </div>

        <div className={`p-4 rounded-xl border space-y-4 ${
          darkMode ? "bg-red-950/10 border-red-500/20" : "bg-red-50/50 border-red-200"
        }`}>
          {/* Action 1: Delete All Private Chats */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b dark:border-red-500/15 border-red-200/60">
            <div>
              <h4 className="text-xs font-bold text-gray-200">{t.clearChatsBtn}</h4>
              <p className="text-[11px] text-gray-400 mt-0.5">{t.clearChatsDesc}</p>
            </div>
            <button
              onClick={handleClearChats}
              disabled={isPurging || (breakdown.chats?.count === 0 && chatBytes === 0)}
              className="py-1.5 px-3 rounded-lg text-xs font-semibold bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            >
              {t.clearChatsBtn}
            </button>
          </div>

          {/* Action 2: Delete All Collabs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b dark:border-red-500/15 border-red-200/60">
            <div>
              <h4 className="text-xs font-bold text-gray-200">{t.clearCollabsBtn}</h4>
              <p className="text-[11px] text-gray-400 mt-0.5">{t.clearCollabsDesc}</p>
            </div>
            <button
              onClick={handleClearCollabs}
              disabled={isPurging || (breakdown.collabs?.count === 0 && collabBytes === 0)}
              className="py-1.5 px-3 rounded-lg text-xs font-semibold bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            >
              {t.clearCollabsBtn}
            </button>
          </div>

          {/* Action 3: Wipe All Data */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h4 className="text-xs font-bold text-red-400">{t.wipeAllBtn}</h4>
              <p className="text-[11px] text-gray-400 mt-0.5">{t.wipeAllDesc}</p>
            </div>
            <button
              onClick={handleWipeAll}
              disabled={isPurging || used === 0}
              className="py-1.5 px-3 rounded-lg text-xs font-bold bg-red-600 hover:bg-red-500 text-white transition-all shadow-md shadow-red-600/20 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            >
              {t.wipeAllBtn}
            </button>
          </div>
        </div>
      </div>

      {/* 🛡️ INTERACTIVE CONFIRMATION POPUP MODAL */}
      <StorageConfirmModal
        isOpen={Boolean(confirmAction)}
        actionType={confirmAction}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleExecuteConfirm}
        isLoading={isPurging}
        darkMode={darkMode}
        language={language}
      />
    </div>
  );
}
