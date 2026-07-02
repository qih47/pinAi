import re

with open('webui/src/features/chat/ChatPage.jsx', 'r') as f:
    content = f.read()

# Split into imports, logic, and return
logic_start = content.find('export default function ChatPage({')
return_start = content.find('  return (\n    <div style={{ ...styles.root')

imports = content[:logic_start]
logic = content[logic_start:return_start]
return_block = content[return_start:]

# Extract arguments of ChatPage
args_match = re.search(r'export default function ChatPage\(\{([\s\S]*?)\}\) {', logic)
args = args_match.group(1).strip() if args_match else ""

# Replace function signature for hook
logic_body = logic[args_match.end():]

# We need to collect all state variables, refs, functions to return them from the hook.
# A regex to find all consts let vars and functions declared at the root level of ChatPage
# Actually, returning an object with everything needed is safe but tedious to write regex for.
# Instead, let's use a robust regex to find all top-level declarations.
declarations = re.findall(r'^(?:  )?const \[([a-zA-Z0-9_]+),', logic_body, re.MULTILINE)
declarations += re.findall(r'^(?:  )?const ([a-zA-Z0-9_]+) = (?:useRef|useMemo|useChatStore|useChatAuthStore|useToast|useNavigate|useParams)', logic_body, re.MULTILINE)
declarations += re.findall(r'^(?:  )?const ([a-zA-Z0-9_]+) = (?:useCallback|function|\([^)]*\) =>)', logic_body, re.MULTILINE)
declarations += re.findall(r'^(?:  )?const ([a-zA-Z0-9_]+) = (?:[a-zA-Z0-9_]+ \?|\[\.\.\.)', logic_body, re.MULTILINE)

# Also capture simple variable declarations like:
# const theme = darkMode ? darkColors : lightColors;
# const hasSidebar = !isGuest && currentIsLoggedIn;
# const mainMarginLeft = ...
declarations += ['theme', 'hasSidebar', 'mainMarginLeft', 'mainMarginRight', 'isThinking', 'isStreamingText', 'isEmptyChat', 'showWelcome']

# Let's clean up and deduplicate
decls = set(declarations)

# Remove things that are not needed to be returned (like internal variables)
# But it's safer to just return all top-level variables.

return_statement = "  return {\n    " + ",\n    ".join(sorted(decls)) + "\n  };\n"

hook_content = f"""import React, {{ useState, useRef, useEffect, useMemo, useCallback }} from "react";
import {{ useNavigate, useParams }} from "react-router-dom";
import {{ useChatStore, API_BASE, getUploadUrl }} from "../../../stores/chatStore";
import {{ useChatAuthStore }} from "../../../stores/authStore";
import {{ uploadDocuments }} from "../../../services/endpoints";
import useToast from "../../../hooks/useToast";
import {{ styles, lightColors, darkColors }} from "../chatPage.styles";

export function useChatLogic({{ {args} }}) {{
{logic_body}
{return_statement}
}}
"""

with open('webui/src/features/chat/hooks/useChatLogic.js', 'w') as f:
    f.write(hook_content)

# Now, we rewrite ChatPage.jsx to use this hook
chatpage_content = f"""{imports}import {{ useChatLogic }} from "./hooks/useChatLogic";

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function ChatPage({{ {args} }}) {{
  const chatLogic = useChatLogic({{ {args} }});
  const {{
    {", ".join(sorted(decls))}
  }} = chatLogic;

{return_block}"""

with open('webui/src/features/chat/ChatPage.jsx', 'w') as f:
    f.write(chatpage_content)

print("Extraction completed.")
