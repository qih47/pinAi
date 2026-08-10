const fs = require('fs');
const file = '/home/qisthi/pinAi/webui/src/features/chat/components/CakraResponseRenderer.jsx';
let content = fs.readFileSync(file, 'utf8');

// 1. Add latestProps
content = content.replace(
    "const tGlobal = translations[language] || translations.id;",
    "const tGlobal = translations[language] || translations.id;\n    const latestProps = React.useRef({ darkMode, theme, searchQuery, isStreaming, language });\n    latestProps.current = { darkMode, theme, searchQuery, isStreaming, language };"
);

// 2. Remove dependencies from useMemo
content = content.replace(
    "}), [darkMode, theme, searchQuery, isStreaming]);",
    "}), []);"
);

// 3. Inject latestProps reading into every component function
// Find all occurrences of component functions: e.g. `p({ children, ...props }) {`
const components = ['p', 'h1', 'h2', 'h3', 'h4', 'ol', 'ul', 'li', 'input', 'strong', 'blockquote', 'a', 'table', 'th', 'td', 'code'];
components.forEach(comp => {
    const regex = new RegExp(`(\\b${comp}\\s*\\(\\{.*?\\}\\)\\s*\\{)`, 'g');
    content = content.replace(regex, `$1\n            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;`);
});

fs.writeFileSync(file, content);
