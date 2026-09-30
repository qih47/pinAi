import React, { useState, useMemo } from 'react';
import { useChatStore } from '../../../stores/chatStore';
import { translations } from '../../../utils/translations';

export default function DeckTasksWidget({ data, darkMode = true }) {
  const language = useChatStore((state) => state.language) || 'id';
  const t = translations[language]?.deck || translations.id.deck;

  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'active' | 'done'
  const [selectedBoardId, setSelectedBoardId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Pastikan data valid
  const parsedData = useMemo(() => {
    if (!data) return null;
    if (typeof data === 'string') {
      try {
        return JSON.parse(data);
      } catch (e) {
        return null;
      }
    }
    return data;
  }, [data]);

  if (!parsedData || !parsedData.boards) {
    return null;
  }

  const { boards = [], total_assigned = 0, active_count = 0, done_count = 0 } = parsedData;

  // Pilih board aktif (default board pertama jika belum ada yang dipilih)
  const currentBoard = useMemo(() => {
    if (!boards.length) return null;
    if (selectedBoardId) {
      return boards.find((b) => b.board_id === selectedBoardId) || boards[0];
    }
    return boards[0];
  }, [boards, selectedBoardId]);

  // Filter kartu berdasarkan tab & search query
  const filteredCards = useMemo(() => {
    if (!currentBoard) return [];
    let list = currentBoard.cards || [];

    if (activeTab === 'active') {
      list = list.filter((c) => !c.is_done);
    } else if (activeTab === 'done') {
      list = list.filter((c) => c.is_done);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (c) =>
          c.title?.toLowerCase().includes(q) ||
          c.stack_title?.toLowerCase().includes(q) ||
          c.team?.some((m) => m.name?.toLowerCase().includes(q))
      );
    }

    return list;
  }, [currentBoard, activeTab, searchQuery]);

  return (
    <div
      style={{
        margin: '16px 0',
        borderRadius: '16px',
        border: darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.08)',
        background: darkMode
          ? 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)'
          : 'linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 250, 252, 0.95) 100%)',
        backdropFilter: 'blur(12px)',
        boxShadow: darkMode
          ? '0 8px 32px -4px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
          : '0 8px 24px -4px rgba(0, 0, 0, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
        overflow: 'hidden',
        fontFamily: 'inherit',
      }}
    >
      {/* ── Header Widget ────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          padding: '14px 18px',
          borderBottom: darkMode ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.06)',
          background: darkMode ? 'rgba(15, 23, 42, 0.4)' : 'rgba(241, 245, 249, 0.6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: '18px',
              boxShadow: '0 2px 8px rgba(2, 132, 199, 0.3)',
            }}
          >
            🗂️
          </div>
          <div>
            <div
              style={{
                fontSize: '14px',
                fontWeight: 600,
                color: darkMode ? '#f1f5f9' : '#0f172a',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>{t.title || 'Pincloud Deck (Proyek & Tugas)'}</span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: darkMode ? 'rgba(56, 189, 248, 0.15)' : 'rgba(2, 132, 199, 0.1)',
                  color: darkMode ? '#38bdf8' : '#0284c7',
                }}
              >
                {total_assigned} {t.assignedToMe || 'Tugas'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: darkMode ? '#94a3b8' : '#64748b' }}>
              {boards.map((b) => b.title).join(' • ')}
            </div>
          </div>
        </div>

        {/* Tombol Buka di Pincloud */}
        {currentBoard?.url && (
          <a
            href={currentBoard.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: 500,
              padding: '6px 14px',
              borderRadius: '8px',
              textDecoration: 'none',
              color: '#ffffff',
              background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
              boxShadow: '0 2px 6px rgba(2, 132, 199, 0.25)',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            <span>{t.openInDeck || 'Buka di Pincloud'}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg>
          </a>
        )}
      </div>

      {/* ── Subheader: Board Selector & Filter Tabs ──────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '10px',
          padding: '10px 18px',
          borderBottom: darkMode ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.04)',
        }}
      >
        {/* Selector Board jika lebih dari 1 board */}
        {boards.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {boards.map((b) => {
              const isSelected = (currentBoard?.board_id === b.board_id);
              return (
                <button
                  key={b.board_id}
                  type="button"
                  onClick={() => setSelectedBoardId(b.board_id)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '6px',
                    border: 'none',
                    fontSize: '11px',
                    fontWeight: isSelected ? 600 : 500,
                    cursor: 'pointer',
                    background: isSelected
                      ? darkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.08)'
                      : 'transparent',
                    color: isSelected
                      ? darkMode ? '#38bdf8' : '#0284c7'
                      : darkMode ? '#94a3b8' : '#64748b',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {b.title} ({b.total_cards})
                </button>
              );
            })}
          </div>
        )}

        {/* Right Controls: Search Bar & Filter Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Search Input Field */}
          <div
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke={darkMode ? '#94a3b8' : '#64748b'}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                position: 'absolute',
                left: '8px',
                pointerEvents: 'none',
              }}
            >
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder={t.searchPlaceholder || 'Cari tugas atau tim...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                fontSize: '11px',
                padding: '4px 24px 4px 26px',
                borderRadius: '6px',
                border: darkMode ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid rgba(0, 0, 0, 0.1)',
                background: darkMode ? 'rgba(0, 0, 0, 0.25)' : '#ffffff',
                color: darkMode ? '#f1f5f9' : '#0f172a',
                outline: 'none',
                width: '145px',
                transition: 'all 0.2s ease',
              }}
              onFocus={(e) => {
                e.target.style.width = '185px';
                e.target.style.borderColor = '#38bdf8';
              }}
              onBlur={(e) => {
                if (!searchQuery) e.target.style.width = '145px';
                e.target.style.borderColor = darkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)';
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                title="Hapus pencarian"
                style={{
                  position: 'absolute',
                  right: '6px',
                  background: 'transparent',
                  border: 'none',
                  color: darkMode ? '#94a3b8' : '#64748b',
                  cursor: 'pointer',
                  fontSize: '11px',
                  lineHeight: 1,
                  padding: '2px',
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Tab Filter (Semua / Aktif / Selesai) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              background: darkMode ? 'rgba(0, 0, 0, 0.25)' : 'rgba(0, 0, 0, 0.04)',
              padding: '3px',
              borderRadius: '8px',
            }}
          >
            {[
              { id: 'all', label: t.all || 'Semua', count: currentBoard?.cards?.length || 0 },
              { id: 'active', label: t.active || 'Sedang Berjalan', count: (currentBoard?.cards || []).filter(c => !c.is_done).length },
              { id: 'done', label: t.done || 'Selesai', count: (currentBoard?.cards || []).filter(c => c.is_done).length },
            ].map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '6px',
                    border: 'none',
                    fontSize: '11px',
                    fontWeight: isActive ? 600 : 500,
                    cursor: 'pointer',
                    background: isActive
                      ? darkMode ? '#1e293b' : '#ffffff'
                      : 'transparent',
                    color: isActive
                      ? darkMode ? '#f1f5f9' : '#0f172a'
                      : darkMode ? '#94a3b8' : '#64748b',
                    boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.15)' : 'none',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <span>{tab.label}</span>
                  <span
                    style={{
                      fontSize: '10px',
                      opacity: 0.75,
                      background: darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)',
                      padding: '1px 5px',
                      borderRadius: '8px',
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Task Cards List ──────────────────────────────────────── */}
      <div style={{ padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {filteredCards.length === 0 ? (
          <div
            style={{
              padding: '24px 0',
              textAlign: 'center',
              color: darkMode ? '#64748b' : '#94a3b8',
              fontSize: '13px',
            }}
          >
            {searchQuery ? `Tidak ada tugas yang cocok dengan "${searchQuery}"` : (t.noTasksFound || 'Tidak ada tugas yang sesuai pada filter ini.')}
          </div>
        ) : (
          filteredCards.map((card) => {
            const isDone = card.is_done;
            return (
              <div
                key={card.card_id}
                style={{
                  borderRadius: '10px',
                  padding: '12px 14px',
                  border: darkMode ? '1px solid rgba(255, 255, 255, 0.06)' : '1px solid rgba(0, 0, 0, 0.05)',
                  background: darkMode ? 'rgba(30, 41, 59, 0.4)' : '#ffffff',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  transition: 'all 0.2s ease',
                }}
              >
                {/* Baris 1: Judul Kartu + Badge Status */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: isDone ? '#10b981' : '#38bdf8',
                        flexShrink: 0,
                      }}
                    />
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: darkMode ? '#f8fafc' : '#1e293b',
                        textDecoration: isDone ? 'line-through' : 'none',
                        opacity: isDone ? 0.75 : 1,
                      }}
                    >
                      {card.title}
                    </div>
                  </div>

                  {/* Badge Kolom/Tahap */}
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 500,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: isDone
                        ? darkMode ? 'rgba(16, 185, 129, 0.15)' : 'rgba(16, 185, 129, 0.1)'
                        : darkMode ? 'rgba(56, 189, 248, 0.12)' : 'rgba(2, 132, 199, 0.08)',
                      color: isDone
                        ? darkMode ? '#34d399' : '#059669'
                        : darkMode ? '#38bdf8' : '#0284c7',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {card.stack_title}
                  </span>
                </div>

                {/* Baris 2: Detail (Due Date & Anggota Tim) */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    fontSize: '11px',
                    color: darkMode ? '#94a3b8' : '#64748b',
                    marginTop: '2px',
                  }}
                >
                  {/* Due Date jika ada */}
                  {card.duedate && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: darkMode ? '#fbbf24' : '#d97706' }}>
                      <span>📅</span>
                      <span style={{ fontWeight: 500 }}>
                        {t.dueDate || 'Tenggat'}: {new Date(card.duedate).toLocaleDateString(language === 'en' ? 'en-US' : 'id-ID', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </span>
                    </div>
                  )}

                  {/* Team Members Chips (Deduplicated & Prevent Text Wrap on 'Tim:') */}
                  {(() => {
                    const rawTeam = card.team || [];
                    const seen = new Set();
                    const uniqueTeam = rawTeam.filter((m) => {
                      const key = (m.primary_key || m.name || '').trim().toLowerCase();
                      if (!key || seen.has(key)) return false;
                      seen.add(key);
                      return true;
                    });

                    if (uniqueTeam.length === 0) return null;

                    return (
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            opacity: 0.85,
                            whiteSpace: 'nowrap',
                            flexShrink: 0,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            paddingTop: '2px',
                            color: darkMode ? '#cbd5e1' : '#475569',
                          }}
                        >
                          👥 {t.team || 'Tim'}:
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap', flex: 1 }}>
                          {uniqueTeam.map((m, idx) => {
                            const displayName = m.name 
                              ? m.name.split(' ').slice(0, 2).join(' ') 
                              : (m.primary_key || 'User');
                            return (
                              <span
                                key={idx}
                                title={m.name}
                                style={{
                                  fontSize: '10.5px',
                                  fontWeight: 500,
                                  padding: '2px 7px',
                                  borderRadius: '5px',
                                  background: darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)',
                                  color: darkMode ? '#e2e8f0' : '#334155',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {displayName}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
