import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../../stores/chatStore';
import { Activity, ShieldAlert, FileText, Settings, LogOut, Hexagon, Wrench, Database, ChevronLeft, ChevronRight, FileSearch, Code2, Archive, Key, Brain } from 'lucide-react';
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
import { HardwareMonitor } from './components/HardwareMonitor';
import { TokenLeaderboard } from './components/TokenLeaderboard';
import AuditLogsPage from '../admin/AuditLogsPage';
import { OCRSandbox } from '../admin/components/OCRSandbox';
import { PromptStudio } from '../admin/components/PromptStudio';
import ArtifactVault from '../admin/components/ArtifactVault';
import ApiManagement from '../admin/components/ApiManagement';
import DeepLearningTab from '../admin/components/DeepLearningTab';
import SyntheticQATab from '../admin/components/SyntheticQATab';
import { useChatAuthStore } from '../../stores/authStore';

export const DashboardLayout = () => {
  const navigate = useNavigate();
  const logout = useChatAuthStore((state) => state.logout);
  const [activeTab, setActiveTab] = useState('overview');
  const [isSidebarExpanded, setIsSidebarExpanded] = useState(true);
  const [overviewTab, setOverviewTab] = useState('main');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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
          <NavItem icon={<Activity />} label="Overview" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Database />} label="Knowledge Base" active={activeTab === 'knowledge'} onClick={() => setActiveTab('knowledge')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Brain />} label="Deep Learning Hub" active={activeTab === 'training' || activeTab === 'synthetic'} onClick={() => setActiveTab('training')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<ShieldAlert />} label="Cyber Security" active={activeTab === 'security'} onClick={() => setActiveTab('security')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Code2 />} label="Prompt Studio" active={activeTab === 'prompts'} onClick={() => setActiveTab('prompts')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Archive />} label="Artifact Vault" active={activeTab === 'artifacts'} onClick={() => setActiveTab('artifacts')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<FileSearch />} label="OCR Sandbox" active={activeTab === 'ocr'} onClick={() => setActiveTab('ocr')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Wrench />} label="Operations" active={activeTab === 'operations'} onClick={() => setActiveTab('operations')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<FileText />} label="Logs" active={activeTab === 'logs'} onClick={() => setActiveTab('logs')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Database />} label="Session Audit" active={activeTab === 'audit'} onClick={() => setActiveTab('audit')} isExpanded={isSidebarExpanded} />
          <NavItem icon={<Settings />} label="Settings" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} isExpanded={isSidebarExpanded} />
        </nav>

        <div className={`${isSidebarExpanded ? 'px-4' : 'px-3'} pb-4 space-y-2`}>
          <button 
            onClick={() => {
              useChatStore.getState().clearChat();
              window.location.href = import.meta.env.VITE_CHAT_URL || `${window.location.protocol}//${window.location.hostname}:5173/chat/new`;
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
              <h2 className="text-2xl font-bold tracking-wide text-gray-100 flex items-center gap-3">
                OPERATIONAL INTELLIGENCE
                <span className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs px-2 py-1 rounded tracking-widest uppercase">Live</span>
              </h2>
              <p className="text-sm text-gray-500 mt-1">Real-time system health and bottleneck monitoring.</p>
            </div>
          </div>
          
          <div className="flex gap-4">
            <div className="bg-[#0B0F19] border border-gray-800 rounded-lg px-4 py-2 flex flex-col">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">System Status</span>
              <span className="text-green-400 font-bold text-sm tracking-wide">OPERATIONAL</span>
            </div>
          </div>
        </header>

        {/* Tab Content */}
        {activeTab === 'overview' ? (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            {/* Sub Tabs Navigation */}
            <div className="flex gap-2 border-b border-gray-800 pb-2">
              <button 
                onClick={() => setOverviewTab('main')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'main' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Main Dashboard
              </button>
              <button 
                onClick={() => setOverviewTab('metrics')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'metrics' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Metrics & Quality
              </button>
              <button 
                onClick={() => setOverviewTab('resources')}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${overviewTab === 'resources' ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-900/20' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
              >
                Resources & Telemetry
              </button>
            </div>

            {/* Main Tab */}
            {overviewTab === 'main' && (
              <div className="flex flex-col gap-6 animate-in fade-in duration-300">
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
                <DeepLearningTab />
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
            {!['overview', 'knowledge', 'training', 'security', 'operations', 'settings', 'logs', 'audit', 'ocr', 'prompts', 'artifacts'].includes(activeTab) && (
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
const NavItem = ({ icon, label, active, onClick, isExpanded }) => {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center ${isExpanded ? 'justify-start' : 'justify-center'} gap-3 p-3 rounded-lg transition-all duration-200 ${
        active 
          ? 'bg-gradient-to-r from-cyan-900/40 to-transparent text-cyan-400 border-l-2 border-cyan-400' 
          : 'text-gray-500 hover:bg-gray-800/30 hover:text-gray-300'
      }`}
      title={!isExpanded ? label : undefined}
    >
      <div className="shrink-0">
        {React.cloneElement(icon, { size: 20 })}
      </div>
      <span className={`${isExpanded ? 'block' : 'hidden'} text-sm font-medium tracking-wide whitespace-nowrap`}>{label}</span>
    </button>
  );
};
