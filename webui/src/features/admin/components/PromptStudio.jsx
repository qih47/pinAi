import React, { useState, useEffect, useMemo } from 'react';
import { 
  Terminal, 
  Save, 
  RefreshCw, 
  Code2, 
  AlertCircle, 
  CheckCircle2, 
  Search, 
  Tag, 
  RotateCcw
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

const CATEGORY_STYLES = {
  ALL: {
    badge: 'bg-gray-800 text-gray-300 border-gray-700',
    activeTab: 'bg-purple-600 text-white shadow-purple-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  },
  ROUTER: {
    badge: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    activeTab: 'bg-cyan-600 text-white shadow-cyan-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  },
  RAG: {
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    activeTab: 'bg-emerald-600 text-white shadow-emerald-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  },
  SECURITY: {
    badge: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    activeTab: 'bg-rose-600 text-white shadow-rose-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  },
  CORPORATE: {
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    activeTab: 'bg-amber-600 text-white shadow-amber-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  },
  CORE: {
    badge: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    activeTab: 'bg-purple-600 text-white shadow-purple-900/40',
    inactiveTab: 'bg-gray-800/60 text-gray-400 hover:text-gray-200'
  }
};

const CATEGORIES = ['ALL', 'CORE', 'ROUTER', 'RAG', 'SECURITY', 'CORPORATE'];

export function PromptStudio() {
  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [editedTemplate, setEditedTemplate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('ALL');

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

  // Robust category resolver
  const getPromptCategory = (prompt) => {
    if (prompt?.category && prompt.category.toUpperCase() !== 'CORE') {
      return prompt.category.toUpperCase();
    }
    const name = typeof prompt === 'string' ? prompt : (prompt?.name || '');
    const n = name.toLowerCase();
    const d = (prompt?.description || '').toLowerCase();
    
    if (n.includes('router') || n.includes('routing') || n.includes('dispatcher') || n.includes('preset') || n.includes('intent') || n.includes('classify')) {
      return 'ROUTER';
    }
    if (n.includes('security') || n.includes('guardrail') || n.includes('redteam') || n.includes('compliance') || n.includes('threat')) {
      return 'SECURITY';
    }
    if (n.includes('rag') || n.includes('peraturan') || n.includes('document') || n.includes('doc_audit') || n.includes('focus') || n.includes('insight') || n.includes('attachment')) {
      return 'RAG';
    }
    if (n.includes('corporate') || n.includes('nota_dinas') || n.includes('smart_mail') || n.includes('vendor_analyzer') || n.includes('email') || d.includes('email')) {
      return 'CORPORATE';
    }
    return prompt?.category ? prompt.category.toUpperCase() : 'CORE';
  };

  // Calculate items count per category for dynamic badges
  const categoryCounts = useMemo(() => {
    const counts = { ALL: prompts.length, CORE: 0, ROUTER: 0, RAG: 0, SECURITY: 0, CORPORATE: 0 };
    prompts.forEach(p => {
      const cat = getPromptCategory(p);
      if (counts[cat] !== undefined) {
        counts[cat]++;
      } else {
        counts.CORE++;
      }
    });
    return counts;
  }, [prompts]);

  const filteredPrompts = useMemo(() => {
    return prompts.filter(p => {
      const matchesSearch = !searchQuery || 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
        (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));
      const cat = getPromptCategory(p);
      const matchesCat = activeCategory === 'ALL' || cat === activeCategory;
      return matchesSearch && matchesCat;
    });
  }, [prompts, searchQuery, activeCategory]);

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

  const selectedCategory = selectedPrompt ? getPromptCategory(selectedPrompt) : 'CORE';
  const selectedCatStyle = CATEGORY_STYLES[selectedCategory] || CATEGORY_STYLES.CORE;

  return (
    <div className="flex h-full bg-[#0B0F19] border border-gray-800 rounded-2xl overflow-hidden animate-in fade-in duration-500">
      
      {/* Sidebar: Prompt List */}
      <div className="w-84 border-r border-gray-800 bg-[#090C15] flex flex-col shrink-0">
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
            {CATEGORIES.map(cat => {
              const count = categoryCounts[cat] || 0;
              const isActive = activeCategory === cat;
              const style = CATEGORY_STYLES[cat] || CATEGORY_STYLES.CORE;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-md transition-all flex items-center gap-1 shrink-0 ${
                    isActive ? style.activeTab : style.inactiveTab
                  }`}
                >
                  <span>{cat}</span>
                  <span className={`text-[9px] px-1 rounded-full ${isActive ? 'bg-black/30 text-white' : 'bg-gray-800 text-gray-400'}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Prompt Items List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {filteredPrompts.length === 0 ? (
            <div className="text-center text-gray-600 py-10 text-xs font-mono">
              Tidak ada prompt pada kategori {activeCategory}.
            </div>
          ) : (
            filteredPrompts.map(p => {
              const isSelected = selectedPrompt?.name === p.name;
              const cat = getPromptCategory(p);
              const catStyle = CATEGORY_STYLES[cat] || CATEGORY_STYLES.CORE;
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
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className={`text-xs font-semibold truncate ${isSelected ? 'text-purple-300' : 'text-gray-300'}`}>
                      {p.name}
                    </h3>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${catStyle.badge}`}>
                        {cat}
                      </span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-cyan-400 font-mono">
                        v{p.version || 1}
                      </span>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500 line-clamp-1">
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
                  <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${selectedCatStyle.badge}`}>
                    {selectedCategory}
                  </span>
                  <span className="text-[10px] uppercase font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    Jinja2
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
