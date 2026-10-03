import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useChatStore } from '../../stores/chatStore';
import { Activity, ShieldAlert, FileText, Settings, LogOut, Hexagon, Wrench, Database, ChevronLeft, ChevronRight, FileSearch, Code2, Archive, Key, Brain, Users, MessageSquare, Coins, Zap, Network } from 'lucide-react';
import apiClient from '../../services/apiClient';
import { LiveTerminal } from './components/LiveTerminal';
import { RequestLatencyChart } from './components/RequestLatencyChart';
import { AgenticRadar } from './components/AgenticRadar';
import { BottleneckRadar } from './components/BottleneckRadar';
import { ContextMemoryBar } from './components/ContextMemoryBar';
import { TokenVelocityMeter } from './components/TokenVelocityMeter';
import { SystemHealthOverview } from './components/SystemHealthOverview';
import { OperationsPanel } from './components/OperationsPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { OllamaProfiler } from './components/OllamaProfiler';
import { KnowledgeMonitor } from './components/KnowledgeMonitor';
import { CyberSecurityTab } from './components/CyberSecurityTab';
import { QualityRadar } from './components/QualityRadar';
import { PipelineVisualizer } from './components/PipelineVisualizer';
import { PipelineFlowCanvas } from './components/PipelineFlowCanvas';
import { HardwareMonitor } from './components/HardwareMonitor';
import { TokenLeaderboard } from './components/TokenLeaderboard';
import { TokenMonitorTab } from './components/TokenMonitorTab';
import AuditLogsPage from '../admin/AuditLogsPage';
import { OCRSandbox } from '../admin/components/OCRSandbox';
import { PromptStudio } from '../admin/components/PromptStudio';
import ArtifactVault from '../admin/components/ArtifactVault';
import ApiManagement from '../admin/components/ApiManagement';
import DeepLearningTab from '../admin/components/DeepLearningTab';
import SyntheticQATab from '../admin/components/SyntheticQATab';
import UserManagementTab from '../admin/components/UserManagementTab';
import { ChatExplorer } from './components/ChatExplorer';
import { useChatAuthStore } from '../../stores/authStore';

export const DashboardLayout = () => {
  const navigate = useNavigate();
  const logout = useChatAuthStore((state) => state.logout);
  const [searchParams, setSearchParams] = useSearchParams();

  // URL Query Parameters Sync (Deep Linking)
  const activeTab = searchParams.get('tab') || 'overview';
  const subTabParam = searchParams.get('subtab');

  const [isSidebarExpanded, setIsSidebarExpanded] = useState(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [loraTelemetry, setLoraTelemetry] = useState(null);

  // Derived subtabs based on URL parameters
  const overviewTab = activeTab === 'overview' ? (subTabParam || 'main') : 'main';
  const deepLearningSubTab = (activeTab === 'training' || activeTab === 'synthetic') ? (subTabParam || 'pipelines') : 'pipelines';

  const handleTabChange = (newTab, newSubTab = null) => {
    const params = new URLSearchParams();
    params.set('tab', newTab);
    if (newSubTab) {
      params.set('subtab', newSubTab);
    } else if (newTab === 'training') {
      params.set('subtab', searchParams.get('subtab') || 'pipelines');
    } else if (newTab === 'overview') {
      params.set('subtab', searchParams.get('subtab') || 'main');
    }
    setSearchParams(params);
  };

  const handleSubTabChange = (newSubTab) => {
    const params = new URLSearchParams(searchParams);
    params.set('tab', activeTab);
    params.set('subtab', newSubTab);
    setSearchParams(params);
  };

  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await apiClient.get('/training/lora/telemetry', { timeout: 4000 });
        if (res.data?.data) {
          setLoraTelemetry(res.data.data);
        }
      } catch (e) {
        // silent fail
      }
    };
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3500);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen w-full bg-[#05070A] text-gray-200 overflow-hidden font-sans">
      
      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden" 
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar - Sleek & Premium */}
      <aside className={`absolute md:relative z-50 h-full transform ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'} ${isSidebarExpanded ? 'w-64' : 'w-20'} border-r border-gray-800 bg-[#0B0F19] flex flex-col ${isSidebarExpanded ? 'items-stretch' : 'items-center'} py-6 transition-all duration-300 shrink-0`}>
        
        {/* Toggle Button */}
        <button 
          onClick={() => setIsSidebarExpanded(!isSidebarExpanded)}
          className="hidden md:flex absolute -right-3 top-8 bg-gray-900 text-gray-400 hover:text-cyan-400 p-1 rounded-full border border-gray-700 z-50 transition-colors"
        >
          {isSidebarExpanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>

        <div className={`flex items-center ${isSidebarExpanded ? 'justify-start px-6' : 'justify-center'} mb-10 gap-3`}>
          <img src="/src/assets/cakra.png" alt="Cakra" className="w-8 h-8 object-contain drop-shadow-[0_0_8px_rgba(34,211,238,0.8)] shrink-0" />
          <div className={`${isSidebarExpanded ? 'block' : 'hidden'}`}>
            <h1 className="font-bold text-lg tracking-widest text-cyan-50">CAKRA</h1>
            <p className="text-[10px] text-cyan-400 tracking-widest uppercase">Intelligence</p>
          </div>
        </div>

        <nav className={`flex-1 w-full ${isSidebarExpanded ? 'px-4' : 'px-3'} space-y-2 overflow-y-auto custom-scrollbar`}>
          <NavItem icon={<Activity />} label="Overview" active={activeTab === 'overview'} onClick={() => handleTabChange('overview', 'main')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Database />} label="Knowledge Base" active={activeTab === 'knowledge'} onClick={() => handleTabChange('knowledge')} isExpanded={isSidebarExpanded} />
          <NavItem 
            icon={<Brain />} 
            label="Deep Learning Hub" 
            active={activeTab === 'training' || activeTab === 'synthetic'} 
            onClick={() => handleTabChange('training', 'pipelines')} 
            isExpanded={isSidebarExpanded} 
            badge={loraTelemetry?.is_running ? `${loraTelemetry.percentage?.toFixed(0)}%` : null}
          />
          <NavItem icon={<Network />} label="Pipeline Flow" active={activeTab === 'pipeline_flow'} onClick={() => handleTabChange('pipeline_flow')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<ShieldAlert />} label="Cyber Security" active={activeTab === 'security'} onClick={() => handleTabChange('security')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Code2 />} label="Prompt Studio" active={activeTab === 'prompts'} onClick={() => handleTabChange('prompts')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Archive />} label="Artifact Vault" active={activeTab === 'artifacts'} onClick={() => handleTabChange('artifacts')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<FileSearch />} label="OCR Sandbox" active={activeTab === 'ocr'} onClick={() => handleTabChange('ocr')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Wrench />} label="Operations" active={activeTab === 'operations'} onClick={() => handleTabChange('operations')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Users />} label="User Management" active={activeTab === 'users'} onClick={() => handleTabChange('users')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<FileText />} label="Logs" active={activeTab === 'logs'} onClick={() => handleTabChange('logs')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Database />} label="Session Audit" active={activeTab === 'audit'} onClick={() => handleTabChange('audit')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<MessageSquare />} label="Chat Explorer" active={activeTab === 'chat_explorer'} onClick={() => handleTabChange('chat_explorer')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Settings />} label="Settings" active={activeTab === 'settings'} onClick={() => handleTabChange('settings')} isExpanded={isSidebarExpanded} />
        </nav>

        <div className={`${isSidebarExpanded ? 'px-4' : 'px-3'} pb-4 space-y-2`}>
          <button 
            onClick={() => {
              useChatStore.getState().clearChat();
              window.location.href = import.meta.env.VITE_CHAT_URL || '/chat/new';
            }}
            className={`w-full flex items-center ${isSidebarExpanded ? 'justify-start' : 'justify-center'} gap-3 p-3 rounded-lg text-gray-500 hover:bg-gray-800/50 hover:text-gray-300 transition-colors`}
          >
            <Hexagon size={20} className="shrink-0" />
            <span className={`${isSidebarExpanded ? 'block' : 'hidden'} text-sm font-medium whitespace-nowrap`}>Back to Chat</span>
          </button>
          
          <button 
            onClick={handleLogout}
            className={`w-full flex items-center ${isSidebarExpanded ? 'justify-start' : 'justify-center'} gap-3 p-3 rounded-lg text-red-500/70 hover:bg-red-500/10 hover:text-red-400 transition-colors`}
          >
            <LogOut size={20} className="shrink-0" />
            <span className={`${isSidebarExpanded ? 'block' : 'hidden'} text-sm font-medium whitespace-nowrap`}>Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 p-6 lg:p-8 overflow-y-auto">
        {/* Topbar */}
        <header className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-3">
            <button 
              className="md:hidden p-2 bg-gray-800 rounded text-gray-300 hover:text-cyan-400 transition-colors" 
              onClick={() => setIsMobileMenuOpen(true)}
            >
               <ChevronRight size={20} />
            </button>
            <div>
              <h2 className="text-2xl font-bold tracking-wide text-gray-100">
                OPERATIONAL INTELLIGENCE
              </h2>
              <p className="text-sm text-gray-500 mt-1">Real-time system health and bottleneck monitoring.</p>
            </div>
          </div>
        </header>

        {/* Tab Content */}
        {activeTab === 'overview' ? (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            {/* Sub Tabs Navigation */}
            <div className="flex gap-2 border-b border-gray-800 pb-2">
              <button 
                onClick={() => handleTabChange('overview', 'main')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'main' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Main Dashboard
              </button>
              <button 
                onClick={() => handleTabChange('overview', 'tokens')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-1.5 ${overviewTab === 'tokens' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                <Coins size={14} /> Token Monitor
              </button>
              <button 
                onClick={() => handleTabChange('overview', 'metrics')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'metrics' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Metrics & Quality
              </button>
              <button 
                onClick={() => handleTabChange('overview', 'resources')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'resources' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Resources & Telemetry
              </button>
            </div>

            {/* Main Tab */}
            {overviewTab === 'main' && (
              <div className="flex flex-col gap-6 animate-in fade-in duration-300">
                {/* Live Training Banner if active */}
                {loraTelemetry?.is_running && (
                  <div 
                    onClick={() => handleTabChange('training', 'lora')}
                    className="group bg-gradient-to-r from-amber-950/60 via-purple-950/40 to-slate-900 border border-amber-500/50 hover:border-amber-400 rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer transition-all shadow-lg hover:shadow-amber-500/20"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-amber-500/20 border border-amber-500/40 rounded-xl text-amber-400 animate-pulse shrink-0">
                        <Zap size={24} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
                            ⚡ LIVE QLoRA TRAINING
                          </span>
                          <span className="text-white font-semibold text-sm">Gemma 4 31B (Router LoRA Adapter)</span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 font-mono">
                            Batch {loraTelemetry.batch_size}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Step <span className="text-amber-400 font-bold font-mono">{loraTelemetry.current_step}</span> / {loraTelemetry.total_steps} ({loraTelemetry.percentage?.toFixed(1)}%) • Kecepatan: <span className="text-cyan-400 font-mono">{loraTelemetry.speed}</span> • Sisa: <span className="text-emerald-400 font-mono">{loraTelemetry.eta}</span> • VRAM: <span className="text-pink-400 font-mono">{loraTelemetry.gpu_memory}</span>
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="w-28 md:w-36 bg-slate-800 rounded-full h-2.5 overflow-hidden border border-slate-700">
                        <div 
                          className="bg-gradient-to-r from-amber-500 to-emerald-400 h-2.5 rounded-full transition-all duration-500" 
                          style={{ width: `${Math.min(100, Math.max(0, loraTelemetry.percentage || 0))}%` }}
                        />
                      </div>
                      <button className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs rounded-xl transition-all shadow group-hover:scale-105">
                        Buka Live Monitor 🚀
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex-none">
                  <SystemHealthOverview />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-none">
                  <div className="lg:col-span-2 min-h-[350px]">
                    <RequestLatencyChart />
                  </div>
                  <div className="lg:col-span-1 min-h-[350px]">
                    <AgenticRadar />
                  </div>
                  <div className="lg:col-span-1 min-h-[350px]">
                    <BottleneckRadar />
                  </div>
                </div>
              </div>
            )}

            {/* Token Monitor Tab */}
            {overviewTab === 'tokens' && (
              <TokenMonitorTab />
            )}

            {/* Metrics Tab */}
            {overviewTab === 'metrics' && (
              <div className="flex flex-col gap-6 animate-in fade-in duration-300">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-none min-h-[320px]">
                  <OllamaProfiler />
                  <TokenVelocityMeter />
                  <QualityRadar />
                </div>
                <div className="flex-none h-[220px]">
                  <PipelineVisualizer />
                </div>
              </div>
            )}

            {/* Resources Tab */}
            {overviewTab === 'resources' && (
              <div className="flex flex-col gap-6 animate-in fade-in duration-300">
                <div className="flex-none h-[180px]">
                  <ContextMemoryBar />
                </div>
                <div className="flex-none">
                  <HardwareMonitor />
                </div>
                <div className="flex-none mb-10 min-h-[360px]">
                  <TokenLeaderboard />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex flex-col gap-6">
            {activeTab === 'operations' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <OperationsPanel />
              </div>
            )}
            {activeTab === 'settings' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <SettingsPanel />
              </div>
            )}
            {activeTab === 'logs' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <LiveTerminal />
              </div>
            )}
            {activeTab === 'knowledge' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <KnowledgeMonitor />
              </div>
            )}
            {(activeTab === 'training' || activeTab === 'synthetic') && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <DeepLearningTab 
                  initialSubTab={deepLearningSubTab} 
                  onSubTabChange={handleSubTabChange} 
                />
              </div>
            )}
            {activeTab === 'pipeline_flow' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <PipelineFlowCanvas />
              </div>
            )}
            {activeTab === 'security' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <CyberSecurityTab />
              </div>
            )}
            {activeTab === 'audit' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <AuditLogsPage />
              </div>
            )}
            {activeTab === 'ocr' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <OCRSandbox />
              </div>
            )}
            {activeTab === 'prompts' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <PromptStudio />
              </div>
            )}
            {activeTab === 'artifacts' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <ArtifactVault />
              </div>
            )}
            {activeTab === 'users' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <UserManagementTab />
              </div>
            )}
            {activeTab === 'chat_explorer' && (
              <div className="flex-1 flex flex-col min-h-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <ChatExplorer />
              </div>
            )}
            {!['overview', 'knowledge', 'training', 'pipeline_flow', 'security', 'operations', 'settings', 'logs', 'audit', 'ocr', 'prompts', 'artifacts', 'users', 'chat_explorer'].includes(activeTab) && (
              <div className="flex-1 flex items-center justify-center rounded-xl border border-dashed border-gray-800 bg-[#0B0F19]/50 min-h-[500px]">
                <div className="text-center flex flex-col items-center">
                  <Wrench className="w-12 h-12 text-gray-700 mb-4 animate-[spin_6s_linear_infinite]" />
                  <h3 className="text-lg font-bold text-gray-500 tracking-widest uppercase">Module In Development</h3>
                  <p className="text-gray-600 mt-2 text-sm max-w-sm">
                    Fitur <span className="text-cyan-600 font-semibold">{activeTab}</span> sedang dalam tahap perakitan oleh tim engineering CAKRA.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

// Sidebar Nav Item Helper
const NavItem = ({ icon, label, active, onClick, isExpanded, badge }) => {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center ${isExpanded ? 'justify-between' : 'justify-center'} p-3 rounded-lg transition-all duration-200 ${
        active 
          ? 'bg-gradient-to-r from-cyan-900/40 to-transparent text-cyan-400 border-l-2 border-cyan-400' 
          : 'text-gray-500 hover:bg-gray-800/30 hover:text-gray-300'
      }`}
      title={!isExpanded ? label : undefined}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="shrink-0">
          {React.cloneElement(icon, { size: 20 })}
        </div>
        <span className={`${isExpanded ? 'block' : 'hidden'} text-sm font-medium tracking-wide whitespace-nowrap truncate`}>{label}</span>
      </div>
      {isExpanded && badge && (
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono animate-pulse shrink-0">
          {badge}
        </span>
      )}
    </button>
  );
};
