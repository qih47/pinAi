import React, { useState, useEffect, useRef } from "react";
import { Globe, FileText, Code2, Target, ArrowUpRight, BarChart3, Workflow, FilePlus, Mail, ChevronDown, ChevronUp, HelpCircle, ArrowLeft } from "lucide-react";
import { fetchChatSuggestions } from "../../../services/endpoints";
import { translations } from "../../../utils/translations";
import { useChatStore } from "../../../stores/chatStore";

export default function HintSuggestions({
  input,
  setInput,
  activeModeTag,
  setActiveModeTag,
  onSelectHint,
  darkMode = true,
  theme,
  isStreaming = false,
  isGuest = false,
  language = "id",
  isMobile = false
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null); // Step 2 state for document & focus modes
  const debounceTimerRef = useRef(null);

  const activeIsolatedDocId = useChatStore(state => state.activeIsolatedDocId);
  const setContextIsolation = useChatStore(state => state.setContextIsolation);

  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;

  // Reset selectedDoc if activeModeTag changes to non-doc mode or is cleared
  useEffect(() => {
    if (activeModeTag !== "focus" && activeModeTag !== "documents") {
      setSelectedDoc(null);
    }
  }, [activeModeTag]);

  // Reset selectedDoc if isolated document is cleared from banner
  useEffect(() => {
    if (!activeIsolatedDocId && selectedDoc) {
      setSelectedDoc(null);
    }
  }, [activeIsolatedDocId]);

  // Daftar seluruh aksi mode Cakra AI dengan Multi-Bahasa
  // Baris 1: Code, Search the web, Document search, Focus & Audit
  // Baris 2: Chart & Data, Diagram & Flow, Create File, Draft Surat
  const allActions = [
    // ── BARIS 1 (Primary 4 Actions) ──
    {
      id: "code",
      label: tHints.code,
      icon: Code2,
    },
    {
      id: "websearch",
      label: tHints.websearch,
      icon: Globe,
    },
    {
      id: "documents",
      label: tHints.documents,
      icon: FileText,
    },
    {
      id: "focus",
      label: tHints.focus,
      icon: Target,
    },
    // ── BARIS 2 (Secondary 4 Actions / Expandable) ──
    {
      id: "chart",
      label: tHints.chart,
      icon: BarChart3,
    },
    {
      id: "diagram",
      label: tHints.diagram,
      icon: Workflow,
    },
    {
      id: "create_file",
      label: tHints.createFile,
      icon: FilePlus,
    },
    {
      id: "smart_mail",
      label: tHints.smartMail,
      icon: Mail,
    }
  ];

  // Guest users only have access to safe public tools (Code, Web Search, Diagram, Chart)
  const defaultActions = isGuest
    ? [
        { id: "code", label: tHints.code, icon: Code2 },
        { id: "websearch", label: tHints.websearch, icon: Globe },
        { id: "diagram", label: tHints.diagram, icon: Workflow },
        { id: "chart", label: tHints.chart, icon: BarChart3 },
      ]
    : allActions;

  // Bagi aksi: Jika mobile, tampilkan maksimal 3 di baris utama (primary) dan sisanya saat di-expand
  const splitCount = isMobile ? 3 : 4;
  const primaryActions = defaultActions.slice(0, splitCount);
  const secondaryActions = defaultActions.slice(splitCount);

  // Fetch dynamic suggestions (documents list OR questions for selected doc)
  useEffect(() => {
    if (!activeModeTag) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      try {
        if (selectedDoc) {
          // ── STEP 2: Ambil Rekomendasi Pertanyaan Sintetis Dokumen ──
          const results = await fetchChatSuggestions(
            "doc_questions", 
            input || selectedDoc.title, 
            5, 
            selectedDoc.doc_id || selectedDoc.id
          );
          setSuggestions(results || []);
        } else {
          // ── STEP 1: Ambil Daftar Dokumen atau Rekomendasi Mode Biasa ──
          const results = await fetchChatSuggestions(activeModeTag, input || "", 5);
          setSuggestions(results || []);
        }
      } catch (err) {
        console.error("Failed to fetch suggestions:", err);
      } finally {
        setIsLoading(false);
      }
    }, 150);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [activeModeTag, input, selectedDoc]);

  // Handle item click (2-Step Flow for Focus / Documents)
  const handleItemClick = (item) => {
    const isDocMode = activeModeTag === "focus" || activeModeTag === "documents";

    if (isDocMode && !selectedDoc) {
      // 🚀 STEP 1 -> STEP 2: Lock Document & Transition to Synthetic Questions
      const docId = item.doc_id || item.id || item.id_berita || item.title;
      const docTitle = item.title;

      // Lock context isolation UI
      if (activeModeTag === "focus") {
        setContextIsolation(docId, docTitle, "focus");
      } else {
        setContextIsolation(docId, docTitle, "auto");
      }

      // Transition to Step 2 without auto-sending
      setSelectedDoc({ ...item, doc_id: docId, title: docTitle });
    } else {
      // 🎯 STEP 2 or Regular Modes: Send question / prompt directly!
      const finalDocId = selectedDoc?.doc_id || selectedDoc?.id || item.doc_id;
      const finalDocTitle = selectedDoc?.title || item.title;

      onSelectHint(item.title, activeModeTag, {
        ...item,
        doc_id: finalDocId,
        doc_title: finalDocTitle,
        isolated_doc_id: finalDocId
      });
    }
  };

  // If streaming or if there are no hints and no default actions to show, return null
  if (isStreaming) return null;
  if (activeModeTag && suggestions.length === 0 && !selectedDoc) return null;

  return (
    <div className="w-full flex flex-col items-center justify-center gap-1 mt-2 mb-1 px-1 select-none">
      {/* 💫 Dynamic Micro-Animation Keyframes */}
      <style>{`
        @keyframes cakraSpringBounce {
          0% {
            opacity: 0;
            transform: translateY(14px) scale(0.82);
          }
          60% {
            opacity: 1;
            transform: translateY(-4px) scale(1.04);
          }
          80% {
            transform: translateY(1.5px) scale(0.98);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        @keyframes cakraRowCascade {
          0% {
            opacity: 0;
            transform: translateY(-8px) scale(0.92);
          }
          60% {
            opacity: 1;
            transform: translateY(2px) scale(1.02);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
      `}</style>

      {/* 🧭 STATE 2: BARIS OPSI UTAMA DENGAN SPRING BOUNCE ANIMATION */}
      {!activeModeTag && !input.trim() && (
        <div className="flex flex-col items-center justify-center gap-1.5 w-full">
          {/* Baris 1: 3 Tombol Berjejer Alami dengan Lebar Dinamis (Proporsional Sesuai Panjang Teks) */}
          <div className="flex flex-nowrap items-center justify-center gap-1.5 sm:gap-2.5 w-full max-w-full px-1">
            {primaryActions.map((action, idx) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => setActiveModeTag(action.id)}
                  className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1.5 rounded-xl transition-all duration-200 cursor-pointer group border-0 text-center flex-shrink-0 hover:scale-[1.04] active:scale-[0.96] ${
                    darkMode
                      ? "text-[#d1d5db] hover:text-white hover:bg-[#1f1f23] shadow-black/20"
                      : "text-gray-700 hover:text-gray-900 hover:bg-gray-100"
                  }`}
                  style={{
                    outline: "none",
                    background: "transparent",
                    animation: `cakraSpringBounce 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) ${idx * 45}ms both`
                  }}
                >
                  <Icon
                    size={15}
                    className="opacity-75 group-hover:opacity-100 group-hover:scale-110 transition-transform duration-150 flex-shrink-0"
                  />
                  <span className="text-[13px] font-normal tracking-wide text-center leading-none whitespace-nowrap">
                    {action.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Tombol 'Lainnya ▾' di tengah tepat di bawah Baris 1 saat collapsed */}
          {!isExpanded && secondaryActions.length > 0 && (
            <div className="flex justify-center w-full pt-0.5">
              <button
                type="button"
                onClick={() => setIsExpanded(true)}
                className={`inline-flex items-center justify-center gap-1 px-3 py-1 rounded-lg text-xs transition-all duration-200 cursor-pointer group border-0 text-center hover:scale-[1.05] active:scale-[0.95] ${
                  darkMode
                    ? "text-[#9ca3af] hover:text-white hover:bg-[#1f1f23]"
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                }`}
                style={{
                  outline: "none",
                  background: "transparent",
                  animation: `cakraRowCascade 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) 180ms both`
                }}
                title={tHints.moreTitle}
              >
                <span className="font-medium tracking-wide">
                  {tHints.more}
                </span>
                <ChevronDown size={13} className="opacity-70 group-hover:opacity-100 group-hover:translate-y-0.5 transition-transform" />
              </button>
            </div>
          )}

          {/* Baris Secondary: Muncul dinamis dengan format 3-3-2 di Mobile saat di-expand */}
          {isExpanded && secondaryActions.length > 0 && (
            <div className="flex flex-col items-center justify-center gap-1.5 w-full text-center">
              {/* Row 2: 3 Tombol di Mobile / 4 Tombol di Desktop */}
              <div className="flex flex-nowrap sm:flex-wrap items-center justify-center gap-1.5 sm:gap-2.5 w-full max-w-full px-1">
                {(isMobile ? secondaryActions.slice(0, 3) : secondaryActions).map((action, idx) => {
                  const Icon = action.icon;
                  return (
                    <button
                      key={action.id}
                      type="button"
                      onClick={() => setActiveModeTag(action.id)}
                      className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1.5 rounded-xl transition-all duration-200 cursor-pointer group border-0 text-center flex-shrink-0 hover:scale-[1.03] active:scale-[0.97] ${
                        darkMode
                          ? "text-[#d1d5db] hover:text-white hover:bg-[#1f1f23]"
                          : "text-gray-700 hover:text-gray-900 hover:bg-gray-100"
                      }`}
                      style={{
                        outline: "none",
                        background: "transparent",
                        animation: `cakraSpringBounce 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) ${idx * 50 + 40}ms both`
                      }}
                    >
                      <Icon
                        size={15}
                        className="opacity-75 group-hover:opacity-100 group-hover:scale-110 transition-transform duration-150 flex-shrink-0"
                      />
                      <span className="text-[13px] font-normal tracking-wide leading-none whitespace-nowrap">
                        {action.label}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Row 3 (Khusus Mobile: 2 Tombol Terakhir) */}
              {isMobile && secondaryActions.slice(3).length > 0 && (
                <div className="flex flex-nowrap items-center justify-center gap-1.5 sm:gap-2.5 w-full max-w-full px-1">
                  {secondaryActions.slice(3).map((action, idx) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={action.id}
                        type="button"
                        onClick={() => setActiveModeTag(action.id)}
                        className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1.5 rounded-xl transition-all duration-200 cursor-pointer group border-0 text-center flex-shrink-0 hover:scale-[1.03] active:scale-[0.97] ${
                          darkMode
                            ? "text-[#d1d5db] hover:text-white hover:bg-[#1f1f23]"
                            : "text-gray-700 hover:text-gray-900 hover:bg-gray-100"
                        }`}
                        style={{
                          outline: "none",
                          background: "transparent",
                          animation: `cakraSpringBounce 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) ${(idx + 3) * 50 + 40}ms both`
                        }}
                      >
                        <Icon
                          size={15}
                          className="opacity-75 group-hover:opacity-100 group-hover:scale-110 transition-transform duration-150 flex-shrink-0"
                        />
                        <span className="text-[13px] font-normal tracking-wide leading-none whitespace-nowrap">
                          {action.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Tombol 'Tutup ▴' tepat di bawah baris ke-3 (Centered) */}
              <div className="flex justify-center w-full pt-0.5">
                <button
                  type="button"
                  onClick={() => setIsExpanded(false)}
                  className={`inline-flex items-center justify-center gap-1 px-3.5 py-1 rounded-lg text-xs transition-all duration-200 cursor-pointer group border-0 text-center hover:scale-[1.05] active:scale-[0.95] ${
                    darkMode
                      ? "text-indigo-400/90 hover:text-indigo-300 hover:bg-indigo-500/10"
                      : "text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                  }`}
                  style={{
                    outline: "none",
                    animation: `cakraRowCascade 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) 220ms both`
                  }}
                  title={tHints.lessTitle}
                >
                  <span className="font-medium tracking-wide">
                    {tHints.less}
                  </span>
                  <ChevronUp size={13} className="opacity-80 group-hover:opacity-100 group-hover:-translate-y-0.5 transition-transform" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 💡 STATE 3: DYNAMIC RECOMENDATION HINTS (STEP 1 & STEP 2) */}
      {activeModeTag && (
        <div className="flex flex-col gap-1 w-full mt-1">
          {/* Breadcrumb Header jika sedang di STEP 2 (Memilih Pertanyaan Dokumen) */}
          {selectedDoc && (
            <div className="flex items-center justify-between px-3 py-1 mb-0.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs animate-fadeIn">
              <div className="flex items-center gap-1.5 text-indigo-300 overflow-hidden font-medium">
                <HelpCircle size={13} className="text-indigo-400 flex-shrink-0" />
                <span className="truncate">Rekomendasi Pertanyaan: <strong className="text-white">{selectedDoc.title}</strong></span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDoc(null)}
                className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-white/10 transition-colors flex-shrink-0 ml-2"
                title="Pilih dokumen lain"
              >
                <ArrowLeft size={11} />
                <span>Ganti Dokumen</span>
              </button>
            </div>
          )}

          {suggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleItemClick(item)}
              className={`flex items-center justify-between w-full px-3.5 py-2 rounded-xl text-left transition-all duration-150 group cursor-pointer border-0 ${
                darkMode
                  ? "text-[#d1d5db] hover:text-white hover:bg-[#1a1a1e]"
                  : "text-gray-700 hover:text-gray-900 hover:bg-gray-100"
              }`}
              style={{
                outline: "none",
                background: "transparent",
                animation: `cakraSpringBounce 0.38s cubic-bezier(0.34, 1.56, 0.64, 1) ${idx * 40}ms both`
              }}
            >
              <div className="flex items-center gap-2.5 overflow-hidden flex-1 pr-3">
                <ArrowUpRight
                  size={15}
                  className="opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all flex-shrink-0 text-indigo-400"
                />
                <span className="text-[13px] font-normal truncate">
                  {item.title}
                </span>
              </div>
              {item.category && (
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-md font-medium flex-shrink-0 ${
                    darkMode
                      ? "bg-white/5 text-gray-400 group-hover:text-gray-300"
                      : "bg-gray-200/70 text-gray-500 group-hover:text-gray-700"
                  }`}
                >
                  {item.category}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
