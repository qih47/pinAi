import os

filepath = 'webui/src/features/chat/ChatPage.jsx'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove dead code from bottom to top to avoid line number shifting
# 1. Dead Right Sidebar <aside> block (lines 2252 - 2701)
# 2. Dead renderInputForm function (lines 930 - 1445)

ranges_to_delete = [
    (2252, 2701),
    (930, 1445)
]

imports_to_remove = [
    'import CakraResponseRenderer from "./components/CakraResponseRenderer";',
    "import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';",
    "import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';",
    'import CustomModeSelector from "./components/CustomModeSelector";',
    'import PlusButton from "./components/PlusButton";',
    'import SendButton from "./components/SendButton";'
]

new_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    
    # Check if line is within any of the deletion ranges
    skip_range = False
    for r_start, r_end in ranges_to_delete:
        if r_start <= line_num <= r_end:
            skip_range = True
            break
            
    if skip_range:
        continue
        
    # Check if line is one of the dead imports
    if line.strip() in imports_to_remove:
        continue
        
    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Dead code successfully removed from ChatPage.jsx!")
