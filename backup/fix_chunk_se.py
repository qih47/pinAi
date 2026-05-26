#!/usr/bin/env python3

# Read the file
with open('/workspace/embeddings/chunk_se.py', 'r') as f:
    lines = f.readlines()

# Define the new section
new_lines = [
    "        elif re.match(r'^\\s*\\d+\\.\\s*', stripped):\n",
    "            # Set status bahwa kita sekarang dalam konteks struktur hukum\n",
    "            in_structured_section = True\n",
    "            # Simpan section sebelumnya beserta sub-itemsnya jika ada\n",
    "            if current_section:\n",
    "                sections.append(current_section)\n",
    "                # Tambahkan sub-items\n",
    "                for sub_item in current_sub_items:\n",
    "                    sections.append(sub_item)\n",
    "            \n",
    "            # Ekstrak nomor dan judul\n",
    "            parts = re.split(r'\\.\\s*', stripped, 1)\n",
    "            number = parts[0].strip()\n",
    "            title = parts[1].strip() if len(parts) > 1 else \"\"\n",
    "            \n",
    "            current_section = {\n",
    "                'type': 'butir',\n",
    "                'title': f\"{number}. {title}\".strip(),\n",
    "                'content': stripped,\n",
    "                'level': 2,\n",
    "                'order': item_counter,\n",
    "                'parent_id': None,  # Akan diisi di database berdasarkan pasal/bab jika ada\n",
    "                'metadata': {'item_number': number}\n",
    "            }\n",
    "            current_sub_items = []\n",
    "            item_counter += 1\n",
    "            \n"
]

# Replace lines 99-127 (0-indexed: 98-126) with new_lines
lines[98:127] = new_lines

# Write the file back
with open('/workspace/embeddings/chunk_se.py', 'w') as f:
    f.writelines(lines)

print("File embeddings/chunk_se.py has been updated successfully!")