import React, { useState, useEffect } from 'react';
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
  Search
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

const DeepLearningTab = () => {
  const [activeSubTab, setActiveSubTab] = useState('pipelines'); // 'pipelines' | 'synthetic' | 'jobs'
  const [sourceDocs, setSourceDocs] = useState([]);
  const [syntheticDocs, setSyntheticDocs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Pipeline Modal State
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [trainingMethod, setTrainingMethod] = useState('STANDARD');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBatchSubmitting, setIsBatchSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

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
      const res = await apiClient.get('/training/status');
      setJobs(res.data?.data || []);
    } catch (e) {
      console.error("Failed to fetch job statuses", e);
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

      {/* Main Grid Content */}
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
