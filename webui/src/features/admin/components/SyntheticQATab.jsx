import React, { useState, useEffect } from 'react';
import { Brain, FileText, Activity, Database, CheckCircle2, XCircle, Play } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const SyntheticQATab = () => {
  const [sourceDocs, setSourceDocs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isBatchSubmitting, setIsBatchSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    setLoading(true);
    await Promise.all([fetchSourceDocs(), fetchJobs()]);
    setLoading(false);
  };

  const fetchSourceDocs = async () => {
    try {
      const res = await apiClient.get('/synthetic/source-docs');
      setSourceDocs(res.data.data);
    } catch (e) {
      console.error("Failed to fetch source docs", e);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await apiClient.get('/training/status');
      setJobs(res.data.data);
    } catch (e) {
      console.error("Failed to fetch job statuses", e);
    }
  };

  const handleBatchSubmit = async () => {
    setIsBatchSubmitting(true);
    try {
      const res = await apiClient.post('/synthetic/submit-batch');
      alert(`Berhasil memulai batch job dengan ID: ${res.data.job_id}. Pantau progresnya di Live Job Monitor.`);
      fetchJobs();
    } catch (e) {
      alert("Gagal submit batch training.");
      console.error(e);
    } finally {
      setIsBatchSubmitting(false);
    }
  };

  const handleSingleSubmit = async (docId) => {
    try {
      await apiClient.post('/synthetic/submit', { dokumen_id: docId });
      fetchJobs();
    } catch (e) {
      alert("Gagal submit training.");
      console.error(e);
    }
  };

  const renderStatusBadge = (status) => {
    switch (status) {
      case 'RUNNING': return <span className="flex items-center gap-1 text-blue-400 bg-blue-500/10 px-2 py-1 rounded text-xs"><Activity className="w-3 h-3 animate-pulse" /> Running</span>;
      case 'DONE': return <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded text-xs"><CheckCircle2 className="w-3 h-3" /> Done</span>;
      case 'FAILED': return <span className="flex items-center gap-1 text-red-400 bg-red-500/10 px-2 py-1 rounded text-xs"><XCircle className="w-3 h-3" /> Failed</span>;
      default: return <span className="flex items-center gap-1 text-slate-400 bg-slate-500/10 px-2 py-1 rounded text-xs">Pending</span>;
    }
  };

  return (
    <div className="flex flex-col gap-6 text-slate-200 animate-in fade-in duration-500">
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-purple-500/20 border border-purple-500/30 rounded-xl">
            <Brain className="w-8 h-8 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-indigo-400">
              Synthetic Q&A Training
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Generate ratusan/ribuan pertanyaan simulasi dari metadata dokumen (MySQL) dan tanamkan ke dalam vector database (PostgreSQL) menggunakan LLM Gemma.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden flex flex-col h-[600px]">
          <div className="p-4 border-b border-slate-800 bg-slate-900 flex justify-between items-center">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" /> MySQL Source: Tabel Berita
            </h3>
            <div className="flex items-center gap-3">
              <button 
                onClick={handleBatchSubmit}
                disabled={isBatchSubmitting}
                className="text-xs bg-purple-600 hover:bg-purple-500 text-white px-4 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {isBatchSubmitting ? <Activity className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                Train All Missing
              </button>
              <button onClick={fetchSourceDocs} className="text-xs text-blue-400 hover:text-blue-300">Refresh Data</button>
            </div>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {loading ? (
              <div className="animate-pulse space-y-3">
                {[1,2,3,4].map(i => <div key={i} className="h-16 bg-slate-800/50 rounded-xl" />)}
              </div>
            ) : (
              <div className="space-y-3">
                {sourceDocs.map(doc => (
                  <div key={doc.id} className="flex items-center justify-between p-4 bg-slate-950 border border-slate-800 rounded-xl hover:border-slate-700 transition-colors">
                    <div className="flex items-start gap-3">
                      <FileText className="w-5 h-5 text-slate-500 mt-0.5 shrink-0" />
                      <div>
                        <h4 className="text-sm font-medium text-slate-200 line-clamp-1">{doc.judul}</h4>
                        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                          <span>{doc.noper}</span>
                          <span>•</span>
                          <span>{doc.file_name}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4 shrink-0">
                      {doc.is_synthetic_embedded ? (
                        <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full text-xs font-medium border border-emerald-500/20">
                          <CheckCircle2 className="w-4 h-4" /> Embedded
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 text-slate-400 rounded-full text-xs font-medium border border-slate-700">
                          <XCircle className="w-4 h-4" /> Not Embedded
                        </span>
                      )}
                      
                      <button 
                        onClick={() => handleSingleSubmit(doc.id)}
                        disabled={doc.is_synthetic_embedded}
                        className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          doc.is_synthetic_embedded 
                            ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                            : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20'
                        }`}
                      >
                        <Play className="w-3 h-3" /> Train
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl flex flex-col h-[600px] overflow-hidden">
          <div className="p-4 border-b border-slate-800 bg-slate-900">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-400" /> Live Job Monitor
            </h3>
          </div>
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {jobs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm">
                <Brain className="w-8 h-8 mb-2 opacity-50" />
                Tidak ada antrean pelatihan.
              </div>
            ) : (
              jobs.map(job => (
                <div key={job.job_id} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Doc ID: {job.dokumen_id} • {job.tipe_training}</div>
                      {renderStatusBadge(job.status)}
                    </div>
                    <span className="text-xs font-mono text-slate-500" title={job.job_id}>{job.job_id.substring(0,8)}...</span>
                  </div>
                  
                  {job.status === 'RUNNING' && (
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-blue-400">{job.progress}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  <div className="bg-black/50 p-2 rounded text-[10px] font-mono text-slate-400 h-16 overflow-y-auto whitespace-pre-wrap">
                    {job.logs || "No logs available."}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SyntheticQATab;
