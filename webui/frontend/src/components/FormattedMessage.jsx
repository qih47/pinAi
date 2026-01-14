import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { renderStyledText } from "./renderStyledText";

const FormattedMessage = ({ text, showNotification, isAI }) => {
  if (!text) return null;

  let cleanText = typeof text !== "string" ? String(text) : text;
  cleanText = cleanText.replace(/&nbsp;/g, " ").replace(/<br\s*\/?>/gi, "\n").trim();

  // Gunakan renderStyledText hanya untuk deteksi visual, 
  // tapi kita butuh teks asli (raw) untuk tabel agar tidak bentrok dengan HTML tags
  const rawLines = cleanText.split("\n");
  const baseTextColor = isAI ? "text-gray-800 dark:text-gray-200" : "text-white";
  const accentColor = isAI ? "text-blue-600 dark:text-blue-400" : "text-blue-200";

  const finalElements = [];
  let tableBuffer = [];

  const flushTable = (index) => {
    if (tableBuffer.length > 0) {
      const tableMarkdown = tableBuffer.join("\n");
      finalElements.push(
        <div key={`table-${index}`} className="my-4 overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              table: ({node, ...props}) => <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-[#1e1e20]" {...props} />,
              thead: ({node, ...props}) => <thead className="bg-gray-50 dark:bg-[#2e2e33]" {...props} />,
              th: ({node, ...props}) => <th className="px-4 py-2 text-left text-xs font-bold uppercase text-blue-600 dark:text-blue-400" {...props} />,
              td: ({node, ...props}) => <td className="px-4 py-2 text-sm border-t border-gray-100 dark:border-gray-700" {...props} />,
              // Mengatasi masalah bold di dalam tabel:
              strong: ({node, ...props}) => <strong className="font-bold text-gray-900 dark:text-white" {...props} />
            }}
          >
            {tableMarkdown}
          </ReactMarkdown>
        </div>
      );
      tableBuffer = [];
    }
  };

  rawLines.forEach((line, index) => {
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith("|")) {
      tableBuffer.push(trimmedLine);
    } else {
      flushTable(index);
      if (trimmedLine === "") return;

      // Render baris biasa menggunakan renderStyledText agar animasi tetap jalan
      const styledLine = renderStyledText(trimmedLine, isAI);

      if (trimmedLine === "---" || trimmedLine === "***") {
        finalElements.push(
          <hr key={index} className={`my-4 border-t ${isAI ? "border-gray-200 dark:border-[#2E2E33]" : "border-white/20"}`} />
        );
      } else {
        const numberMatch = trimmedLine.match(/^(\d+)\.\s+(.+)/);
        const bulletMatch = trimmedLine.match(/^[-*•]\s+(.+)/);

        if (numberMatch) {
          const [, number, contentText] = numberMatch;
          finalElements.push(
            <div className="flex" key={index}>
              <span className={`font-bold min-w-[1.2rem] ${accentColor}`}>{number}.</span>
              <div className="ml-2" dangerouslySetInnerHTML={{ __html: renderStyledText(contentText, isAI) }} />
            </div>
          );
        } else if (bulletMatch) {
          const [, contentText] = bulletMatch;
          finalElements.push(
            <div className="flex ml-5" key={index}>
              <span className={`${accentColor} mr-2`}>•</span>
              <div dangerouslySetInnerHTML={{ __html: renderStyledText(contentText, isAI) }} />
            </div>
          );
        } else {
          finalElements.push(<div key={index} dangerouslySetInnerHTML={{ __html: styledLine }} />);
        }
      }
    }
  });

  flushTable("final");

  return (
    <div className={`markdown-body space-y-2 leading-relaxed ${baseTextColor}`}>
      {finalElements}
    </div>
  );
};

export default FormattedMessage;