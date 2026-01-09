import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { renderStyledText } from "./renderStyledText";

const FormattedMessage = ({ text, showNotification, isAI }) => {
  if (!text) return null;

  // 1. Pre-processing: Bersihkan text
  let cleanText = typeof text !== "string" ? String(text) : text;
  cleanText = cleanText
    .replace(/&nbsp;/g, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .trim();

  // 2. Logic Khusus Tabel:
  // Jika teks mengandung pola tabel (| --- |), gunakan ReactMarkdown secara utuh
  // karena tabel tidak bisa diproses baris-per-baris secara manual.
  const hasTable = /\|(.+)\|/.test(cleanText) && /\|[\s-]*:?[\s-]*\|/.test(cleanText);

  if (isAI && hasTable) {
    return (
      <div className={`markdown-body prose prose-sm max-w-none leading-relaxed 
        ${isAI ? "text-gray-800 dark:text-gray-200" : "text-white"}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: ({ node, ...props }) => (
              <div className="my-4 overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-[#1e1e20]" {...props} />
              </div>
            ),
            thead: ({ node, ...props }) => <thead className="bg-gray-50 dark:bg-[#2e2e33]" {...props} />,
            th: ({ node, ...props }) => (
              <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400" {...props} />
            ),
            td: ({ node, ...props }) => (
              <td className="px-4 py-2 text-sm border-t border-gray-100 dark:border-gray-700" {...props} />
            ),
          }}
        >
          {cleanText}
        </ReactMarkdown>
      </div>
    );
  }

  // 3. Logic Manual Lu (Untuk Text Biasa & Animasi Typing)
  const styledText = renderStyledText(cleanText, isAI);
  const lines = styledText.split("\n").filter((line) => line.trim() !== "");

  const baseTextColor = isAI ? "text-gray-800 dark:text-gray-200" : "text-white";
  const accentColor = isAI ? "text-blue-600 dark:text-blue-400" : "text-blue-200";

  return (
    <div className={`markdown-body space-y-2 leading-relaxed ${baseTextColor}`}>
      {lines.map((line, lineIndex) => {
        const trimmedLine = line.trim();

        // Handler Horizontal Rule
        if (trimmedLine === "---" || trimmedLine === "***") {
          return (
            <hr
              key={lineIndex}
              className={`my-4 border-t ${
                isAI ? "border-gray-200 dark:border-[#2E2E33]" : "border-white/20"
              }`}
            />
          );
        }

        const numberMatch = trimmedLine.match(/^(\d+)\.\s+(.+)/);
        const bulletMatch = trimmedLine.match(/^[-*•]\s+(.+)/);
        const isHTML = /<(h1|h2|h3|blockquote)/.test(trimmedLine);

        if (isHTML) {
          return <div key={lineIndex} dangerouslySetInnerHTML={{ __html: trimmedLine }} />;
        } else if (numberMatch) {
          const [, number, contentText] = numberMatch;
          return (
            <div className="flex" key={lineIndex}>
              <span className={`font-bold min-w-[1.2rem] ${accentColor}`}>{number}.</span>
              <div className="ml-2" dangerouslySetInnerHTML={{ __html: contentText }} />
            </div>
          );
        } else if (bulletMatch) {
          const [, contentText] = bulletMatch;
          return (
            <div className="flex ml-5" key={lineIndex}>
              <span className={`${accentColor} mr-2`}>•</span>
              <div dangerouslySetInnerHTML={{ __html: contentText }} />
            </div>
          );
        }

        return <div key={lineIndex} dangerouslySetInnerHTML={{ __html: trimmedLine }} />;
      })}
    </div>
  );
};

export default FormattedMessage;