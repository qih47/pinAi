import React from 'react';

/**
 * W15 — RAG Metrics Component
 * Displays search execution duration, embedding cache status (hit/miss), and citation counts.
 */
const RAGMetrics = ({ sources, darkMode, theme }) => {
  if (!sources || sources.length === 0) return null;

  // Extract metrics from the first source
  const searchTimeMs = sources[0].search_time_ms;
  const isCacheHit = sources[0].cache_hit;

  if (searchTimeMs === undefined) return null;

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 600,
    background: darkMode ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.03)',
    border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)'}`,
    color: theme?.textColor || (darkMode ? '#cbd5e1' : '#475569'),
    transition: 'all 0.2s ease',
    marginBottom: '10px',
  };

  const statusDotStyle = (active) => ({
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: active ? '#10b981' : '#3b82f6', // Green for cache hit, blue for live Ollama
    boxShadow: active ? '0 0 8px #10b981' : '0 0 8px #3b82f6',
    display: 'inline-block',
  });

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
      <div style={badgeStyle} title="Lama waktu pencarian regulasi internal di database">
        <span>⏱️ Found in {searchTimeMs}ms</span>
      </div>
      <div style={badgeStyle} title={isCacheHit ? "Embedding diambil dari LRU Cache (instan)" : "Embedding dihitung via Ollama Model"}>
        <span style={statusDotStyle(isCacheHit)} />
        <span>{isCacheHit ? '🧠 Cache Hit' : '🌐 Live Ollama Embed'}</span>
      </div>
      <div style={badgeStyle}>
        <span>📄 {sources.length} Rujukan Terpilih</span>
      </div>
    </div>
  );
};

export default RAGMetrics;
