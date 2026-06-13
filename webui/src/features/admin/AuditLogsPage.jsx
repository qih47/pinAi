import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatAuthStore } from '@/stores/authStore';
import { fetchAuditLogs, fetchAuditStats, exportAuditLogs, downloadAuditExport } from '@/services/auditService';

// ===================================================================
// AUDIT LOG EVENT TYPES
// ===================================================================
const EVENT_TYPES = [
  { value: 'ALL', label: 'Semua Event', emoji: '📋' },
  { value: 'LOGIN', label: 'Login', emoji: '🔐' },
  { value: 'LOGOUT', label: 'Logout', emoji: '🚪' },
  { value: 'LOGIN_FAILED', label: 'Login Gagal', emoji: '❌' },
  { value: 'CHAT', label: 'Chat', emoji: '💬' },
  { value: 'UPLOAD', label: 'Upload Dokumen', emoji: '📎' },
  { value: 'ADMIN', label: 'Aksi Admin', emoji: '⚙️' },
];

// ===================================================================
// STYLE HELPERS
// ===================================================================
const getEventBadgeStyle = (eventType) => {
  const map = {
    LOGIN: { bg: 'rgba(34,197,94,0.12)', color: '#22c55e', border: 'rgba(34,197,94,0.25)' },
    LOGOUT: { bg: 'rgba(148,163,184,0.12)', color: '#94a3b8', border: 'rgba(148,163,184,0.25)' },
    LOGIN_FAILED: { bg: 'rgba(239,68,68,0.12)', color: '#ef4444', border: 'rgba(239,68,68,0.25)' },
    CHAT: { bg: 'rgba(99,102,241,0.12)', color: '#6366f1', border: 'rgba(99,102,241,0.25)' },
    UPLOAD: { bg: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: 'rgba(245,158,11,0.25)' },
    ADMIN: { bg: 'rgba(168,85,247,0.12)', color: '#a855f7', border: 'rgba(168,85,247,0.25)' },
  };
  return map[eventType] || { bg: 'rgba(100,116,139,0.12)', color: '#64748b', border: 'rgba(100,116,139,0.25)' };
};

const formatTimestamp = (ts) => {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleString('id-ID', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
};

// ===================================================================
// STAT CARD
// ===================================================================
function StatCard({ icon, label, value, color, trend }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '16px',
      padding: '20px 24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      flex: '1 1 180px',
      minWidth: 0,
      transition: 'all 0.2s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '22px' }}>{icon}</span>
        <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: '28px', fontWeight: 700, color: color || '#e2e8f0', lineHeight: 1 }}>
        {value?.toLocaleString('id-ID') ?? '—'}
      </div>
      {trend && (
        <div style={{ fontSize: '11px', color: '#64748b' }}>{trend}</div>
      )}
    </div>
  );
}

// ===================================================================
// MAIN AUDIT LOG PAGE
// ===================================================================
export default function AuditLogsPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useChatAuthStore();

  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState('ALL');
  const [nppFilter, setNppFilter] = useState('');
  const [daysFilter, setDaysFilter] = useState(7);

  // Data
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const PAGE_SIZE = 50;

  // UI State
  const [isLoading, setIsLoading] = useState(true);
  const [isStatsLoading, setIsStatsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState('csv');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportRef = useRef(null);

  // Check admin access
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, navigate]);

  // Fetch stats once
  const loadStats = useCallback(async () => {
    setIsStatsLoading(true);
    try {
      const data = await fetchAuditStats();
      setStats(data?.data || data);
    } catch (err) {
      console.error('Failed to load audit stats:', err);
      // Use mock data if backend not available yet
      setStats({
        total_logins: null,
        unique_users: null,
        failed_attempts: null,
        total_events: null,
      });
    } finally {
      setIsStatsLoading(false);
    }
  }, []);

  // Fetch logs with current filters
  const loadLogs = useCallback(async (currentOffset = 0) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchAuditLogs({
        event_type: eventTypeFilter,
        npp: nppFilter,
        days: daysFilter,
        limit: PAGE_SIZE,
        offset: currentOffset,
      });
      const data = result?.data || result;
      setLogs(Array.isArray(data) ? data : (data?.items || []));
      setTotalCount(result?.total || result?.count || (Array.isArray(data) ? data.length : 0));
    } catch (err) {
      console.error('Failed to load audit logs:', err);
      setError(`Gagal memuat audit log: ${err.message}`);
      setLogs([]);
    } finally {
      setIsLoading(false);
    }
  }, [eventTypeFilter, nppFilter, daysFilter]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    setOffset(0);
    loadLogs(0);
  }, [loadLogs]);

  // Close export menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (exportRef.current && !exportRef.current.contains(e.target)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleExport = async (fmt) => {
    setIsExporting(true);
    setShowExportMenu(false);
    try {
      const blob = await exportAuditLogs(fmt, {
        event_type: eventTypeFilter,
        npp: nppFilter,
        days: daysFilter,
      });
      downloadAuditExport(blob, fmt);
    } catch (err) {
      alert(`Gagal export: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const handlePageChange = (newOffset) => {
    setOffset(newOffset);
    loadLogs(newOffset);
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1117',
      color: '#e2e8f0',
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      padding: '0',
    }}>
      {/* =========================================================
          HEADER BAR
      ========================================================= */}
      <div style={{
        background: 'rgba(21,21,23,0.98)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        height: '64px',
        gap: '16px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        backdropFilter: 'blur(12px)',
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '10px',
            color: '#94a3b8',
            padding: '7px 14px',
            fontSize: '13px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.2s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = '#e2e8f0'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#94a3b8'; }}
        >
          ← Kembali
        </button>

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '20px' }}>🛡️</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#e2e8f0' }}>
              Audit Log Viewer
            </h1>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>
              Admin Compliance Dashboard — CAKRA AI
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#64748b' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          {user?.fullname || user?.name || 'Admin'}
        </div>

        {/* Export Button */}
        <div ref={exportRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setShowExportMenu(!showExportMenu)}
            disabled={isExporting}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none',
              borderRadius: '10px',
              color: '#fff',
              padding: '8px 16px',
              fontSize: '13px',
              cursor: isExporting ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              opacity: isExporting ? 0.7 : 1,
              transition: 'all 0.2s',
            }}
          >
            {isExporting ? '⏳ Exporting...' : '📥 Export'}
          </button>
          {showExportMenu && (
            <div style={{
              position: 'absolute',
              top: '110%',
              right: 0,
              background: '#1e1e24',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              padding: '8px',
              minWidth: '160px',
              zIndex: 200,
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            }}>
              <button onClick={() => handleExport('csv')} style={exportMenuItemStyle}>
                📊 Export CSV
              </button>
              <button onClick={() => handleExport('json')} style={exportMenuItemStyle}>
                📄 Export JSON
              </button>
            </div>
          )}
        </div>
      </div>

      {/* =========================================================
          MAIN CONTENT
      ========================================================= */}
      <div style={{ padding: '32px', maxWidth: '1400px', margin: '0 auto' }}>

        {/* STATS ROW */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '28px' }}>
          <StatCard
            icon="🔐"
            label="Total Login"
            value={stats?.total_logins}
            color="#22c55e"
            trend={isStatsLoading ? 'Memuat...' : null}
          />
          <StatCard
            icon="👥"
            label="Pengguna Unik"
            value={stats?.unique_users}
            color="#6366f1"
          />
          <StatCard
            icon="❌"
            label="Login Gagal"
            value={stats?.failed_attempts}
            color="#ef4444"
          />
          <StatCard
            icon="📋"
            label="Total Event"
            value={stats?.total_events || totalCount}
            color="#f59e0b"
          />
        </div>

        {/* FILTER ROW */}
        <div style={{
          display: 'flex',
          gap: '12px',
          flexWrap: 'wrap',
          alignItems: 'center',
          marginBottom: '20px',
          padding: '16px 20px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '16px',
        }}>
          <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 600, flexShrink: 0 }}>Filter:</span>

          {/* Event Type */}
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            style={selectStyle}
          >
            {EVENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.emoji} {t.label}</option>
            ))}
          </select>

          {/* NPP */}
          <input
            type="text"
            placeholder="Filter NPP..."
            value={nppFilter}
            onChange={(e) => setNppFilter(e.target.value)}
            style={{ ...inputStyle, width: '140px' }}
          />

          {/* Days */}
          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            style={selectStyle}
          >
            <option value={1}>1 Hari</option>
            <option value={7}>7 Hari</option>
            <option value={14}>14 Hari</option>
            <option value={30}>30 Hari</option>
            <option value={90}>3 Bulan</option>
          </select>

          <button
            onClick={() => { setOffset(0); loadLogs(0); }}
            style={refreshBtnStyle}
          >
            🔄 Refresh
          </button>

          {totalCount > 0 && (
            <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#64748b' }}>
              {totalCount.toLocaleString('id-ID')} records
            </span>
          )}
        </div>

        {/* TABLE */}
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '16px',
          overflow: 'hidden',
        }}>
          {/* Table Header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '180px 100px 120px 1fr 120px 70px',
            padding: '12px 20px',
            background: 'rgba(255,255,255,0.04)',
            borderBottom: '1px solid rgba(255,255,255,0.07)',
            fontSize: '11px',
            fontWeight: 700,
            color: '#64748b',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            gap: '8px',
          }}>
            <span>Timestamp</span>
            <span>NPP</span>
            <span>Event</span>
            <span>Detail / IP</span>
            <span>IP Address</span>
            <span>Status</span>
          </div>

          {/* Table Body */}
          {isLoading ? (
            <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
              <div>Memuat audit log...</div>
            </div>
          ) : error ? (
            <div style={{ padding: '48px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
              <div style={{ color: '#ef4444', fontSize: '14px', marginBottom: '8px' }}>{error}</div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                Endpoint backend mungkin belum terhubung.
              </div>
            </div>
          ) : logs.length === 0 ? (
            <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
              <div>Tidak ada audit log yang ditemukan</div>
              <div style={{ fontSize: '12px', marginTop: '6px' }}>Coba ubah filter atau rentang tanggal</div>
            </div>
          ) : (
            logs.map((log, idx) => {
              const eventStyle = getEventBadgeStyle(log.event_type);
              const isEven = idx % 2 === 0;
              const isSuccess = log.status === 'SUCCESS' || log.status === 'success' || !log.status;
              return (
                <div
                  key={log.id || idx}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '180px 100px 120px 1fr 120px 70px',
                    padding: '12px 20px',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    fontSize: '12px',
                    gap: '8px',
                    alignItems: 'center',
                    background: isEven ? 'transparent' : 'rgba(255,255,255,0.01)',
                    transition: 'background 0.15s',
                    cursor: 'default',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.05)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = isEven ? 'transparent' : 'rgba(255,255,255,0.01)'; }}
                >
                  <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: '11px' }}>
                    {formatTimestamp(log.created_at || log.timestamp)}
                  </span>
                  <span style={{ color: '#e2e8f0', fontWeight: 600 }}>
                    {log.npp || '—'}
                  </span>
                  <span>
                    <span style={{
                      background: eventStyle.bg,
                      color: eventStyle.color,
                      border: `1px solid ${eventStyle.border}`,
                      borderRadius: '8px',
                      padding: '2px 8px',
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '0.3px',
                    }}>
                      {log.event_type || 'UNKNOWN'}
                    </span>
                  </span>
                  <span style={{ color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    title={log.description || log.detail || ''}>
                    {log.description || log.detail || log.action || '—'}
                  </span>
                  <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '11px' }}>
                    {log.ip_address || log.ip || '—'}
                  </span>
                  <span>
                    <span style={{
                      background: isSuccess ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: isSuccess ? '#22c55e' : '#ef4444',
                      borderRadius: '6px',
                      padding: '2px 8px',
                      fontSize: '10px',
                      fontWeight: 600,
                    }}>
                      {log.status || 'OK'}
                    </span>
                  </span>
                </div>
              );
            })
          )}
        </div>

        {/* PAGINATION */}
        {totalPages > 1 && (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px',
            marginTop: '20px',
          }}>
            <button
              onClick={() => handlePageChange(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              style={pageBtnStyle(offset === 0)}
            >
              ← Sebelumnya
            </button>
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>
              Halaman {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => handlePageChange(offset + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= totalCount}
              style={pageBtnStyle(offset + PAGE_SIZE >= totalCount)}
            >
              Selanjutnya →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ===================================================================
// STYLE HELPERS
// ===================================================================
const selectStyle = {
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px',
  color: '#e2e8f0',
  padding: '8px 12px',
  fontSize: '12px',
  cursor: 'pointer',
  outline: 'none',
};

const inputStyle = {
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px',
  color: '#e2e8f0',
  padding: '8px 12px',
  fontSize: '12px',
  outline: 'none',
};

const refreshBtnStyle = {
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px',
  color: '#94a3b8',
  padding: '8px 14px',
  fontSize: '12px',
  cursor: 'pointer',
  fontWeight: 600,
  transition: 'all 0.2s',
};

const exportMenuItemStyle = {
  display: 'block',
  width: '100%',
  background: 'transparent',
  border: 'none',
  color: '#e2e8f0',
  padding: '10px 14px',
  fontSize: '13px',
  cursor: 'pointer',
  textAlign: 'left',
  borderRadius: '8px',
  transition: 'background 0.15s',
};

const pageBtnStyle = (disabled) => ({
  background: disabled ? 'rgba(255,255,255,0.02)' : 'rgba(99,102,241,0.12)',
  border: `1px solid ${disabled ? 'rgba(255,255,255,0.05)' : 'rgba(99,102,241,0.3)'}`,
  borderRadius: '10px',
  color: disabled ? '#475569' : '#818cf8',
  padding: '8px 16px',
  fontSize: '12px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontWeight: 600,
  transition: 'all 0.2s',
});
