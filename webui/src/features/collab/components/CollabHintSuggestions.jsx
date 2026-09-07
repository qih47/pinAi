import React, { useState, useEffect, useRef } from "react";
import {
  Globe,
  FileText,
  Code2,
  Target,
  ArrowUpRight,
  BarChart3,
  Workflow,
  FilePlus,
  Mail,
  HelpCircle,
  Tag
} from "lucide-react";
import { fetchChatSuggestions } from "../../../services/endpoints";
import { translations } from "../../../utils/translations";

export default function CollabHintSuggestions({
  activeModeTag,
  input = "",
  onSelectDocument,
  onSelectPrompt,
  darkMode = true,
  theme,
  language = "id",
  isMobile = false
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const debounceTimerRef = useRef(null);

  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;
  const isDocMode = activeModeTag === "documents" || activeModeTag === "focus";

  // Ambil daftar rekomendasi dari endpoint suggestions
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
        const modeQuery = isDocMode ? "documents" : activeModeTag;
        const results = await fetchChatSuggestions(modeQuery, input || "", 5);
        setSuggestions(results || []);
      } catch (err) {
        console.error("[COLLAB_SUGGESTIONS] Failed to fetch suggestions:", err);
      } finally {
        setIsLoading(false);
      }
    }, 150);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [activeModeTag, input, isDocMode]);

  if (!activeModeTag || suggestions.length === 0) return null;

  const handleItemClick = (item) => {
    if (isDocMode) {
      // 📄 Pilihan Dokumen: Dijadikan rujukan dokumen aktif diskusi tim
      if (onSelectDocument) {
        const fname = item.filename || null;
        const fpath = item.file_path || (fname ? (fname.startsWith('file_peraturan/') ? fname : `file_peraturan/${fname}`) : null);
        onSelectDocument({
          title: item.title,
          doc_id: item.id_berita || item.doc_id || item.id || item.title,
          filename: fname,
          file_path: fpath,
          category: item.category || "Regulasi",
          nomor: item.nomor || "",
          total_pages: item.total_pages || null
        });
      }
    } else {
      // ⚡ Pilihan Prompt Tool (Websearch, Code, Diagram, dll.)
      if (onSelectPrompt) {
        onSelectPrompt(item.title, activeModeTag);
      }
    }
  };

  const getModeIcon = () => {
    switch (activeModeTag) {
      case "code":
        return <Code2 size={13} className="text-indigo-400 shrink-0" />;
      case "websearch":
        return <Globe size={13} className="text-blue-400 shrink-0" />;
      case "documents":
      case "focus":
        return <FileText size={13} className="text-amber-400 shrink-0" />;
      case "diagram":
        return <Workflow size={13} className="text-purple-400 shrink-0" />;
      case "chart":
        return <BarChart3 size={13} className="text-emerald-400 shrink-0" />;
      case "create_file":
        return <FilePlus size={13} className="text-cyan-400 shrink-0" />;
      case "smart_mail":
        return <Mail size={13} className="text-rose-400 shrink-0" />;
      default:
        return <Target size={13} className="text-teal-400 shrink-0" />;
    }
  };

  return (
    <div
      className="w-full flex flex-col gap-1 select-none mb-1 animate-fadeInUp"
      style={{ overflow: "visible" }}
    >
      {/* Micro-animation CSS */}
      <style>{`
        @keyframes cakraCollabSpring {
          0% {
            opacity: 0;
            transform: translateY(10px) scale(0.96);
          }
          60% {
            opacity: 1;
            transform: translateY(-2px) scale(1.02);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
      `}</style>

      {/* Header kecil penjelas rujukan */}
      <div
        className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-medium"
        style={{
          background: darkMode ? "rgba(255, 255, 255, 0.04)" : "rgba(0, 0, 0, 0.04)",
          color: darkMode ? "#94a3b8" : "#64748b",
          border: `1px solid ${darkMode ? "rgba(255, 255, 255, 0.07)" : "rgba(0, 0, 0, 0.06)"}`
        }}
      >
        <Tag size={12} className="text-teal-400 shrink-0" />
        <span>
          {isDocMode
            ? "Pilih dokumen untuk dijadikan rujukan diskusi tim:"
            : "Rekomendasi instruksi diskusi tim:"}
        </span>
      </div>

      {/* Daftar Kartu Rekomendasi */}
      <div className="flex flex-col gap-0.5 w-full">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleItemClick(item)}
            className={`flex items-center justify-between w-full px-3.5 py-2 rounded-xl text-left transition-all duration-150 group cursor-pointer border-0 ${
              darkMode
                ? "text-[#d1d5db] hover:text-white hover:bg-[#1f1f24]"
                : "text-gray-700 hover:text-gray-900 hover:bg-gray-100"
            }`}
            style={{
              outline: "none",
              background: darkMode ? "rgba(24, 24, 28, 0.75)" : "#f8fafc",
              border: `1px solid ${darkMode ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}`,
              animation: `cakraCollabSpring 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) ${idx * 40}ms both`,
              marginBottom: "2px"
            }}
          >
            <div className="flex items-center gap-2.5 min-w-0 pr-2">
              {getModeIcon()}
              <span className="text-[13px] font-medium tracking-tight truncate">
                {item.title}
              </span>
            </div>

            <div className="flex items-center gap-1.5 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all shrink-0">
              <span className="text-[10px] hidden sm:inline text-teal-400 font-medium">
                {isDocMode ? "Jadikan Rujukan" : "Pilih"}
              </span>
              <ArrowUpRight
                size={13}
                className={darkMode ? "text-gray-400 group-hover:text-white" : "text-gray-500 group-hover:text-gray-900"}
              />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
