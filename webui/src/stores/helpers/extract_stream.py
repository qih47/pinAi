import sys

with open('/home/qisthi/pinAi/webui/src/stores/chatStore.js', 'r') as f:
    lines = f.readlines()

stream_helper_content = 'import * as endpoints from "../../services/endpoints";\n\n'
stream_helper_content += "".join(lines[8:371]).replace('function _normalizeAttachments', 'export function normalizeAttachments').replace('async function _performStream', 'export async function performStream')

with open('/home/qisthi/pinAi/webui/src/stores/helpers/streamHelper.js', 'w') as f:
    f.write(stream_helper_content)

print("Extracted stream helper")
