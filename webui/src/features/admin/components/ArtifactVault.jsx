import React, { useState, useEffect } from 'react';
import { 
  Archive,
  RefreshCw,
  Code2,
  Download,
  X,
  FileText
} from 'lucide-react';
import apiClient from '../../../services/apiClient';
import CakraResponseRenderer from '../../chat/components/CakraResponseRenderer';

const ArtifactVault = () => {
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal Viewer State
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerContent, setViewerContent] = useState('');
  const [viewerLoading, setViewerLoading] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState(null);

  const fetchArtifacts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/admin/artifacts');
      setArtifacts(response.data.artifacts || []);
    } catch (err) {
      console.error("Gagal memuat artifacts:", err);
      setError(err.message || "Terjadi kesalahan saat memuat data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, []);

  const handleView = async (artifact) => {
    setSelectedArtifact(artifact);
    setViewerOpen(true);
    setViewerLoading(true);
    setViewerContent('');

    try {
      const response = await apiClient.get('/admin/artifacts/read', {
        params: {
          npp: artifact.npp,
          session_id: artifact.session_id,
          filename: artifact.filename
        }
      });
      setViewerContent(response.data);
    } catch (err) {
      console.error("Gagal membaca artifact:", err);
      setViewerContent("Error memuat konten file: " + (err.response?.data?.detail || err.message));
    } finally {
      setViewerLoading(false);
    }
  };

  const handleDownload = (artifact) => {
    const url = `/api/admin/artifacts/download?npp=${encodeURIComponent(artifact.npp)}&session_id=${encodeURIComponent(artifact.session_id)}&filename=${encodeURIComponent(artifact.filename)}`;
    window.open(url, '_blank');
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleString('id-ID');
  };

  const getLanguage = (filename) => {
    if (!filename) return 'text';
    const ext = filename.split('.').pop().toLowerCase();
    const map = {
      'js': 'javascript', 'jsx': 'jsx', 'ts': 'typescript', 'tsx': 'tsx',
      'py': 'python', 'json': 'json', 'md': 'markdown', 'html': 'html',
      'css': 'css', 'sh': 'bash', 'php': 'php', 'go': 'go', 'rs': 'rust',
      'java': 'java', 'c': 'c', 'cpp': 'cpp', 'sql': 'sql', 'xml': 'xml'
    };
    return map[ext] || ext;
  };

  return (
    <div className="flex-1 flex flex-col p-6 animate-in fade-in duration-500 max-w-7xl mx-auto w-full">
      
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-bold tracking-wide text-gray-100 flex items-center gap-3">
            <Archive className="text-cyan-400" size={28} />
            GENERATED ARTIFACTS VAULT
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Pusat audit untuk seluruh file dan kode yang pernah diciptakan oleh AI.
          </p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => window.open('/api/admin/artifacts/download_all', '_blank')}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Download size={16} />
            Download All
          </button>
          <button 
            onClick={fetchArtifacts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 p-4 bg-red-900/20 border border-red-500/30 rounded-lg flex items-center gap-3 text-red-400">
          <span className="font-semibold text-sm">Error: {error}</span>
        </div>
      )}

      {/* Table Container */}
      <div className="bg-[#0B0F19] border border-gray-800 rounded-xl overflow-hidden flex-1 flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-900/50 border-b border-gray-800 text-gray-400 text-sm uppercase tracking-wider">
                <th className="p-4 font-medium">Tanggal</th>
                <th className="p-4 font-medium">Pengguna (NPP)</th>
                <th className="p-4 font-medium">ID Sesi</th>
                <th className="p-4 font-medium">Nama File</th>
                <th className="p-4 font-medium text-right">Ukuran</th>
                <th className="p-4 font-medium text-center">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50 text-gray-300">
              {loading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-gray-500">
                    <RefreshCw className="animate-spin w-8 h-8 mx-auto mb-3 text-cyan-500/50" />
                    Memuat data artifacts...
                  </td>
                </tr>
              ) : artifacts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-gray-500 flex flex-col items-center">
                    <FileText className="w-12 h-12 mb-3 text-gray-700" />
                    Belum ada file artifact yang di-generate.
                  </td>
                </tr>
              ) : (
                artifacts.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-800/20 transition-colors">
                    <td className="p-4 text-sm whitespace-nowrap">{formatDate(row.created_at)}</td>
                    <td className="p-4">
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-md ${row.npp === 'guest' ? 'bg-gray-800 text-gray-400' : 'bg-cyan-900/40 text-cyan-400 border border-cyan-800/50'}`}>
                        {row.npp}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-xs text-gray-500">{row.session_id.substring(0, 8)}...</td>
                    <td className="p-4 font-semibold text-gray-200">{row.filename}</td>
                    <td className="p-4 text-sm text-right text-gray-400">{formatSize(row.size)}</td>
                    <td className="p-4 flex justify-center gap-2">
                      <button 
                        onClick={() => handleView(row)}
                        title="Lihat Kode"
                        className="p-2 text-gray-400 hover:text-cyan-400 hover:bg-cyan-400/10 rounded-lg transition-colors"
                      >
                        <Code2 size={18} />
                      </button>
                      <button 
                        onClick={() => handleDownload(row)}
                        title="Download File"
                        className="p-2 text-gray-400 hover:text-green-400 hover:bg-green-400/10 rounded-lg transition-colors"
                      >
                        <Download size={18} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Code Viewer Modal */}
      {viewerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="bg-[#0B0F19] border border-gray-700 rounded-xl w-full max-w-5xl max-h-full flex flex-col shadow-2xl overflow-hidden">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/30">
              <div className="flex items-center gap-3">
                <FileText className="text-cyan-400" size={20} />
                <h3 className="font-bold text-gray-200">{selectedArtifact?.filename}</h3>
                <span className="px-2 py-0.5 text-[10px] bg-gray-800 text-gray-400 rounded border border-gray-700 uppercase tracking-wider">
                  {selectedArtifact?.npp}
                </span>
              </div>
              <button 
                onClick={() => setViewerOpen(false)}
                className="text-gray-400 hover:text-white p-1 rounded-md hover:bg-gray-800 transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="flex-1 overflow-auto bg-[#05070A] p-4 relative min-h-[300px]">
              {viewerLoading ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <RefreshCw className="animate-spin w-8 h-8 text-cyan-500/50" />
                </div>
              ) : (
                <CakraResponseRenderer 
                  rawContent={
                    selectedArtifact?.filename?.toLowerCase().endsWith('.md') 
                      ? viewerContent 
                      : `\`\`\`${getLanguage(selectedArtifact?.filename)}\n${viewerContent}\n\`\`\``
                  } 
                  darkMode={true} 
                />
              )}
            </div>
            
            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-800 bg-gray-900/30 flex justify-end gap-3">
              <button 
                onClick={() => setViewerOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
              >
                Tutup
              </button>
              <button 
                onClick={() => handleDownload(selectedArtifact)}
                className="px-4 py-2 text-sm font-medium flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
              >
                <Download size={16} />
                Download File
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default ArtifactVault;
