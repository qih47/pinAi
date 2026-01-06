import React from "react";
import { copyToClipboard } from "../utils/copyToClipboard";

const CodeBlockComponent = ({ language, content, showNotification, isAnimatingBlock }) => {
  return (
    <div className="code-block-container my-3">
      <div className="code-header flex justify-between items-center bg-gray-800 text-gray-200 px-3 py-2 rounded-t-lg text-sm">
        <span className="font-medium capitalize">{language || "code"}</span>
        <button
          onClick={() => copyToClipboard(content, showNotification)}
          className="copy-button text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded transition-colors flex items-center gap-1"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3 w-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
        </button>
      </div>
      <pre className="hljs bg-gray-900 text-gray-100 p-4 rounded-b-lg overflow-x-auto text-sm">
        <code className={`language-${language}`}>
          {content}
          {isAnimatingBlock && <span className="typing-cursor"></span>}
        </code>
      </pre>
    </div>
  );
};

export default CodeBlockComponent;