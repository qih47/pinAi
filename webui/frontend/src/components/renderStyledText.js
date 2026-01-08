export const renderStyledText = (text, isAI) => {
  if (!text || typeof text !== "string") return text;
  let processedText = text;

  // Handler Warna Text & Heading
  // AI Mode: Light (Gray-900) | Dark (White)
  // User Mode: Always White (karena bubble biru)
  const hColor = isAI 
    ? "text-gray-900 dark:text-gray-100" 
    : "text-white";

  // Handler Blockquote Border & Text
  const bColor = isAI
    ? "border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400"
    : "border-blue-300 text-blue-100";

  // Handler Link
  const linkColor = isAI
    ? "text-blue-600 dark:text-blue-400 hover:underline"
    : "text-blue-200 hover:text-white underline";

  // Handler Code (Inline Code)
  const codeClass = isAI 
    ? "bg-gray-200 dark:bg-[#2E2E33] text-red-600 dark:text-red-400" 
    : "bg-blue-800 text-blue-100";

  // Handler Horizontal Rule (HR)
  const hrColor = isAI 
    ? "border-gray-200 dark:border-[#2E2E33]" 
    : "border-white/20";

  // --- Regex Processing ---
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
  
  processedText = processedText.replace(/`([^`]+)`/g, `<code class="${codeClass} px-1.5 py-0.5 rounded font-mono text-[0.8em] break-all">$1</code>`);
  
  processedText = processedText.replace(/^(--[-]+|\*\*[\*]+)$/gm, `<hr class="my-4 border-t ${hrColor}" />`);

  return processedText;
};