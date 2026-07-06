import React, { useState, useEffect } from 'react';
import { Settings, Shield, Server, Database, Save, Lock, X, Key } from 'lucide-react';
import apiClient from '../../../services/apiClient';
import ApiManagement from '../../admin/components/ApiManagement';

export const SettingsPanel = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);
  
  const [sudoPrompt, setSudoPrompt] = useState(false);
  const [password, setPassword] = useState('');
  const [activeTab, setActiveTab] = useState('general');

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

  const handleSave = async (pwd) => {
    setSaving(true);
    setSudoPrompt(false);
    try {
      await apiClient.patch('/analytics/settings', {
        settings: config,
        sudo_password: pwd
      });
      alert("Settings saved. Server is restarting... The page will refresh shortly.");
      setTimeout(() => window.location.reload(), 5000);
    } catch (e) {
      alert("Failed to save settings: " + (e.response?.data?.detail || e.message));
      setSaving(false);
    }
  };

  const handleChange = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return <div className="animate-pulse flex items-center justify-center h-64 text-cyan-500">Loading Configuration...</div>;
  }

  return (
    <div className="flex-1 flex flex-col gap-6">
      <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 relative">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-xl font-bold text-gray-200 flex items-center gap-2">
              <Settings className="text-cyan-400" /> System Configuration
            </h3>
            <p className="text-sm text-gray-500 mt-1">Manage CAKRA AI environment variables and API integrations.</p>
          </div>
          {activeTab === 'general' && (
            <button 
              onClick={() => setSudoPrompt(true)}
              disabled={saving}
              className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-600 text-black font-bold px-4 py-2 rounded transition-colors disabled:opacity-50"
            >
              <Save size={16} /> {saving ? "Saving..." : "Save & Restart"}
            </button>
          )}
        </div>

        <div className="flex gap-2 border-b border-gray-800 mb-6">
          <button 
            onClick={() => setActiveTab('general')}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'general' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
          >
            <Settings size={16} /> General Settings
          </button>
          <button 
            onClick={() => setActiveTab('api')}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'api' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
          >
            <Key size={16} /> API Keys
          </button>
        </div>

        {activeTab === 'general' ? (
          config ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-300">
              <ConfigSection title="Model Engines" icon={<Server className="text-indigo-400" size={18}/>}>
              <ConfigDropdown 
                label="Persona Engine" 
                value={config.MODEL_PERSONA} 
                options={ollamaModels} 
                onChange={(val) => handleChange('MODEL_PERSONA', val)} 
              />
              <ConfigDropdown 
                label="Embedding Engine" 
                value={config.MODEL_EMBEDDING} 
                options={ollamaModels} 
                onChange={(val) => handleChange('MODEL_EMBEDDING', val)} 
              />
              <ConfigInput 
                label="Ollama Endpoint" 
                value={config.OLLAMA_BASE_URL} 
                onChange={(val) => handleChange('OLLAMA_BASE_URL', val)} 
              />
            </ConfigSection>

            <ConfigSection title="Data & Storage" icon={<Database className="text-red-400" size={18}/>}>
              <ConfigInput label="Database Host" value={config.DB_HOST} onChange={(val) => handleChange('DB_HOST', val)} />
              <ConfigInput label="Session Limit" value={config.MAX_SESSIONS} disabled />
            </ConfigSection>

            <ConfigSection title="Security & Environment" icon={<Shield className="text-amber-400" size={18}/>}>
              <ConfigInput label="Environment" value={config.ENVIRONMENT} onChange={(val) => handleChange('ENVIRONMENT', val)} />
              <ConfigDropdown 
                label="Debug Mode" 
                value={config.DEBUG_MODE} 
                options={["True", "False"]}
                onChange={(val) => handleChange('DEBUG_MODE', val)} 
              />
            </ConfigSection>
          </div>
        ) : (
          <div className="text-red-400">Failed to load configuration. Check backend logs.</div>
        )
      ) : (
        <div className="animate-in fade-in duration-300 -mx-6 -mt-6">
          <ApiManagement />
        </div>
      )}
      </div>

      {/* Sudo Password Modal */}
      {sudoPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-6 w-[400px] shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-200 flex items-center gap-2">
                <Lock className="text-red-500 w-5 h-5" /> Admin Authorization
              </h3>
              <button onClick={() => setSudoPrompt(false)} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">Applying these settings will restart the server. Enter OS sudo password.</p>
            <input
              type="password"
              placeholder="Sudo Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#111827] border border-gray-700 rounded-lg px-4 py-2 text-gray-200 focus:outline-none focus:border-cyan-500 mb-6"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleSave(password)}
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setSudoPrompt(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200">Cancel</button>
              <button onClick={() => handleSave(password)} className="px-4 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/50 rounded-lg text-sm font-bold transition-colors">
                Authorize & Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ConfigSection = ({ title, icon, children }) => (
  <div className="bg-[#111827] border border-gray-800/50 rounded-lg p-5">
    <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-300 mb-4 border-b border-gray-800/50 pb-2">
      {icon} {title}
    </h4>
    <div className="space-y-4">
      {children}
    </div>
  </div>
);

const ConfigInput = ({ label, value, onChange, disabled }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs text-gray-500">{label}</label>
    <input 
      type="text" 
      value={value || ''} 
      onChange={(e) => onChange && onChange(e.target.value)}
      disabled={disabled}
      className="bg-[#05070A] border border-gray-700 text-sm text-gray-200 rounded p-2 focus:border-cyan-500 focus:outline-none disabled:opacity-50"
    />
  </div>
);

const ConfigDropdown = ({ label, value, options, onChange }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs text-gray-500">{label}</label>
    <select 
      value={value || ''} 
      onChange={(e) => onChange(e.target.value)}
      className="bg-[#05070A] border border-gray-700 text-sm text-gray-200 rounded p-2 focus:border-cyan-500 focus:outline-none"
    >
      <option value={value}>{value}</option>
      {options.map((opt, i) => opt !== value && (
        <option key={i} value={opt}>{opt}</option>
      ))}
    </select>
  </div>
);
