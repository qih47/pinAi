import React, { useState, useEffect } from 'react';
import { Target, ThumbsUp, ThumbsDown, AlertTriangle } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const QualityRadar = () => {
  const [metrics, setMetrics] = useState({ upvotes: 0, downvotes: 0, total_ratings: 0 });
  const [loading, setLoading] = useState(true);

  const fetchQuality = async () => {
    try {
      const res = await apiClient.get('/analytics/quality');
      if (res.data.status === 'success') {
        setMetrics(res.data.metrics);
      }
    } catch (e) {
      console.error("Failed to fetch quality metrics", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuality();
    const interval = setInterval(fetchQuality, 30000); // 30s polling
    return () => clearInterval(interval);
  }, []);

  const totalVotes = metrics.upvotes + metrics.downvotes;
  const downvoteRatio = totalVotes > 0 ? (metrics.downvotes / totalVotes) * 100 : 0;
  const isHighHallucination = downvoteRatio > 30;

  return (
    <div className={`border rounded-xl p-6 h-full flex flex-col transition-colors ${
      isHighHallucination ? 'bg-red-950/20 border-red-900' : 'bg-[#0B0F19]/90 border-gray-800'
    }`}>
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-bold tracking-widest uppercase flex items-center gap-2 text-gray-400">
          <Target size={16} className={isHighHallucination ? 'text-red-500' : 'text-purple-500'} /> 
          AI Quality Radar
        </h3>
        
        {isHighHallucination && (
          <span className="flex items-center gap-1 bg-red-500/20 text-red-500 px-2 py-1 rounded text-xs font-bold border border-red-500/50 animate-pulse">
            <AlertTriangle size={14} /> HALLUCINATION ALERT
          </span>
        )}
      </div>

      <div className="flex-1 flex flex-col justify-center">
        {loading && totalVotes === 0 ? (
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-800 rounded w-1/2 mx-auto"></div>
            <div className="h-4 bg-gray-800 rounded w-full"></div>
          </div>
        ) : (
          <>
            <div className="flex justify-center items-end gap-8 mb-8">
              <div className="flex flex-col items-center">
                <ThumbsUp size={32} className="text-emerald-500 mb-2" />
                <span className="text-3xl font-bold text-gray-200">{metrics.upvotes}</span>
                <span className="text-xs text-gray-500 uppercase tracking-wider mt-1">High Quality</span>
              </div>
              <div className="flex flex-col items-center">
                <ThumbsDown size={32} className={isHighHallucination ? 'text-red-500' : 'text-orange-500'} style={{ marginBottom: '0.5rem' }} />
                <span className={`text-3xl font-bold ${isHighHallucination ? 'text-red-500' : 'text-gray-200'}`}>{metrics.downvotes}</span>
                <span className="text-xs text-gray-500 uppercase tracking-wider mt-1">Poor / Hallucinated</span>
              </div>
            </div>

            <div className="w-full bg-gray-800 rounded-full h-4 overflow-hidden flex shadow-inner">
              <div 
                className="bg-emerald-500 h-full transition-all duration-1000" 
                style={{ width: `${totalVotes > 0 ? (metrics.upvotes / totalVotes) * 100 : 50}%` }}
              ></div>
              <div 
                className={`${isHighHallucination ? 'bg-red-500 animate-pulse' : 'bg-orange-500'} h-full transition-all duration-1000`} 
                style={{ width: `${totalVotes > 0 ? downvoteRatio : 50}%` }}
              ></div>
            </div>
            <div className="text-center mt-3 text-sm text-gray-400">
              {totalVotes === 0 ? 'No feedback recorded yet' : (
                <>Downvote Ratio: <span className={`font-bold ${isHighHallucination ? 'text-red-500' : 'text-gray-300'}`}>{downvoteRatio.toFixed(1)}%</span></>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
