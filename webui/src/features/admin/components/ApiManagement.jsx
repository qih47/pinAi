import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Plus, 
  Trash2, 
  Copy, 
  Check, 
  AlertTriangle,
  Server,
  Activity,
  Calendar,
  X
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

const ApiManagement = () => {
  const [keys, setKeys] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [newAppName, setNewAppName] = useState('');
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [newlyGeneratedKey, setNewlyGeneratedKey] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get('/keys/list');
      setKeys(response.data);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch API keys", err);
      setError("Gagal mengambil data API Keys. Pastikan Anda memiliki akses Admin.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateKey = async (e) => {
    e.preventDefault();
    if (!newAppName.trim()) return;

    setIsGenerating(true);
    try {
      const response = await apiClient.post('/keys/generate', { app_name: newAppName });
      setNewlyGeneratedKey(response.data.raw_key);
      setNewAppName('');
      fetchKeys(); // Refresh list
    } catch (err) {
      console.error("Failed to generate key", err);
      setError("Gagal membuat API Key baru.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRevokeKey = async (id, appName) => {
    if (!window.confirm(`Apakah Anda yakin ingin MENCABUT akses untuk aplikasi '${appName}'? Kunci yang dicabut tidak dapat digunakan kembali.`)) {
      return;
    }
    try {
      await apiClient.delete(`/keys/revoke/${id}`);
      fetchKeys(); // Refresh list
    } catch (err) {
      console.error("Failed to revoke key", err);
      alert("Gagal mencabut API Key.");
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen text-slate-200 p-6 space-y-6 animate-in fade-in zoom-in-95 duration-500">
      
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 bg-blue-500/20 rounded-xl border border-blue-500/30">
              <Key className="w-6 h-6 text-blue-400" />
            </div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
              API Management
            </h1>
          </div>
          <p className="text-slate-400 max-w-2xl text-sm leading-relaxed">
            Kelola kunci Server-to-Server (API Keys) untuk aplikasi eksternal seperti Portal Pindad. 
            Kunci ini memberikan akses penuh ke mesin AI CAKRA secara programmatic.
          </p>
        </div>
        
        <button
          onClick={() => setShowGenerateModal(true)}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-500/25 active:scale-95 group"
        >
          <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform" />
          Generate New Key
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Keys List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isLoading ? (
          [1, 2, 3].map(i => (
            <div key={i} className="h-48 rounded-2xl bg-slate-800/50 border border-slate-700/50 animate-pulse" />
          ))
        ) : keys.length === 0 ? (
          <div className="col-span-full py-16 flex flex-col items-center justify-center text-center border-2 border-dashed border-slate-700 rounded-3xl bg-slate-900/30">
            <Server className="w-16 h-16 text-slate-600 mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">Belum Ada API Key</h3>
            <p className="text-slate-500 max-w-md">
              Anda belum membuat API Key apa pun. Buat kunci baru untuk mulai mengintegrasikan CAKRA dengan aplikasi eksternal.
            </p>
          </div>
        ) : (
          keys.map((key) => (
            <div 
              key={key.id}
              className={`relative overflow-hidden group rounded-2xl p-6 transition-all duration-300 ${
                key.is_active 
                  ? 'bg-slate-900/80 border-slate-700 hover:border-blue-500/50 hover:bg-slate-800/80 hover:shadow-xl hover:shadow-blue-500/10' 
                  : 'bg-slate-900/40 border-slate-800 opacity-60'
              } border`}
            >
              {/* Status Indicator */}
              <div className={`absolute top-0 right-0 w-24 h-24 -mt-12 -mr-12 rounded-full opacity-20 blur-2xl ${key.is_active ? 'bg-blue-500' : 'bg-red-500'}`} />
              
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-slate-200 mb-1 line-clamp-1" title={key.app_name}>
                    {key.app_name}
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      key.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {key.is_active ? 'Active' : 'Revoked'}
                    </span>
                    <span className="text-xs text-slate-500">By: {key.owner_npp}</span>
                  </div>
                </div>
                {key.is_active && (
                  <button
                    onClick={() => handleRevokeKey(key.id, key.app_name)}
                    className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                    title="Revoke Key"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <div className="p-3 bg-black/40 rounded-xl border border-slate-800 font-mono text-sm text-slate-400 text-center select-none">
                  {key.key_prefix}
                </div>
                
                <div className="flex items-center justify-between text-sm text-slate-400">
                  <div className="flex items-center gap-1.5" title="Total Requests">
                    <Activity className="w-4 h-4 text-blue-400" />
                    <span>{key.total_requests.toLocaleString()} Hits</span>
                  </div>
                  <div className="flex items-center gap-1.5" title="Dibuat pada">
                    <Calendar className="w-4 h-4 text-slate-500" />
                    <span>{new Date(key.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Generate Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !newlyGeneratedKey && setShowGenerateModal(false)} />
          
          <div className="relative w-full max-w-md bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-800/30">
              <h3 className="text-xl font-bold text-slate-200">Generate API Key</h3>
              {!newlyGeneratedKey && (
                <button onClick={() => setShowGenerateModal(false)} className="text-slate-400 hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <div className="p-6">
              {newlyGeneratedKey ? (
                <div className="space-y-6">
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl">
                    <p className="text-emerald-400 font-medium text-center mb-1">Berhasil Dibuat!</p>
                    <p className="text-slate-400 text-xs text-center">
                      Simpan kunci rahasia ini SEKARANG. Kunci ini tidak akan ditampilkan lagi demi keamanan.
                    </p>
                  </div>
                  
                  <div className="relative group">
                    <div className="p-4 bg-black/50 border border-slate-700 rounded-xl font-mono text-sm text-blue-300 break-all pr-12">
                      {newlyGeneratedKey}
                    </div>
                    <button
                      onClick={() => copyToClipboard(newlyGeneratedKey)}
                      className="absolute top-1/2 -translate-y-1/2 right-2 p-2 bg-slate-800 hover:bg-blue-600 text-slate-300 hover:text-white rounded-lg transition-all"
                    >
                      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                  
                  <button
                    onClick={() => {
                      setNewlyGeneratedKey(null);
                      setShowGenerateModal(false);
                    }}
                    className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-medium transition-colors"
                  >
                    Saya Sudah Menyimpannya
                  </button>
                </div>
              ) : (
                <form onSubmit={handleGenerateKey} className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-300">Nama Aplikasi / Penggunaan</label>
                    <input
                      type="text"
                      required
                      value={newAppName}
                      onChange={(e) => setNewAppName(e.target.value)}
                      placeholder="Misal: Portal Pindad"
                      className="w-full px-4 py-3 bg-slate-950 border border-slate-700 focus:border-blue-500 rounded-xl text-white outline-none transition-colors placeholder:text-slate-600"
                    />
                    <p className="text-xs text-slate-500">
                      Gunakan nama yang jelas agar mudah diidentifikasi jika suatu saat perlu dicabut (revoke).
                    </p>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowGenerateModal(false)}
                      className="flex-1 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-medium transition-colors"
                    >
                      Batal
                    </button>
                    <button
                      type="submit"
                      disabled={isGenerating || !newAppName.trim()}
                      className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white rounded-xl font-medium transition-colors flex justify-center items-center gap-2"
                    >
                      {isGenerating ? (
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      ) : (
                        'Generate Key'
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiManagement;
