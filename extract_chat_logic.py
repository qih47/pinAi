import re

with open('webui/src/features/chat/ChatPage.jsx', 'r') as f:
    content = f.read()

# Find imports
imports_end = content.find('\n// ============================================================')
imports = content[:imports_end]

# Extract logic
logic_start = content.find('export default function ChatPage({')
# find return statement of ChatPage
return_start = content.find('  return (\n    <div style={{ ...styles.root')

logic = content[logic_start:return_start]

# Modify logic to be useChatLogic
logic = logic.replace('export default function ChatPage({', 'export function useChatLogic({')

# we need to return everything
# let's write a simple extraction of all consts and functions defined at top level of useChatLogic
# It's easier to just do this manually or let the LLM do it.
