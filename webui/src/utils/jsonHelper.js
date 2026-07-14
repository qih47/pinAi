export function parsePartialJSON(jsonString) {
  let str = jsonString;
  try {
    return JSON.parse(str);
  } catch (e) {}
  
  // A naive but often effective way to close partial JSON arrays/objects
  let openBraces = 0;
  let openBrackets = 0;
  let inString = false;
  let escape = false;

  for (let i = 0; i < str.length; i++) {
    const char = str[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (char === '\\') {
      escape = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (!inString) {
      if (char === '{') openBraces++;
      if (char === '}') openBraces--;
      if (char === '[') openBrackets++;
      if (char === ']') openBrackets--;
    }
  }

  if (inString) str += '"';
  
  // Close any unclosed objects and arrays
  // We need to figure out the order, but naively we can just append missing braces
  // This is a simple approach, a robust one is more complex.
  // Actually, there's a library for this, or we can just append `]}` until it parses.
  
  // Better naive approach:
  let suffix = '';
  if (inString) suffix += '"';
  
  // Try appending combinations of closing brackets
  const combinations = [
    '',
    '}',
    ']',
    '}',
    ']}',
    ']} ]',
    '}]',
    '"]}',
    '"}',
    '"]'
  ];
  
  for (let i = 0; i < 20; i++) {
     try {
       return JSON.parse(str + '"'.repeat(i%2) + '}'.repeat(Math.floor(i/2)) + ']'.repeat(i%3));
     } catch(e) {}
  }
  
  // If we really can't, return null
  return null;
}
