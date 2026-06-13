import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatAuthStore } from '@/stores/authStore';
import { 
  fetchCacheStats, 
  clearEmbeddingCache, 
  fetchVectorIndexStatus, 
  optimizeVectorIndex 
} from '@/services/endpoints';

/**
 * W13 & W15 — Cache & Vector Search Performance Admin Page
 * Standalone dark-themed dashboard presenting cache metrics and database HNSW index health.
 */
const CacheStatsPage = () => {
  const navigate = useNavigate();
  const { user, checkSession } = useChatAuthStore();
  const isAdmin = user?.role === 'admin';

  // State Management
  const [cacheStats, setCacheStats] = useState(null);
  const [indexStatus, setIndexStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isClearing, setIsClearing] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Auto-clear notification toast after 4s
  useEffect(() => {
    if (successMessage || errorMessage) {
      const timer = setTimeout(() => {
        setSuccessMessage('');
        setErrorMessage('');
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [successMessage, errorMessage]);

  // Load Dashboard Data
  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const [cacheData, indexData] = await Promise.all([
        fetchCacheStats(),
        fetchVectorIndexStatus()
      ]);

      if (cacheData.status === 'success') {
        setCacheStats(cacheData.stats);
      }
      if (indexData.status === 'success') {
        setIndexStatus(indexData);
      }
    } catch (err) {
      console.error('Failed to load performance metrics:', err);
      setErrorMessage(err.message || 'Gagal memuat metrik performa sistem.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Check authentication & load data
  useEffect(() => {
    const initPage = async () => {
      await checkSession();
      if (user && user.role !== 'admin') {
        // Redirect non-admin users to chat page
        navigate('/chat/guest');
      } else {
        loadDashboardData();
      }
    };
    initPage();
  }, [user, checkSession, navigate, loadDashboardData]);

  // Clear Embedding Cache handler
  const handleClearCache = async () => {
    if (!window.confirm('Apakah Anda yakin ingin mengosongkan cache embedding? Pencarian pertama setelah ini akan menjadi sedikit lebih lambat.')) {
      return;
    }
    
    setIsClearing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const response = await clearEmbeddingCache();
      if (response.status === 'success') {
        setSuccessMessage('Cache embedding berhasil dikosongkan!');
        // Refresh cache stats
        const cacheData = await fetchCacheStats();
        if (cacheData.status === 'success') {
          setCacheStats(cacheData.stats);
        }
      }
    } catch (err) {
      setErrorMessage(err.message || 'Gagal mengosongkan cache.');
    } finally {
      setIsClearing(false);
    }
  };

  // Optimize Vector Index (Vacuum Analyze) handler
  const handleOptimizeIndex = async () => {
    setIsOptimizing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const response = await optimizeVectorIndex();
      if (response.status === 'success') {
        setSuccessMessage('Optimasi VACUUM ANALYZE berhasil diselesaikan!');
        // Refresh index status
        const indexData = await fetchVectorIndexStatus();
        if (indexData.status === 'success') {
          setIndexStatus(indexData);
        }
      }
    } catch (err) {
      setErrorMessage(err.message || 'Gagal menjalankan optimasi index.');
    } finally {
      setIsOptimizing(false);
    }
  };

  // Custom Cyberpunk Styles
  const pageContainerStyle = {
    minHeight: '100vh',
    background: '#09090b',
    color: '#f4f4f5',
    padding: '24px',
    fontFamily: '"Outfit", "Inter", sans-serif',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    overflowX: 'hidden'
  };

  const headerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: '20px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    marginBottom: '30px'
  };

  const titleGroupStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px'
  };

  const titleStyle = {
    fontSize: '24px',
    fontWeight: 800,
    background: 'linear-gradient(to right, #a78bfa, #6366f1, #3b82f6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-0.025em'
  };

  const subtitleStyle = {
    fontSize: '12px',
    color: '#a1a1aa',
    fontWeight: 500
  };

  const backButtonStyle = {
    background: 'rgba(255, 255, 255, 0.04)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    color: '#f4f4f5',
    padding: '8px 16px',
    borderRadius: '24px',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    transition: 'all 0.2s ease-out'
  };

  const dashboardGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
    gap: '24px',
    width: '100%',
    maxWidth: '1200px',
    margin: '0 auto'
  };

  const cardStyle = {
    background: '#121214',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    borderRadius: '20px',
    padding: '24px',
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 4px 30px rgba(0, 0, 0, 0.2)'
  };

  const cardHeaderStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
    paddingBottom: '12px'
  };

  const cardTitleStyle = {
    fontSize: '16px',
    fontWeight: 700,
    color: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  const statusBadgeStyle = (active) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '11px',
    fontWeight: 700,
    background: active ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
    color: active ? '#34d399' : '#f87171',
    border: active ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid rgba(239, 68, 68, 0.2)'
  });

  const pulsingDotStyle = (active) => ({
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: active ? '#10b981' : '#ef4444',
    animation: active ? 'pulse 2s infinite' : 'none',
    display: 'inline-block'
  });

  const buttonStyle = (variant, disabled) => ({
    marginTop: 'auto',
    padding: '12px 20px',
    borderRadius: '24px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    border: 'none',
    transition: 'all 0.2s ease',
    opacity: disabled ? 0.6 : 1,
    background: variant === 'danger' 
      ? 'linear-gradient(to right, #ef4444, #dc2626)' 
      : 'linear-gradient(to right, #6366f1, #4f46e5)',
    color: '#ffffff',
    boxShadow: variant === 'danger'
      ? '0 4px 14px 0 rgba(239, 68, 68, 0.3)'
      : '0 4px 14px 0 rgba(99, 102, 241, 0.3)'
  });

  const toastStyle = (type) => ({
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    padding: '12px 24px',
    borderRadius: '12px',
    fontSize: '13px',
    fontWeight: 600,
    boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: type === 'success' ? '#064e3b' : '#7f1d1d',
    color: type === 'success' ? '#34d399' : '#f87171',
    border: `1px solid ${type === 'success' ? '#059669' : '#dc2626'}`
  });

  const metricBlockStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    background: 'rgba(255, 255, 255, 0.02)',
    padding: '14px 18px',
    borderRadius: '16px',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    flex: 1
  };

  const metricLabelStyle = {
    fontSize: '11px',
    color: '#a1a1aa',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  };

  const metricValueStyle = {
    fontSize: '18px',
    fontWeight: 800,
    color: '#ffffff'
  };

  const chartAreaStyle = {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    margin: '16px 0',
    position: 'relative'
  };

  // Helper to render circular progress ring
  const ProgressDial = ({ percentage, color = '#6366f1', label = 'Hit Rate' }) => {
    const cleanPercent = Math.max(0, Math.min(100, percentage || 0));
    const radius = 50;
    const stroke = 8;
    const normalizedRadius = radius - stroke * 2;
    const circumference = normalizedRadius * 2 * Math.PI;
    const strokeDashoffset = circumference - (cleanPercent / 100) * circumference;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <svg height={radius * 2} width={radius * 2}>
          <circle
            stroke="rgba(255, 255, 255, 0.04)"
            fill="transparent"
            strokeWidth={stroke}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
          />
          <circle
            stroke={color}
            fill="transparent"
            strokeWidth={stroke}
            strokeDasharray={circumference + ' ' + circumference}
            style={{ strokeDashoffset, transition: 'stroke-dashoffset 0.8s ease' }}
            strokeLinecap="round"
            r={normalizedRadius}
            cx={radius}
            cy={radius}
            transform={`rotate(-90 ${radius} ${radius})`}
          />
          <text
            x="50%"
            y="52%"
            textAnchor="middle"
            fill="#ffffff"
            fontSize="14px"
            fontWeight="bold"
            dy=".3em"
          >
            {Math.round(cleanPercent)}%
          </text>
        </svg>
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#a1a1aa' }}>{label}</span>
      </div>
    );
  };

  if (!isAdmin) {
    return null; // Let useEffect handle redirect
  }

  return (
    <div style={pageContainerStyle}>
      {/* Dynamic Keyframes inject */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.9); }
        }
        button:hover {
          filter: brightness(1.1);
          transform: translateY(-1px);
        }
        button:active {
          transform: translateY(0);
        }
      `}</style>

      {/* Header bar */}
      <div style={headerStyle}>
        <div style={titleGroupStyle}>
          <h1 style={titleStyle}>Performance & Cache Dashboard</h1>
          <span style={subtitleStyle}>
            Admin Panel — Monitor LRU embedding cache & pgvector HNSW search indices.
          </span>
        </div>
        <button 
          onClick={() => navigate('/chat/guest')} 
          style={backButtonStyle}
        >
          <span>🔙 Kembali ke Obrolan</span>
        </button>
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: '16px' }}>
          <div style={{ width: '40px', height: '40px', border: '3px solid rgba(99, 102, 241, 0.2)', borderTop: '3px solid #6366f1', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '13px', color: '#a1a1aa', fontWeight: 600 }}>Memuat metrik performa database...</span>
        </div>
      ) : (
        <div style={dashboardGridStyle}>
          
          {/* Card 1: Embedding Cache Stats (W13) */}
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div style={cardTitleStyle}>
                <span>🧠 Embedding LRU Cache</span>
              </div>
              <div style={statusBadgeStyle(true)}>
                <span style={pulsingDotStyle(true)} />
                <span>ACTIVE</span>
              </div>
            </div>

            {cacheStats ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
                <div style={{ display: 'flex', gap: '14px' }}>
                  <div style={metricBlockStyle}>
                    <span style={metricLabelStyle}>Entries</span>
                    <span style={metricValueStyle}>
                      {cacheStats.total_entries} / {cacheStats.max_size}
                    </span>
                  </div>
                  <div style={metricBlockStyle}>
                    <span style={metricLabelStyle}>TTL</span>
                    <span style={metricValueStyle}>1 Jam</span>
                  </div>
                </div>

                <div style={chartAreaStyle}>
                  <div style={{ display: 'flex', gap: '30px' }}>
                    <ProgressDial 
                      percentage={cacheStats.utilization_percent} 
                      color="#3b82f6" 
                      label="Kapasitas Cache" 
                    />
                    <ProgressDial 
                      percentage={cacheStats.hit_rate_percent} 
                      color="#10b981" 
                      label="Hit Rate" 
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '10px', fontSize: '12px', color: '#a1a1aa', margin: '8px 0', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '12px' }}>
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <strong>{cacheStats.hits}</strong> hits
                  </div>
                  <div style={{ width: '1px', background: 'rgba(255,255,255,0.08)' }} />
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <strong>{cacheStats.misses}</strong> misses
                  </div>
                </div>

                <button
                  onClick={handleClearCache}
                  disabled={isClearing}
                  style={buttonStyle('danger', isClearing)}
                >
                  {isClearing ? 'Mengosongkan Cache...' : '🧹 Kosongkan Embedding Cache'}
                </button>
              </div>
            ) : (
              <div style={{ color: '#a1a1aa', textAlign: 'center', padding: '40px 0' }}>
                Gagal memuat statistik cache.
              </div>
            )}
          </div>

          {/* Card 2: HNSW Vector Search Performance (W15) */}
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <div style={cardTitleStyle}>
                <span>⚡ Vector HNSW Index Status</span>
              </div>
              <div style={statusBadgeStyle(indexStatus?.hnsw_active)}>
                <span style={pulsingDotStyle(indexStatus?.hnsw_active)} />
                <span>{indexStatus?.hnsw_active ? 'INDEX ACTIVE' : 'INACTIVE'}</span>
              </div>
            </div>

            {indexStatus ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', gap: '14px' }}>
                    <div style={metricBlockStyle}>
                      <span style={metricLabelStyle}>Total Chunks</span>
                      <span style={metricValueStyle}>{indexStatus.stats?.total_chunks || 0} Chunks</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '14px' }}>
                    <div style={metricBlockStyle}>
                      <span style={metricLabelStyle}>Table Size</span>
                      <span style={metricValueStyle}>{indexStatus.stats?.table_size || '0 kB'}</span>
                    </div>
                    <div style={metricBlockStyle}>
                      <span style={metricLabelStyle}>Total w/ Index</span>
                      <span style={metricValueStyle}>{indexStatus.stats?.total_with_indexes || '0 kB'}</span>
                    </div>
                  </div>
                </div>

                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <span style={metricLabelStyle}>Index List:</span>
                  <div style={{ maxHeight: '120px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.03)' }}>
                    {indexStatus.indexes && indexStatus.indexes.length > 0 ? (
                      indexStatus.indexes.map((idx, i) => (
                        <div key={i} style={{ fontSize: '11px', paddingBottom: '6px', borderBottom: i < indexStatus.indexes.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none', marginBottom: '6px' }}>
                          <div style={{ fontWeight: 700, color: '#818cf8', marginBottom: '2px' }}>{idx.name} ({idx.size})</div>
                          <div style={{ color: '#71717a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{idx.definition}</div>
                          <div style={{ color: '#a1a1aa', marginTop: '2px' }}>Scans: {idx.scans} | Read: {idx.tuples_read}</div>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '11px', color: '#71717a', textAlign: 'center' }}>Tidak ada index terdaftar</div>
                    )}
                  </div>
                </div>

                <button
                  onClick={handleOptimizeIndex}
                  disabled={isOptimizing}
                  style={buttonStyle('primary', isOptimizing)}
                >
                  {isOptimizing ? 'Mengoptimasi Index...' : '🔧 Jalankan Vacuum & Optimize Index'}
                </button>
              </div>
            ) : (
              <div style={{ color: '#a1a1aa', textAlign: 'center', padding: '40px 0' }}>
                Gagal memuat statistik vector index.
              </div>
            )}
          </div>

        </div>
      )}

      {/* SUCCESS TOAST */}
      {successMessage && (
        <div style={toastStyle('success')}>
          <span>✅</span>
          <span>{successMessage}</span>
        </div>
      )}

      {/* ERROR TOAST */}
      {errorMessage && (
        <div style={toastStyle('error')}>
          <span>🚨</span>
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};

export default CacheStatsPage;
