export const renderStyledText = (text, isAI) => {
    if (!text || typeof text !== "string") return text;
    let processedText = text;
  
    const hColor = isAI ? "text-gray-900" : "text-white";
    const bColor = isAI
      ? "border-gray-300 text-gray-600"
      : "border-blue-300 text-blue-100";
    const linkColor = isAI
      ? "text-blue-600 hover:underline"
      : "text-blue-200 hover:text-white underline";
  
    processedText = processedText.replace(/^#### (.*$)/gm, `<h4 class="text-base font-bold mt-3 mb-1 ${hColor}">$1</h4>`);
    processedText = processedText.replace(/^### (.*$)/gm, `<h3 class="text-lg font-bold mt-4 mb-1 ${hColor}">$1</h3>`);
    processedText = processedText.replace(/^## (.*$)/gm, `<h2 class="text-xl font-bold mt-5 mb-2 ${hColor}">$1</h2>`);
    processedText = processedText.replace(/^# (.*$)/gm, `<h1 class="text-2xl font-extrabold mt-6 mb-3 ${hColor}">$1</h1>`);
    processedText = processedText.replace(/^> (.*$)/gm, `<blockquote class="border-l-4 ${bColor} pl-4 italic my-2">$1</blockquote>`);
    processedText = processedText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, `<a href="$2" target="_blank" rel="noopener noreferrer" class="${linkColor}">$1</a>`);
    processedText = processedText.replace(/\*\*\*(.*?)\*\*\*/g, "<strong><em>$1</em></strong>");
    processedText = processedText.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    processedText = processedText.replace(/\*(.*?)\*/g, "<em>$1</em>");
    processedText = processedText.replace(/~~(.*?)~~/g, "<del>$1</del>");
    
    const codeClass = isAI ? "bg-gray-200 text-red-600" : "bg-blue-800 text-blue-100";
    processedText = processedText.replace(/`([^`]+)`/g, `<code class="${codeClass} px-1 rounded font-mono text-xs break-all">$1</code>`);
    
    const hrColor = isAI ? "border-gray-200" : "border-white/20";
    processedText = processedText.replace(/^(--[-]+|\*\*[\*]+)$/gm, `<hr class="my-4 border-t ${hrColor}" />`);
  
    return processedText;
  };