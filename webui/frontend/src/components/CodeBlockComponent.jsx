import React, { useEffect, useRef } from "react";
import hljs from "highlight.js";
import { copyToClipboard } from "../utils/copyToClipboard";

const CodeBlockComponent = ({ language, content, showNotification, isAnimatingBlock }) => {
  const codeRef = useRef(null);

  useEffect(() => {
    if (codeRef.current && !isAnimatingBlock) {
      codeRef.current.removeAttribute("data-highlighted");
      hljs.highlightElement(codeRef.current);
    }
  }, [content, isAnimatingBlock]);

  return (
    <div className="code-block-container my-4 rounded-xl overflow-hidden border border-gray-200 dark:border-[#3E3E42] shadow-lg">
      {/* Header Bar */}
      <div className="flex justify-between items-center bg-[#F8FAFC] dark:bg-[#2E2E33] px-4 py-2.5 border-b border-gray-200 dark:border-transparent">
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-gray-500 dark:text-gray-400">
          {language || "source code"}
        </span>
        <button
          onClick={() => copyToClipboard(content, showNotification)}
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 dark:text-gray-500 hover:text-blue-500 dark:hover:text-white transition-all"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </button>
      </div>

      {/* Code Content */}
      <pre 
        className="m-0 p-5 overflow-x-auto text-sm !bg-[#E9EEF6] dark:!bg-[#232326] transition-all duration-300"
        style={{ 
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace", 
            lineHeight: '1.8' 
        }}
      >
        <code 
          ref={codeRef} 
          className={`language-${language || 'plaintext'} !bg-transparent !p-0`}
        >
          {content}
          {isAnimatingBlock && (
            <span className="inline-block w-2 h-4 ml-1 bg-blue-500 animate-pulse align-middle"></span>
          )}
        </code>
      </pre>
    </div>
  );
};

export default CodeBlockComponent;