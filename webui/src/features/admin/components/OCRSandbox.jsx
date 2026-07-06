import React, { useState, useRef } from 'react';
import { Upload, FileText, Image as ImageIcon, Loader2, AlertCircle, FileUp, Zap, FileSearch } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export function OCRSandbox() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState('text'); // 'text' or 'images'
  
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setError(null);
      setResult(null);
    } else {
      setError('Mohon unggah file PDF yang valid.');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
      setError(null);
      setResult(null);
    } else {
      setError('Mohon unggah file PDF yang valid.');
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const runSimulation = async () => {
    if (!file) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await apiClient.post('/analytics/simulate-ocr', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 120000 // OCR can take a while
      });
      
      if (res.data?.status === 'success') {
        setResult({
          text: res.data.extracted_text,
          images: res.data.images || []
        });
        if (!res.data.extracted_text && res.data.images?.length > 0) {
          setActiveTab('images');
        } else {
          setActiveTab('text');
        }
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Terjadi kesalahan saat mengeksekusi OCR Sandbox.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#090b10] text-gray-200">
      <div className="p-6 border-b border-[#2d3748] bg-[#11151f]">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/30">
            <FileSearch className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
              OCR & Vision Fallback Sandbox
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Simulasikan ekstraksi teks pada dokumen PDF "kotor" menggunakan mesin OCRmyPDF dan pipeline Vision.
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* LEFT PANEL - UPLOAD */}
        <div className="w-full md:w-1/3 border-r border-[#2d3748] bg-[#0d1017] p-6 flex flex-col">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest mb-4">Target File</h3>
          
          <div 
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors cursor-pointer
              ${file ? 'border-blue-500/50 bg-blue-500/5' : 'border-[#2d3748] hover:border-blue-500/30 hover:bg-[#11151f]'}`}
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept="application/pdf"
              onChange={handleFileSelect}
            />
            
            {file ? (
              <>
                <FileText className="w-12 h-12 text-blue-400 mb-3" />
                <p className="text-sm font-bold text-gray-200 break-all">{file.name}</p>
                <p className="text-xs text-gray-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                <p className="text-[10px] text-blue-400 mt-4 border border-blue-500/30 px-2 py-1 rounded bg-blue-500/10">Klik untuk mengganti file</p>
              </>
            ) : (
              <>
                <FileUp className="w-12 h-12 text-gray-600 mb-3" />
                <p className="text-sm font-bold text-gray-300">Drag & Drop file PDF ke sini</p>
                <p className="text-xs text-gray-500 mt-1">atau klik untuk memilih dari komputer</p>
              </>
            )}
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3 text-red-400">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <p className="text-xs leading-relaxed">{error}</p>
            </div>
          )}

          <div className="mt-auto pt-6">
            <button
              onClick={runSimulation}
              disabled={!file || loading}
              className={`w-full py-3 rounded-xl flex items-center justify-center gap-2 font-bold transition-all shadow-lg
                ${!file || loading 
                  ? 'bg-[#1a2235] text-gray-500 cursor-not-allowed shadow-none' 
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-900/20'}`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Mengeksekusi Pipeline...
                </>
              ) : (
                <>
                  <Zap className="w-5 h-5" />
                  Simulasikan Ekstraksi
                </>
              )}
            </button>
          </div>
        </div>

        {/* RIGHT PANEL - RESULTS */}
        <div className="w-full md:w-2/3 flex flex-col min-h-0 bg-[#0b0e14]">
          {!result && !loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-600 p-8 text-center">
              <FileSearch className="w-16 h-16 opacity-20 mb-4" />
              <h3 className="text-lg font-bold text-gray-400 mb-2">Menunggu Input Dokumen</h3>
              <p className="text-sm">Unggah file PDF di sebelah kiri dan klik tombol simulasi untuk melihat hasil ekstraksi mesin OCR.</p>
            </div>
          ) : loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-blue-400 p-8 text-center">
              <Loader2 className="w-12 h-12 animate-spin mb-4" />
              <h3 className="text-sm font-bold uppercase tracking-widest animate-pulse">Memproses OCR...</h3>
              <p className="text-xs text-gray-500 mt-2 font-mono">Proses ini mungkin memakan waktu untuk dokumen hasil scan.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1 p-3 border-b border-[#2d3748] bg-[#11151f]">
                <button
                  onClick={() => setActiveTab('text')}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold transition-colors
                    ${activeTab === 'text' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'text-gray-500 hover:bg-[#1a2235]'}`}
                >
                  <FileText className="w-4 h-4" /> Teks Murni
                </button>
                <button
                  onClick={() => setActiveTab('images')}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold transition-colors
                    ${activeTab === 'images' ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' : 'text-gray-500 hover:bg-[#1a2235]'}`}
                >
                  <ImageIcon className="w-4 h-4" /> Fallback VLM (Images)
                  <span className="bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded text-[10px] ml-1">
                    {result.images.length}
                  </span>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 relative">
                {activeTab === 'text' ? (
                  result.text ? (
                    <div className="bg-[#0d1017] border border-[#2d3748] rounded-xl p-4 min-h-full">
                      <pre className="text-[11px] text-gray-300 font-mono whitespace-pre-wrap leading-relaxed">
                        {result.text}
                      </pre>
                    </div>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-yellow-500/70 p-8 text-center border-2 border-dashed border-yellow-900/30 rounded-xl">
                      <AlertCircle className="w-12 h-12 mb-4 opacity-50" />
                      <p className="text-sm font-bold">Tidak ada teks yang dapat diekstrak secara murni.</p>
                      <p className="text-xs text-yellow-500/50 mt-2 max-w-md">
                        Dokumen ini kemungkinan adalah hasil scan gambar. Sistem telah menjalankan OCR dan mengirimkan versi gambarnya ke fallback VLM. Silakan cek tab Images.
                      </p>
                    </div>
                  )
                ) : (
                  result.images.length > 0 ? (
                    <div className="flex flex-col gap-6">
                      {result.images.map((img, idx) => (
                        <div key={idx} className="border border-[#2d3748] rounded-xl overflow-hidden bg-black/50">
                          <div className="p-2 border-b border-[#2d3748] bg-[#11151f] flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-400">Halaman {idx + 1}</span>
                            <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded border border-blue-500/30 uppercase">PNG / 150 DPI</span>
                          </div>
                          <div className="p-4 flex justify-center bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAAXNSR0IArs4c6QAAACVJREFUKFNjZCASMDKgAnv37v3/n4GRkZGBkQzDhBpoYDQ1xAEAMi8Q8eQO/xMAAAAASUVORK5CYII=')]">
                            <img 
                              src={`data:image/png;base64,${img.base64}`} 
                              alt={`Page ${idx + 1}`}
                              className="max-w-full h-auto rounded shadow-2xl shadow-black/50 ring-1 ring-white/10"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-gray-600 p-8 text-center border-2 border-dashed border-[#2d3748] rounded-xl">
                      <ImageIcon className="w-12 h-12 mb-4 opacity-20" />
                      <p className="text-sm font-bold">Tidak ada gambar yang dihasilkan.</p>
                      <p className="text-xs mt-2 max-w-md">
                        Karena teks berhasil diekstrak murni dari PDF, fallback image tidak perlu di-generate untuk VLM demi menghemat VRAM.
                      </p>
                    </div>
                  )
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
