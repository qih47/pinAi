import React from "react";
import { renderStyledText } from "./renderStyledText";

const FormattedMessage = ({ text, showNotification, isAI }) => {
  if (!text) return null;
  let cleanText = typeof text !== "string" ? String(text) : text;
  cleanText = cleanText
    .replace(/&nbsp;/g, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .trim();

  const styledText = renderStyledText(cleanText, isAI);
  const lines = styledText.split("\n").filter((line) => line.trim() !== "");

  const baseTextColor = isAI ? "text-gray-800" : "text-white";
  const accentColor = isAI ? "text-blue-600" : "text-blue-200";

  return (
    <div className={`markdown-body space-y-2 leading-relaxed ${baseTextColor}`}>
      {lines.map((line, lineIndex) => {
        const trimmedLine = line.trim();
        if (trimmedLine === "---" || trimmedLine === "***") {
          return (
            <hr
              key={lineIndex}
              className={`my-4 border-t ${isAI ? "border-gray-200" : "border-white/20"}`}
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