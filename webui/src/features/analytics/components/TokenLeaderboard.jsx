import React, { useState, useEffect } from 'react';
import { Users, Trophy, Eye, MessageSquare, Clock } from 'lucide-react';
import apiClient from '../../../services/apiClient';
import { ChatReplayModal } from './ChatReplayModal';

const RANK_STYLE = [
  'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40',
  'bg-gray-400/20 text-gray-300 border border-gray-400/40',
  'bg-amber-700/20 text-amber-500 border border-amber-700/40',
];

const formatTimeAgo = (isoStr) => {
  if (!isoStr) return '—';
  const diff = Date.now() - new Date(isoStr).getTime();
  const h = Math.floor(diff / 3600000);
  const d = Math.floor(diff / 86400000);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  return 'Just now';
};

export const TokenLeaderboard = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAuditNpp, setSelectedAuditNpp] = useState(null);

  const fetchLeaderboard = async () => {
    try {
      const res = await apiClient.get('/analytics/users/leaderboard');
      if (res.data.status === 'success') {
        setUsers(res.data.leaderboard);
      }
    } catch (e) {
      console.error('Failed to fetch leaderboard', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
    const interval = setInterval(fetchLeaderboard, 15000);
    return () => clearInterval(interval);
  }, []);

  const maxTokens = users[0]?.tokens || 1;

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold tracking-widest text-yellow-500 uppercase flex items-center gap-2">
          <Trophy size={15}/> Top Token Consumers
        </h3>
        <span className="text-[10px] text-gray-600 border border-gray-800 px-2 py-0.5 rounded font-mono">7-day window</span>
      </div>

      {/* Body */}
      {loading && users.length === 0 ? (
        <div className="animate-pulse flex flex-col gap-3">
          {[1, 2, 3].map(i => <div key={i} className="h-14 bg-gray-800 rounded-lg"/>)}
        </div>
      ) : users.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-gray-600">
          <Users size={32} className="opacity-20"/>
          <p className="text-sm">Belum ada data aktivitas pengguna.</p>
          <p className="text-xs text-gray-700">Data akan muncul setelah ada percakapan dengan CAKRA.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {users.map((u, i) => {
            const pct = Math.round((u.tokens / maxTokens) * 100);
            return (
              <button
                key={i}
                onClick={() => setSelectedAuditNpp(u.npp)}
                className="w-full flex flex-col gap-2 p-3 rounded-xl bg-[#0d1117] border border-gray-800 hover:border-cyan-800 hover:bg-cyan-950/20 transition-all group text-left"
              >
                {/* Top row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center font-black text-xs shrink-0 ${RANK_STYLE[i] || 'bg-gray-800 text-gray-500'}`}>
                      {i + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-gray-200 text-sm">NPP {u.npp}</span>
                        <Eye size={12} className="text-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity"/>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-[10px] text-gray-500 flex items-center gap-1">
                          <MessageSquare size={9}/> {(u.msgs || Math.round(u.tokens / 450)).toLocaleString()} msgs
                        </span>
                        {u.last_active && (
                          <span className="text-[10px] text-gray-600 flex items-center gap-1">
                            <Clock size={9}/> {formatTimeAgo(u.last_active)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <span className="font-mono text-sm font-black text-yellow-400">
                    {u.tokens.toLocaleString()} <span className="text-yellow-700 text-[10px] font-normal">Tk</span>
                  </span>
                </div>
                {/* Token bar */}
                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000"
                    style={{
                      width: `${pct}%`,
                      background: i === 0
                        ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                        : i === 1
                        ? 'linear-gradient(90deg, #9ca3af, #d1d5db)'
                        : i === 2
                        ? 'linear-gradient(90deg, #b45309, #d97706)'
                        : 'linear-gradient(90deg, #374151, #4b5563)',
                    }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      )}

      {selectedAuditNpp && (
        <ChatReplayModal npp={selectedAuditNpp} onClose={() => setSelectedAuditNpp(null)}/>
      )}
    </div>
  );
};
