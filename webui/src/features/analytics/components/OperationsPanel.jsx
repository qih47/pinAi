import React, { useState } from 'react';
import { Power, Trash2, RotateCcw, Cpu, CheckCircle, Lock, X } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const OperationsPanel = () => {
  const [loadingAction, setLoadingAction] = useState(null);
  const [lastAction, setLastAction] = useState(null);
  const [sudoPrompt, setSudoPrompt] = useState({ open: false, actionId: null });
  const [password, setPassword] = useState('');

  const confirmAction = (actionId) => {
    if (actionId === 'restart_services') {
      setSudoPrompt({ open: true, actionId });
    } else {
      handleAction(actionId);
    }
  };

  const handleAction = async (actionId, pwd = "") => {
    setLoadingAction(actionId);
    setSudoPrompt({ open: false, actionId: null });
    setPassword('');
    try {
      const res = await apiClient.post(`/analytics/operations/${actionId}`, { sudo_password: pwd });
      setLastAction({ status: 'success', message: res.data.message });
    } catch (e) {
      setLastAction({ status: 'error', message: e.response?.data?.detail || "Operation failed" });
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6">
      <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6">
        <h3 className="text-xl font-bold text-gray-200 mb-2">System Operations</h3>
        <p className="text-sm text-gray-500 mb-6">Execute critical administrative commands. Proceed with caution.</p>
        
        {lastAction && (
          <div className={`p-4 rounded-lg mb-6 border ${lastAction.status === 'success' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
            <span className="flex items-center gap-2">
              <CheckCircle size={16} /> {lastAction.message}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <OperationButton 
            id="reload_llm"
            icon={<Cpu />}
            label="Reload LLM Models"
            description="Clear VRAM and re-mount Gemma4"
            color="amber"
            isLoading={loadingAction === 'reload_llm'}
            onClick={() => handleAction('reload_llm')}
          />
          <OperationButton 
            id="clear_vector_cache"
            icon={<Trash2 />}
            label="Clear Vector Cache"
            description="Purge embedding search cache"
            color="cyan"
            isLoading={loadingAction === 'clear_vector_cache'}
            onClick={() => handleAction('clear_vector_cache')}
          />
          <OperationButton 
            id="clear_sessions"
            icon={<RotateCcw />}
            label="Clear Stale Sessions"
            description="Remove inactive chat sessions"
            color="indigo"
            isLoading={loadingAction === 'clear_sessions'}
            onClick={() => handleAction('clear_sessions')}
          />
          <OperationButton 
            id="restart_services"
            icon={<Power />}
            label="Restart Services"
            description="Perform a rolling restart"
            color="red"
            isLoading={loadingAction === 'restart_services'}
            onClick={() => confirmAction('restart_services')}
          />
        </div>
      </div>
      
      {/* Sudo Password Modal */}
      {sudoPrompt.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-6 w-[400px] shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-200 flex items-center gap-2">
                <Lock className="text-red-500 w-5 h-5" /> Admin Authorization
              </h3>
              <button onClick={() => setSudoPrompt({ open: false, actionId: null })} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">This operation requires OS sudo privileges. Enter your system password.</p>
            <input
              type="password"
              placeholder="Sudo Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#111827] border border-gray-700 rounded-lg px-4 py-2 text-gray-200 focus:outline-none focus:border-cyan-500 mb-6"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleAction(sudoPrompt.actionId, password)}
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setSudoPrompt({ open: false, actionId: null })} className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200">Cancel</button>
              <button onClick={() => handleAction(sudoPrompt.actionId, password)} className="px-4 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/50 rounded-lg text-sm font-bold transition-colors">
                Authorize
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const OperationButton = ({ icon, label, description, color, isLoading, onClick }) => {
  const colorClasses = {
    amber: "hover:border-amber-500/50 hover:bg-amber-500/10 text-amber-500",
    cyan: "hover:border-cyan-500/50 hover:bg-cyan-500/10 text-cyan-400",
    red: "hover:border-red-500/50 hover:bg-red-500/10 text-red-500",
    indigo: "hover:border-indigo-500/50 hover:bg-indigo-500/10 text-indigo-400",
  };

  return (
    <button 
      onClick={onClick}
      disabled={isLoading}
      className={`relative flex flex-col items-center text-center p-6 rounded-xl border border-gray-800 bg-[#111827] transition-all group ${colorClasses[color]} ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <div className={`mb-3 p-3 rounded-full bg-gray-800/50 group-hover:scale-110 transition-transform ${isLoading ? 'animate-pulse' : ''}`}>
        {icon}
      </div>
      <span className="font-bold text-gray-200 group-hover:text-white transition-colors">{label}</span>
      <span className="text-xs text-gray-500 mt-2">{description}</span>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#111827]/80 rounded-xl backdrop-blur-sm">
          <span className="text-sm font-bold tracking-widest animate-pulse">EXECUTING...</span>
        </div>
      )}
    </button>
  );
};
