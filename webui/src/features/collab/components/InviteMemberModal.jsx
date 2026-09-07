import React, { useState, useEffect } from 'react';
import { X, UserPlus, Search, Check, Loader2 } from 'lucide-react';
import { collabApi } from '../services/collabApi';

const InviteMemberModal = ({ isOpen, onClose, roomId, currentMembers = [], onMembersInvited, darkMode = true, theme }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [invitingNpp, setInvitingNpp] = useState(null);
  const [invitedNpps, setInvitedNpps] = useState(new Set());
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');

  const modalBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const headerFooterBg = darkMode ? '#18181b' : '#f9fafb';
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const inputBg = theme?.inputBg || (darkMode ? '#1e1e20' : '#f3f4f6');
  const cardBg = darkMode ? '#1e1e20' : '#ffffff';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  const currentNppSet = new Set(currentMembers.map((m) => m.npp));

  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await collabApi.searchPersonnel(searchQuery.trim());
        setSearchResults(results);
      } catch (err) {
        console.error('Failed to search personnel:', err);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleInvitePerson = async (person) => {
    if (!roomId || !person?.npp) return;
    setInvitingNpp(person.npp);
    setError('');

    try {
      await collabApi.inviteMembers(roomId, [person.npp]);
      setInvitedNpps((prev) => new Set([...prev, person.npp]));
      if (onMembersInvited) onMembersInvited();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Gagal mengundang anggota.');
    } finally {
      setInvitingNpp(null);
    }
  };

  const handleClose = () => {
    setSearchQuery('');
    setInvitedNpps(new Set());
    setError('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="w-full max-w-md border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        style={{
          background: modalBg,
          borderColor: borderColor,
          color: textColor
        }}
      >
        {/* Header */}
        <div
          className="px-5 py-4 border-b flex items-center justify-between"
          style={{
            background: headerFooterBg,
            borderColor: borderColor
          }}
        >
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <UserPlus size={16} />
            </div>
            <h2 className="text-sm font-bold" style={{ color: textColor }}>Undang Rekan Kerja</h2>
          </div>

          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 flex-1 overflow-y-auto space-y-3" style={{ background: modalBg }}>
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
              {error}
            </div>
          )}

          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: secondaryTextColor }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ketik nama atau NPP..."
              className="w-full pl-8 pr-4 py-2 border rounded-xl text-xs focus:outline-none focus:border-teal-500 transition-all"
              style={{
                background: inputBg,
                borderColor: borderColor,
                color: textColor
              }}
              autoFocus
            />
            {isSearching && (
              <Loader2 size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-teal-400 animate-spin" />
            )}
          </div>

          {/* Results List */}
          <div
            className="max-h-60 overflow-y-auto divide-y rounded-xl border"
            style={{
              background: cardBg,
              borderColor: borderColor
            }}
          >
            {searchResults.length === 0 ? (
              <div className="p-4 text-center text-xs" style={{ color: secondaryTextColor }}>
                {searchQuery.trim().length >= 2 ? 'Tidak ada personil ditemukan' : 'Cari personil untuk ditambahkan ke ruang diskusi'}
              </div>
            ) : (
              searchResults.map((person) => {
                const isAlreadyMember = currentNppSet.has(person.npp) || invitedNpps.has(person.npp);
                const isInvitingThis = invitingNpp === person.npp;

                return (
                  <div
                    key={person.npp}
                    className="px-3 py-2.5 flex items-center justify-between transition-colors hover:bg-white/5"
                    style={{ borderColor: borderColor }}
                  >
                    <div className="min-w-0 pr-3">
                      <div className="text-xs font-semibold flex items-center gap-2" style={{ color: textColor }}>
                        <span className="truncate">{person.name}</span>
                        {isAlreadyMember && (
                          <span className="text-[10px] text-teal-400 font-normal">
                            {invitedNpps.has(person.npp) ? '✓ Baru Ditambahkan' : '(Sudah Bergabung)'}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] truncate" style={{ color: secondaryTextColor }}>
                        {person.divisi} • NPP: {person.npp}
                      </div>
                    </div>

                    {isAlreadyMember ? (
                      <span
                        className="shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border"
                        style={{
                          background: darkMode ? '#1c1c1f' : '#f3f4f6',
                          borderColor: borderColor,
                          color: secondaryTextColor
                        }}
                      >
                        <Check size={12} className="text-teal-400" />
                        <span>Bergabung</span>
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={isInvitingThis}
                        onClick={() => handleInvitePerson(person)}
                        className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shadow-sm ${
                          isInvitingThis
                            ? 'bg-teal-600/50 text-teal-200 cursor-wait'
                            : 'bg-teal-600 hover:bg-teal-500 text-white hover:scale-[1.02]'
                        }`}
                      >
                        {isInvitingThis ? (
                          <>
                            <Loader2 size={12} className="animate-spin" />
                            <span>Mengundang...</span>
                          </>
                        ) : (
                          <>
                            <UserPlus size={13} />
                            <span>Undang</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          className="px-5 py-3 border-t flex items-center justify-end"
          style={{
            background: headerFooterBg,
            borderColor: borderColor
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
          >
            Selesai
          </button>
        </div>
      </div>
    </div>
  );
};

export default InviteMemberModal;
