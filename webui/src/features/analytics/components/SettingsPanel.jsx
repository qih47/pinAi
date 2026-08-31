import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  Shield, 
  Server, 
  Database, 
  Save, 
  Lock, 
  X, 
  Key, 
  Sliders, 
  Cpu, 
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import apiClient from '../../../services/apiClient';
import ApiManagement from '../../admin/components/ApiManagement';

export const SettingsPanel = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [activeTab, setActiveTab] = useState('engines'); // 'engines' | 'rag' | 'system' | 'api'
  const [saveStatus, setSaveStatus] = useState(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await apiClient.get('/analytics/settings');
        if (res.data.status === 'success') {
          setConfig(res.data.data);
        }
        const modelsRes = await apiClient.get('/analytics/ollama/models');
        if (modelsRes.data.status === 'success') {
          setOllamaModels(modelsRes.data.models);
        }
      } catch (e) {
        console.error("Failed to fetch settings", e);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus(null);
    try {
      await apiClient.patch('/analytics/settings', {
        settings: config,
        sudo_password: ""
      });
      setSaveStatus({ type: 'success', message: 'Konfigurasi berhasil disimpan.' });
    } catch (e) {
      setSaveStatus({ type: 'error', message: e.response?.data?.detail || "Gagal menyimpan konfigurasi." });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveStatus(null), 4000);
    }
  };

  const handleChange = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-cyan-400">
        <div className="flex items-center gap-3">
          <Cpu className="animate-spin w-6 h-6" /> Memuat Konfigurasi Sistem...
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-6 animate-in fade-in duration-500">
      
      {/* Top Banner */}
      <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-6 relative">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h3 className="text-xl font-bold text-gray-200 flex items-center gap-2">
              <Settings className="text-cyan-400" /> System & Engine Settings
            </h3>
            <p className="text-sm text-gray-400 mt-1">Kelola parameter model AI, context window, database, dan security firewall.</p>
          </div>
          
          {activeTab !== 'api' && (
            <button 
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-cyan-900/30 disabled:opacity-50"
            >
              <Save size={15} /> {saving ? "Menyimpan..." : "Simpan Pengaturan"}
            </button>
          )}
        </div>

        {saveStatus && (
          <div className={`p-3 rounded-xl mb-4 text-xs font-semibold flex items-center gap-2 border ${
            saveStatus.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'
          }`}>
            {saveStatus.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            {saveStatus.message}
          </div>
        )}

        {/* Settings Sub-tabs */}
        <div className="flex gap-2 border-b border-gray-800">
          <button 
            onClick={() => setActiveTab('engines')}
            className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 ${
              activeTab === 'engines' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Server size={14} /> AI Engines & VRAM
          </button>
          <button 
            onClick={() => setActiveTab('rag')}
            className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 ${
              activeTab === 'rag' ? 'text-purple-400 border-b-2 border-purple-400 bg-purple-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Sliders size={14} /> RAG & Search Parameters
          </button>
          <button 
            onClick={() => setActiveTab('system')}
            className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 ${
              activeTab === 'system' ? 'text-emerald-400 border-b-2 border-emerald-400 bg-emerald-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Shield size={14} /> Infrastructure & Env
          </button>
          <button 
            onClick={() => setActiveTab('api')}
            className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 ${
              activeTab === 'api' ? 'text-amber-400 border-b-2 border-amber-400 bg-amber-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
          >
            <Key size={14} /> API Keys
          </button>
        </div>
      </div>

      {/* Tab Panels */}
      {config && activeTab === 'engines' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-300">
          <ConfigSection title="Core Model Engines" icon={<Server className="text-indigo-400" size={18}/>}>
            <ConfigDropdown 
              label="Persona & Chat Engine" 
              description="Model utama penjawab percakapan"
              value={config.MODEL_PERSONA} 
              options={ollamaModels.length ? ollamaModels : ["gemma4:31b", "gemma4:12b"]} 
              onChange={(val) => handleChange('MODEL_PERSONA', val)} 
            />
            <ConfigDropdown 
              label="Router Model Engine" 
              description="Model Call 1 untuk klasifikasi intent"
              value={config.MODEL_ROUTER || "gemma4:e4b"} 
              options={ollamaModels.length ? ollamaModels : ["gemma4:e4b", "gemma4:31b"]} 
              onChange={(val) => handleChange('MODEL_ROUTER', val)} 
            />
            <ConfigDropdown 
              label="Embedding Engine" 
              description="Model konversi vektor untuk database regulasi"
              value={config.MODEL_EMBEDDING} 
              options={ollamaModels.length ? ollamaModels : ["mxbai-embed-large:latest", "nomic-embed-text:latest"]} 
              onChange={(val) => handleChange('MODEL_EMBEDDING', val)} 
            />
            <ConfigDropdown 
              label="Vision / OCR Engine" 
              description="Model ekstraksi gambar & attachment"
              value={config.MODEL_VISION || "minicpm-v:latest"} 
              options={ollamaModels.length ? ollamaModels : ["minicpm-v:latest", "llava:latest"]} 
              onChange={(val) => handleChange('MODEL_VISION', val)} 
            />
          </ConfigSection>

          <ConfigSection title="VRAM & Context Window" icon={<Cpu className="text-cyan-400" size={18}/>}>
            <ConfigInput 
              label="Core Context Window (NUM_CTX_CORE)" 
              description="Panjang context tetap untuk model utama (16384)"
              value={config.NUM_CTX_CORE || 16384} 
              onChange={(val) => handleChange('NUM_CTX_CORE', parseInt(val) || 16384)} 
            />
            <ConfigInput 
              label="Router Context Window (NUM_CTX_ROUTER)" 
              description="Panjang context untuk router (4096)"
              value={config.NUM_CTX_ROUTER || 4096} 
              onChange={(val) => handleChange('NUM_CTX_ROUTER', parseInt(val) || 4096)} 
            />
            <ConfigInput 
              label="Ollama Server URL" 
              description="Endpoint HTTP daemon Ollama"
              value={config.OLLAMA_BASE_URL} 
              onChange={(val) => handleChange('OLLAMA_BASE_URL', val)} 
            />
          </ConfigSection>
        </div>
      )}

      {config && activeTab === 'rag' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-300">
          <ConfigSection title="Vector Retrieval Thresholds" icon={<Sliders className="text-purple-400" size={18}/>}>
            <ConfigInput 
              label="Similarity Threshold (Cosine Distance)" 
              description="Ambang batas minimal kemiripan dokumen (0.0 - 1.0)"
              value={config.SIMILARITY_THRESHOLD || 0.75} 
              onChange={(val) => handleChange('SIMILARITY_THRESHOLD', parseFloat(val) || 0.75)} 
            />
            <ConfigInput 
              label="Max Retrieval Chunks (Search Limit)" 
              description="Jumlah dokumen relevan yang disuplai ke context AI"
              value={config.SEARCH_LIMIT || 5} 
              onChange={(val) => handleChange('SEARCH_LIMIT', parseInt(val) || 5)} 
            />
          </ConfigSection>
        </div>
      )}

      {config && activeTab === 'system' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-300">
          <ConfigSection title="Database & Storage" icon={<Database className="text-red-400" size={18}/>}>
            <ConfigInput label="PostgreSQL Host" value={config.DB_HOST} onChange={(val) => handleChange('DB_HOST', val)} />
            <ConfigInput label="Target Database" value={config.DB_DATABASE || "ragdb"} disabled />
            <ConfigInput label="Session Capacity" value={config.MAX_SESSIONS} disabled />
          </ConfigSection>

          <ConfigSection title="Environment & Build" icon={<Shield className="text-emerald-400" size={18}/>}>
            <ConfigInput label="Environment" value={config.ENVIRONMENT} disabled />
            <ConfigDropdown 
              label="Debug Mode" 
              value={config.DEBUG_MODE} 
              options={["True", "False"]}
              onChange={(val) => handleChange('DEBUG_MODE', val)} 
            />
            <ConfigInput label="System Version" value={config.SYSTEM_VERSION} disabled />
          </ConfigSection>
        </div>
      )}

      {activeTab === 'api' && (
        <div className="animate-in fade-in duration-300">
          <ApiManagement />
        </div>
      )}
    </div>
  );
};

const ConfigSection = ({ title, icon, children }) => (
  <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-5 flex flex-col gap-4">
    <div className="flex items-center gap-2 border-b border-gray-800/80 pb-3">
      {icon}
      <h4 className="text-sm font-bold text-gray-200">{title}</h4>
    </div>
    <div className="flex flex-col gap-3">{children}</div>
  </div>
);

const ConfigInput = ({ label, description, value, onChange, disabled }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-semibold text-gray-300">{label}</label>
    {description && <span className="text-[10px] text-gray-500 mb-0.5">{description}</span>}
    <input 
      type="text" 
      value={value || ''} 
      onChange={e => onChange && onChange(e.target.value)}
      disabled={disabled}
      className={`bg-slate-950 border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-gray-200 outline-none focus:border-cyan-500 transition-colors ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    />
  </div>
);

const ConfigDropdown = ({ label, description, value, options, onChange }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-semibold text-gray-300">{label}</label>
    {description && <span className="text-[10px] text-gray-500 mb-0.5">{description}</span>}
    <select 
      value={value || ''} 
      onChange={e => onChange && onChange(e.target.value)}
      className="bg-slate-950 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 outline-none focus:border-cyan-500 transition-colors cursor-pointer"
    >
      {options.map((opt, idx) => (
        <option key={idx} value={opt} className="bg-slate-900 text-gray-200">{opt}</option>
      ))}
    </select>
  </div>
);
