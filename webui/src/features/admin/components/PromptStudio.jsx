import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  Save, 
  RefreshCw, 
  Code2, 
  AlertCircle, 
  CheckCircle2, 
  Search, 
  Tag, 
  Eye, 
  Layers, 
  Sparkles,
  RotateCcw
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

export function PromptStudio() {
  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [editedTemplate, setEditedTemplate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('ALL'); // 'ALL' | 'ROUTER' | 'RAG' | 'CORE' | 'SECURITY'

  const fetchPrompts = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/analytics/prompts');
      if (res.data?.status === 'success') {
        const fetched = res.data.prompts || [];
        setPrompts(fetched);
        if (fetched.length > 0 && !selectedPrompt) {
          selectPrompt(fetched[0]);
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
      
      const updated = prompts.map(p => 
        p.name === selectedPrompt.name ? { ...p, template: editedTemplate, version: (p.version || 1) + 1 } : p
      );
      setPrompts(updated);
      setSelectedPrompt({ ...selectedPrompt, version: (selectedPrompt.version || 1) + 1 });
    } catch (err) {
      setSaveStatus({ type: 'error', msg: 'Gagal menyimpan prompt.' });
      console.error(err);
    } finally {
      setSaving(false);
      setTimeout(() => setSaveStatus(null), 5000);
    }
  };

  const insertVariable = (varName) => {
    setEditedTemplate(prev => prev + ` {{ ${varName} }} `);
  };

  // Categorize helper
  const getPromptCategory = (name) => {
    const n = name.toLowerCase();
    if (n.includes('router') || n.includes('intent') || n.includes('classify')) return 'ROUTER';
    if (n.includes('rag') || n.includes('peraturan') || n.includes('document')) return 'RAG';
    if (n.includes('security') || n.includes('guardrail') || n.includes('redteam')) return 'SECURITY';
    return 'CORE';
  };

  const filteredPrompts = prompts.filter(p => {
    const matchesSearch = !searchQuery || p.name.toLowerCase().includes(searchQuery.toLowerCase()) || (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));
    const cat = getPromptCategory(p.name);
    const matchesCat = activeCategory === 'ALL' || cat === activeCategory;
    return matchesSearch && matchesCat;
  });

  const COMMON_VARIABLES = [
    "user_query",
    "retrieved_context",
    "user_name",
    "user_divisi",
    "current_date",
    "intent_type"
  ];

  if (loading && prompts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#090b10] text-purple-400">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin" /> Memuat Prompt Studio...
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-[#0B0F19] border border-gray-800 rounded-2xl overflow-hidden animate-in fade-in duration-500">
      
      {/* Sidebar: Prompt List */}
      <div className="w-80 border-r border-gray-800 bg-[#090C15] flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-800 bg-slate-950">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-bold text-gray-200 flex items-center gap-2 uppercase tracking-wider">
              <Code2 size={15} className="text-purple-400" /> Prompt Studio
            </h2>
            <button onClick={fetchPrompts} className="text-gray-500 hover:text-gray-300 p-1" title="Refresh Prompts">
              <RotateCcw size={13} />
            </button>
          </div>

          {/* Search Box */}
          <div className="flex items-center gap-2 bg-slate-900 border border-gray-800 rounded-lg px-2.5 py-1.5 mb-2.5">
            <Search size={13} className="text-gray-500" />
            <input
              type="text"
              placeholder="Cari prompt..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-none outline-none text-xs text-gray-200 w-full placeholder-gray-500"
            />
          </div>

          {/* Category Filter Pills */}
          <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar pb-1">
            {['ALL', 'CORE', 'ROUTER', 'RAG', 'SECURITY'].map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-md transition-colors ${
                  activeCategory === cat ? 'bg-purple-600 text-white' : 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Prompt Items List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {filteredPrompts.length === 0 ? (
            <div className="text-center text-gray-600 py-10 text-xs font-mono">
              Tidak ada prompt ditemukan.
            </div>
          ) : (
            filteredPrompts.map(p => {
              const isSelected = selectedPrompt?.name === p.name;
              const cat = getPromptCategory(p.name);
              return (
                <div 
                  key={p.name}
                  onClick={() => selectPrompt(p)}
                  className={`p-3 rounded-xl cursor-pointer border transition-all ${
                    isSelected 
                      ? 'bg-purple-500/10 border-purple-500/50 shadow-lg shadow-purple-500/10' 
                      : 'bg-slate-950/60 border-gray-800/80 hover:border-gray-700 hover:bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className={`text-xs font-semibold truncate ${isSelected ? 'text-purple-300' : 'text-gray-300'}`}>
                      {p.name}
                    </h3>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-cyan-400 font-mono">
                      v{p.version || 1}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-1 line-clamp-1">
                    {p.description || "System prompt template"}
                  </p>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Prompt Editor Canvas */}
      <div className="flex-1 flex flex-col min-h-0 bg-[#05070D]">
        {selectedPrompt ? (
          <>
            <div className="p-4 border-b border-gray-800 bg-[#090C15] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    Jinja2 Template
                  </span>
                  <h3 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                    <Terminal size={14} className="text-gray-500" /> {selectedPrompt.name}
                  </h3>
                </div>
                <p className="text-xs text-gray-500 mt-1">{selectedPrompt.description}</p>
              </div>

              <button 
                onClick={handleSave}
                disabled={saving || editedTemplate === selectedPrompt.template}
                className={`px-4 py-2 rounded-xl flex items-center gap-2 text-xs font-semibold transition-all shadow-lg
                  ${saving || editedTemplate === selectedPrompt.template 
                    ? 'bg-gray-800 text-gray-500 cursor-not-allowed shadow-none' 
                    : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-purple-900/30'}`}
              >
                {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                {saving ? 'Menyimpan...' : 'Simpan & Hot-Reload'}
              </button>
            </div>
            
            {saveStatus && (
              <div className={`px-4 py-2.5 text-xs flex items-center gap-2 border-b ${
                saveStatus.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
              }`}>
                {saveStatus.type === 'success' ? <CheckCircle2 size={14}/> : <AlertCircle size={14}/>}
                {saveStatus.msg}
              </div>
            )}

            {/* Quick Variable Insert Bar */}
            <div className="px-4 py-2 bg-slate-950/80 border-b border-gray-800/80 flex items-center gap-2 overflow-x-auto custom-scrollbar">
              <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider flex items-center gap-1 shrink-0">
                <Tag size={10} /> Insert Tag:
              </span>
              {COMMON_VARIABLES.map(v => (
                <button
                  key={v}
                  onClick={() => insertVariable(v)}
                  className="text-[10px] font-mono text-cyan-400 bg-cyan-950/40 border border-cyan-800/40 hover:bg-cyan-900/50 hover:border-cyan-500 px-2 py-0.5 rounded transition-all shrink-0"
                >
                  +{`{{${v}}}`}
                </button>
              ))}
            </div>

            {/* Code Editor Window */}
            <div className="flex-1 p-4 flex flex-col min-h-0">
              <div className="bg-[#0B0F19] rounded-xl border border-gray-800 flex-1 flex flex-col overflow-hidden shadow-2xl">
                <div className="bg-slate-950 px-4 py-2 border-b border-gray-800 flex justify-between items-center">
                  <span className="text-[11px] text-gray-400 font-mono flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-500" /> {selectedPrompt.name}.jinja2
                  </span>
                  <span className="text-[10px] text-gray-600 font-mono">
                    UTF-8 · Jinja Template Hot-Reload Engine
                  </span>
                </div>
                <textarea 
                  value={editedTemplate}
                  onChange={(e) => setEditedTemplate(e.target.value)}
                  className="flex-1 bg-transparent text-gray-200 font-mono text-xs p-4 outline-none resize-none custom-scrollbar leading-relaxed"
                  spellCheck="false"
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
