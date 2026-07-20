import React, { useState, useEffect } from 'react';
import { X, Folder, File as FileIcon, LogIn, HardDrive, RefreshCw } from 'lucide-react';
import useNextcloudStore from '../../../stores/nextcloudStore';
import { translations } from '../../../utils/translations';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000';

export default function NextcloudModal({ darkMode, onFileSelect, language = 'id' }) {
  const tGlobal = translations[language] || translations.id;
  const { isModalOpen, closeModal } = useNextcloudStore();

  const [isConnected, setIsConnected] = useState(true);

  const [currentPath, setCurrentPath] = useState('/');
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isModalOpen) {
      setIsConnected(true);
      fetchFiles(currentPath);
    }
  }, [isModalOpen, currentPath]);

  const fetchFiles = async (path) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/nextcloud/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: localStorage.getItem('cakra_token') || '',
          path: path
        })
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          setIsConnected(false);
          throw new Error('Sesi berakhir atau Cloud belum terhubung. Silakan sambungkan di menu Pengaturan.');
        }
        throw new Error(tGlobal.nextcloud.fetchError);
      }

      const data = await response.json();

      // Parse XML response
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(data.raw_xml, "text/xml");
      const responses = xmlDoc.getElementsByTagNameNS("DAV:", "response");

      const parsedFiles = [];
      for (let i = 0; i < responses.length; i++) {
        const href = responses[i].getElementsByTagNameNS("DAV:", "href")[0].textContent;
        // Skip current directory reference
        if (href === `/remote.php/webdav${path}` || href === `/remote.php/webdav${path}/`) continue;

        const propstat = responses[i].getElementsByTagNameNS("DAV:", "propstat")[0];
        const prop = propstat.getElementsByTagNameNS("DAV:", "prop")[0];
        const displayname = prop.getElementsByTagNameNS("DAV:", "displayname")[0]?.textContent;

        const resourcetype = prop.getElementsByTagNameNS("DAV:", "resourcetype")[0];
        const isDir = resourcetype.getElementsByTagNameNS("DAV:", "collection").length > 0;

        let cleanName = displayname;
        if (!cleanName) {
          const parts = href.split('/').filter(Boolean);
          cleanName = decodeURIComponent(parts[parts.length - 1]);
        }

        parsedFiles.push({
          name: cleanName,
          path: href.replace('/remote.php/webdav', ''),
          isDir
        });
      }

      setFiles(parsedFiles);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = async (file) => {
    if (file.isDir) {
      setCurrentPath(file.path);
    } else {
      // It's a file, we can select it
      // Nextcloud download API returns file content.
      // Usually, we'd want to attach it as a File object to the chat.
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/api/nextcloud/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: localStorage.getItem('cakra_token') || '', path: file.path })
        });

        if (!res.ok) throw new Error(tGlobal.nextcloud.downloadError);

        const blob = await res.blob();
        const downloadedFile = new File([blob], file.name, { type: blob.type || 'text/plain' });

        if (onFileSelect) {
          onFileSelect([downloadedFile]);
        }

        closeModal();
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
  };

  const navigateUp = () => {
    if (currentPath === '/' || currentPath === '') return;
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const newPath = '/' + parts.join('/') + (parts.length > 0 ? '/' : '');
    setCurrentPath(newPath);
  };

  if (!isModalOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={`w-full max-w-md rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] ${darkMode ? 'bg-gray-800 text-gray-100 border border-gray-700' : 'bg-white text-gray-800'}`}>

        {/* Header */}
        <div className={`p-4 flex items-center justify-between border-b ${darkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'}`}>
          <div className="flex items-center gap-2">
            <HardDrive className="text-blue-500" />
            <h3 className="font-bold">PinCloud Storage</h3>
          </div>
          <button onClick={closeModal} className={`p-1 rounded-md ${darkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200'}`}>
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 flex-1 overflow-y-auto">
          {!isConnected ? (
            <div className="text-center py-10 flex flex-col items-center justify-center">
              <CloudIcon className="w-16 h-16 mx-auto text-blue-500 mb-4 opacity-50" />
              <p className="text-sm font-semibold mb-2">Cloud Pindad Belum Tersambung</p>
              <p className="text-xs text-gray-500 max-w-[250px]">Silakan buka menu Pengaturan &gt; Akun untuk menautkan akun Nextcloud Anda.</p>
            </div>
          ) : (
            <div className="flex flex-col h-full">
              {/* Toolbar Path */}
              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={navigateUp}
                  disabled={currentPath === '/'}
                  className={`px-2 py-1 text-xs rounded border ${darkMode ? 'border-gray-600 hover:bg-gray-700 disabled:opacity-50' : 'border-gray-300 hover:bg-gray-100 disabled:opacity-50'}`}
                >
                  ↑ Up
                </button>
                <div className={`text-xs truncate flex-1 px-2 py-1.5 rounded ${darkMode ? 'bg-gray-700' : 'bg-gray-100'}`}>
                  {currentPath}
                </div>
                <button
                  onClick={() => fetchFiles(currentPath)}
                  className={`p-1.5 rounded ${darkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
                >
                  <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                </button>
              </div>

              {error && <div className="text-xs text-red-500 mb-4 p-2 bg-red-50 dark:bg-red-900/30 rounded">{error}</div>}

              {/* File List */}
              <div className="flex-1 min-h-[200px]">
                {loading && files.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <RefreshCw className="animate-spin text-blue-500" size={24} />
                  </div>
                ) : files.length === 0 ? (
                  <div className="text-center text-sm text-gray-500 mt-10">{tGlobal.nextcloud.emptyFolder}</div>
                ) : (
                  <div className="space-y-1">
                    {files.map((file, idx) => (
                      <div
                        key={idx}
                        onClick={() => handleFileClick(file)}
                        className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors ${darkMode ? 'hover:bg-gray-700/80' : 'hover:bg-blue-50'}`}
                      >
                        {file.isDir ? <Folder className="text-yellow-500 shrink-0" size={20} /> : <FileIcon className="text-blue-500 shrink-0" size={20} />}
                        <span className="text-sm truncate">{file.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-dashed border-gray-300 dark:border-gray-700 flex justify-between items-center">
                <span className="text-xs text-gray-500">Tersambung via Integrasi Akun</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Missing Lucide Icon fallback inline just in case
function CloudIcon(props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
    </svg>
  );
}
