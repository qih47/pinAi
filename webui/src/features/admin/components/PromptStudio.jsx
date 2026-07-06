import React, { useState, useEffect } from 'react';
import { Terminal, Save, RefreshCw, Code2, AlertCircle, CheckCircle2 } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export function PromptStudio() {
  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [editedTemplate, setEditedTemplate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);

  const fetchPrompts = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/analytics/prompts');
      if (res.data?.status === 'success') {
        setPrompts(res.data.prompts);
        if (res.data.prompts.length > 0 && !selectedPrompt) {
          selectPrompt(res.data.prompts[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch prompts", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrompts();
  }, []);

  const selectPrompt = (prompt) => {
    setSelectedPrompt(prompt);
    setEditedTemplate(prompt.template);
    setSaveStatus(null);
  };

  const handleSave = async () => {
    if (!selectedPrompt) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      await apiClient.put(`/analytics/prompts/${selectedPrompt.name}`, {
        template: editedTemplate
      });
      setSaveStatus({ type: 'success', msg: 'Prompt berhasil disimpan & Hot-Reload aktif!' });
      // Update local state
      const updated = prompts.map(p => 
        p.name === selectedPrompt.name ? { ...p, template: editedTemplate, version: p.version + 1 } : p
      );
      setPrompts(updated);
      setSelectedPrompt({ ...selectedPrompt, version: selectedPrompt.version + 1 });
    } catch (err) {
      setSaveStatus({ type: 'error', msg: 'Gagal menyimpan prompt.' });
      console.error(err);
    } finally {
      setSaving(false);
      setTimeout(() => setSaveStatus(null), 5000);
    }
  };

  if (loading && prompts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#090b10] text-gray-500">
        <RefreshCw className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-full bg-[#090b10] text-gray-200">
      {/* Sidebar Daftar Prompts */}
      <div className="w-1/4 border-r border-[#2d3748] bg-[#0d1017] flex flex-col">
        <div className="p-4 border-b border-[#2d3748] bg-[#11151f]">
          <h2 className="text-sm font-black text-gray-300 flex items-center gap-2 uppercase tracking-widest">
            <Code2 size={16} className="text-purple-400" /> Prompt Studio
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {prompts.map(p => (
            <div 
              key={p.name}
              onClick={() => selectPrompt(p)}
              className={`p-3 rounded-xl cursor-pointer border transition-all ${
                selectedPrompt?.name === p.name 
                  ? 'bg-purple-500/10 border-purple-500/50 shadow-[0_0_15px_rgba(168,85,247,0.1)]' 
                  : 'bg-[#161b22] border-transparent hover:border-[#2d3748]'
              }`}
            >
              <h3 className={`text-xs font-bold ${selectedPrompt?.name === p.name ? 'text-purple-400' : 'text-gray-300'}`}>
                {p.name}
              </h3>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[9px] text-gray-500 font-mono">v{p.version}</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">Jinja2</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Editor Utama */}
      <div className="flex-1 flex flex-col min-h-0 bg-[#0b0e14]">
        {selectedPrompt ? (
          <>
            <div className="p-4 border-b border-[#2d3748] bg-[#11151f] flex justify-between items-center shrink-0">
              <div>
                <h3 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                  <Terminal size={14} className="text-gray-500" /> {selectedPrompt.name}
                </h3>
                <p className="text-xs text-gray-500 mt-1">{selectedPrompt.description}</p>
              </div>
              <button 
                onClick={handleSave}
                disabled={saving || editedTemplate === selectedPrompt.template}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 text-xs font-bold transition-all shadow-lg
                  ${saving || editedTemplate === selectedPrompt.template 
                    ? 'bg-[#1a2235] text-gray-600 cursor-not-allowed shadow-none' 
                    : 'bg-purple-600 hover:bg-purple-500 text-white shadow-purple-900/20'}`}
              >
                {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                {saving ? 'Menyimpan...' : 'Simpan & Hot-Reload'}
              </button>
            </div>
            
            {saveStatus && (
              <div className={`px-4 py-2 text-xs flex items-center gap-2 border-b ${
                saveStatus.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
              }`}>
                {saveStatus.type === 'success' ? <CheckCircle2 size={14}/> : <AlertCircle size={14}/>}
                {saveStatus.msg}
              </div>
            )}

            <div className="flex-1 p-4 flex flex-col min-h-0">
              <div className="bg-[#1e1e1e] rounded-xl border border-[#2d3748] flex-1 flex flex-col overflow-hidden">
                <div className="bg-[#252526] px-4 py-2 border-b border-[#3c3c3c] flex gap-4">
                  <span className="text-[10px] text-[#cccccc] font-mono">Template.jinja2</span>
                  <span className="text-[10px] text-[#808080] font-mono">| Gunakan {'{{ variabel }}'} atau {'{% if kondisi %}'}</span>
                </div>
                <textarea 
                  value={editedTemplate}
                  onChange={(e) => setEditedTemplate(e.target.value)}
                  className="flex-1 bg-transparent text-[#d4d4d4] font-mono text-sm p-4 outline-none resize-none"
                  spellCheck="false"
                  style={{ lineHeight: '1.5' }}
                />
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-600">
            <Code2 size={48} className="opacity-20 mb-4" />
            <p className="text-sm font-mono">Pilih prompt di sebelah kiri untuk mengedit.</p>
          </div>
        )}
      </div>
    </div>
  );
}
