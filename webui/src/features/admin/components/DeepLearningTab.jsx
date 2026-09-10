import React, { useState, useEffect, useRef } from 'react';
import { 
  Brain, 
  FileText, 
  Activity, 
  Database, 
  GitMerge, 
  FileImage, 
  Play, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Layers, 
  Sparkles, 
  RotateCcw,
  Search,
  Moon,
  Square,
  Zap,
  ShieldCheck,
  Calendar,
  Terminal,
  Code2,
  Maximize2,
  ExternalLink,
  Network,
  Copy,
  Check,
  Eye,
  BookOpen,
  ChevronRight,
  Pause,
  RefreshCw,
  AlertCircle,
  FileCode,
  ListFilter,
  CornerDownRight,
  ZoomIn,
  ZoomOut,
  X
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

const DeepLearningTab = () => {
  const [activeSubTab, setActiveSubTab] = useState('pipelines'); // 'pipelines' | 'synthetic' | 'jobs'
  const [sourceDocs, setSourceDocs] = useState([]);
  const [syntheticDocs, setSyntheticDocs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Nightly 5-Worker Training State
  const [nightlyStatus, setNightlyStatus] = useState(null);
  const [isNightlyStarting, setIsNightlyStarting] = useState(false);
  const [isNightlyStopping, setIsNightlyStopping] = useState(false);
  const [isSyncingCatalog, setIsSyncingCatalog] = useState(false);
  
  // Live Job Monitor & Two-Page Spread State
  const [liveMonitor, setLiveMonitor] = useState(null);
  const [monitorTab, setMonitorTab] = useState('terminal'); // 'terminal' | 'chunks' | 'qa' | 'graph' | 'lora'
  const [workerFilter, setWorkerFilter] = useState('ALL'); // 'ALL' | 'W1-TEXT' | 'W2-QA' | 'W3-GRAPH' | 'W4-VISION' | 'W5-LORA' | 'SYSTEM'
  const [autoScrollTerminal, setAutoScrollTerminal] = useState(true);
  const [previewImageModal, setPreviewImageModal] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);
  const [showLegacyJobs, setShowLegacyJobs] = useState(false);
  const terminalEndRef = useRef(null);

  // Polling control refs
  const isPollingRef = useRef(false);
  const activeSubTabRef = useRef(activeSubTab);
  activeSubTabRef.current = activeSubTab;

  // Pipeline Modal State
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [trainingMethod, setTrainingMethod] = useState('STANDARD');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBatchSubmitting, setIsBatchSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
    fetchNightlyStatus();
    fetchLiveMonitor();

    const interval = setInterval(async () => {
      // Guard against request piling/storming
      if (isPollingRef.current) return;
      isPollingRef.current = true;
      try {
        if (activeSubTabRef.current === 'jobs') {
          await Promise.all([
            fetchLiveMonitor(),
            fetchNightlyStatus()
          ]);
        } else {
          await Promise.all([
            fetchJobs(),
            fetchNightlyStatus()
          ]);
        }
      } catch (err) {
        // non-blocking
      } finally {
        isPollingRef.current = false;
      }
    }, 3500);

    return () => clearInterval(interval);
  }, [activeSubTab]);

  useEffect(() => {
    if (autoScrollTerminal && monitorTab === 'terminal' && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveMonitor?.terminal_stream, autoScrollTerminal, monitorTab]);

  const fetchLiveMonitor = async () => {
    try {
      const res = await apiClient.get('/training/nightly/live-monitor', { timeout: 7000 });
      if (res.data?.data) {
        setLiveMonitor(res.data.data);
      }
    } catch (e) {
      // non-blocking
    }
  };

  const copyToClipboard = (text, key) => {
    if (!text) return;
    const str = typeof text === 'object' ? JSON.stringify(text, null, 2) : String(text);
    navigator.clipboard.writeText(str);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const getImageUrl = (url) => {
    if (!url) return null;
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const base = typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : '';
    return `${base}${url}`;
  };

  const fetchNightlyStatus = async () => {
    try {
      const res = await apiClient.get('/training/nightly/status', { timeout: 7000 });
      if (res.data?.data) {
        setNightlyStatus(res.data.data);
      }
    } catch (e) {
      // non-blocking
    }
  };

  const handleStartNightly = async () => {
    if (!window.confirm("Mulai proses Nightly Training & Fine-Tuning sekarang? 5 worker akan memproses dokumen halaman per halaman dan menyimpan checkpoint ke ragdb.")) return;
    setIsNightlyStarting(true);
    try {
      await apiClient.post('/training/nightly/start', {});
      await fetchNightlyStatus();
    } catch (e) {
      const err = e.response?.data?.detail;
      const msg = typeof err === 'object' ? JSON.stringify(err) : (err || e.message);
      alert("Gagal memulai nightly training: " + msg);
    } finally {
      setIsNightlyStarting(false);
    }
  };

  const handleStopNightly = async () => {
    if (!window.confirm("Hentikan training malam? Sistem akan menyelesaikan halaman saat ini dan menyimpan checkpoint dengan aman ke ragdb.")) return;
    setIsNightlyStopping(true);
    try {
      await apiClient.post('/training/nightly/stop');
      await fetchNightlyStatus();
    } catch (e) {
      alert("Gagal menghentikan nightly training.");
    } finally {
      setIsNightlyStopping(false);
    }
  };

  const [isResetting, setIsResetting] = useState(false);

  const handleResetNightly = async () => {
    if (!window.confirm("⚠️ PERINGATAN RESET TRAINING KE TITIK 0:\n\nApakah Anda yakin ingin me-reset seluruh progres training malam kembali ke Titik 0 (Dokumen #1, Halaman 1)?\n\n- Seluruh 2.245 dokumen akan dikembalikan ke status PENDING\n- Dataset JSONL Call 1 Router e4b dan Call 2 Core akan diarsipkan dan dikosongkan untuk mulai fresh\n- Database MySQL peraturan_db tetap 100% aman (Read-Only)")) return;
    setIsResetting(true);
    try {
      const res = await apiClient.post('/training/nightly/reset?clean_artifacts=true');
      alert("✅ " + (res.data?.message || "Training berhasil di-reset ke titik 0!"));
      await fetchNightlyStatus();
      await fetchLiveMonitor();
    } catch (e) {
      alert("Gagal reset training: " + (e.response?.data?.detail || e.message));
    } finally {
      setIsResetting(false);
    }
  };

  const handleTestQuickNightly = async (docId = null) => {
    const label = docId ? `Dokumen ID #${docId}` : "1 Dokumen Pertama";
    if (!window.confirm(`Jalankan uji coba cepat Nightly Training untuk ${label} (maksimal 2 halaman saja)?`)) return;
    setIsNightlyStarting(true);
    try {
      const payload = { max_docs: 1, page_limit: 2 };
      if (docId) payload.doc_id = docId;
      await apiClient.post('/training/nightly/start', payload);
      await fetchNightlyStatus();
    } catch (e) {
      const err = e.response?.data?.detail;
      const msg = typeof err === 'object' ? JSON.stringify(err) : (err || e.message);
      alert("Gagal memulai uji coba: " + msg);
    } finally {
      setIsNightlyStarting(false);
    }
  };

  const handleSyncCatalog = async () => {
    if (!window.confirm("Sinkronkan katalog peraturan dari database berita MySQL ke antrean ragdb? (Aman, 100% Read-Only ke MySQL)")) return;
    setIsSyncingCatalog(true);
    try {
      const res = await apiClient.post('/training/nightly/sync-catalog');
      const data = res.data?.data;
      alert(`Sinkronisasi Selesai!\n• Total Dokumen: ${data?.total_mysql_records || 0}\n• Tier 1 (Berlaku): ${data?.tier1_active_regulations || 0}\n• Tier 2 (Dicabut): ${data?.tier2_obsolete_regulations || 0}`);
      await fetchNightlyStatus();
      await fetchData();
    } catch (e) {
      const err = e.response?.data?.detail;
      const msg = typeof err === 'object' ? JSON.stringify(err) : (err || e.message);
      alert("Gagal sinkronisasi katalog: " + msg);
    } finally {
      setIsSyncingCatalog(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    await Promise.all([fetchSourceDocs(), fetchSyntheticDocs(), fetchJobs()]);
    setLoading(false);
  };

  const fetchSourceDocs = async () => {
    try {
      const res = await apiClient.get('/training/source-docs');
      setSourceDocs(res.data?.data || []);
    } catch (e) {
      console.error("Failed to fetch source docs", e);
    }
  };

  const fetchSyntheticDocs = async () => {
    try {
      const res = await apiClient.get('/synthetic/source-docs');
      setSyntheticDocs(res.data?.data || []);
    } catch (e) {
      console.error("Failed to fetch synthetic docs", e);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await apiClient.get('/training/status', { timeout: 7000 });
      setJobs(res.data?.data || []);
    } catch (e) {
      // non-blocking
    }
  };

  const handleSubmitPipelineJob = async () => {
    if (!selectedDoc) return;
    setIsSubmitting(true);
    try {
      await apiClient.post('/training/submit', {
        dokumen_id: selectedDoc.id,
        tipe_training: trainingMethod
      });
      setShowModal(false);
      setSelectedDoc(null);
      fetchJobs();
    } catch (e) {
      alert("Gagal submit training job.");
      console.error(e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBatchSyntheticSubmit = async () => {
    setIsBatchSubmitting(true);
    try {
      const res = await apiClient.post('/synthetic/submit-batch');
      alert(`Berhasil memulai batch synthetic job dengan ID: ${res.data.job_id}.`);
      fetchJobs();
    } catch (e) {
      alert("Gagal submit batch training.");
      console.error(e);
    } finally {
      setIsBatchSubmitting(false);
    }
  };

  const handleSingleSyntheticSubmit = async (docId) => {
    try {
      await apiClient.post('/synthetic/submit', { dokumen_id: docId });
      fetchJobs();
    } catch (e) {
      alert("Gagal submit synthetic training.");
      console.error(e);
    }
  };

  const renderStatusBadge = (status) => {
    switch (status) {
      case 'RUNNING': 
        return <span className="flex items-center gap-1 text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded text-xs font-semibold"><Activity className="w-3 h-3 animate-pulse" /> Running</span>;
      case 'DONE': 
        return <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded text-xs font-semibold"><CheckCircle2 className="w-3 h-3" /> Done</span>;
      case 'FAILED': 
        return <span className="flex items-center gap-1 text-red-400 bg-red-500/10 px-2 py-0.5 rounded text-xs font-semibold"><XCircle className="w-3 h-3" /> Failed</span>;
      default: 
        return <span className="flex items-center gap-1 text-slate-400 bg-slate-500/10 px-2 py-0.5 rounded text-xs font-semibold"><Clock className="w-3 h-3" /> Pending</span>;
    }
  };

  const TRAINING_METHODS = [
    { id: 'STANDARD', icon: <Database />, title: "Standard RAG", desc: "Text extraction & MXBAI Vector Embedding" },
    { id: 'SYNTHETIC_QA', icon: <Brain />, title: "Synthetic Q&A", desc: "LLM Generates 100+ simulated questions" },
    { id: 'GRAPH_RAG', icon: <GitMerge />, title: "Graph RAG", desc: "Entity & Relationship extraction" },
    { id: 'VISION_RAG', icon: <FileImage />, title: "Vision RAG", desc: "ColPali image-based vectorization" }
  ];

  const filteredPipelineDocs = sourceDocs.filter(d => 
    !searchQuery || d.judul?.toLowerCase().includes(searchQuery.toLowerCase()) || d.noper?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredSyntheticDocs = syntheticDocs.filter(d => 
    !searchQuery || d.judul?.toLowerCase().includes(searchQuery.toLowerCase()) || d.noper?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const embeddedCount = sourceDocs.filter(d => d.is_embedded).length;
  const syntheticEmbeddedCount = syntheticDocs.filter(d => d.is_synthetic_embedded).length;
  const activeJobsCount = jobs.filter(j => j.status === 'RUNNING').length;

  return (
    <div className="flex flex-col gap-6 text-slate-200 animate-in fade-in duration-500">
      
      {/* Header & Stats Banner */}
      <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-6 relative overflow-hidden">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-xl text-purple-400">
              <Brain className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 via-indigo-300 to-cyan-400">
                Deep Learning & Training Hub
              </h1>
              <p className="text-slate-400 text-sm mt-1">
                Orkestrasi model training, vector embedding, dan synthetic Q&A generation untuk otak CAKRA AI.
              </p>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-3">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2 flex flex-col items-center min-w-[110px]">
              <span className="text-[10px] uppercase text-gray-500 font-bold tracking-wider">Total Docs</span>
              <span className="text-lg font-bold text-white">{sourceDocs.length}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2 flex flex-col items-center min-w-[110px]">
              <span className="text-[10px] uppercase text-emerald-500 font-bold tracking-wider">Embedded</span>
              <span className="text-lg font-bold text-emerald-400">{embeddedCount}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2 flex flex-col items-center min-w-[110px]">
              <span className="text-[10px] uppercase text-purple-500 font-bold tracking-wider">Synthetic QA</span>
              <span className="text-lg font-bold text-purple-400">{syntheticEmbeddedCount}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2 flex flex-col items-center min-w-[110px]">
              <span className="text-[10px] uppercase text-cyan-500 font-bold tracking-wider">Active Jobs</span>
              <span className="text-lg font-bold text-cyan-400">{activeJobsCount}</span>
            </div>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div className="flex items-center gap-2 border-b border-gray-800 mt-6 pt-2">
          <button
            onClick={() => setActiveSubTab('pipelines')}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-t-lg transition-all ${
              activeSubTab === 'pipelines'
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Layers size={16} /> Ingestion & Model Pipelines
          </button>
          <button
            onClick={() => setActiveSubTab('synthetic')}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-t-lg transition-all ${
              activeSubTab === 'synthetic'
                ? 'text-purple-400 border-b-2 border-purple-400 bg-purple-900/20'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Sparkles size={16} /> Synthetic Q&A Generation
          </button>
          <button
            onClick={() => setActiveSubTab('jobs')}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-t-lg transition-all ${
              activeSubTab === 'jobs'
                ? 'text-emerald-400 border-b-2 border-emerald-400 bg-emerald-900/20'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Activity size={16} /> Live Job Monitor ({jobs.length})
          </button>
        </div>
      </div>

      {/* ── NIGHTLY 5-WORKER AUTOMATED TRAINING & FINE-TUNING PANEL ── */}
      <div className="bg-gradient-to-r from-indigo-950/40 via-purple-950/30 to-slate-900/60 border border-indigo-500/30 rounded-2xl p-5 relative overflow-hidden backdrop-blur-sm shadow-xl">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          
          {/* Left: Title, Badges & Schedule Info */}
          <div className="flex items-start gap-3.5">
            <div className={`p-3 rounded-xl border ${nightlyStatus?.is_running ? 'bg-indigo-500/20 border-indigo-400 text-indigo-300 animate-pulse' : 'bg-slate-800/80 border-slate-700 text-indigo-400'}`}>
              <Moon className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  Nightly 5-Worker Training & Fine-Tuning
                </h2>
                {nightlyStatus?.is_running ? (
                  <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-300 animate-pulse">
                    <Activity className="w-3.5 h-3.5" />
                    RUNNING: Dokumen #{nightlyStatus.current_doc?.id} (Hal {nightlyStatus.current_doc?.current_page || 1}/{nightlyStatus.current_doc?.total_pages || 1})
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    STANDBY (Jadwal Cron Aktif: 18:00 WIB)
                  </span>
                )}
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 flex items-center gap-1">
                  <Database className="w-3 h-3 text-cyan-400" /> ragdb only
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-500/40 flex items-center gap-1 font-medium">
                  <Sparkles className="w-3 h-3 text-purple-400" /> Vision-First (2-Page Spread)
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                <span>⏰ Jadwal: <strong className="text-slate-200">18:00 - 07:30 WIB</strong> (Toleransi Batch s.d. 08:00 WIB)</span>
                <span>•</span>
                <span>🤖 Model: <strong className="text-purple-300">gemma4:31b</strong> + mxbai-embed-large</span>
                <span>•</span>
                <span className="text-indigo-300">Otomatis via Crontab (0 18 * * *)</span>
              </p>
            </div>
          </div>

          {/* Right: Action Buttons */}
          <div className="flex items-center gap-2 w-full lg:w-auto justify-end flex-wrap">
            {nightlyStatus?.is_running ? (
              <button
                onClick={handleStopNightly}
                disabled={isNightlyStopping}
                className="flex items-center gap-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-bold px-4 py-2.5 rounded-xl shadow-lg shadow-rose-900/30 transition-all cursor-pointer"
              >
                {isNightlyStopping ? <Activity className="w-4 h-4 animate-spin" /> : <Square className="w-4 h-4 fill-white" />}
                Hentikan & Checkpoint
              </button>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={handleSyncCatalog}
                  disabled={isSyncingCatalog}
                  className="flex items-center gap-1.5 bg-slate-800/90 hover:bg-slate-700/90 border border-cyan-500/40 text-cyan-300 hover:text-white text-xs font-semibold px-3 py-2.5 rounded-xl transition-all cursor-pointer shadow-md"
                  title="Sinkronkan katalog berita MySQL ke antrean ragdb (Aman, 100% Read-Only)"
                >
                  {isSyncingCatalog ? <Activity className="w-3.5 h-3.5 animate-spin text-cyan-400" /> : <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />}
                  Sinkron Katalog
                </button>
                <button
                  onClick={() => handleTestQuickNightly(null)}
                  disabled={isNightlyStarting}
                  className="flex items-center gap-1.5 bg-slate-800/90 hover:bg-slate-700/90 border border-indigo-500/40 text-indigo-300 hover:text-white text-xs font-semibold px-3.5 py-2.5 rounded-xl transition-all cursor-pointer shadow-md"
                  title="Uji coba cepat 1 dokumen pertama sebanyak 2 halaman saja"
                >
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  Test 1 File (Bentangan 2 Hal)
                </button>
                <button
                  onClick={() => setActiveSubTab('jobs')}
                  className="flex items-center gap-1.5 bg-gradient-to-r from-emerald-600/80 to-teal-600/80 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold px-3.5 py-2.5 rounded-xl transition-all cursor-pointer shadow-md"
                  title="Buka Cockpit Monitoring Interaktif Bentangan 2 Halaman dan Terminal Multi-Worker"
                >
                  <Eye className="w-3.5 h-3.5 text-emerald-200" />
                  Buka Live Cockpit (2 Hal & Terminal)
                </button>
                <button
                  onClick={handleStartNightly}
                  disabled={isNightlyStarting}
                  className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 text-white text-xs font-bold px-4 py-2.5 rounded-xl shadow-lg shadow-indigo-900/30 transition-all cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
                >
                  {isNightlyStarting ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
                  Mulai Full Antrean
                </button>
                <button
                  onClick={handleResetNightly}
                  disabled={isResetting || nightlyStatus?.is_running}
                  className="flex items-center gap-1.5 bg-rose-950/60 hover:bg-rose-900/80 border border-rose-500/40 text-rose-300 hover:text-white text-xs font-semibold px-3 py-2.5 rounded-xl transition-all cursor-pointer shadow-md disabled:opacity-40"
                  title="Reset seluruh progres training dan checkpoint ke titik 0 (Dokumen 1, Halaman 1)"
                >
                  <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
                  Reset ke 0
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 2-Tier Lineage Progress Indicators */}
        {nightlyStatus?.tiered_stats && (
          <div className="mt-3.5 pt-3 border-t border-indigo-900/40 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div className="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-3 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-bold text-emerald-300">Tier 1: Regulasi Berlaku (Prioritas #1)</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Diproses pertama hingga tuntas 100%
                </p>
              </div>
              <div className="text-right">
                <span className="text-sm font-bold text-white">
                  {nightlyStatus.tiered_stats.tier1?.completed || 0} / {nightlyStatus.tiered_stats.tier1?.total || 1392}
                </span>
                <span className="text-[10px] text-emerald-400 block font-medium">
                  {(((nightlyStatus.tiered_stats.tier1?.completed || 0) / (nightlyStatus.tiered_stats.tier1?.total || 1)) * 100).toFixed(1)}% tuntas
                </span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-amber-500/30 rounded-xl p-3 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-xs font-bold text-amber-300">Tier 2: Regulasi Dicabut (Prioritas #2)</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Diproses setelah seluruh Tier 1 selesai
                </p>
              </div>
              <div className="text-right">
                <span className="text-sm font-bold text-white">
                  {nightlyStatus.tiered_stats.tier2?.completed || 0} / {nightlyStatus.tiered_stats.tier2?.total || 842}
                </span>
                <span className="text-[10px] text-amber-400 block font-medium">
                  {(((nightlyStatus.tiered_stats.tier2?.completed || 0) / (nightlyStatus.tiered_stats.tier2?.total || 1)) * 100).toFixed(1)}% tuntas
                </span>
              </div>
            </div>
          </div>
        )}

        {/* 5-Worker Status Strip */}
        <div className="mt-4 pt-3 border-t border-indigo-900/40 grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2 flex flex-col">
            <span className="text-[10px] text-slate-400 font-medium">Worker 1: Text RAG</span>
            <span className="font-bold text-cyan-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${nightlyStatus?.workers?.w1_text === 'RUNNING' ? 'bg-cyan-400 animate-ping' : 'bg-slate-500'}`} />
              {nightlyStatus?.workers?.w1_text || 'STANDBY'}
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2 flex flex-col">
            <span className="text-[10px] text-slate-400 font-medium">Worker 2: Q&A (Unlimited)</span>
            <span className="font-bold text-purple-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${nightlyStatus?.workers?.w2_qa === 'RUNNING' ? 'bg-purple-400 animate-ping' : 'bg-slate-500'}`} />
              {nightlyStatus?.workers?.w2_qa || 'STANDBY'}
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2 flex flex-col">
            <span className="text-[10px] text-slate-400 font-medium">Worker 3: Graph RAG</span>
            <span className="font-bold text-emerald-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${nightlyStatus?.workers?.w3_graph === 'RUNNING' ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'}`} />
              {nightlyStatus?.workers?.w3_graph || 'STANDBY'}
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2 flex flex-col">
            <span className="text-[10px] text-slate-400 font-medium">Worker 4: Vision RAG</span>
            <span className="font-bold text-amber-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${nightlyStatus?.workers?.w4_vision === 'RUNNING' ? 'bg-amber-400 animate-ping' : 'bg-slate-500'}`} />
              {nightlyStatus?.workers?.w4_vision || 'STANDBY'}
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2 flex flex-col col-span-2 sm:col-span-1">
            <span className="text-[10px] text-slate-400 font-medium">Worker 5: LoRA Adapter</span>
            <span className="font-bold text-pink-400 flex items-center gap-1 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${nightlyStatus?.workers?.w5_lora === 'RUNNING' ? 'bg-pink-400 animate-ping' : 'bg-slate-500'}`} />
              {nightlyStatus?.workers?.w5_lora || 'STANDBY'}
            </span>
          </div>
        </div>

        {/* Live Ticker Log */}
        {nightlyStatus?.latest_log && (
          <div className="mt-3 px-3 py-1.5 bg-slate-950/70 border border-slate-800/80 rounded-lg text-[11px] text-slate-300 font-mono flex items-center justify-between">
            <span className="truncate">📡 {nightlyStatus.latest_log}</span>
            <span className="text-[10px] text-slate-500 shrink-0 ml-2">ragdb checkpoint synced</span>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {activeSubTab === 'jobs' ? (
        /* ── INTERACTIVE TWO-PAGE SPREAD & MULTI-WORKER LIVE COCKPIT ── */
        <div className="space-y-6">
          {/* Laser Scanner Keyframes */}
          <style>{`
            @keyframes laserSweep {
              0% { top: 0%; opacity: 0.8; }
              50% { top: 96%; opacity: 1; }
              100% { top: 0%; opacity: 0.8; }
            }
            .laser-scanner-beam {
              animation: laserSweep 3.5s ease-in-out infinite;
            }
          `}</style>

          {/* Cockpit Top Bar Info */}
          <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl border ${liveMonitor?.is_running ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 animate-pulse' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    Live Training Cockpit: Bentangan 2 Halaman & Multi-Worker Monitor
                  </h3>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                    liveMonitor?.is_running 
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 animate-pulse' 
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}>
                    {liveMonitor?.is_running ? 'ACTIVE SCANNING' : 'STANDBY'}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400 mt-1 flex-wrap">
                  <span>Dokumen: <strong className="text-cyan-300">{liveMonitor?.current_doc?.title || liveMonitor?.artifacts?.doc_title || nightlyStatus?.current_doc?.title || 'Belum ada dokumen aktif'}</strong></span>
                  <span>•</span>
                  <span className="font-mono text-purple-300">{liveMonitor?.current_doc?.nomor_dokumen || liveMonitor?.artifacts?.nomor_dokumen || 'N/A'}</span>
                  <span>•</span>
                  <span className="text-emerald-400 font-semibold">
                    {liveMonitor?.current_doc?.page_left ? `Bentangan Hal ${liveMonitor.current_doc.page_left}${liveMonitor.current_doc.page_right ? `-${liveMonitor.current_doc.page_right}` : ''} (${liveMonitor.current_doc.current_page || 1}/${liveMonitor.current_doc.total_pages || 1})` : (liveMonitor?.artifacts?.spread_label || 'Bentangan Siap')}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleTestQuickNightly(null)}
                disabled={isNightlyStarting || liveMonitor?.is_running}
                className="text-xs bg-indigo-600/80 hover:bg-indigo-500 text-white px-3 py-2 rounded-lg font-semibold transition-all flex items-center gap-1.5 disabled:opacity-50"
              >
                <Zap className="w-3.5 h-3.5 text-amber-300" />
                Test 1 File (2 Hal)
              </button>
              <button
                onClick={fetchLiveMonitor}
                className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                title="Refresh Live Data"
              >
                <RotateCcw size={14} />
              </button>
            </div>
          </div>

          {/* Cockpit Split Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* ── LEFT COLUMN (5 cols): TWO-PAGE SPREAD VIEWER ── */}
            <div className="lg:col-span-5 bg-[#0B0F19] border border-gray-800 rounded-2xl p-4 flex flex-col h-[700px]">
              <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-3">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                    Two-Page Spread (Bentangan 2 Halaman)
                  </span>
                </div>
                <span className="text-[10px] text-gray-500 font-mono">
                  Worker 4 • 150 DPI Render
                </span>
              </div>

              {/* Dual Book Canvas */}
              <div className="relative flex-1 bg-[#060911] border border-slate-800 rounded-xl overflow-hidden flex shadow-2xl p-2 gap-2">
                
                {/* Center Book Spine Shadow */}
                <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-6 bg-gradient-to-r from-black/50 via-black/80 to-black/50 pointer-events-none z-10" />

                {/* Laser Scanning Beam (when running) */}
                {liveMonitor?.is_running && (
                  <div className="absolute inset-x-0 z-30 pointer-events-none laser-scanner-beam">
                    <div className="w-full h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_15px_#22d3ee]" />
                    <div className="w-full h-12 bg-gradient-to-b from-cyan-500/20 via-cyan-500/5 to-transparent" />
                    <div className="absolute right-3 -top-2 px-2 py-0.5 rounded bg-cyan-950/90 border border-cyan-400/60 text-[9px] font-mono text-cyan-300 backdrop-blur-sm shadow-md">
                      [W4-VISION] AI Scan Line
                    </div>
                  </div>
                )}

                {/* Left Page (Halaman Ganjil) */}
                {(() => {
                  const leftPageNum = liveMonitor?.current_spread_left?.page || liveMonitor?.current_doc?.page_left || 1;
                  const leftImg = liveMonitor?.current_spread_left?.image_url || liveMonitor?.current_doc?.page_left_url;
                  const leftWidth = liveMonitor?.current_spread_left?.width || 595;
                  const leftHeight = liveMonitor?.current_spread_left?.height || 842;

                  return (
                    <div className="w-1/2 h-full bg-slate-950/90 border border-slate-800/80 rounded-lg p-2.5 flex flex-col justify-between relative overflow-hidden group">
                      <div className="flex items-center justify-between text-[10px] font-mono pb-1 border-b border-slate-800/60 mb-2">
                        <span className="px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 font-bold border border-cyan-800/50">
                          HALAMAN {leftPageNum}
                        </span>
                        <span className="text-gray-500">
                          {leftWidth}x{leftHeight} pt
                        </span>
                      </div>

                      <div className="flex-1 flex items-center justify-center overflow-hidden relative">
                        {leftImg ? (
                          <img 
                            src={getImageUrl(leftImg)} 
                            alt="Left Page Spread"
                            className="max-h-[550px] w-full object-contain rounded cursor-zoom-in group-hover:brightness-105 transition-all shadow-md"
                            onClick={() => setPreviewImageModal(getImageUrl(leftImg))}
                          />
                        ) : (
                          <div className="flex flex-col items-center justify-center p-4 text-center text-gray-500">
                            <FileImage className="w-10 h-10 mb-2 opacity-30 text-cyan-400" />
                            <p className="text-xs font-medium text-slate-400">Halaman Kiri</p>
                            <p className="text-[10px] text-gray-600 mt-1 max-w-[140px]">
                              {liveMonitor?.is_running ? 'Worker 4 sedang merender visual halaman...' : 'Standby / Menunggu proses scan training'}
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px]">
                        <span className="text-gray-500 font-mono">Page Left</span>
                        {leftImg && (
                          <button 
                            onClick={() => setPreviewImageModal(getImageUrl(leftImg))}
                            className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
                          >
                            <ZoomIn size={11} /> Perbesar
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* Right Page (Halaman Genap) */}
                {(() => {
                  const rightPageNum = liveMonitor?.current_spread_right?.page || liveMonitor?.current_doc?.page_right;
                  const rightImg = liveMonitor?.current_spread_right?.image_url || liveMonitor?.current_doc?.page_right_url;
                  const rightWidth = liveMonitor?.current_spread_right?.width || 595;
                  const rightHeight = liveMonitor?.current_spread_right?.height || 842;
                  const isEndOfDoc = liveMonitor?.current_spread_right && liveMonitor.current_spread_right.page === null;

                  return (
                    <div className="w-1/2 h-full bg-slate-950/90 border border-slate-800/80 rounded-lg p-2.5 flex flex-col justify-between relative overflow-hidden group">
                      <div className="flex items-center justify-between text-[10px] font-mono pb-1 border-b border-slate-800/60 mb-2">
                        <span className="px-1.5 py-0.5 rounded bg-purple-950/80 text-purple-400 font-bold border border-purple-800/50">
                          {rightPageNum ? `HALAMAN ${rightPageNum}` : 'AKHIR DOKUMEN'}
                        </span>
                        <span className="text-gray-500">
                          {rightWidth}x{rightHeight} pt
                        </span>
                      </div>

                      <div className="flex-1 flex items-center justify-center overflow-hidden relative">
                        {rightImg ? (
                          <img 
                            src={getImageUrl(rightImg)} 
                            alt="Right Page Spread"
                            className="max-h-[550px] w-full object-contain rounded cursor-zoom-in group-hover:brightness-105 transition-all shadow-md"
                            onClick={() => setPreviewImageModal(getImageUrl(rightImg))}
                          />
                        ) : isEndOfDoc ? (
                          <div className="flex flex-col items-center justify-center p-4 text-center text-gray-500">
                            <CheckCircle className="w-8 h-8 mb-2 opacity-20 text-emerald-400" />
                            <p className="text-xs font-medium text-slate-400">Akhir Dokumen</p>
                            <p className="text-[10px] text-gray-600 mt-1">Halaman ganjil terakhir (tidak ada hal genap).</p>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center p-4 text-center text-gray-500">
                            <FileImage className="w-10 h-10 mb-2 opacity-30 text-purple-400" />
                            <p className="text-xs font-medium text-slate-400">Halaman Kanan</p>
                            <p className="text-[10px] text-gray-600 mt-1 max-w-[140px]">
                              {liveMonitor?.is_running ? 'Worker 4 sedang merender visual halaman...' : 'Standby / Menunggu proses scan training'}
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px]">
                        <span className="text-gray-500 font-mono">Page Right</span>
                        {rightImg && (
                          <button 
                            onClick={() => setPreviewImageModal(getImageUrl(rightImg))}
                            className="text-purple-400 hover:text-purple-300 flex items-center gap-1 font-semibold"
                          >
                            <ZoomIn size={11} /> Perbesar
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })()}

              </div>
            </div>

            {/* ── RIGHT COLUMN (7 cols): MULTI-WORKER TERMINAL & TRAINING ARTIFACTS COCKPIT ── */}
            <div className="lg:col-span-7 bg-[#0B0F19] border border-gray-800 rounded-2xl flex flex-col h-[700px] overflow-hidden">
              
              {/* Cockpit Sub-tabs Bar */}
              <div className="p-3 border-b border-gray-800 bg-slate-900/70 flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    onClick={() => setMonitorTab('terminal')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'terminal'
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <Terminal size={13} />
                    Live Terminal
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-cyan-400 font-mono">
                      {liveMonitor?.terminal_stream?.length || 0}
                    </span>
                  </button>

                  <button
                    onClick={() => setMonitorTab('chunks')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'chunks'
                        ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <FileText size={13} />
                    Chunks (W1)
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-blue-400 font-mono">
                      {liveMonitor?.artifacts?.chunks?.length || 0}
                    </span>
                  </button>

                  <button
                    onClick={() => setMonitorTab('qa')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'qa'
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <Sparkles size={13} />
                    Synthetic Q&A (W2)
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-purple-400 font-mono">
                      {liveMonitor?.artifacts?.qa_pairs?.length || 0}
                    </span>
                  </button>

                  <button
                    onClick={() => setMonitorTab('graph')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'graph'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <Network size={13} />
                    Triples (W3)
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-emerald-400 font-mono">
                      {liveMonitor?.artifacts?.graph_triplets?.length || 0}
                    </span>
                  </button>

                  <button
                    onClick={() => setMonitorTab('visual')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'visual'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <Eye size={13} />
                    Visual (W4)
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-amber-400 font-mono">
                      {liveMonitor?.artifacts?.visual_diagrams?.length || 0}
                    </span>
                  </button>

                  <button
                    onClick={() => setMonitorTab('lora')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      monitorTab === 'lora'
                        ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40 shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                    }`}
                  >
                    <Code2 size={13} />
                    LoRA Data (W5)
                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-pink-400 font-mono">
                      {liveMonitor?.artifacts?.lora_samples?.length || 0}
                    </span>
                  </button>
                </div>
              </div>

              {/* ── TAB 1: LIVE TERMINAL MONITOR ── */}
              {monitorTab === 'terminal' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                  {/* Filter Pills & Options */}
                  <div className="px-3 py-2 bg-slate-950/80 border-b border-gray-800 flex items-center justify-between text-xs flex-wrap gap-2">
                    <div className="flex items-center gap-1 flex-wrap">
                      <span className="text-[10px] text-gray-500 font-medium mr-1">Filter:</span>
                      {['ALL', 'W1-TEXT', 'W2-QA', 'W3-GRAPH', 'W4-VISION', 'W5-LORA', 'SYSTEM'].map(pill => (
                        <button
                          key={pill}
                          onClick={() => setWorkerFilter(pill)}
                          className={`text-[10px] font-mono px-2 py-0.5 rounded transition-colors ${
                            workerFilter === pill
                              ? 'bg-cyan-500/30 text-cyan-300 font-bold border border-cyan-500/50'
                              : 'bg-slate-900 text-gray-400 hover:text-gray-200'
                          }`}
                        >
                          {pill}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-1 text-[11px] text-gray-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={autoScrollTerminal}
                          onChange={(e) => setAutoScrollTerminal(e.target.checked)}
                          className="rounded border-gray-700 text-cyan-500 focus:ring-0 w-3 h-3"
                        />
                        Auto-scroll
                      </label>
                      <button
                        onClick={() => copyToClipboard(liveMonitor?.terminal_stream, 'terminal_logs')}
                        className="text-[11px] text-gray-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
                        title="Copy All Terminal Logs"
                      >
                        {copiedKey === 'terminal_logs' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        {copiedKey === 'terminal_logs' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                  </div>

                  {/* Terminal Screen Body */}
                  <div className="flex-1 bg-black/95 p-3.5 font-mono text-[11px] overflow-y-auto space-y-1 custom-scrollbar">
                    {(!liveMonitor?.terminal_stream || liveMonitor.terminal_stream.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-600 text-xs font-sans">
                        <Terminal className="w-8 h-8 mb-2 opacity-30 text-cyan-500" />
                        <p>Terminal siap. Menunggu aktivitas dari 5-worker orchestrator...</p>
                        <span className="text-[10px] text-gray-600 mt-1">Klik "Test 1 File" atau "Mulai Pelatihan" untuk memicu alur kerja.</span>
                      </div>
                    ) : (
                      liveMonitor.terminal_stream
                        .filter(entry => {
                          if (workerFilter === 'ALL') return true;
                          const eWorker = (entry.worker || '').toUpperCase().replace(/_/g, '-');
                          const tFilter = workerFilter.toUpperCase().replace(/_/g, '-');
                          return eWorker.includes(tFilter);
                        })
                        .map((entry, idx) => {
                          const worker = (entry.worker || 'SYS').toUpperCase();
                          let tagColor = 'text-blue-400 bg-blue-950/40 border-blue-800/50';
                          if (worker.includes('W1')) tagColor = 'text-cyan-400 bg-cyan-950/40 border-cyan-800/50';
                          if (worker.includes('W2')) tagColor = 'text-purple-400 bg-purple-950/40 border-purple-800/50';
                          if (worker.includes('W3')) tagColor = 'text-emerald-400 bg-emerald-950/40 border-emerald-800/50';
                          if (worker.includes('W4')) tagColor = 'text-amber-400 bg-amber-950/40 border-amber-800/50';
                          if (worker.includes('W5')) tagColor = 'text-pink-400 bg-pink-950/40 border-pink-800/50';

                          return (
                            <div key={idx} className="flex items-start gap-2 hover:bg-slate-900/40 px-1 py-0.5 rounded transition-colors leading-relaxed">
                              <span className="text-gray-600 select-none shrink-0 font-mono text-[10px]">
                                {entry.timestamp || entry.time || '00:00:00'}
                              </span>
                              <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold border shrink-0 ${tagColor}`}>
                                {entry.worker || 'SYS'}
                              </span>
                              <span className="text-slate-300 break-words flex-1">
                                {entry.message}
                                {entry.details && (
                                  <pre className="mt-1 p-2 bg-slate-900/90 rounded border border-gray-800 text-[10px] text-gray-400 overflow-x-auto">
                                    {typeof entry.details === 'object' ? JSON.stringify(entry.details, null, 2) : entry.details}
                                  </pre>
                                )}
                              </span>
                            </div>
                          );
                        })
                    )}
                    <div ref={terminalEndRef} />
                  </div>
                </div>
              )}

              {/* ── TAB 2: CHUNKS INSPECTOR (W1 TEXT-RAG) ── */}
              {monitorTab === 'chunks' && (
                <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                  <div className="p-3 border-b border-gray-800 bg-slate-950/90 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-blue-400" />
                        Hasil Ekstraksi Chunks (Worker 1)
                      </h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        Chunking semantik tersimpan di tabel PostgreSQL <code className="text-cyan-300 font-mono">dokumen_chunk</code> dengan embedding BAAI/bge-m3 (1536-dim).
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300 text-xs font-bold font-mono">
                      {liveMonitor?.artifacts?.chunks?.length || 0} Chunks
                    </span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto space-y-3 custom-scrollbar">
                    {(!liveMonitor?.artifacts?.chunks || liveMonitor.artifacts.chunks.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-xs">
                        <FileText className="w-8 h-8 mb-2 opacity-30 text-blue-400" />
                        <p>Belum ada chunk yang diekstrak dari bentangan halaman saat ini.</p>
                      </div>
                    ) : (
                      liveMonitor.artifacts.chunks.map((chk, idx) => (
                        <div key={idx} className="p-3 bg-slate-900/90 border border-slate-800 rounded-xl space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-400 font-mono font-bold text-[10px] border border-blue-800">
                                Chunk #{chk.chunk_index !== undefined ? chk.chunk_index + 1 : idx + 1}
                              </span>
                              {chk.title && (
                                <span className="text-[11px] text-cyan-300 font-semibold">
                                  {chk.title}
                                </span>
                              )}
                              <span className="text-[10px] text-gray-400 font-mono">
                                Hal. {chk.page_range || chk.halaman || chk.page || '1'} • ~{chk.char_count || chk.token_count || (chk.preview || chk.text || chk.content || '').length} chars
                              </span>
                            </div>
                            <button
                              onClick={() => copyToClipboard(chk.preview || chk.text || chk.content || JSON.stringify(chk, null, 2), `chunk_${idx}`)}
                              className="text-[10px] text-gray-400 hover:text-white flex items-center gap-1 font-mono"
                            >
                              {copiedKey === `chunk_${idx}` ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                              Copy
                            </button>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80 font-mono whitespace-pre-wrap">
                            {chk.preview || chk.text || chk.content || JSON.stringify(chk, null, 2)}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB 3: GENERATED Q&A INSPECTOR (W2 SYNTHETIC) ── */}
              {monitorTab === 'qa' && (
                <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                  <div className="p-3 border-b border-gray-800 bg-slate-950/90 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                        Hasil Sintesis Tanya-Jawab (Worker 2 Qwen2.5)
                      </h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        Q&A pairs yang di-generate langsung dari konteks bentangan visual 2 halaman untuk evaluasi & RAG benchmark.
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-purple-950 border border-purple-800 text-purple-300 text-xs font-bold font-mono">
                      {liveMonitor?.artifacts?.qa_pairs?.length || 0} Pairs
                    </span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto space-y-3 custom-scrollbar">
                    {(!liveMonitor?.artifacts?.qa_pairs || liveMonitor.artifacts.qa_pairs.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-xs">
                        <Sparkles className="w-8 h-8 mb-2 opacity-30 text-purple-400" />
                        <p>Belum ada Synthetic Q&A yang diproduksi untuk bentangan saat ini.</p>
                      </div>
                    ) : (
                      liveMonitor.artifacts.qa_pairs.map((qa, idx) => (
                        <div key={idx} className="p-3.5 bg-slate-900/90 border border-purple-900/30 rounded-xl space-y-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-start gap-2">
                              <span className="px-1.5 py-0.5 rounded bg-purple-950 text-purple-400 font-mono font-bold text-[10px] border border-purple-800 shrink-0 mt-0.5">
                                Q{idx + 1}
                              </span>
                              <h5 className="text-xs font-semibold text-cyan-300 leading-snug">
                                {qa.question || qa.pertanyaan || "Pertanyaan regulasi"}
                              </h5>
                            </div>
                            <button
                              onClick={() => copyToClipboard(`Q: ${qa.question || qa.pertanyaan}\nA: ${qa.answer || qa.jawaban}`, `qa_${idx}`)}
                              className="text-[10px] text-gray-400 hover:text-white shrink-0 font-mono flex items-center gap-1"
                            >
                              {copiedKey === `qa_${idx}` ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                              Copy
                            </button>
                          </div>

                          <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80 text-xs text-slate-300 leading-relaxed">
                            <span className="text-[10px] text-emerald-400 font-bold block mb-1 font-mono">JAWABAN (GROUND TRUTH):</span>
                            {qa.answer || qa.jawaban || "Jawaban komprehensif berdasarkan regulasi..."}
                          </div>

                          {(qa.pasal || qa.context) && (
                            <div className="text-[10px] text-gray-500 font-mono">
                              Referensi: <span className="text-purple-300">{qa.pasal || qa.context}</span>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB 4: KNOWLEDGE GRAPH TRIPLES (W3 GRAPH-RAG) ── */}
              {monitorTab === 'graph' && (
                <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                  <div className="p-3 border-b border-gray-800 bg-slate-950/90 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                        <Network className="w-3.5 h-3.5 text-emerald-400" />
                        Knowledge Graph Triples (Worker 3)
                      </h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        Hubungan semantik antar-entitas hukum (Peraturan, Lembaga, Kewajiban, Sanksi) untuk Graph-RAG.
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs font-bold font-mono">
                      {liveMonitor?.artifacts?.graph_triplets?.length || 0} Triples
                    </span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto space-y-2.5 custom-scrollbar">
                    {(!liveMonitor?.artifacts?.graph_triplets || liveMonitor.artifacts.graph_triplets.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-xs">
                        <Network className="w-8 h-8 mb-2 opacity-30 text-emerald-400" />
                        <p>Belum ada entitas Knowledge Graph yang diekstrak untuk bentangan saat ini.</p>
                      </div>
                    ) : (
                      liveMonitor.artifacts.graph_triplets.map((trip, idx) => {
                        const subject = trip.subject || trip.source || trip[0] || "Entitas";
                        const relation = trip.relation || trip.predicate || trip[1] || "berhubungan_dengan";
                        const object = trip.object || trip.target || trip[2] || "Objek";

                        return (
                          <div key={idx} className="p-3 bg-slate-900/90 border border-emerald-900/30 rounded-xl flex items-center justify-between gap-3 text-xs">
                            <div className="flex items-center gap-2 flex-1 flex-wrap">
                              <span className="px-2.5 py-1 rounded-lg bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 font-semibold text-xs">
                                {subject}
                              </span>
                              <span className="text-gray-500 font-mono flex items-center gap-1 text-[11px]">
                                ───[ <strong className="text-purple-300">{relation}</strong> ]──▶
                              </span>
                              <span className="px-2.5 py-1 rounded-lg bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-semibold text-xs">
                                {object}
                              </span>
                            </div>
                            <button
                              onClick={() => copyToClipboard(`(${subject}) -[${relation}]-> (${object})`, `trip_${idx}`)}
                              className="text-gray-500 hover:text-white"
                              title="Copy Triple"
                            >
                              {copiedKey === `trip_${idx}` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB 4.5: VISUAL ARTIFACTS & DIAGRAMS (W4 VISION RAG) ── */}
              {monitorTab === 'visual' && (
                <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                  <div className="p-3 border-b border-gray-800 bg-slate-950/90 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                        <Eye className="w-3.5 h-3.5 text-amber-400" />
                        Visual Artifacts & Diagrams (Worker 4)
                      </h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        Bagan alir (Flowchart Mermaid), Tabel Matriks, dan Cap Legalitas yang diekstrak oleh Gemma-4 31B Multimodal.
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-amber-950 border border-amber-800 text-amber-300 text-xs font-bold font-mono">
                      {liveMonitor?.artifacts?.visual_diagrams?.length || 0} Artifacts
                    </span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto space-y-3 custom-scrollbar">
                    {(!liveMonitor?.artifacts?.visual_diagrams || liveMonitor.artifacts.visual_diagrams.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-xs py-8">
                        <Eye className="w-8 h-8 mb-2 opacity-30 text-amber-400" />
                        <p>Belum ada diagram alur atau tabel visual yang terdeteksi untuk bentangan saat ini.</p>
                      </div>
                    ) : (
                      liveMonitor.artifacts.visual_diagrams.map((vis, idx) => (
                        <div key={idx} className="p-3.5 bg-slate-900/90 border border-amber-900/30 rounded-xl space-y-2.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 font-mono font-bold text-[10px] border border-amber-800">
                              {vis.type || 'DIAGRAM'} #{idx + 1}
                            </span>
                            <span className="text-[10px] text-gray-400 font-mono">
                              Halaman {vis.page_range}
                            </span>
                          </div>
                          <h5 className="text-xs font-bold text-slate-100">{vis.title}</h5>
                          {vis.preview && (
                            <p className="text-xs text-gray-300 whitespace-pre-wrap bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
                              {vis.preview}
                            </p>
                          )}
                          {vis.mermaid && (
                            <div className="space-y-1">
                              <span className="text-[10px] font-mono text-cyan-400 font-semibold">Kode Diagram Mermaid:</span>
                              <pre className="text-[10px] text-cyan-300 font-mono bg-black/80 p-2.5 rounded-lg border border-cyan-900/40 overflow-x-auto custom-scrollbar">
                                {vis.mermaid}
                              </pre>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB 5: LORA INSTRUCTION DATASET (W5 LORA INGEST) ── */}
              {monitorTab === 'lora' && (
                <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                  <div className="p-3 border-b border-gray-800 bg-slate-950/90 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                        <Code2 className="w-3.5 h-3.5 text-pink-400" />
                        LoRA Fine-Tuning Instruction Dataset (Worker 5)
                      </h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        Dataset percakapan multi-turn siap ekspor ke format JSONL Llama-Factory / Unsloth untuk fine-tuning model LLM lokal.
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-pink-950 border border-pink-800 text-pink-300 text-xs font-bold font-mono">
                      {liveMonitor?.artifacts?.lora_samples?.length || 0} Samples
                    </span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto space-y-3 custom-scrollbar">
                    {(!liveMonitor?.artifacts?.lora_samples || liveMonitor.artifacts.lora_samples.length === 0) ? (
                      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-xs">
                        <Code2 className="w-8 h-8 mb-2 opacity-30 text-pink-400" />
                        <p>Belum ada sampel data LoRA instruction yang diproduksi untuk bentangan saat ini.</p>
                      </div>
                    ) : (
                      liveMonitor.artifacts.lora_samples.map((lora, idx) => (
                        <div key={idx} className="p-3.5 bg-slate-900/90 border border-pink-900/30 rounded-xl space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="px-2 py-0.5 rounded bg-pink-950 text-pink-300 font-mono font-bold text-[10px] border border-pink-800">
                              Instruction Sample #{idx + 1}
                            </span>
                            <button
                              onClick={() => copyToClipboard(lora, `lora_${idx}`)}
                              className="text-[10px] text-gray-400 hover:text-white flex items-center gap-1 font-mono"
                            >
                              {copiedKey === `lora_${idx}` ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                              Copy JSON
                            </button>
                          </div>
                          <pre className="text-[11px] text-slate-300 font-mono bg-black/90 p-3 rounded-lg border border-gray-800 overflow-x-auto custom-scrollbar">
                            {typeof lora === 'object' ? JSON.stringify(lora, null, 2) : lora}
                          </pre>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

            </div>
          </div>

          {/* Collapsible Legacy Job Queue Drawer */}
          <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl overflow-hidden">
            <button
              onClick={() => setShowLegacyJobs(!showLegacyJobs)}
              className="w-full p-4 flex items-center justify-between hover:bg-slate-900/40 transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Antrean Pekerjaan Latar Belakang Klasik ({jobs.length} Jobs)
                </span>
              </div>
              <span className="text-xs text-gray-500 font-mono">
                {showLegacyJobs ? 'Tutup Antrean ▲' : 'Buka Antrean ▼'}
              </span>
            </button>

            {showLegacyJobs && (
              <div className="p-4 border-t border-gray-800 bg-slate-950/60 max-h-64 overflow-y-auto space-y-3 custom-scrollbar">
                {jobs.length === 0 ? (
                  <p className="text-xs text-gray-500 text-center py-4">Tidak ada pekerjaan background manual yang sedang berjalan.</p>
                ) : (
                  jobs.map(job => (
                    <div key={job.job_id} className="p-3 bg-slate-900 border border-gray-800 rounded-xl flex items-center justify-between gap-4">
                      <div>
                        <div className="text-xs text-gray-300 font-medium">
                          Doc #{job.dokumen_id} • <span className="text-cyan-400">{job.tipe_training}</span>
                        </div>
                        <div className="text-[10px] text-gray-500 font-mono mt-0.5">{job.job_id}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        {renderStatusBadge(job.status)}
                        <span className="text-xs font-mono text-cyan-400 font-bold">{job.progress}%</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ── TWO-COLUMN VIEW FOR PIPELINES & SYNTHETIC ── */
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          
          {/* Left 2 Columns: Table of Documents */}
          <div className="xl:col-span-2 bg-[#0B0F19] border border-gray-800 rounded-2xl overflow-hidden flex flex-col h-[650px]">
            <div className="p-4 border-b border-gray-800 bg-slate-900/60 flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3">
              <div className="flex items-center gap-2 flex-1 max-w-md bg-slate-950 border border-gray-800 rounded-lg px-3 py-1.5">
                <Search size={15} className="text-gray-500" />
                <input
                  type="text"
                  placeholder="Cari dokumen atau nomor regulasi..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-transparent border-none outline-none text-xs text-gray-200 w-full placeholder-gray-500"
                />
              </div>
              
              <div className="flex items-center gap-2 shrink-0">
                {activeSubTab === 'synthetic' && (
                  <button
                    onClick={handleBatchSyntheticSubmit}
                    disabled={isBatchSubmitting}
                    className="text-xs bg-purple-600 hover:bg-purple-500 text-white px-3.5 py-2 rounded-lg font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {isBatchSubmitting ? <Activity className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    Train All Missing
                  </button>
                )}
                <button 
                  onClick={fetchData} 
                  className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                  title="Refresh Data"
                >
                  <RotateCcw size={14} />
                </button>
              </div>
            </div>

            {/* Document List Container */}
            <div className="flex-1 overflow-auto p-4 custom-scrollbar">
              {loading ? (
                <div className="animate-pulse space-y-3">
                  {[1,2,3,4,5].map(i => <div key={i} className="h-16 bg-slate-800/40 rounded-xl" />)}
                </div>
              ) : activeSubTab === 'pipelines' ? (
                filteredPipelineDocs.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm">
                    <Database className="w-8 h-8 mb-2 opacity-40" />
                    Tidak ada dokumen ditemukan.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredPipelineDocs.map(doc => (
                      <div key={doc.id} className="flex items-center justify-between p-4 bg-slate-950/80 border border-gray-800 rounded-xl hover:border-gray-700 transition-colors">
                        <div className="flex items-start gap-3 min-w-0 pr-4">
                          <FileText className="w-5 h-5 text-gray-500 mt-0.5 shrink-0" />
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-slate-200 truncate">{doc.judul}</h4>
                            <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                              <span className="font-mono text-cyan-400/80">{doc.noper || "Tanpa Nomor"}</span>
                              <span>•</span>
                              <span className="truncate">{doc.file_name}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-3 shrink-0">
                          {doc.is_embedded ? (
                            <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full text-xs font-semibold border border-emerald-500/20">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Embedded
                            </span>
                          ) : (
                            <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 text-slate-400 rounded-full text-xs font-semibold border border-slate-700">
                              <XCircle className="w-3.5 h-3.5" /> Pending
                            </span>
                          )}
                          
                          <button 
                            onClick={() => { setSelectedDoc(doc); setShowModal(true); }}
                            disabled={doc.is_embedded}
                            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                              doc.is_embedded 
                                ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/20'
                            }`}
                          >
                            <Play className="w-3 h-3" /> Train
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              ) : (
                filteredSyntheticDocs.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm">
                    <Sparkles className="w-8 h-8 mb-2 opacity-40" />
                    Tidak ada dokumen synthetic ditemukan.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredSyntheticDocs.map(doc => (
                      <div key={doc.id} className="flex items-center justify-between p-4 bg-slate-950/80 border border-gray-800 rounded-xl hover:border-gray-700 transition-colors">
                        <div className="flex items-start gap-3 min-w-0 pr-4">
                          <Sparkles className="w-5 h-5 text-purple-400 mt-0.5 shrink-0" />
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-slate-200 truncate">{doc.judul}</h4>
                            <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                              <span className="font-mono text-purple-400/80">{doc.noper || "Tanpa Nomor"}</span>
                              <span>•</span>
                              <span className="truncate">{doc.file_name}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-3 shrink-0">
                          {doc.is_synthetic_embedded ? (
                            <span className="flex items-center gap-1.5 px-3 py-1 bg-purple-500/10 text-purple-400 rounded-full text-xs font-semibold border border-purple-500/20">
                              <CheckCircle2 className="w-3.5 h-3.5" /> QA Ready
                            </span>
                          ) : (
                            <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 text-slate-400 rounded-full text-xs font-semibold border border-slate-700">
                              <XCircle className="w-3.5 h-3.5" /> No QA
                            </span>
                          )}
                          
                          <button 
                            onClick={() => handleSingleSyntheticSubmit(doc.id)}
                            disabled={doc.is_synthetic_embedded}
                            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                              doc.is_synthetic_embedded 
                                ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                                : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-lg shadow-purple-500/20'
                            }`}
                          >
                            <Play className="w-3 h-3" /> Gen QA
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          </div>

          {/* Right Column: Live Job Monitor */}
          <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl flex flex-col h-[650px] overflow-hidden">
            <div className="p-4 border-b border-gray-800 bg-slate-900/60 flex justify-between items-center">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2 text-sm">
                <Activity className="w-4 h-4 text-cyan-400" /> Live Job Monitor
              </h3>
              <span className="text-xs text-gray-500 font-mono">{jobs.length} total</span>
            </div>
            
            <div className="flex-1 overflow-auto p-4 space-y-4 custom-scrollbar">
              {jobs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm">
                  <Brain className="w-8 h-8 mb-2 opacity-30 text-gray-600" />
                  <p>Tidak ada antrean pelatihan aktif.</p>
                  <span className="text-xs text-gray-600 mt-1">Submit dokumen untuk memulai training.</span>
                </div>
              ) : (
                jobs.map(job => (
                  <div key={job.job_id} className="p-4 bg-slate-950 border border-gray-800/80 rounded-xl space-y-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-xs text-gray-400 font-medium mb-1">
                          Doc #{job.dokumen_id} • <span className="text-cyan-400 font-semibold">{job.tipe_training}</span>
                        </div>
                        {renderStatusBadge(job.status)}
                      </div>
                      <span className="text-[10px] font-mono text-gray-500" title={job.job_id}>
                        {job.job_id?.substring(0,8)}...
                      </span>
                    </div>
                    
                    {job.status === 'RUNNING' && (
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400">Progress</span>
                          <span className="text-cyan-400 font-bold">{job.progress}%</span>
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-500 transition-all duration-500"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                    
                    <div className="bg-black/60 p-2.5 rounded-lg text-[10px] font-mono text-slate-400 h-20 overflow-y-auto whitespace-pre-wrap border border-gray-800/60 custom-scrollbar">
                      {job.logs || "Sedang menjalankan alur pipeline..."}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Image Preview Zoom Modal */}
      {previewImageModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setPreviewImageModal(null)}
        >
          <div 
            className="relative max-w-4xl max-h-[90vh] bg-slate-950 border border-gray-700 rounded-2xl overflow-hidden shadow-2xl p-2 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-3 border-b border-gray-800 text-xs text-gray-300">
              <span className="font-mono text-cyan-400 flex items-center gap-1.5">
                <FileImage size={14} /> Inspeksi Resolusi Tinggi Halaman Dokumen
              </span>
              <div className="flex items-center gap-2">
                <a 
                  href={previewImageModal} 
                  target="_blank" 
                  rel="noreferrer" 
                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-gray-300 flex items-center gap-1 text-[11px]"
                >
                  <ExternalLink size={12} /> Buka Tab Baru
                </a>
                <button 
                  onClick={() => setPreviewImageModal(null)}
                  className="p-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-black/40">
              <img 
                src={previewImageModal} 
                alt="Zoomed Document Page" 
                className="max-h-[75vh] w-auto object-contain rounded shadow-lg"
              />
            </div>
          </div>
        </div>
      )}

      {/* Select Method Modal */}
      {showModal && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-gray-700 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-gray-800">
              <h3 className="text-xl font-bold text-slate-200">Konfigurasi Pelatihan AI</h3>
              <p className="text-sm text-gray-400 mt-1">Dokumen: <span className="text-cyan-400 font-semibold">{selectedDoc.judul}</span></p>
            </div>
            
            <div className="p-6">
              <label className="text-sm font-semibold text-slate-300 mb-4 block">Pilih Metode Ingesti (Deep Learning Architecture):</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {TRAINING_METHODS.map(method => (
                  <button
                    key={method.id}
                    onClick={() => setTrainingMethod(method.id)}
                    className={`flex items-start gap-4 p-4 rounded-xl border text-left transition-all ${
                      trainingMethod === method.id 
                        ? 'bg-purple-500/10 border-purple-500/50 ring-1 ring-purple-500 shadow-lg shadow-purple-500/10' 
                        : 'bg-slate-950 border-gray-800 hover:border-gray-700 hover:bg-slate-900'
                    }`}
                  >
                    <div className={`p-2.5 rounded-lg ${trainingMethod === method.id ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-800 text-slate-400'}`}>
                      {React.cloneElement(method.icon, { className: 'w-5 h-5' })}
                    </div>
                    <div>
                      <h4 className={`font-semibold text-sm ${trainingMethod === method.id ? 'text-purple-300' : 'text-slate-300'}`}>{method.title}</h4>
                      <p className="text-xs text-gray-400 mt-1">{method.desc}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="p-4 border-t border-gray-800 bg-slate-950 flex justify-end gap-3">
              <button 
                onClick={() => setShowModal(false)}
                className="px-5 py-2 text-slate-400 hover:text-white text-sm font-semibold rounded-lg hover:bg-gray-800 transition-colors"
              >
                Batal
              </button>
              <button 
                onClick={handleSubmitPipelineJob}
                disabled={isSubmitting}
                className="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-sm font-semibold rounded-lg transition-all flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Mulai Pelatihan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DeepLearningTab;
