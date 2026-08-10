import React from 'react';
import { translations } from '../../../utils/translations';

/**
 * W15 — RAG Metrics Component
 * Displays search execution duration, embedding cache status (hit/miss), and citation counts.
 */
const RAGMetrics = ({ sources, eval_count, eval_duration, darkMode, theme, language = 'id' }) => {
  const t = translations[language]?.chat || translations.id.chat;
  const hasSources = sources && sources.length > 0;
  const hasMetrics = eval_count > 0 && eval_duration > 0;
  
  if (!hasSources && !hasMetrics) return null;

  // Extract metrics from the first source
  const searchTimeMs = hasSources ? sources[0].search_time_ms : undefined;
  const isCacheHit = hasSources ? sources[0].cache_hit : false;
  
  const tps = hasMetrics ? (eval_count / (eval_duration / 1e9)).toFixed(1) : null;

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

  const statusDotStyle = (active, color = null) => ({
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: color ? color : (active ? '#10b981' : '#3b82f6'),
    boxShadow: color ? `0 0 8px ${color}` : (active ? '0 0 8px #10b981' : '0 0 8px #3b82f6'),
    display: 'inline-block',
  });

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
      {hasSources && searchTimeMs !== undefined && (
        <div style={badgeStyle} title="Lama waktu pencarian regulasi internal di database">
          <span>⏱️ {t.foundIn} {searchTimeMs}ms</span>
        </div>
      )}
      {hasSources && (
        <div style={badgeStyle} title={isCacheHit ? "Embedding diambil dari LRU Cache (instan)" : "Embedding dihitung via Ollama Model"}>
          <span style={statusDotStyle(isCacheHit)} />
          <span>{isCacheHit ? '🧠 Cache Hit' : `🌐 ${t.liveOllamaEmbed}`}</span>
        </div>
      )}
      {hasSources && (
        <div style={badgeStyle}>
          <span>📄 {sources.length} {t.selectedRefs}</span>
        </div>
      )}
      {hasMetrics && (
        <div style={badgeStyle} title={`Generated ${eval_count} tokens in ${(eval_duration / 1e9).toFixed(2)}s`}>
          <span style={statusDotStyle(true, '#8b5cf6')} />
          <span>⚡ {tps} Tokens/sec</span>
        </div>
      )}
    </div>
  );
};

export default RAGMetrics;
