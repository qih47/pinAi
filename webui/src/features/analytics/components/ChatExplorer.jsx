import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, Users, Ghost, ChevronRight, RefreshCw, Shield
} from 'lucide-react';
import { ChatReplayModal } from './ChatReplayModal';
import apiClient from '../../../services/apiClient';

const formatDateShort = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
};

const formatDateFull = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const UserRow = ({ user, onOpenAudit }) => {
  const initials = user.is_guest
    ? '?'
    : (user.display_name || user.npp || '?').slice(0, 2).toUpperCase();
  const avatarBg = user.is_guest ? 'from-gray-600 to-gray-700' : 'from-cyan-700 to-blue-700';

  return (
    <div
      className="grid items-center gap-4 px-4 py-3 hover:bg-white/5 transition-colors cursor-pointer rounded-lg group border border-transparent hover:border-gray-800"
      style={{ gridTemplateColumns: '2.5rem 1fr 130px 80px 80px 90px 40px' }}
      onClick={() => onOpenAudit(user.npp)}
    >
      <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${avatarBg} flex items-center justify-center text-xs font-bold text-white shrink-0 select-none`}>
        {initials}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-200 truncate">
            {user.display_name || user.npp || 'Unknown'}
          </span>
          {user.is_guest ? (
            <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">GUEST</span>
          ) : (
            <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">{user.npp}</span>
          )}
        </div>
        <p className="text-xs text-gray-500 truncate mt-0.5">
          {user.divisi ? user.divisi : user.is_guest ? 'Guest User' : 'Pegawai Pindad'}
        </p>
      </div>
      <div className="text-xs text-gray-400 whitespace-nowrap" title={formatDateFull(user.last_active)}>
        {formatDateShort(user.last_active)}
      </div>
      <div className="text-center">
        <span className="text-sm font-bold text-gray-200">{user.total_sessions}</span>
        <p className="text-[10px] text-gray-600">sessions</p>
      </div>
      <div className="text-center">
        <span className="text-sm font-bold text-green-400">{user.active_sessions}</span>
        <p className="text-[10px] text-gray-600">active</p>
      </div>
      <div className="text-xs text-gray-500 whitespace-nowrap" title={formatDateFull(user.first_active)}>
        {formatDateShort(user.first_active)}
      </div>
      <button
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400"
        onClick={(e) => { e.stopPropagation(); onOpenAudit(user.npp); }}
        title="Buka Chat Audit"
      >
        <ChevronRight size={14} />
      </button>
    </div>
  );
};

export const ChatExplorer = () => {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState('last_active');
  const [page, setPage] = useState(0);
  const [auditNpp, setAuditNpp] = useState(null);
  const LIMIT = 50;

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/analytics/chat-explorer', {
        params: { search: debouncedSearch, filter_type: filterType, sort_by: sortBy, limit: LIMIT, offset: page * LIMIT }
      });
      if (res.data.status === 'success') {
        setUsers(res.data.users);
        setTotal(res.data.total);
      }
    } catch (e) {
      console.error('Chat Explorer fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, filterType, sortBy, page]);

  useEffect(() => { setPage(0); }, [debouncedSearch, filterType, sortBy]);
  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const registeredCount = users.filter(u => !u.is_guest).length;
  const guestCount = users.filter(u => u.is_guest).length;

  return (
    <>
      <div className="flex flex-col h-full min-h-0 gap-4">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-xl font-bold text-gray-100 flex items-center gap-2">
              <Users className="text-cyan-400" size={22} />
              Chat Explorer
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">Seluruh aktivitas percakapan pengguna CAKRA — registered & guest</p>
          </div>
          <button
            onClick={fetchUsers}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 text-sm transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 shrink-0">
          {[
            { label: 'Total Pengguna', value: total, icon: <Users size={16} />, color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/20' },
            { label: 'Registered', value: registeredCount, icon: <Shield size={16} />, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
            { label: 'Guest', value: guestCount, icon: <Ghost size={16} />, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
          ].map(s => (
            <div key={s.label} className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${s.bg} bg-[#0B0F19]`}>
              <div className={s.color}>{s.icon}</div>
              <div>
                <p className="text-xs text-gray-500">{s.label}</p>
                <p className={`text-xl font-bold ${s.color}`}>{s.value.toLocaleString()}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Toolbar */}
        <div className="flex gap-3 items-center shrink-0">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Cari nama, NPP, atau guest ID..."
              className="w-full pl-9 pr-4 py-2 bg-[#0B0F19] border border-gray-800 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-cyan-800 transition-colors"
            />
          </div>
          <div className="flex items-center gap-1 bg-[#0B0F19] border border-gray-800 rounded-lg p-1">
            {[
              { value: 'all', label: 'Semua' },
              { value: 'registered', label: 'Registered' },
              { value: 'guest', label: 'Guest' },
            ].map(f => (
              <button
                key={f.value}
                onClick={() => setFilterType(f.value)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filterType === f.value ? 'bg-cyan-500/20 text-cyan-400' : 'text-gray-500 hover:text-gray-300'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="px-3 py-2 bg-[#0B0F19] border border-gray-800 rounded-lg text-sm text-gray-400 focus:outline-none focus:border-cyan-800 transition-colors cursor-pointer"
          >
            <option value="last_active">Terakhir Aktif</option>
            <option value="total_sessions">Paling Banyak Chat</option>
            <option value="name">Nama A–Z</option>
          </select>
        </div>

        {/* Table */}
        <div className="flex-1 min-h-0 bg-[#0B0F19] border border-gray-800 rounded-xl overflow-hidden flex flex-col">
          <div
            className="grid items-center gap-4 px-4 py-2.5 border-b border-gray-800 bg-[#111827] shrink-0"
            style={{ gridTemplateColumns: '2.5rem 1fr 130px 80px 80px 90px 40px' }}
          >
            {['', 'Pengguna', 'Terakhir Aktif', 'Sessions', 'Aktif', 'Sejak', ''].map((h, i) => (
              <span key={i} className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider text-center first:text-left last:text-right">{h}</span>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-48 gap-3">
                <RefreshCw size={24} className="text-cyan-500 animate-spin" />
                <p className="text-sm text-gray-500">Memuat data pengguna...</p>
              </div>
            ) : users.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 gap-3">
                <Users size={32} className="text-gray-700" />
                <p className="text-sm text-gray-500">Tidak ada pengguna ditemukan</p>
              </div>
            ) : (
              users.map((user, idx) => (
                <UserRow key={`${user.npp}-${user.is_guest ? 'g' : 'r'}-${idx}`} user={user} onOpenAudit={setAuditNpp} />
              ))
            )}
          </div>

          {total > LIMIT && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800 shrink-0 bg-[#111827]">
              <span className="text-xs text-gray-500">
                Menampilkan {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} dari {total} pengguna
              </span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                  className="px-3 py-1.5 text-xs rounded-lg bg-gray-800 text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">← Prev</button>
                <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * LIMIT >= total}
                  className="px-3 py-1.5 text-xs rounded-lg bg-gray-800 text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">Next →</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {auditNpp && (
        <ChatReplayModal npp={auditNpp} onClose={() => setAuditNpp(null)} />
      )}
    </>
  );
};

export default ChatExplorer;
