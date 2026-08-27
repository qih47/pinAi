/**
 * Resilient Partial JSON Parser
 * Secara deterministik memperbaiki dan menutup JSON yang belum selesai (streaming)
 * Menggunakan stack tracking untuk braces {} dan brackets [].
 */
export function parsePartialJSON(jsonString) {
  if (!jsonString || typeof jsonString !== 'string') return null;
  const str = jsonString.trim();
  if (!str) return null;

  // 1. Coba parse langsung jika JSON sudah utuh
  try {
    return JSON.parse(str);
  } catch (_) {}

  // 2. Ambil substring mulai dari kurung buka pertama '{' atau '['
  const firstBrace = str.indexOf('{');
  const firstBracket = str.indexOf('[');
  let startIdx = 0;
  if (firstBrace !== -1 && firstBracket !== -1) {
    startIdx = Math.min(firstBrace, firstBracket);
  } else if (firstBrace !== -1) {
    startIdx = firstBrace;
  } else if (firstBracket !== -1) {
    startIdx = firstBracket;
  } else {
    return null;
  }

  const target = str.substring(startIdx);

  // Coba parse target langsung
  try {
    return JSON.parse(target);
  } catch (_) {}

  // 3. Deterministic Stack-Based Auto-Repair
  let inString = false;
  let isEscaped = false;
  const stack = [];

  for (let i = 0; i < target.length; i++) {
    const char = target[i];

    if (isEscaped) {
      isEscaped = false;
      continue;
    }

    if (char === '\\') {
      isEscaped = true;
      continue;
    }

    if (char === '"') {
      inString = !inString;
      continue;
    }

    if (!inString) {
      if (char === '{') {
        stack.push('}');
      } else if (char === '[') {
        stack.push(']');
      } else if (char === '}') {
        if (stack.length > 0 && stack[stack.length - 1] === '}') {
          stack.pop();
        }
      } else if (char === ']') {
        if (stack.length > 0 && stack[stack.length - 1] === ']') {
          stack.pop();
        }
      }
    }
  }

  // Jika string terpotong di tengah jalan, tutup tanda kutip
  let repaired = target;
  if (inString) {
    repaired += '"';
  }

  // Bersihkan trailing koma atau titik dua yang menggantung sebelum ditutup
  repaired = repaired.replace(/,\s*$/, '').replace(/:\s*$/, ': null');

  // Tutup semua objek/array sesuai urutan stack terbalik
  for (let i = stack.length - 1; i >= 0; i--) {
    repaired += stack[i];
  }

  try {
    return JSON.parse(repaired);
  } catch (_) {
    // Fallback: jika trailing property key belum selesai, tambahkan value dummy
    try {
      const fallback = repaired.replace(/"[^"]*"\s*$/, '""');
      return JSON.parse(fallback);
    } catch (_) {
      return null;
    }
  }
}

