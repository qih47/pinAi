import React, { useState, useEffect } from 'react';
import { X, Users, Search, Plus, Check, Loader2, Sparkles } from 'lucide-react';
import { collabApi } from '../services/collabApi';
import { translations } from '../../../utils/translations';

const CreateRoomModal = ({ isOpen, onClose, onRoomCreated, darkMode = true, theme, language = 'id' }) => {
  const t = translations[language]?.collab || translations.id.collab;
  const [name, setName] = useState('');
  const [topic, setTopic] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedMembers, setSelectedMembers] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const modalBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const headerFooterBg = darkMode ? '#18181b' : '#f9fafb';
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const inputBg = theme?.inputBg || (darkMode ? '#1e1e20' : '#f3f4f6');
  const cardBg = darkMode ? '#1e1e20' : '#ffffff';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  // Live search personil
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

  const toggleMember = (person) => {
    setSelectedMembers((prev) => {
      const exists = prev.some((m) => m.npp === person.npp);
      if (exists) {
        return prev.filter((m) => m.npp !== person.npp);
      }
      return [...prev, person];
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(t.roomNameRequired || 'Nama ruang diskusi wajib diisi.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const room = await collabApi.createRoom({
        name: name.trim(),
        topic: topic.trim(),
        initialMembers: selectedMembers.map((m) => m.npp)
      });
      onRoomCreated(room);
      handleClose();
    } catch (err) {
      setError(err?.response?.data?.detail || t.roomCreateFailed || 'Gagal membuat ruang diskusi.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setTopic('');
    setSearchQuery('');
    setSelectedMembers([]);
    setError('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        style={{
          background: modalBg,
          borderColor: borderColor,
          color: textColor
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{
            background: headerFooterBg,
            borderColor: borderColor
          }}
        >
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Users size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold" style={{ color: textColor }}>{t.createRoomModalTitle}</h2>
              <p className="text-xs" style={{ color: secondaryTextColor }}>{t.createRoomModalSubtitle}</p>
            </div>
          </div>

          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-4 flex-1" style={{ background: modalBg }}>
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
              {error}
            </div>
          )}

          {/* Nama Ruangan */}
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: textColor }}>
              {t.roomNameLabel} <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t.roomNamePlaceholder}
              className="w-full px-3.5 py-2.5 border rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all"
              style={{
                background: inputBg,
                borderColor: borderColor,
                color: textColor
              }}
              required
            />
          </div>

          {/* Topik / Agenda */}
          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: textColor }}>
              {t.topicLabel}
            </label>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={t.topicPlaceholder}
              rows={2}
              className="w-full px-3.5 py-2 border rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all resize-none"
              style={{
                background: inputBg,
                borderColor: borderColor,
                color: textColor
              }}
            />
          </div>

          {/* Anggota Terpilih */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold" style={{ color: textColor }}>
                {t.inviteMembersLabel} ({selectedMembers.length})
              </label>
              <span className="text-[11px] text-teal-400 font-medium flex items-center gap-1">
                <Sparkles size={11} />
                {t.cakraAutoMember}
              </span>
            </div>

            {selectedMembers.length > 0 && (
              <div
                className="flex flex-wrap gap-1.5 mb-2.5 p-2 rounded-xl border"
                style={{
                  background: inputBg,
                  borderColor: borderColor
                }}
              >
                {selectedMembers.map((m) => (
                  <span
                    key={m.npp}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-teal-950/80 text-teal-300 border border-teal-700/60 text-xs"
                  >
                    <span>{m.name}</span>
                    <button
                      type="button"
                      onClick={() => toggleMember(m)}
                      className="hover:text-rose-400"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Input Cari Personil */}
            <div className="relative">
              <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: secondaryTextColor }} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t.searchPersonInputPlaceholder}
                className="w-full pl-9 pr-4 py-2 border rounded-xl text-xs focus:outline-none focus:border-teal-500 transition-all"
                style={{
                  background: inputBg,
                  borderColor: borderColor,
                  color: textColor
                }}
              />
              {isSearching && (
                <Loader2 size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-teal-400 animate-spin" />
              )}
            </div>

            {/* Search Results Dropdown */}
            {searchResults.length > 0 && (
              <div
                className="mt-1.5 max-h-36 overflow-y-auto border rounded-xl shadow-lg"
                style={{
                  background: cardBg,
                  borderColor: borderColor
                }}
              >
                {searchResults.map((person) => {
                  const isSelected = selectedMembers.some((m) => m.npp === person.npp);
                  return (
                    <div
                      key={person.npp}
                      onClick={() => toggleMember(person)}
                      className="px-3 py-2 flex items-center justify-between cursor-pointer transition-colors hover:bg-white/5 border-b last:border-b-0"
                      style={{ borderColor: borderColor }}
                    >
                      <div>
                        <div className="text-xs font-semibold" style={{ color: textColor }}>{person.name}</div>
                        <div className="text-[11px]" style={{ color: secondaryTextColor }}>{person.divisi} • NPP: {person.npp}</div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleMember(person);
                        }}
                        className={`shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                          isSelected
                            ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/40'
                            : 'border hover:bg-teal-600 hover:text-white'
                        }`}
                        style={!isSelected ? {
                          background: inputBg,
                          borderColor: borderColor,
                          color: textColor
                        } : {}}
                      >
                        {isSelected ? (
                          <>
                            <Check size={12} />
                            <span>{t.selected}</span>
                          </>
                        ) : (
                          <>
                            <Plus size={12} />
                            <span>{t.select}</span>
                          </>
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </form>

        {/* Footer Actions */}
        <div
          className="px-6 py-3.5 border-t flex items-center justify-end gap-2.5"
          style={{
            background: headerFooterBg,
            borderColor: borderColor
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold hover:bg-white/5 transition-colors"
            style={{ color: secondaryTextColor }}
          >
            {t.cancel}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!name.trim() || isSubmitting}
            className={`px-5 py-2 rounded-xl text-xs font-semibold transition-all ${
              name.trim() && !isSubmitting
                ? 'bg-gradient-to-r from-teal-500 to-emerald-600 text-white shadow-md shadow-teal-950/40 hover:brightness-110'
                : 'opacity-50 cursor-not-allowed border'
            }`}
            style={(!name.trim() || isSubmitting) ? { background: inputBg, borderColor: borderColor, color: secondaryTextColor } : {}}
          >
            {isSubmitting ? t.creating : t.createBtn}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateRoomModal;
