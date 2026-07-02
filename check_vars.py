import re

with open('webui/src/features/chat/ChatPage.backup.jsx', 'r') as f:
    content = f.read()

# Get all declarations in the component body
body_start = content.find('export default function ChatPage({')
return_start = content.find('  return (\n    <div style={{ ...styles.root')

body = content[body_start:return_start]

# extract all let/const declarations
decls = set()
for match in re.finditer(r'(?:const|let)\s+(?:\[(.*?)\]|\{(.*?)\}|([a-zA-Z0-9_]+))\s*=', body):
    groups = match.groups()
    if groups[0]: # array destructuring
        vars = [v.strip() for v in groups[0].split(',')]
        for v in vars:
            if v: decls.add(v)
    elif groups[1]: # object destructuring
        vars = [v.split(':')[0].strip() for v in groups[1].split(',')]
        for v in vars:
            if v: decls.add(v)
    elif groups[2]:
        decls.add(groups[2])

# Add functions declared as function XXX()
for match in re.finditer(r'function\s+([a-zA-Z0-9_]+)\s*\(', body):
    decls.add(match.group(1))

# now parse the JSX part
jsx = content[return_start:]
# find all words in JSX
words = set(re.findall(r'[a-zA-Z0-9_]+', jsx))

# the intersection of decls and words is what MUST be returned
required = decls.intersection(words)

# let's write out the required variables
print(", ".join(sorted(required)))
