import React, { useState, useEffect } from "react";
import FormattedMessage from "./FormattedMessage";
import CodeBlockComponent from "./CodeBlockComponent";
import { extractCodeBlocks } from "../utils/extractCodeBlocks";

const MessageRenderer = ({ text, showNotification, isTyping = false, isAI = false }) => {
  const [displayText, setDisplayText] = useState("");
  const [isAnimating, setIsAnimating] = useState(false);
  const { codeBlocks: originalBlocks } = extractCodeBlocks(text || "");

  useEffect(() => {
    if (!text) return;
    if (isTyping) {
      setIsAnimating(true);
      let i = 0;
      const typingSpeed = 10;
      const typeTimer = setInterval(() => {
        if (i < text.length) {
          setDisplayText(text.slice(0, i + 1));
          i++;
        } else {
          clearInterval(typeTimer);
          setIsAnimating(false);
        }
      }, typingSpeed);
      return () => clearInterval(typeTimer);
    } else {
      setDisplayText(text);
    }
  }, [text, isTyping]);

  const renderContent = () => {
    if (originalBlocks.length === 0) {
      return (
        <>
          <FormattedMessage text={displayText} showNotification={showNotification} isAI={isAI} />
          {isAnimating && <span className="typing-cursor"></span>}
        </>
      );
    }

    const parts = text.split(/(```[\s\S]*?```)/g);
    let currentPos = 0;
    return parts.map((part, index) => {
      const partStart = currentPos;
      const partEnd = currentPos + part.length;
      currentPos = partEnd;
      if (displayText.length <= partStart) return null;
      const visiblePart = text.slice(partStart, Math.min(partEnd, displayText.length));
      if (part.startsWith("```")) {
        const lines = visiblePart.split("\n");
        const langMatch = lines[0].match(/```(\w+)/);
        const language = langMatch ? langMatch[1] : "code";
        let content = lines.slice(1).join("\n").replace(/```$/, "");
        const isCurrentlyTypingThisBlock = displayText.length > partStart && displayText.length < partEnd;
        return (
          <CodeBlockComponent
            key={index}
            language={language}
            content={content}
            showNotification={showNotification}
            isAnimatingBlock={isCurrentlyTypingThisBlock}
          />
        );
      } else {
        return <FormattedMessage key={index} text={visiblePart} showNotification={showNotification} isAI={isAI} />;
      }
    });
  };

// Menggunakan nilai 720px (di antara 672px dan 768px)
return <div className="space-y-3 message-renderer max-w-[720px] mx-auto">{renderContent()}</div>;
};

export default MessageRenderer;