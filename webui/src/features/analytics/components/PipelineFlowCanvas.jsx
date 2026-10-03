import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Server,
  Shield,
  ShieldAlert,
  BrainCircuit,
  Zap,
  Database,
  Network,
  Code2,
  Terminal,
  Layers,
  Sparkles,
  CheckCircle2,
  Radio,
  Play,
  RotateCcw,
  Cpu,
  User,
  Activity,
  X,
  Search,
  ListTodo,
  FileCode,
  Boxes,
  Compass,
  HelpCircle,
  BookOpen,
  Mail,
  Paperclip,
  FilePlus,
  Users,
  CheckCheck
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

// ── Custom Compact Authentic n8n-Style Node Component ────────────────────────
const N8NCompactNode = ({ id, data, selected }) => {
  const {
    label,
    subtitle,
    category,
    icon: IconComponent,
    color = 'border-gray-700',
    bgColor = 'bg-gray-800/40',
    status = 'idle',
    badgeText,
    latency,
    params = [],
    hasInput = true,
    hasOutput = true,
    hasTopInput = false,
    hasTopOutput = false,
    hasBottomInput = false,
    hasBottomOutput = false
  } = data;

  // Status-driven styling
  const getStatusBorder = () => {
    if (status === 'active') {
      return 'border-2 border-cyan-400 bg-gradient-to-br from-[#132c45] via-[#0f2032] to-[#0a1522] ring-4 ring-cyan-400/50 shadow-[0_0_35px_rgba(6,182,212,0.7)] scale-[1.04] z-30';
    }
    if (status === 'blocked') {
      return 'border-2 border-red-500 bg-gradient-to-br from-[#3b1219] to-[#1c0d12] ring-4 ring-red-500/50 shadow-[0_0_35px_rgba(239,68,68,0.75)] animate-pulse z-30';
    }
    if (status === 'completed') {
      return 'border-2 border-emerald-400 bg-gradient-to-br from-[#0e3023] via-[#0a2218] to-[#081519] ring-2 ring-emerald-400/40 shadow-[0_0_30px_rgba(16,185,129,0.55)] scale-[1.02] z-20';
    }
    return selected 
      ? 'border-2 border-indigo-400 ring-2 ring-indigo-400/30 shadow-lg bg-[#141720]/95' 
      : 'border border-[#283245] bg-[#10141d]/90 hover:border-gray-400 hover:shadow-lg transition-all';
  };

  const getStatusBadge = () => {
    if (status === 'active') {
      return (
        <span className="flex items-center gap-1 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full bg-cyan-950/90 border border-cyan-400 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.6)] animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          ACTIVE {latency ? `(${latency})` : ''}
        </span>
      );
    }
    if (status === 'blocked') {
      return (
        <span className="flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 rounded-full bg-red-950/90 border border-red-500 text-red-300 font-bold shadow-[0_0_12px_rgba(239,68,68,0.6)]">
          🚨 403 BLOCKED
        </span>
      );
    }
    if (status === 'completed') {
      return (
        <span className="flex items-center gap-1 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-950/90 border border-emerald-400 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.4)]">
          ✓ {latency ? latency : 'OK'}
        </span>
      );
    }
    return badgeText ? (
      <span className="text-[8.5px] font-mono px-1.5 py-0.5 rounded-full bg-gray-800/90 border border-gray-700/80 text-gray-400 truncate max-w-[110px]">
        {badgeText}
      </span>
    ) : null;
  };

  return (
    <div
      className={`group relative flex flex-col bg-[#141720]/95 ${getStatusBorder()} rounded-xl px-3.5 py-3 shadow-xl w-[270px] min-h-[102px] transition-all duration-300 select-none backdrop-blur-md`}
    >
      {/* Left Input Handle */}
      {hasInput && (
        <Handle
          type="target"
          position={Position.Left}
          id="left"
          className="!w-3 !h-3 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}

      {/* Top Input Handle */}
      {hasTopInput && (
        <Handle
          type="target"
          position={Position.Top}
          id="top"
          className="!w-2.5 !h-2.5 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}

      {/* Top Output Handle */}
      {hasTopOutput && (
        <Handle
          type="source"
          position={Position.Top}
          id="top"
          className="!w-2.5 !h-2.5 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}

      {/* Top Meta Line: Category + Status Badge */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-gray-400 font-semibold truncate">
          {category}
        </span>
        {getStatusBadge()}
      </div>

      {/* Main Info Row: Icon + Title & Subtitle */}
      <div className="flex items-center gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 shadow-inner ${bgColor} border ${color}`}
        >
          {IconComponent && <IconComponent size={18} className={color.replace('border-', 'text-')} />}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-white tracking-wide truncate group-hover:text-cyan-300 transition-colors">
            {label}
          </h4>
          <p className="text-[10.5px] text-gray-400 truncate mt-0.5">
            {subtitle}
          </p>
        </div>
      </div>

      {/* Compact Pill Tags & Parameters Row */}
      {params && params.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap mt-2.5 pt-2 border-t border-gray-800/80">
          {params.map((p, idx) => (
            <span
              key={idx}
              className={`text-[9.5px] font-mono px-2 py-0.5 rounded-md ${
                p.theme === 'cyan'
                  ? 'bg-cyan-950/60 border border-cyan-800/40 text-cyan-300'
                  : p.theme === 'emerald'
                  ? 'bg-emerald-950/60 border border-emerald-800/40 text-emerald-300'
                  : p.theme === 'amber'
                  ? 'bg-amber-950/60 border border-amber-800/40 text-amber-300'
                  : p.theme === 'purple'
                  ? 'bg-purple-950/60 border border-purple-800/40 text-purple-300'
                  : p.theme === 'rose'
                  ? 'bg-rose-950/60 border border-rose-800/40 text-rose-300'
                  : 'bg-gray-800/80 border border-gray-700/60 text-gray-300'
              }`}
            >
              {p.label}
            </span>
          ))}
        </div>
      )}

      {/* Bottom Input Handle */}
      {hasBottomInput && (
        <Handle
          type="target"
          position={Position.Bottom}
          id="bottom"
          className="!w-2.5 !h-2.5 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}

      {/* Bottom Output Handle */}
      {hasBottomOutput && (
        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="!w-2.5 !h-2.5 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}

      {/* Right Output Handle */}
      {hasOutput && (
        <Handle
          type="source"
          position={Position.Right}
          id="right"
          className="!w-3 !h-3 !bg-[#242b3b] !border-2 !border-gray-400 hover:!border-cyan-400 transition-colors"
        />
      )}
    </div>
  );
};

// Map node types
const nodeTypes = {
  n8nCompact: N8NCompactNode
};

// ── Authentic CAKRA AI Backend Topology ──────────────────────────────────────
const initialNodes = [
  // ── CLUSTER 1: INGRESS & SECURITY (x: 50 - 1070) ──
  // 1. User Ingress
  {
    id: 'user',
    type: 'n8nCompact',
    position: { x: 50, y: 340 },
    data: {
      category: 'Trigger',
      label: 'User Chat Ingress',
      subtitle: 'Client Prompt & EventSource',
      icon: User,
      bgColor: 'bg-emerald-500/20',
      color: 'border-emerald-500/50',
      hasInput: false,
      hasOutput: true,
      badgeText: 'INGRESS',
      params: [
        { label: 'Event: SSE', theme: 'emerald' },
        { label: 'client: webui', theme: 'default' }
      ]
    }
  },

  // 2. Gateway
  {
    id: 'gateway',
    type: 'n8nCompact',
    position: { x: 390, y: 340 },
    data: {
      category: 'Ingress Proxy',
      label: 'API Gateway (:8000)',
      subtitle: 'Reverse Proxy & Rate Limit',
      icon: Server,
      bgColor: 'bg-blue-500/20',
      color: 'border-blue-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'PORT 8000',
      params: [
        { label: 'limit: 60/m', theme: 'cyan' },
        { label: 'cors: allow', theme: 'default' }
      ]
    }
  },

  // 3. Security Firewall L1-6
  {
    id: 'firewall',
    type: 'n8nCompact',
    position: { x: 730, y: 340 },
    data: {
      category: 'Security Filter',
      label: 'Firewall L1–L6',
      subtitle: 'SQLi, XSS, Jailbreak & Anomaly',
      icon: Shield,
      bgColor: 'bg-teal-500/20',
      color: 'border-teal-500/50',
      hasInput: true,
      hasOutput: true,
      hasBottomOutput: true,
      badgeText: 'DEFENSE L1-6',
      params: [
        { label: 'sqli: strict', theme: 'emerald' },
        { label: 'jailbreak: drop', theme: 'rose' }
      ]
    }
  },

  // 3-Drop: Security Drop (Strictly Below Firewall)
  {
    id: 'drop',
    type: 'n8nCompact',
    position: { x: 730, y: 560 },
    data: {
      category: 'Security Drop',
      label: 'Security Drop 403',
      subtitle: 'Blacklist IP & Alert Terminate',
      icon: ShieldAlert,
      bgColor: 'bg-red-500/25',
      color: 'border-red-500/70',
      hasInput: false,
      hasTopInput: true,
      hasOutput: false,
      hasBottomOutput: false,
      badgeText: 'HTTP 403',
      params: [
        { label: 'audit: logged', theme: 'rose' },
        { label: 'action: block', theme: 'rose' },
        { label: 'sink: dead_end', theme: 'rose' }
      ]
    }
  },

  // 4. Session Brain & Context Memory
  {
    id: 'memory',
    type: 'n8nCompact',
    position: { x: 1070, y: 340 },
    data: {
      category: 'Context Memory',
      label: 'Session Brain',
      subtitle: 'Multi-turn & Directive Ingestion',
      icon: Layers,
      bgColor: 'bg-indigo-500/20',
      color: 'border-indigo-500/50',
      hasInput: true,
      hasBottomInput: true,
      hasOutput: true,
      badgeText: '16K WINDOW',
      params: [
        { label: 'ctx: 16k', theme: 'purple' },
        { label: 'history: hydrated', theme: 'cyan' }
      ]
    }
  },

  // 4-DB: PostgreSQL (ragdb & HRIS)
  {
    id: 'postgres_db',
    type: 'n8nCompact',
    position: { x: 1070, y: 560 },
    data: {
      category: 'Relational DB Pool',
      label: 'PostgreSQL & HRIS DB',
      subtitle: 'Chat Sessions, HRIS & Preferences',
      icon: Database,
      bgColor: 'bg-blue-500/15',
      color: 'border-blue-500/40',
      hasInput: false,
      hasTopOutput: true,
      hasOutput: false,
      badgeText: 'ASYNC-PG',
      params: [
        { label: 'pool: 20 conn', theme: 'cyan' },
        { label: 'npp: active', theme: 'emerald' },
        { label: 'cache: semantic', theme: 'default' }
      ]
    }
  },

  // ── CLUSTER 2: CALL 1 DUAL DISPATCHER LAYER (x: 1450) ──
  // 5A. Call 1 Intent Router (General Prompt Flow)
  {
    id: 'router',
    type: 'n8nCompact',
    position: { x: 1450, y: 240 },
    data: {
      category: 'Intent Classifier',
      label: 'Call 1: Intent Router',
      subtitle: 'Gemma 4 31B LoRA Decision',
      icon: Cpu,
      bgColor: 'bg-amber-500/20',
      color: 'border-amber-500/60',
      hasInput: true,
      hasOutput: true,
      badgeText: 'CALL 1 LORA',
      params: [
        { label: 'model: Gemma 4', theme: 'amber' },
        { label: 'predict: 150 tok', theme: 'purple' },
        { label: 'temp: 0.1', theme: 'default' }
      ]
    }
  },

  // 5B. Call 1 Preset Dispatcher (Fast-Path Hint / Pill Tag Bypass)
  {
    id: 'preset_dispatcher',
    type: 'n8nCompact',
    position: { x: 1450, y: 460 },
    data: {
      category: 'Fast-Path Bypass',
      label: 'Call 1: Preset Dispatcher',
      subtitle: 'Pill Tag & Hint Bypass (&lt;50ms)',
      icon: Zap,
      bgColor: 'bg-orange-500/20',
      color: 'border-orange-500/60',
      hasInput: true,
      hasOutput: true,
      badgeText: 'FAST PRESET',
      params: [
        { label: 'mode_bypass: true', theme: 'amber' },
        { label: 'multi-turn reasoning', theme: 'cyan' },
        { label: 'title_gen: &lt;40ms', theme: 'emerald' }
      ]
    }
  },

  // ── CLUSTER 3: HIGHWAY MODES / DISPATCH BRANCHES (x: 1830) ──
  // Mode 1: Flash Direct Mode (Zero-RAG / Direct Chitchat & QnA)
  {
    id: 'flash',
    type: 'n8nCompact',
    position: { x: 1830, y: 60 },
    data: {
      category: 'Lane A · Flash',
      label: 'Flash Direct Mode',
      subtitle: 'Zero-RAG Chitchat & Direct QnA',
      icon: Zap,
      bgColor: 'bg-yellow-500/20',
      color: 'border-yellow-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: '&lt;180ms TTFT',
      params: [
        { label: 'zero-rag: true', theme: 'amber' },
        { label: 'direct_to_call2: on', theme: 'default' }
      ]
    }
  },

  // Mode 2: Hybrid RAG Knowledge Engine
  {
    id: 'rag',
    type: 'n8nCompact',
    position: { x: 1830, y: 240 },
    data: {
      category: 'Lane B · RAG',
      label: 'Hybrid RAG Engine',
      subtitle: 'Query Dispatch to Peraturan & pgvector',
      icon: Compass,
      bgColor: 'bg-cyan-500/20',
      color: 'border-cyan-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'HYBRID SEARCH',
      params: [
        { label: 'queries: multi-tag', theme: 'cyan' },
        { label: 'top_k: 8', theme: 'cyan' },
        { label: 'need_rag: true', theme: 'default' }
      ]
    }
  },

  // Mode 3: Red-Team & Compliance Audit (Deep Legal & Risk Analysis)
  {
    id: 'redteam_compliance',
    type: 'n8nCompact',
    position: { x: 1830, y: 420 },
    data: {
      category: 'Lane E · Deep Audit',
      label: 'Red-Team & Compliance',
      subtitle: 'Bedah Celah, SOP Pindad & ISO-9001',
      icon: ShieldAlert,
      bgColor: 'bg-rose-500/20',
      color: 'border-rose-500/60',
      hasInput: true,
      hasOutput: true,
      badgeText: 'RED-TEAM AUDIT',
      params: [
        { label: 'klausul risk: high', theme: 'rose' },
        { label: 'sop_conformance', theme: 'amber' },
        { label: 'context_isolation', theme: 'purple' }
      ]
    }
  },

  // Mode 4: Attachment & PDF Interrogator Mode
  {
    id: 'attachment',
    type: 'n8nCompact',
    position: { x: 1830, y: 600 },
    data: {
      category: 'Lane D · Attachment',
      label: 'PDF Interrogator',
      subtitle: 'OCR, Audit, Deep-Diff & Multi-Doc',
      icon: Paperclip,
      bgColor: 'bg-orange-500/20',
      color: 'border-orange-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'DOCLING OCR',
      params: [
        { label: 'ocr: tesseract', theme: 'amber' },
        { label: 'diff: deep', theme: 'rose' },
        { label: 'batch: 10 hal', theme: 'default' }
      ]
    }
  },

  // Mode 5: Agentic Multi-Tool & Code Sandbox
  {
    id: 'tools',
    type: 'n8nCompact',
    position: { x: 1830, y: 780 },
    data: {
      category: 'Lane C · Tools',
      label: 'Multi-Tool Dispatcher',
      subtitle: 'Python, SearXNG Web, Deck & Files',
      icon: Boxes,
      bgColor: 'bg-purple-500/20',
      color: 'border-purple-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'AGENTIC BUS',
      params: [
        { label: 'parallel: true', theme: 'purple' },
        { label: 'widget_bus: active', theme: 'default' }
      ]
    }
  },

  // Mode 6: Corporate Editor & Collab Space
  {
    id: 'collab_editor',
    type: 'n8nCompact',
    position: { x: 1830, y: 960 },
    data: {
      category: 'Lane F · Collab & Mail',
      label: 'Collab Space & Smart Mail',
      subtitle: 'Nota Dinas, Email Triage & Teammates',
      icon: Users,
      bgColor: 'bg-pink-500/20',
      color: 'border-pink-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'COLLAB & MAIL',
      params: [
        { label: 'template: dinas', theme: 'rose' },
        { label: 'zimbra_triage', theme: 'default' },
        { label: 'ai_teammates', theme: 'cyan' }
      ]
    }
  },

  // Special Gate: Ambiguity Wizard
  {
    id: 'wizard',
    type: 'n8nCompact',
    position: { x: 1830, y: 1140 },
    data: {
      category: 'Interactive Clarifier',
      label: 'Ambiguity Wizard',
      subtitle: 'Interactive Option & Clarification Gate',
      icon: HelpCircle,
      bgColor: 'bg-amber-500/25',
      color: 'border-amber-500/70',
      hasInput: true,
      hasOutput: true,
      badgeText: 'DECISION WIZARD',
      params: [
        { label: 'is_ambiguous: true', theme: 'amber' },
        { label: 'wizard_options', theme: 'purple' },
        { label: 'guided_clarify', theme: 'rose' }
      ]
    }
  },

  // ── CLUSTER 4: KNOWLEDGE RETRIEVAL & TOOL ENGINES (x: 2210) ──
  // Subnode B1: MySQL Peraturan Pindad DB (Corporate Laws & SOPs)
  {
    id: 'mysql_peraturan',
    type: 'n8nCompact',
    position: { x: 2210, y: 200 },
    data: {
      category: 'Corporate Law DB',
      label: 'MySQL Peraturan DB',
      subtitle: 'SOP Pindad, Peraturan & ISO-9001',
      icon: BookOpen,
      bgColor: 'bg-sky-500/15',
      color: 'border-sky-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'SOP PINDAD',
      params: [
        { label: 'tbl: peraturan', theme: 'cyan' },
        { label: 'status: berlaku', theme: 'default' }
      ]
    }
  },

  // Subnode B2: PostgreSQL pgvector
  {
    id: 'pgvector_db',
    type: 'n8nCompact',
    position: { x: 2210, y: 360 },
    data: {
      category: 'Vector Store',
      label: 'PostgreSQL pgvector',
      subtitle: 'mxbai-embed-large (1024d) <=> Cosine',
      icon: Database,
      bgColor: 'bg-emerald-500/15',
      color: 'border-emerald-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'PGVECTOR 1024',
      params: [
        { label: 'tbl: doc_chunks', theme: 'emerald' },
        { label: 'metric: cosine', theme: 'default' }
      ]
    }
  },

  // Subnode B3: Docling & PyMuPDF (Worker 4 Visual)
  {
    id: 'docling_extractor',
    type: 'n8nCompact',
    position: { x: 2210, y: 520 },
    data: {
      category: 'Doc Parser & Vision',
      label: 'Docling & PyMuPDF (W4)',
      subtitle: 'Table Parser, Flowchart & Media Extractor',
      icon: FileCode,
      bgColor: 'bg-teal-500/15',
      color: 'border-teal-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'CHUNK 512 + W4',
      params: [
        { label: 'parser: docling', theme: 'teal' },
        { label: 'flowchart: visual', theme: 'purple' }
      ]
    }
  },

  // Tool 1: Python Code Sandbox Runner
  {
    id: 'tool_python',
    type: 'n8nCompact',
    position: { x: 2210, y: 680 },
    data: {
      category: 'Code Interpreter',
      label: 'Python Code Sandbox',
      subtitle: 'Isolated Docker Ephemeral Jail',
      icon: Terminal,
      bgColor: 'bg-violet-500/15',
      color: 'border-violet-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'DOCKER JAIL',
      params: [
        { label: 'runtime: py3.11', theme: 'purple' },
        { label: 'timeout: 15s', theme: 'rose' }
      ]
    }
  },

  // Tool 2: Web Search & URL Live Reader
  {
    id: 'tool_search',
    type: 'n8nCompact',
    position: { x: 2210, y: 840 },
    data: {
      category: 'Web & Scraper',
      label: 'SearXNG Web & URL',
      subtitle: 'Live Web Snippets & Jina Reader',
      icon: Search,
      bgColor: 'bg-indigo-500/15',
      color: 'border-indigo-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'LIVE WEB',
      params: [
        { label: 'engine: searxng', theme: 'purple' },
        { label: 'url_reader: on', theme: 'default' }
      ]
    }
  },

  // Tool 3: Nextcloud Deck Kanban Tool
  {
    id: 'tool_deck',
    type: 'n8nCompact',
    position: { x: 2210, y: 1000 },
    data: {
      category: 'Kanban Tool',
      label: 'Nextcloud Deck API',
      subtitle: 'Boards, Stacks & Task Cards',
      icon: ListTodo,
      bgColor: 'bg-sky-500/15',
      color: 'border-sky-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'DECK REST',
      params: [
        { label: 'protocol: REST', theme: 'cyan' },
        { label: 'auth: bearer', theme: 'default' }
      ]
    }
  },

  // Tool 4: Generate File / File Output Creator
  {
    id: 'tool_generate_file',
    type: 'n8nCompact',
    position: { x: 2210, y: 1160 },
    data: {
      category: 'File Creator',
      label: 'Generate File Exporter',
      subtitle: 'Script / CSV / JSON File Output',
      icon: FilePlus,
      bgColor: 'bg-lime-500/15',
      color: 'border-lime-500/40',
      hasInput: true,
      hasOutput: true,
      badgeText: 'FILE EXPORT',
      params: [
        { label: 'type: py/csv/json', theme: 'emerald' },
        { label: 'download: true', theme: 'default' }
      ]
    }
  },

  // ── CLUSTER 5: CALL 1.1 CRAG CONTEXT VERIFIER (x: 2600) ──
  // Inilah letak Call 1.1 yang sebenarnya di Cakra AI:
  // Memverifikasi dokumen kandidat hasil penelusuran database/RAG sebelum diserahkan ke Call 2!
  {
    id: 'call1_crag_verifier',
    type: 'n8nCompact',
    position: { x: 2600, y: 280 },
    data: {
      category: 'Call 1.1 · CRAG Verifier',
      label: 'Call 1.1: Context Verifier',
      subtitle: 'CRAG Relevance & Candidate Auditor',
      icon: CheckCheck,
      bgColor: 'bg-cyan-500/20',
      color: 'border-cyan-500/60',
      hasInput: true,
      hasOutput: true,
      badgeText: 'CALL 1.1 CRAG',
      params: [
        { label: 'eval: gemma4:e4b', theme: 'cyan' },
        { label: 'primary_doc_id', theme: 'purple' },
        { label: 'turn_2_retry: on', theme: 'amber' }
      ]
    }
  },

  // ── CLUSTER 6: SYNTHESIS, COMPLIANCE EGRESS & SSE STREAM (x: 2980 - 3740) ──
  // 6. Synthesizer Call 2 (Gemma 4 31B Core)
  {
    id: 'synthesizer',
    type: 'n8nCompact',
    position: { x: 2980, y: 440 },
    data: {
      category: 'Synthesis Call 2',
      label: 'Synthesizer & Reasoning',
      subtitle: 'Gemma 4 31B Core Synthesis',
      icon: Sparkles,
      bgColor: 'bg-fuchsia-500/20',
      color: 'border-fuchsia-500/50',
      hasInput: true,
      hasTopInput: true,
      hasBottomInput: true,
      hasOutput: true,
      badgeText: 'CALL 2 CORE',
      params: [
        { label: 'model: Gemma 4', theme: 'purple' },
        { label: 'temp: 0.3', theme: 'default' },
        { label: 'ctx: 32k', theme: 'cyan' }
      ]
    }
  },

  // 7. Post-Guardrails & Egress Compliance
  {
    id: 'guardrails',
    type: 'n8nCompact',
    position: { x: 3360, y: 440 },
    data: {
      category: 'Egress Compliance',
      label: 'Guardrails & Safety Egress',
      subtitle: 'Defense Redaction, Citation & Cleanse',
      icon: CheckCircle2,
      bgColor: 'bg-emerald-500/20',
      color: 'border-emerald-500/50',
      hasInput: true,
      hasOutput: true,
      badgeText: 'COMPLIANCE PASS',
      params: [
        { label: 'redaction: on', theme: 'rose' },
        { label: 'sanitizer: on', theme: 'emerald' },
        { label: 'citation: verified', theme: 'default' }
      ]
    }
  },

  // 8. SSE Realtime Stream Delivery
  {
    id: 'delivery',
    type: 'n8nCompact',
    position: { x: 3740, y: 440 },
    data: {
      category: 'Delivery Sink',
      label: 'SSE Stream Delivery',
      subtitle: 'Multi-Widget Streaming to User',
      icon: Radio,
      bgColor: 'bg-cyan-500/20',
      color: 'border-cyan-500/50',
      hasInput: true,
      hasOutput: false,
      badgeText: 'STREAMING',
      params: [
        { label: 'proto: sse', theme: 'cyan' },
        { label: 'widgets: live', theme: 'default' }
      ]
    }
  }
];

// ── Clean & Accurate Edge Connections (Visible Circuit Style) ─────────────────
const initialEdges = [
  // ── INGRESS HIGHWAY ──
  { id: 'e-user-gateway', source: 'user', sourceHandle: 'right', target: 'gateway', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-gateway-firewall', source: 'gateway', sourceHandle: 'right', target: 'firewall', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-firewall-memory', source: 'firewall', sourceHandle: 'right', target: 'memory', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── FIREWALL DROP 403 ──
  { id: 'e-firewall-drop', source: 'firewall', sourceHandle: 'bottom', target: 'drop', targetHandle: 'top', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '4 4' } },

  // ── POSTGRESQL & HRIS DB HYDRATION ──
  { id: 'e-memory-postgres', source: 'postgres_db', sourceHandle: 'top', target: 'memory', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '3 3' } },

  // ── MEMORY TO CALL 1 DUAL DISPATCHER ──
  { id: 'e-memory-router', source: 'memory', sourceHandle: 'right', target: 'router', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-memory-preset', source: 'memory', sourceHandle: 'right', target: 'preset_dispatcher', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '4 4' } },

  // ── CALL 1 INTENT ROUTER TO LANES / MODES ──
  { id: 'e-router-flash', source: 'router', sourceHandle: 'right', target: 'flash', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-rag', source: 'router', sourceHandle: 'right', target: 'rag', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-redteam', source: 'router', sourceHandle: 'right', target: 'redteam_compliance', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-attachment', source: 'router', sourceHandle: 'right', target: 'attachment', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-tools', source: 'router', sourceHandle: 'right', target: 'tools', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-collab', source: 'router', sourceHandle: 'right', target: 'collab_editor', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-router-wizard', source: 'router', sourceHandle: 'right', target: 'wizard', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── CALL 1 PRESET DISPATCHER TO LANES / MODES (FAST-PATH BYPASS) ──
  { id: 'e-preset-rag', source: 'preset_dispatcher', sourceHandle: 'right', target: 'rag', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '4 4' } },
  { id: 'e-preset-redteam', source: 'preset_dispatcher', sourceHandle: 'right', target: 'redteam_compliance', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '4 4' } },
  { id: 'e-preset-tools', source: 'preset_dispatcher', sourceHandle: 'right', target: 'tools', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8, strokeDasharray: '4 4' } },

  // ── LANE A: FLASH DIRECT TO SYNTHESIZER (ZERO-RAG DIRECT HIGHWAY!) ──
  { id: 'e-flash-synth', source: 'flash', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'top', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 2 } },

  // ── LANE B: RAG FAN-OUT TO KNOWLEDGE RETRIEVAL DATABASES ──
  { id: 'e-rag-mysql', source: 'rag', sourceHandle: 'right', target: 'mysql_peraturan', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-rag-pgvector', source: 'rag', sourceHandle: 'right', target: 'pgvector_db', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── LANE E: RED-TEAM & COMPLIANCE FAN-OUT TO SOP PINDAD & DRAFT ──
  { id: 'e-redteam-mysql', source: 'redteam_compliance', sourceHandle: 'right', target: 'mysql_peraturan', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-redteam-pgvector', source: 'redteam_compliance', sourceHandle: 'right', target: 'pgvector_db', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── RETRIEVAL OUTPUTS INTO CALL 1.1 CONTEXT VERIFIER (CRAG) ──
  // Hasil query database (kandidat dokumen) diserahkan ke Call 1.1 CRAG Verifier!
  { id: 'e-mysql-crag', source: 'mysql_peraturan', sourceHandle: 'right', target: 'call1_crag_verifier', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-pgvector-crag', source: 'pgvector_db', sourceHandle: 'right', target: 'call1_crag_verifier', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── CALL 1.1 CRAG VERIFIER VERIFIES & FEEDS INTO SYNTHESIZER ──
  { id: 'e-crag-synth', source: 'call1_crag_verifier', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 2 } },

  // ── LANE D: ATTACHMENT TO DOCLING PARSER & INTO SYNTHESIZER ──
  { id: 'e-attachment-docling', source: 'attachment', sourceHandle: 'right', target: 'docling_extractor', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-docling-synth', source: 'docling_extractor', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── LANE C: MULTI-TOOL DISPATCHER: FAN-OUT TO AGENTIC TOOLS ──
  { id: 'e-tools-python', source: 'tools', sourceHandle: 'right', target: 'tool_python', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-tools-search', source: 'tools', sourceHandle: 'right', target: 'tool_search', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-tools-deck', source: 'tools', sourceHandle: 'right', target: 'tool_deck', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-tools-genfile', source: 'tools', sourceHandle: 'right', target: 'tool_generate_file', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── AGENTIC TOOLS FEED RESULTS INTO SYNTHESIZER (Enters from Bottom) ──
  { id: 'e-python-synth', source: 'tool_python', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-search-synth', source: 'tool_search', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-deck-synth', source: 'tool_deck', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },
  { id: 'e-genfile-synth', source: 'tool_generate_file', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── COLLAB & CORPORATE EDITOR TO SYNTHESIZER ──
  { id: 'e-collab-synth', source: 'collab_editor', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── AMBIGUITY WIZARD TO SYNTHESIZER ──
  { id: 'e-wizard-synth', source: 'wizard', sourceHandle: 'right', target: 'synthesizer', targetHandle: 'bottom', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 1.8 } },

  // ── SYNTHESIS -> GUARDRAILS -> REALTIME SSE DELIVERY ──
  { id: 'e-synth-guard', source: 'synthesizer', sourceHandle: 'right', target: 'guardrails', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 2 } },
  { id: 'e-guard-delivery', source: 'guardrails', sourceHandle: 'right', target: 'delivery', targetHandle: 'left', animated: false, type: 'smoothstep', style: { stroke: '#334155', strokeWidth: 2 } }
];

export const PipelineFlowCanvas = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [interactivePrompt, setInteractivePrompt] = useState('');
  const [executionLog, setExecutionLog] = useState(null);
  const animationTimerRef = useRef([]);

  // Clear animation timeouts
  const clearTimers = () => {
    animationTimerRef.current.forEach((t) => clearTimeout(t));
    animationTimerRef.current = [];
  };

  useEffect(() => {
    return () => clearTimers();
  }, []);

  // Update specific node state
  const updateNodeState = (nodeId, status, latency = null) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          return {
            ...n,
            data: {
              ...n.data,
              status,
              latency: latency || n.data.latency
            }
          };
        }
        return n;
      })
    );
  };

  // Update specific edge state
  const updateEdgeState = (edgeId, isLive, color = '#06B6D4', isCompleted = false) => {
    setEdges((eds) =>
      eds.map((e) => {
        if (e.id === edgeId) {
          if (isLive) {
            return {
              ...e,
              animated: true,
              style: {
                stroke: color,
                strokeWidth: 5,
                filter: `drop-shadow(0 0 12px ${color})`,
                opacity: 1
              }
            };
          }
          if (isCompleted) {
            return {
              ...e,
              animated: false,
              style: {
                stroke: color,
                strokeWidth: 4,
                filter: `drop-shadow(0 0 8px ${color})`,
                opacity: 1
              }
            };
          }
          return {
            ...e,
            animated: false,
            style: { stroke: '#334155', strokeWidth: 1.8, opacity: 0.6 }
          };
        }
        return e;
      })
    );
  };

  // Reset whole canvas to idle state
  const resetAllStates = () => {
    clearTimers();
    setIsAnimating(false);
    setExecutionLog(null);
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          status: 'idle',
          latency: null
        }
      }))
    );
    setEdges(initialEdges);
  };

  // ── CORE SEQUENTIAL INTERACTIVE FLOW RUNNER ─────────────────────────────────
  const runSequentialInteractiveFlow = useCallback((routeType = 'rag', promptText = 'Bagaimana ketentuan pengadaan PT Pindad?') => {
    clearTimers();
    resetAllStates();
    setIsAnimating(true);

    const isBlocked = routeType === 'blocked';
    const isPreset = routeType === 'preset_rag' || routeType === 'preset_redteam';
    const isAmbiguous = routeType === 'ambiguous';
    const isAttachment = routeType === 'attachment';
    const isRedTeam = routeType === 'redteam' || routeType === 'preset_redteam';
    const isPython = routeType === 'python';
    const isGenFile = routeType === 'generate_file';
    const isDeck = routeType === 'deck';
    const isSearch = routeType === 'search';
    const isCollab = routeType === 'collab';
    const isFlash = routeType === 'flash';
    const isRag = routeType === 'rag' || routeType === 'preset_rag';

    setExecutionLog({
      prompt: promptText,
      route: routeType.toUpperCase().replace('_', ' '),
      startTime: new Date().toLocaleTimeString(),
      status: 'PROCESSING'
    });

    const timers = [];

    // Step 1: User Ingress Active (0ms)
    timers.push(setTimeout(() => {
      updateNodeState('user', 'active', '0.3ms');
      updateEdgeState('e-user-gateway', true, '#10B981');
    }, 100));

    // Step 2: Gateway Active (550ms)
    timers.push(setTimeout(() => {
      updateNodeState('user', 'completed', '0.3ms');
      updateEdgeState('e-user-gateway', false, '#10B981', true);

      updateNodeState('gateway', 'active', '1.1ms');
      updateEdgeState('e-gateway-firewall', true, '#0284C7');
    }, 550));

    // Step 3: Security Firewall Active (1100ms)
    timers.push(setTimeout(() => {
      updateNodeState('gateway', 'completed', '1.1ms');
      updateEdgeState('e-gateway-firewall', false, '#0284C7', true);

      updateNodeState('firewall', 'active', '3.5ms');

      if (isBlocked) {
        updateEdgeState('e-firewall-drop', true, '#EF4444');
      } else {
        updateEdgeState('e-firewall-memory', true, '#10B981');
      }
    }, 1100));

    // Branch: BLOCKED 403 ATTACK MITIGATED
    if (isBlocked) {
      timers.push(setTimeout(() => {
        updateNodeState('firewall', 'completed', 'Mitigated');
        updateEdgeState('e-firewall-drop', false, '#EF4444', true);

        updateNodeState('drop', 'blocked', 'DROP 403');
        setIsAnimating(false);
        setExecutionLog((prev) => ({
          ...prev,
          status: 'ALERT: BLOCKED 403 (Malicious Injection Dropped by Firewall L1-L6)',
          totalLatency: '16ms'
        }));
      }, 1700));
      animationTimerRef.current = timers;
      return;
    }

    // Step 4: Memory Active & Hydrate Session Brain (1700ms)
    timers.push(setTimeout(() => {
      updateNodeState('firewall', 'completed', 'Clean: 100%');
      updateEdgeState('e-firewall-memory', false, '#10B981', true);

      updateNodeState('memory', 'active', '4.2ms');
      updateEdgeState('e-memory-postgres', true, '#3B82F6');
      updateNodeState('postgres_db', 'active', 'AsyncPG 2ms');

      setTimeout(() => {
        updateNodeState('postgres_db', 'completed', 'NPP & Prefs OK');
        updateEdgeState('e-memory-postgres', false, '#3B82F6', true);

        if (isPreset) {
          updateEdgeState('e-memory-preset', true, '#F97316');
        } else {
          updateEdgeState('e-memory-router', true, '#6366F1');
        }
      }, 300);
    }, 1700));

    // Step 5: Call 1 Intent Classification / Preset Dispatcher (2400ms)
    timers.push(setTimeout(() => {
      updateNodeState('memory', 'completed', 'Context Ready');

      if (isPreset) {
        updateEdgeState('e-memory-preset', false, '#F97316', true);
        updateNodeState('preset_dispatcher', 'active', '&lt;35ms Fast-Path');

        setTimeout(() => {
          updateNodeState('preset_dispatcher', 'completed', 'Fast-Path Bypass OK');
          if (isRag) updateEdgeState('e-preset-rag', true, '#F97316');
          else if (isRedTeam) updateEdgeState('e-preset-redteam', true, '#F43F5E');
          else updateEdgeState('e-preset-tools', true, '#A855F7');
        }, 350);
      } else {
        updateEdgeState('e-memory-router', false, '#6366F1', true);
        updateNodeState('router', 'active', 'Call 1 LoRA');

        setTimeout(() => {
          updateNodeState('router', 'completed', 'Gemma Decision OK');
          if (isAmbiguous) updateEdgeState('e-router-wizard', true, '#F59E0B');
          else if (isFlash) updateEdgeState('e-router-flash', true, '#EAB308');
          else if (isAttachment) updateEdgeState('e-router-attachment', true, '#F97316');
          else if (isRedTeam) updateEdgeState('e-router-redteam', true, '#F43F5E');
          else if (isRag) updateEdgeState('e-router-rag', true, '#06B6D4');
          else if (isCollab) updateEdgeState('e-router-collab', true, '#EC4899');
          else updateEdgeState('e-router-tools', true, '#A855F7');
        }, 450);
      }
    }, 2400));

    // Step 6: Highway Execution & Database Retrieval (3300ms)
    timers.push(setTimeout(() => {
      if (isPreset) {
        if (isRag) updateEdgeState('e-preset-rag', false, '#F97316', true);
        else if (isRedTeam) updateEdgeState('e-preset-redteam', false, '#F43F5E', true);
        else updateEdgeState('e-preset-tools', false, '#A855F7', true);
      } else {
        if (isAmbiguous) updateEdgeState('e-router-wizard', false, '#F59E0B', true);
        else if (isFlash) updateEdgeState('e-router-flash', false, '#EAB308', true);
        else if (isAttachment) updateEdgeState('e-router-attachment', false, '#F97316', true);
        else if (isRedTeam) updateEdgeState('e-router-redteam', false, '#F43F5E', true);
        else if (isRag) updateEdgeState('e-router-rag', false, '#06B6D4', true);
        else if (isCollab) updateEdgeState('e-router-collab', false, '#EC4899', true);
        else updateEdgeState('e-router-tools', false, '#A855F7', true);
      }

      // Branch A: FLASH DIRECT MODE (Direct to Synthesizer without DB or CRAG!)
      if (isFlash) {
        updateNodeState('flash', 'active', '&lt;160ms');
        setTimeout(() => {
          updateEdgeState('e-flash-synth', true, '#EAB308');
        }, 200);
      }
      // Branch B: RAG & RED-TEAM (Query Database First!)
      else if (isRag || isRedTeam) {
        const activeModeId = isRedTeam ? 'redteam_compliance' : 'rag';
        const activeEdgePrefix = isRedTeam ? 'e-redteam' : 'e-rag';
        const modeColor = isRedTeam ? '#F43F5E' : '#06B6D4';

        updateNodeState(activeModeId, 'active', 'Retrieval Query Formed');
        updateEdgeState(`${activeEdgePrefix}-mysql`, true, '#38BDF8');
        updateEdgeState(`${activeEdgePrefix}-pgvector`, true, '#10B981');
        updateNodeState('mysql_peraturan', 'active', 'Query SOP Table');
        updateNodeState('pgvector_db', 'active', 'Dense 1024d Search');

        // Step 6.2: Pass candidate documents into Call 1.1 CRAG Context Verifier!
        setTimeout(() => {
          updateNodeState(activeModeId, 'completed', 'Queries Dispatched');
          updateEdgeState(`${activeEdgePrefix}-mysql`, false, '#38BDF8', true);
          updateEdgeState(`${activeEdgePrefix}-pgvector`, false, '#10B981', true);
          updateNodeState('mysql_peraturan', 'completed', 'Candidates: 5 Docs');
          updateNodeState('pgvector_db', 'completed', 'Top-8 Chunks');

          // Flow into Call 1.1 Context Verifier!
          updateEdgeState('e-mysql-crag', true, '#38BDF8');
          updateEdgeState('e-pgvector-crag', true, '#10B981');
          updateNodeState('call1_crag_verifier', 'active', 'CRAG Turn 1 Eval');

          setTimeout(() => {
            updateEdgeState('e-mysql-crag', false, '#38BDF8', true);
            updateEdgeState('e-pgvector-crag', false, '#10B981', true);
            updateNodeState('call1_crag_verifier', 'completed', 'Primary Doc #1 Verified');
            updateEdgeState('e-crag-synth', true, '#06B6D4');
          }, 600);
        }, 700);
      }
      // Branch C: ATTACHMENT & PDF INTERROGATOR
      else if (isAttachment) {
        updateNodeState('attachment', 'active', 'PDF Parser');
        updateEdgeState('e-attachment-docling', true, '#14B8A6');
        updateNodeState('docling_extractor', 'active', 'Docling W4 Vision');

        setTimeout(() => {
          updateNodeState('attachment', 'completed', 'Batch 10 Hal OK');
          updateEdgeState('e-attachment-docling', false, '#14B8A6', true);
          updateNodeState('docling_extractor', 'completed', 'Parsed 12 Chunks');
          updateEdgeState('e-docling-synth', true, '#14B8A6');
        }, 700);
      }
      // Branch D: COLLAB & SMART MAIL
      else if (isCollab) {
        updateNodeState('collab_editor', 'active', 'Draf Nota Dinas');
        setTimeout(() => {
          updateNodeState('collab_editor', 'completed', 'Template Dinas OK');
          updateEdgeState('e-collab-synth', true, '#EC4899');
        }, 500);
      }
      // Branch E: AGENTIC TOOLS (Python, Search, Deck, Generate File)
      else if (isPython || isSearch || isDeck || isGenFile) {
        updateNodeState('tools', 'active', 'Agentic Bus');

        if (isGenFile) {
          updateEdgeState('e-tools-genfile', true, '#84CC16');
          updateNodeState('tool_generate_file', 'active', 'Exporter');
          setTimeout(() => {
            updateNodeState('tools', 'completed', 'Tool Dispatched');
            updateEdgeState('e-tools-genfile', false, '#84CC16', true);
            updateNodeState('tool_generate_file', 'completed', '.py generated');
            updateEdgeState('e-genfile-synth', true, '#84CC16');
          }, 600);
        } else if (isPython) {
          updateEdgeState('e-tools-python', true, '#8B5CF6');
          updateNodeState('tool_python', 'active', 'Docker Ephemeral');
          setTimeout(() => {
            updateNodeState('tools', 'completed', 'Tool Dispatched');
            updateEdgeState('e-tools-python', false, '#8B5CF6', true);
            updateNodeState('tool_python', 'completed', 'Exit: 0');
            updateEdgeState('e-python-synth', true, '#8B5CF6');
          }, 600);
        } else if (isSearch) {
          updateEdgeState('e-tools-search', true, '#818CF8');
          updateNodeState('tool_search', 'active', 'SearXNG Web');
          setTimeout(() => {
            updateNodeState('tools', 'completed', 'Tool Dispatched');
            updateEdgeState('e-tools-search', false, '#818CF8', true);
            updateNodeState('tool_search', 'completed', '5 Live Hits');
            updateEdgeState('e-search-synth', true, '#818CF8');
          }, 600);
        } else if (isDeck) {
          updateEdgeState('e-tools-deck', true, '#38BDF8');
          updateNodeState('tool_deck', 'active', 'Nextcloud REST');
          setTimeout(() => {
            updateNodeState('tools', 'completed', 'Tool Dispatched');
            updateEdgeState('e-tools-deck', false, '#38BDF8', true);
            updateNodeState('tool_deck', 'completed', 'Card Created');
            updateEdgeState('e-deck-synth', true, '#38BDF8');
          }, 600);
        }
      }
      // Branch F: AMBIGUITY WIZARD
      else if (isAmbiguous) {
        updateNodeState('wizard', 'active', 'Generating Options');
        setTimeout(() => {
          updateNodeState('wizard', 'completed', '3 Guided Options');
          updateEdgeState('e-wizard-synth', true, '#F59E0B');
        }, 500);
      }
    }, 3300));

    // Step 7: Synthesizer & Reasoning Call 2 (4900ms)
    timers.push(setTimeout(() => {
      // Transition all feeding edges to isCompleted: true without gaps!
      if (isFlash) {
        updateNodeState('flash', 'completed', '&lt;160ms OK');
        updateEdgeState('e-flash-synth', false, '#EAB308', true);
      } else if (isRag || isRedTeam) {
        updateEdgeState('e-crag-synth', false, '#06B6D4', true);
      } else if (isAttachment) {
        updateEdgeState('e-docling-synth', false, '#14B8A6', true);
      } else if (isCollab) {
        updateEdgeState('e-collab-synth', false, '#EC4899', true);
      } else if (isGenFile) {
        updateEdgeState('e-genfile-synth', false, '#84CC16', true);
      } else if (isPython) {
        updateEdgeState('e-python-synth', false, '#8B5CF6', true);
      } else if (isSearch) {
        updateEdgeState('e-search-synth', false, '#818CF8', true);
      } else if (isDeck) {
        updateEdgeState('e-deck-synth', false, '#38BDF8', true);
      } else if (isAmbiguous) {
        updateEdgeState('e-wizard-synth', false, '#F59E0B', true);
      }

      updateNodeState('synthesizer', 'active', 'Gemma 4 31B Core');
      updateEdgeState('e-synth-guard', true, '#C026D3');
    }, 4900));

    // Step 8: Post-Guardrails & Egress Compliance (5700ms)
    timers.push(setTimeout(() => {
      updateNodeState('synthesizer', 'completed', 'Gemma 4 Synced');
      updateEdgeState('e-synth-guard', false, '#C026D3', true);

      updateNodeState('guardrails', 'active', 'Defense Redaction & Citation');
      updateEdgeState('e-guard-delivery', true, '#10B981');
    }, 5700));

    // Step 9: SSE Delivery Stream (6300ms)
    timers.push(setTimeout(() => {
      updateNodeState('guardrails', 'completed', 'Redaction Pass 100%');
      updateEdgeState('e-guard-delivery', false, '#10B981', true);

      updateNodeState('delivery', 'completed', 'Stream Sent');
      setIsAnimating(false);
      setExecutionLog((prev) => ({
        ...prev,
        status: isAmbiguous ? 'DECISION WIZARD: Opsi Klarifikasi Dikirim ke User' : 'SUCCESS: Response Streamed to User via SSE',
        totalLatency: isFlash ? '175ms (Zero-RAG Direct)' : isPreset ? '240ms (Preset Fast-Path)' : '380ms'
      }));
    }, 6300));

    animationTimerRef.current = timers;
  }, []);

  // Track active route during live multi-stage telemetry
  const activeRouteRef = useRef('rag');

  // ── REALTIME TELEMETRY LISTENER ─────────────────────────────────────────────
  useEffect(() => {
    let channel;
    let eventSource;

    const handleIncomingEvent = (eventData) => {
      if (eventData?.type === 'PIPELINE_ROUTING') {
        const { lane, mode } = eventData;
        const targetRoute = lane || mode || 'flash';
        activeRouteRef.current = targetRoute;

        updateNodeState('router', 'completed', `Route: ${targetRoute.toUpperCase()}`);

        if (targetRoute === 'flash') {
          updateEdgeState('e-router-flash', false, '#EAB308', true);
          updateNodeState('flash', 'active', 'Fast Chitchat');
          updateEdgeState('e-flash-synth', true, '#EAB308');
        } else if (targetRoute === 'attachment') {
          updateEdgeState('e-router-attachment', false, '#F97316', true);
          updateNodeState('attachment', 'active', 'PDF Interrogator');
          updateEdgeState('e-attachment-docling', true, '#14B8A6');
        } else if (targetRoute === 'redteam' || targetRoute === 'compliance') {
          updateEdgeState('e-router-redteam', false, '#F43F5E', true);
          updateNodeState('redteam_compliance', 'active', 'Audit SOP');
          updateEdgeState('e-redteam-mysql', true, '#38BDF8');
        } else if (targetRoute === 'rag') {
          updateEdgeState('e-router-rag', false, '#06B6D4', true);
          updateNodeState('rag', 'active', 'Hybrid Search');
          updateEdgeState('e-rag-mysql', true, '#38BDF8');
          updateEdgeState('e-rag-pgvector', true, '#10B981');
        }
      }

      if (eventData?.type === 'PIPELINE_LIFECYCLE') {
        const { stage, statusStr, statusKey, prompt } = eventData;

        if (stage === 'INIT') {
          clearTimers();
          resetAllStates();
          setIsAnimating(true);
          const p = prompt || 'User Prompt';
          const lower = p.toLowerCase();
          let r = 'flash';
          if (lower.includes('drop table') || lower.includes('<script>') || lower.includes('jailbreak')) r = 'blocked';
          else if (lower.includes('celah') || lower.includes('redteam') || lower.includes('compliance') || lower.includes('audit')) r = 'redteam';
          else if (lower.includes('bantu saya') || lower.includes('buatkan sesuatu')) r = 'ambiguous';
          else if (lower.includes('pdf') || lower.includes('lampiran') || lower.includes('interrogator')) r = 'attachment';
          else if (lower.includes('buat file') || lower.includes('generate file')) r = 'generate_file';
          else if (lower.includes('python') || lower.includes('hitung') || lower.includes('csv')) r = 'python';
          else if (lower.includes('deck') || lower.includes('kanban')) r = 'deck';
          else if (lower.includes('cari') || lower.includes('search')) r = 'search';
          else if (lower.includes('nota dinas') || lower.includes('surat') || lower.includes('collab')) r = 'collab';
          else if (lower.includes('peraturan') || lower.includes('sop') || lower.includes('pengadaan')) r = 'rag';
          activeRouteRef.current = r;

          updateNodeState('user', 'active', '0.3ms');
          updateEdgeState('e-user-gateway', true, '#10B981');
          setExecutionLog({
            prompt: p,
            route: 'INGRESS',
            startTime: new Date().toLocaleTimeString(),
            status: '1/7: User Ingress → Gateway'
          });
        } 
        else if (stage === 'CONNECTING') {
          updateNodeState('user', 'completed', '0.3ms');
          updateEdgeState('e-user-gateway', false, '#10B981', true);
          updateNodeState('gateway', 'completed', '1.1ms');
          updateEdgeState('e-gateway-firewall', true, '#0284C7');
          updateNodeState('firewall', 'active', 'Firewall Scan');
        }
        else if (stage === 'STATUS') {
          const key = (statusKey || '').toUpperCase();
          const str = (statusStr || '').toLowerCase();

          if (key.includes('CONNECTING') || str.includes('menghubungkan')) {
            updateNodeState('gateway', 'completed', '1.1ms');
            updateNodeState('firewall', 'completed', 'Clean 100%');
            updateEdgeState('e-gateway-firewall', false, '#0284C7', true);
            updateEdgeState('e-firewall-memory', true, '#10B981');
            updateNodeState('memory', 'active', 'Context 4.2ms');
          }
          else if (key.includes('PRESET') || str.includes('preset') || str.includes('bypass')) {
            updateNodeState('memory', 'completed', 'Context Ready');
            updateEdgeState('e-firewall-memory', false, '#10B981', true);
            updateEdgeState('e-memory-preset', true, '#F97316');
            updateNodeState('preset_dispatcher', 'active', 'Fast-Path');
          }
          else if (key.includes('BRAIN') || key.includes('ROUTING') || str.includes('menganalisis') || str.includes('niat')) {
            updateNodeState('memory', 'completed', 'Context Ready');
            updateEdgeState('e-firewall-memory', false, '#10B981', true);
            updateEdgeState('e-memory-router', true, '#6366F1');
            updateNodeState('router', 'active', 'Call 1 LoRA');
          }
          else if (key.includes('DOC') || key.includes('REGULATION') || str.includes('arsip') || str.includes('regulasi')) {
            updateNodeState('router', 'completed', 'Decision: RAG');
            updateEdgeState('e-memory-router', false, '#6366F1', true);
            updateEdgeState('e-router-rag', false, '#06B6D4', true);
            updateNodeState('rag', 'active', 'Searching SOP & Docs');
            updateEdgeState('e-rag-mysql', true, '#38BDF8');
            updateEdgeState('e-rag-pgvector', true, '#10B981');
          }
          else if (key.includes('CRAG') || str.includes('memverifikasi') || str.includes('kandidat')) {
            updateNodeState('mysql_peraturan', 'completed', 'Found Docs');
            updateNodeState('pgvector_db', 'completed', 'Found Chunks');
            updateEdgeState('e-rag-mysql', false, '#38BDF8', true);
            updateEdgeState('e-rag-pgvector', false, '#10B981', true);
            updateEdgeState('e-mysql-crag', true, '#38BDF8');
            updateEdgeState('e-pgvector-crag', true, '#10B981');
            updateNodeState('call1_crag_verifier', 'active', 'Call 1.1 CRAG');
          }
          else if (key.includes('SYNTHESIS') || str.includes('merumuskan') || str.includes('menyusun')) {
            updateNodeState('call1_crag_verifier', 'completed', 'Context OK');
            updateEdgeState('e-mysql-crag', false, '#38BDF8', true);
            updateEdgeState('e-pgvector-crag', false, '#10B981', true);
            updateEdgeState('e-crag-synth', false, '#06B6D4', true);
            updateNodeState('synthesizer', 'active', 'Call 2 Core');
            updateEdgeState('e-synth-guard', true, '#C026D3');
          }
        }
        else if (stage === 'COMPLETED') {
          updateNodeState('synthesizer', 'completed', 'Gemma 4 Synced');
          updateEdgeState('e-synth-guard', false, '#C026D3', true);
          updateNodeState('guardrails', 'completed', 'Pass 100%');
          updateEdgeState('e-guard-delivery', true, '#10B981');
          setTimeout(() => {
            updateEdgeState('e-guard-delivery', false, '#10B981', true);
            updateNodeState('delivery', 'completed', 'Stream Sent');
            setIsAnimating(false);
          }, 350);
        }
      }
    };

    try {
      if (typeof window !== 'undefined' && window.BroadcastChannel) {
        channel = new BroadcastChannel('cakra_pipeline_telemetry');
        channel.onmessage = (event) => handleIncomingEvent(event.data);
      }
    } catch (e) {}

    try {
      const apiBase = apiClient?.defaults?.baseURL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000/api` : '/api');
      const sseUrl = `${apiBase.replace(/\/$/, '')}/analytics/pipeline/live-stream`;
      eventSource = new EventSource(sseUrl);
      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          handleIncomingEvent(parsed);
        } catch (err) {}
      };
    } catch (e) {}

    return () => {
      if (channel) channel.close();
      if (eventSource) eventSource.close();
    };
  }, [runSequentialInteractiveFlow]);

  // Handle user manual prompt submit
  const handleManualTestSubmit = (e) => {
    e?.preventDefault();
    if (!interactivePrompt.trim()) return;

    const lower = interactivePrompt.toLowerCase();
    let route = 'rag';
    if (lower.includes('drop table') || lower.includes('<script>') || lower.includes('injection') || lower.includes('sudo')) {
      route = 'blocked';
    } else if (lower.includes('celah') || lower.includes('redteam') || lower.includes('klausul') || lower.includes('risiko') || lower.includes('compliance')) {
      route = 'redteam';
    } else if (lower.includes('preset') || lower.includes('#dokumen') || lower.includes('#rag')) {
      route = 'preset_rag';
    } else if (lower.includes('bantu saya') || lower.includes('buatkan sesuatu') || lower.includes('undang undang')) {
      route = 'ambiguous';
    } else if (lower.includes('pdf') || lower.includes('lampiran') || lower.includes('interrogator')) {
      route = 'attachment';
    } else if (lower.includes('buat file') || lower.includes('generate file') || lower.includes('buatkan script')) {
      route = 'generate_file';
    } else if (lower.includes('python') || lower.includes('hitung') || lower.includes('chart')) {
      route = 'python';
    } else if (lower.includes('deck') || lower.includes('kanban') || lower.includes('tugas')) {
      route = 'deck';
    } else if (lower.includes('cari') || lower.includes('search') || lower.includes('berita') || lower.includes('http')) {
      route = 'search';
    } else if (lower.includes('nota') || lower.includes('surat') || lower.includes('email') || lower.includes('collab')) {
      route = 'collab';
    } else if (lower.includes('halo') || lower.includes('pagi') || lower.includes('siapa kamu')) {
      route = 'flash';
    } else {
      route = 'rag';
    }

    runSequentialInteractiveFlow(route, interactivePrompt);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0e1118] rounded-2xl border border-gray-800/80 overflow-hidden relative font-sans">
      {/* ── Top Bar: Compact Controls & Preset Pills ── */}
      <div className="bg-[#141720]/95 border-b border-gray-800 px-4 py-2.5 flex flex-col xl:flex-row xl:items-center justify-between gap-2.5 z-10 backdrop-blur-md">
        {/* Title */}
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
            <Network size={16} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold text-white tracking-wide">CAKRA Node Pipeline Visualizer</h2>
              <span className="text-[8.5px] font-mono px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center gap-1">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                </span>
                REAL ARCHITECTURE LIVE
              </span>
            </div>
          </div>
        </div>

        {/* Interactive Prompt Input */}
        <form onSubmit={handleManualTestSubmit} className="flex items-center gap-2 flex-1 max-w-md">
          <input
            type="text"
            value={interactivePrompt}
            onChange={(e) => setInteractivePrompt(e.target.value)}
            placeholder="Ketik prompt uji... (e.g. 'Halo Cakra', 'Bedah celah kontrak', 'SOP Pindad')"
            className="w-full bg-[#0e1118] border border-gray-700/80 rounded-lg px-3 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/40 transition-all font-sans"
          />
          <button
            type="submit"
            disabled={isAnimating || !interactivePrompt.trim()}
            className="px-3 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1 transition-all shadow-[0_0_12px_rgba(6,182,212,0.4)] shrink-0"
          >
            <Play size={11} fill="currentColor" />
            <span>Kirim</span>
          </button>
        </form>

        {/* Compact Quick Preset Pills */}
        <div className="flex items-center gap-1 flex-wrap">
          <button
            onClick={() => runSequentialInteractiveFlow('flash', 'Halo Cakra, selamat pagi!')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-yellow-950/50 hover:bg-yellow-900/60 text-yellow-300 border border-yellow-500/40 transition-all shadow-[0_0_10px_rgba(234,179,8,0.2)]"
          >
            <Zap size={11} />
            <span>Flash (&lt;180ms)</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('rag', 'Bagaimana ketentuan pengadaan barang di PT Pindad?')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-500/40 transition-all"
          >
            <Database size={11} />
            <span>Hybrid RAG + CRAG 1.1</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('redteam', 'Bedah celah klausul dan analisis risiko draft perjanjian ini')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-rose-950/50 hover:bg-rose-900/60 text-rose-300 border border-rose-500/40 transition-all shadow-[0_0_10px_rgba(244,63,94,0.25)]"
          >
            <ShieldAlert size={11} />
            <span>Red-Team Audit</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('preset_rag', '[Preset Bypass #dokumen]: Ketentuan cuti tahunan pegawai')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-orange-950/50 hover:bg-orange-900/60 text-orange-300 border border-orange-500/40 transition-all"
          >
            <Zap size={11} />
            <span>Call 1 Preset (&lt;50ms)</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('attachment', 'Analisis dan audit berkas PDF laporan neraca keuangan')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-amber-950/50 hover:bg-amber-900/60 text-amber-300 border border-amber-500/40 transition-all"
          >
            <Paperclip size={11} />
            <span>PDF Interrogator</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('python', 'Jalankan analisis data CSV dan buatkan visual chart')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-purple-950/50 hover:bg-purple-900/60 text-purple-300 border border-purple-500/40 transition-all"
          >
            <Terminal size={11} />
            <span>Python Sandbox</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('collab', 'Buatkan draf Nota Dinas permohonan lisensi software')}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-pink-950/50 hover:bg-pink-900/60 text-pink-300 border border-pink-500/40 transition-all"
          >
            <Mail size={11} />
            <span>Collab & Surat</span>
          </button>

          <button
            onClick={() => runSequentialInteractiveFlow('blocked', "SELECT * FROM users WHERE 1=1; DROP TABLE logs;--")}
            disabled={isAnimating}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-medium flex items-center gap-1 bg-red-950/50 hover:bg-red-900/60 text-red-300 border border-red-500/40 transition-all"
          >
            <ShieldAlert size={11} />
            <span>Drop 403</span>
          </button>

          <button
            onClick={resetAllStates}
            title="Reset Kanvas"
            className="p-1 rounded-md bg-gray-800 text-gray-400 hover:text-white border border-gray-700 transition-colors ml-0.5"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* ── Active Execution Banner ── */}
      {executionLog && (
        <div className="bg-[#141720]/90 border-b border-gray-800 px-4 py-1.5 flex items-center justify-between text-[11px] backdrop-blur-sm z-10 transition-all">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-cyan-400 font-bold flex items-center gap-1">
              <Activity size={12} className={isAnimating ? 'animate-spin' : ''} />
              JALUR: {executionLog.route}
            </span>
            <span className="text-gray-400 truncate max-w-sm">
              Input: <em className="text-gray-200">"{executionLog.prompt}"</em>
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[10.5px]">
            <span className={executionLog.status.includes('SUCCESS') ? 'text-emerald-400 font-bold' : executionLog.status.includes('ALERT') ? 'text-red-400 font-bold' : executionLog.status.includes('DECISION') ? 'text-amber-400 font-bold' : 'text-yellow-400 animate-pulse'}>
              ● {executionLog.status}
            </span>
            {executionLog.totalLatency && (
              <span className="px-1.5 py-0.2 rounded bg-gray-800 text-cyan-300 border border-gray-700">
                {executionLog.totalLatency}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── xyflow ReactFlow Canvas ── */}
      <div className="flex-1 w-full h-full relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={(e, node) => setSelectedNode(node)}
          fitView
          fitViewOptions={{ padding: 0.04, maxZoom: 1.0 }}
          minZoom={0.25}
          maxZoom={2.0}
        >
          <Background color="#1f2636" gap={22} size={1} />
          <Controls className="!bg-[#141720] !border-gray-800 !rounded-lg !text-white overflow-hidden shadow-2xl scale-90" />
          <MiniMap
            nodeColor={(n) => {
              if (n.data?.status === 'active') return '#06B6D4';
              if (n.data?.status === 'blocked') return '#EF4444';
              if (n.data?.status === 'completed') return '#10B981';
              return '#2a3142';
            }}
            maskColor="rgba(14, 17, 24, 0.85)"
            className="!bg-[#141720] !border-gray-800 !rounded-lg overflow-hidden shadow-2xl scale-90"
          />
        </ReactFlow>

        {/* ── Side Inspection Drawer for Selected Node ── */}
        {selectedNode && (
          <div className="absolute top-3 right-3 w-80 bg-[#141720]/98 border border-gray-700/80 rounded-xl p-3.5 shadow-2xl backdrop-blur-xl z-20 flex flex-col gap-2.5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/40">
                  {selectedNode.data?.category}
                </span>
                <h4 className="text-xs font-bold text-white truncate max-w-[150px]">
                  {selectedNode.data?.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-400 hover:text-white p-1 rounded-md hover:bg-gray-800 transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            <div className="text-xs text-gray-300 space-y-2">
              <p className="text-[11px] text-gray-400">{selectedNode.data?.subtitle}</p>

              {/* Status & Latency */}
              <div className="space-y-1.5 bg-[#0e1118] p-2.5 rounded-lg border border-gray-800 font-mono text-[10.5px]">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Node ID:</span>
                  <span className="text-white font-bold">{selectedNode.id}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Status:</span>
                  <span
                    className={`font-bold ${
                      selectedNode.data?.status === 'active'
                        ? 'text-cyan-400 animate-pulse'
                        : selectedNode.data?.status === 'completed'
                        ? 'text-emerald-400'
                        : selectedNode.data?.status === 'blocked'
                        ? 'text-red-400'
                        : 'text-gray-400'
                    }`}
                  >
                    {selectedNode.data?.status?.toUpperCase() || 'IDLE'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Latency:</span>
                  <span className="text-cyan-300">{selectedNode.data?.latency || '—'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Badge:</span>
                  <span className="text-amber-300">{selectedNode.data?.badgeText || '—'}</span>
                </div>
              </div>

              {/* Node Parameter Chips */}
              {selectedNode.data?.params && selectedNode.data.params.length > 0 && (
                <div>
                  <h5 className="text-[10px] font-mono uppercase text-gray-400 mb-1.5">Parameter Konfigurasi</h5>
                  <div className="flex flex-wrap gap-1">
                    {selectedNode.data.params.map((p, idx) => (
                      <span
                        key={idx}
                        className="text-[9.5px] font-mono px-2 py-0.5 rounded bg-gray-900 border border-gray-700 text-cyan-300"
                      >
                        {p.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button
              onClick={() => setSelectedNode(null)}
              className="w-full py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-semibold text-gray-300 transition-colors mt-1"
            >
              Tutup Panel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default PipelineFlowCanvas;
