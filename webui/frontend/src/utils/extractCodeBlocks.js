export const extractCodeBlocks = (text) => {
    if (!text || typeof text !== "string")
      return { textOnly: text, codeBlocks: [] };
    const parts = text.split(/(```[\s\S]*?```)/g);
    const codeBlocks = [];
    const textParts = [];
    parts.forEach((part, index) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        const lines = part.split("\n");
        const langMatch = lines[0].match(/```(\w+)/);
        const language = langMatch ? langMatch[1] : "text";
        const codeContent = lines.slice(1, lines.length - 1).join("\n");
        codeBlocks.push({
          index,
          language,
          content: codeContent,
          fullText: part,
        });
      } else if (part.trim()) {
        textParts.push(part);
      }
    });
    return {
      textOnly: textParts.join(""),
      codeBlocks,
      hasCodeBlocks: codeBlocks.length > 0,
    };
  };