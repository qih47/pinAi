import React, { useEffect, useRef, useState, useCallback } from 'react';
import apiClient from '../../../services/apiClient';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import { 
  FileText, 
  RotateCw, 
  Download, 
  AlertTriangle, 
  ExternalLink, 
  CheckCircle2, 
  Loader2,
  Terminal,
  HelpCircle
} from 'lucide-react';

const ONLYOFFICE_SERVER_URL = import.meta.env.VITE_ONLYOFFICE_URL || 'http://localhost:8085';

const OnlyOfficeWorkspace = ({
  docId,
  docTitle = 'Dokumen Resmi PT Pindad',
  templateId = 'template_blank',
  darkMode = true,
  theme,
  sessionId = '',
  roomId = '',
  onSaved,
  onClose
}) => {
  const containerRef = useRef(null);
  const docEditorRef = useRef(null);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [isSaved, setIsSaved] = useState(true);
  const [serverOnline, setServerOnline] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const lastAiEditTimestamp = useDocWriterStore((state) => state.lastAiEditTimestamp);

  // Auto-reload jika AI memperbarui dokumen Word di backend
  useEffect(() => {
    if (lastAiEditTimestamp) {
      console.log('[ONLYOFFICE] AI edit terdeteksi, memuat ulang editor dokumen...');
      setRetryCount((prev) => prev + 1);
    }
  }, [lastAiEditTimestamp]);

  // Dapatkan NPP dan sesi aktif
  const currentUser = (() => {
    try {
      const raw = localStorage.getItem('cakra_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  })();

  const currentNpp = currentUser?.npp || 'guest';
  const currentName = currentUser?.nama || currentUser?.name || 'Pegawai PT Pindad';

  // Helper untuk memuat skrip DocsAPI dari ONLYOFFICE Server
  const loadDocsApiScript = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (window.DocsAPI) {
        resolve(window.DocsAPI);
        return;
      }

      const scriptId = 'onlyoffice-api-script';
      const existingScript = document.getElementById(scriptId);
      if (existingScript) {
        existingScript.remove();
      }

      const script = document.createElement('script');
      script.id = scriptId;
      script.src = `${ONLYOFFICE_SERVER_URL}/web-apps/apps/api/documents/api.js`;
      script.async = true;

      script.onload = () => {
        if (window.DocsAPI) {
          resolve(window.DocsAPI);
        } else {
          reject(new Error('DocsAPI tidak ditemukan pada skrip ONLYOFFICE'));
        }
      };

      script.onerror = () => {
        reject(new Error(`Gagal menghubungi ONLYOFFICE Document Server di ${ONLYOFFICE_SERVER_URL}`));
      };

      document.head.appendChild(script);
    });
  }, []);

  // Inisialisasi Editor
  const initEditor = useCallback(async () => {
    if (!docId) return;

    setIsLoading(true);
    setLoadError(null);

    try {
      // 1. Ambil Konfigurasi DocsAPI + JWT dari backend CAKRA
      const configRes = await apiClient.get(`/doc-writer/config/${docId}`, {
        params: {
          npp: currentNpp,
          user_name: currentName,
          session_id: sessionId || '',
          room_id: roomId || ''
        }
      });

      if (!configRes.data?.success || !configRes.data?.config) {
        throw new Error('Gagal menerima konfigurasi editor dari server backend.');
      }

      const editorConfig = configRes.data.config;

      // 2. Muat skrip DocsAPI ONLYOFFICE
      await loadDocsApiScript();
      setServerOnline(true);

      // 3. Bersihkan editor sebelumnya jika ada
      if (docEditorRef.current && typeof docEditorRef.current.destroyEditor === 'function') {
        try {
          docEditorRef.current.destroyEditor();
        } catch (e) {
          console.warn('[ONLYOFFICE] Destroy previous editor:', e);
        }
        docEditorRef.current = null;
      }

      // Pastikan wadah HTML bersih
      const placeholderId = `onlyoffice-canvas-${docId}`;
      if (containerRef.current) {
        containerRef.current.innerHTML = `<div id="${placeholderId}" style="width: 100%; height: 100%;"></div>`;
      }

      // 4. Hubungkan event handlers
      editorConfig.events = {
        onAppReady: () => {
          setIsLoading(false);
          setLoadError(null);
        },
        onDocumentReady: () => {
          setIsLoading(false);
          setIsSaved(true);
        },
        onDocumentStateChange: (event) => {
          const hasChanges = Boolean(event?.data);
          setIsSaved(!hasChanges);
          if (!hasChanges && onSaved) onSaved();
        },
        onError: (event) => {
          console.error('[ONLYOFFICE] Error event:', event);
          setIsLoading(false);
          setLoadError(event?.data?.message || 'Terjadi kesalahan saat merender editor ONLYOFFICE.');
        },
        onRequestSaveObject: () => {
          setIsSaved(true);
        }
      };

      // Terapkan kustomisasi tema ke ONLYOFFICE
      if (editorConfig.editorConfig) {
        editorConfig.editorConfig.customization = {
          ...editorConfig.editorConfig.customization,
          uiTheme: darkMode ? 'theme-dark' : 'theme-classic-light'
        };
      }

      // 5. Inisialisasi DocsAPI.DocEditor
      docEditorRef.current = new window.DocsAPI.DocEditor(placeholderId, editorConfig);
      setIsLoading(false);
    } catch (err) {
      console.error('[ONLYOFFICE] Init failed:', err);
      setIsLoading(false);
      setLoadError(err.message || 'Gagal memuat Document Editor.');
      setServerOnline(false);
    }
  }, [docId, currentNpp, currentName, darkMode, loadDocsApiScript, onSaved]);

  useEffect(() => {
    initEditor();

    return () => {
      if (docEditorRef.current && typeof docEditorRef.current.destroyEditor === 'function') {
        try {
          docEditorRef.current.destroyEditor();
        } catch (e) {
          // ignore
        }
        docEditorRef.current = null;
      }
    };
  }, [docId, retryCount, initEditor]);

  // Handler reload dokumen
  const handleReload = () => {
    setRetryCount((prev) => prev + 1);
  };

  // Handler download dokumen .docx
  const handleDownload = () => {
    if (!docId) return;
    const baseUrl = apiClient.defaults.baseURL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
    const downloadUrl = `${baseUrl}/doc-writer/download/${docId}?npp=${encodeURIComponent(currentNpp)}&session_id=${encodeURIComponent(sessionId || '')}&room_id=${encodeURIComponent(roomId || '')}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', `${docTitle || 'Dokumen_PT_Pindad'}.docx`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden select-none">
      {/* ── Sub-Bar: Info Autosave & Action Buttons ── */}
      <div 
        className="px-3.5 py-1.5 flex items-center justify-between border-b text-[11px] shrink-0"
        style={{
          background: darkMode ? '#18181b' : '#f8fafc',
          borderColor: darkMode ? '#2d2d32' : '#e2e8f0',
          color: darkMode ? '#94a3b8' : '#64748b'
        }}
      >
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold text-sky-500">ONLYOFFICE Docs v8</span>
          </div>
          <span>•</span>
          <span className={isSaved ? 'text-emerald-500 font-medium' : 'text-amber-500 font-medium'}>
            {isSaved ? 'Semua perubahan tersimpan' : 'Menyimpan ke disk...'}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleReload}
            disabled={isLoading}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition-all ${
              darkMode ? 'hover:bg-white/10 text-slate-300' : 'hover:bg-slate-200 text-slate-700'
            }`}
            title="Muat ulang editor jika terdapat pembaruan dari AI"
          >
            <RotateCw size={12} className={isLoading ? 'animate-spin' : ''} />
            <span>Reload</span>
          </button>

          <button
            type="button"
            onClick={handleDownload}
            className={`flex items-center gap-1 px-2.5 py-0.5 rounded font-medium border transition-all ${
              darkMode 
                ? 'bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border-sky-500/30' 
                : 'bg-sky-50 hover:bg-sky-100 text-sky-700 border-sky-200'
            }`}
            title="Unduh berkas Word (.docx)"
          >
            <Download size={12} />
            <span>Unduh .docx</span>
          </button>
        </div>
      </div>

      {/* ── Main Canvas Area ── */}
      <div className="flex-1 relative w-full h-full min-h-0 bg-slate-900">
        {/* Loading Spinner */}
        {isLoading && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm text-slate-300">
            <Loader2 size={36} className="text-sky-400 animate-spin mb-3" />
            <p className="text-sm font-medium">Menghubungkan ke ONLYOFFICE Document Server...</p>
            <p className="text-xs text-slate-400 mt-1">Menyiapkan kanvas Word berskala korporat PT Pindad</p>
          </div>
        )}

        {/* Fallback Banner saat server ONLYOFFICE Docker belum aktif */}
        {loadError && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center p-6 bg-slate-950/95 text-slate-200 overflow-y-auto custom-scrollbar">
            <div className="w-full max-w-lg p-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 shadow-2xl">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                  <AlertTriangle size={24} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-amber-300">
                    Layanan ONLYOFFICE Document Server Belum Aktif
                  </h3>
                  <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                    Dokumen Anda telah tersimpan dengan aman di server backend CAKRA, namun penampil native Word (.docx) membutuhkan container Docker ONLYOFFICE pada port 8085.
                  </p>

                  {/* Perintah Docker */}
                  <div className="mt-3.5 p-3 rounded-xl bg-black/60 border border-white/10 font-mono text-xs text-emerald-400 space-y-1">
                    <div className="text-[11px] text-slate-400 flex items-center gap-1 mb-1">
                      <Terminal size={12} />
                      <span>Jalankan di Terminal Server:</span>
                    </div>
                    <div>docker-compose -f docker-compose.onlyoffice.yml up -d</div>
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3 pt-3 border-t border-white/10">
                    <button
                      type="button"
                      onClick={handleDownload}
                      className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-semibold flex items-center gap-1.5 transition-all text-slate-200"
                    >
                      <Download size={13} />
                      <span>Tetap Unduh .docx</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleReload}
                      className="px-3.5 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-xs font-semibold text-white shadow-md transition-all flex items-center gap-1.5"
                    >
                      <RotateCw size={13} />
                      <span>Coba Hubungkan Kembali</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Iframe ONLYOFFICE Canvas Container */}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  );
};

export default OnlyOfficeWorkspace;
