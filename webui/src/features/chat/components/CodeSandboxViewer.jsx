import React, { useMemo } from 'react';

/**
 * Membersihkan kode JSX AI dari ES Module imports & export statements
 * sebelum di-inject ke iframe.
 */
function preprocessReactCode(rawCode) {
  // Deteksi nama komponen export default
  let appName = 'App';
  const fnMatch = rawCode.match(/export\s+default\s+function\s+(\w+)/);
  const varMatch = rawCode.match(/export\s+default\s+(\w+)\s*;?\s*$/m);
  if (fnMatch) appName = fnMatch[1];
  else if (varMatch && varMatch[1] !== 'function') appName = varMatch[1];

  const processed = rawCode
    // Transpiled imports untuk library umum agar tidak ReferenceError
    .replace(/^import\s*\{\s*([^}]+)\s*\}\s*from\s*['"]lucide-react['"]\s*;?\s*$/gm, (_, p1) => `const { ${p1.replace(/\s+as\s+/g, ': ')} } = window.lucideMock || {};`)
    .replace(/^import\s*\{\s*([^}]+)\s*\}\s*from\s*['"]react-router-dom['"]\s*;?\s*$/gm, (_, p1) => `const { ${p1.replace(/\s+as\s+/g, ': ')} } = window.ReactRouterDOM || {};`)
    .replace(/^import\s*\{\s*([^}]+)\s*\}\s*from\s*['"]react['"]\s*;?\s*$/gm, (_, p1) => `const { ${p1.replace(/\s+as\s+/g, ': ')} } = React || {};`)
    // Hapus semua baris import ES Module sisanya (termasuk file lokal)
    .replace(/^import\s+.*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '')
    .replace(/^import\s+['"][^'"]+['"]\s*;?\s*$/gm, '')
    // export default function Foo → function Foo
    .replace(/export\s+default\s+function\s+/g, 'function ')
    // export default const/arrow → bersihkan
    .replace(/export\s+default\s+/g, '')
    // named exports
    .replace(/^export\s*\{[^}]*\}\s*;?\s*$/gm, '')
    .replace(/^export\s+(const|let|var|function|class)\s+/gm, '$1 ')
    .trim();

  return { processed, appName };
}

/**
 * LivePreview - Render React/HTML menggunakan iframe + Babel.transform() manual.
 * TIDAK pakai <script type="text/babel"> yang memicu caching.ts error.
 * TIDAK butuh Sandpack / CodeSandbox cloud.
 */
export default function CodeSandboxViewer({ code, relatedCode = '', language, darkMode }) {
  const isReact = language === 'react' || language === 'jsx' || language === 'js';

  const srcdoc = useMemo(() => {
    if (!isReact) {
      // Gabungkan related HTML/CSS/JS script jika diperlukan nanti (untuk saat ini cukup code utama)
      return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body { margin:0; font-family: -apple-system, sans-serif; background: ${darkMode ? '#1e1e1e' : '#ffffff'}; color: ${darkMode ? '#e2e8f0' : '#0f172a'}; }</style>
</head>
<body>${code}</body>
</html>`;
    }

    const { processed: mainProcessed, appName } = preprocessReactCode(code);
    const relatedProcessed = relatedCode ? preprocessReactCode(relatedCode).processed : '';
    const finalCode = relatedProcessed + '\n\n' + mainProcessed;

    // Escape backtick dan backslash dalam kode agar aman di dalam template literal JS
    const escapedCode = finalCode
      .replace(/\\/g, '\\\\')
      .replace(/`/g, '\\`')
      .replace(/\${/g, '\\${');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@remix-run/router@1.15.3/dist/router.umd.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-router@6.22.3/dist/umd/react-router.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-router-dom@6.22.3/dist/umd/react-router-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone@7.23.10/babel.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { margin:0; padding:0; min-height:100vh; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: ${darkMode ? '#1e1e1e' : '#f8fafc'}; color: ${darkMode ? '#e2e8f0' : '#0f172a'}; }
    #root { min-height: 100vh; }
    .err { padding:20px; background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.3); border-radius:8px; color:#ef4444; font-family:monospace; font-size:12px; margin:20px; white-space:pre-wrap; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script>
    // Expose React hooks sebagai global var (karena import sudah distrip)
    var useState = React.useState;
    var useEffect = React.useEffect;
    var useRef = React.useRef;
    var useCallback = React.useCallback;
    var useMemo = React.useMemo;
    var useReducer = React.useReducer;
    var useContext = React.useContext;
    var createContext = React.createContext;
    var useId = React.useId;
    var forwardRef = React.forwardRef;
    var memo = React.memo;
    var Fragment = React.Fragment;
    
    // Expose React Router DOM
    if (window.ReactRouterDOM) {
      var BrowserRouter = window.ReactRouterDOM.MemoryRouter; // Force MemoryRouter to prevent URL inheritance
      var MemoryRouter = window.ReactRouterDOM.MemoryRouter;
      var HashRouter = window.ReactRouterDOM.HashRouter;
      var Router = window.ReactRouterDOM.MemoryRouter; // Alias for Router
      var Routes = window.ReactRouterDOM.Routes;
      var Route = window.ReactRouterDOM.Route;
      var Link = window.ReactRouterDOM.Link;
      var NavLink = window.ReactRouterDOM.NavLink;
      var useNavigate = window.ReactRouterDOM.useNavigate;
      var useParams = window.ReactRouterDOM.useParams;
      var useLocation = window.ReactRouterDOM.useLocation;
      var Outlet = window.ReactRouterDOM.Outlet;
    }
    
    // Mock Lucide React Icons (kembalikan SVG dummy dinamis)
    window.lucideMock = new Proxy({}, {
      get: function(target, prop) {
        if (prop === '__esModule') return false;
        return function(props) {
          var size = props.size || 24;
          var color = props.color || 'currentColor';
          return React.createElement('svg', 
            { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', className: props.className, style: props.style },
            React.createElement('rect', { x: 3, y: 3, width: 18, height: 18, rx: 4 }),
            React.createElement('circle', { cx: 12, cy: 12, r: 3 })
          );
        };
      }
    });

    window.addEventListener('load', function() {
      try {
        // Panggil Babel.transform() MANUAL (bukan <script type="text/babel">)
        // Ini bypass caching.ts sepenuhnya, tidak ada IndexedDB/localStorage touch
        var rawCode = \`${escapedCode}\`;

        var result = Babel.transform(rawCode, {
          presets: ['react'],
          filename: 'App.jsx'
        });

        // Eksekusi kode yang sudah ditranspile sebagai fungsi biasa
        var fn = new Function(result.code + '\\n; return ${appName};');
        var App = fn();

        if (typeof App !== 'function') {
          throw new Error('Komponen "${appName}" tidak ditemukan atau bukan sebuah function. Pastikan ada: function ${appName}() { ... }');
        }

        var root = ReactDOM.createRoot(document.getElementById('root'));
        
        // Bungkus dengan MemoryRouter agar hooks seperti useNavigate bekerja secara terisolasi 
        // dan tidak terpengaruh oleh URL dari parent window
        var AppElement = React.createElement(App);
        if (window.ReactRouterDOM && window.ReactRouterDOM.MemoryRouter) {
          AppElement = React.createElement(window.ReactRouterDOM.MemoryRouter, null, AppElement);
        }
        
        root.render(AppElement);
      } catch (err) {
        let msg = err.message;
        if (msg.includes("is not defined")) {
           msg += '\\n\\n(💡 Tips: Code Sandbox hanya mendukung Single-File Component. Jika AI membuat multiple file dan melakukan import file lokal seperti "import Login from \\'./Login\\'", maka komponen tersebut tidak akan ditemukan. Mintalah AI untuk menggabungkan semuanya ke dalam satu file.)';
        }
        document.getElementById('root').innerHTML =
          '<div class="err">⚠️ Render Error:\\n\\n' + msg + '</div>';
      }
    });
  </script>
</body>
</html>`;
  }, [code, language, darkMode]);

  return (
    <div style={{ width: '100%', height: '100%', flex: 1, display: 'flex', flexDirection: 'column' }}>
      <iframe
        srcDoc={srcdoc}
        title="Live Preview"
        sandbox="allow-scripts allow-forms allow-same-origin"
        style={{
          width: '100%',
          flex: 1,
          border: 'none',
          background: darkMode ? '#1e1e1e' : '#f8fafc',
          minHeight: '500px'
        }}
      />
    </div>
  );
}
