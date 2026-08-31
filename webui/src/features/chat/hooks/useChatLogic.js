import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useChatStore, API_BASE, getUploadUrl } from "../../../stores/chatStore";
import { useChatAuthStore } from "../../../stores/authStore";
import { uploadDocuments } from "../../../services/endpoints";
import useToast from "../../../hooks/useToast";
import { styles, lightColors, darkColors } from "../chatPage.styles";
import { translations } from "../../../utils/translations";

export function useChatLogic({ isGuest,
  isLoggedIn: propsIsLoggedIn,
  userData: propsUserData,
  getGreeting, }) {

  const toast = useToast();
  const [input, setInput] = useState("");
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // 📝 R4: Local Input Draft Persistence
  // Load draft on sessionId change
  useEffect(() => {
    const key = `cakra_draft_${sessionId || "new"}`;
    const savedDraft = sessionStorage.getItem(key);
    setInput(savedDraft || "");
  }, [sessionId]);

  // Save/Remove draft on input change
  useEffect(() => {
    const key = `cakra_draft_${sessionId || "new"}`;
    if (input) {
      sessionStorage.setItem(key, input);
    } else {
      sessionStorage.removeItem(key);
    }
  }, [input, sessionId]);

  const authUser = useChatAuthStore((state) => state.user);
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);
  const logout = useChatAuthStore((state) => state.logout);

  const activeIsolatedTitle = useChatStore(
    (state) => state.activeIsolatedTitle,
  );
  const setContextIsolation = useChatStore(
    (state) => state.setContextIsolation,
  );
  const activeIsolatedDocId = useChatStore(
    (state) => state.activeIsolatedDocId,
  );
  const documents = useChatStore((state) => state.documents || []);
  const isLoadingDocuments = useChatStore(
    (state) => state.isLoadingDocuments || false,
  );
  const documentsTotal = useChatStore((state) => state.documentsTotal);
  const fetchDocumentsList = useChatStore((state) => state.fetchDocumentsList);
  const artifacts = useChatStore((state) => state.artifacts || []);
  const isSplitScreen = useChatStore((state) => state.isSplitScreen);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [inputShake, setInputShake] = useState(false);
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [showRightSidebar, setShowRightSidebar] = useState(false);
  const wasLeftSidebarOpenRef = useRef(false);

  // PREVIEW MODALS STATE
  const [previewImage, setPreviewImage] = useState(null);
  const [previewDoc, setPreviewDoc] = useState(null); // { url, name, type }
  const [previewArtifact, setPreviewArtifact] = useState(null); // { filename, code, file_path, language }
  const [docContent, setDocContent] = useState("");
  const [isDocLoading, setIsDocLoading] = useState(false);
  const [artifactContent, setArtifactContent] = useState(""); // konten dari server
  const [isArtifactLoading, setIsArtifactLoading] = useState(false);

  const [language, setLanguage] = useState(() => {
    return localStorage.getItem("cakra_language") || "id";
  });
  const tToast = translations[language]?.toast || translations.id.toast;

  // Deteksi bahasa berdasarkan ekstensi file
  const detectLang = (filename) => {
    const ext = filename?.split('.').pop()?.toLowerCase();
    const langMap = {
      jsx: 'jsx', tsx: 'tsx', js: 'javascript', ts: 'typescript',
      py: 'python', css: 'css', html: 'html', json: 'json',
      md: 'markdown', sh: 'bash', sql: 'sql', yaml: 'yaml', yml: 'yaml',
    };
    return langMap[ext] || 'text';
  };

  useEffect(() => {
    if (!previewDoc) return;

    setIsDocLoading(true);
    setDocContent("");
    
    const controller = new AbortController();
    const endpoint = `${API_BASE}/api/chat/documents/extract?path=${encodeURIComponent(previewDoc.path)}`;

    fetch(endpoint, { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        if (data.content) {
          setDocContent(data.content);
        } else {
          setDocContent("Gagal mengekstrak isi dokumen.");
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setDocContent("Error saat membaca dokumen dari server.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsDocLoading(false);
        }
      });
      
    return () => controller.abort();
  }, [previewDoc]);

  // Effect: Load artifact content dari server jika file_path tersedia
  useEffect(() => {
    if (!previewArtifact) return;
    if (!previewArtifact.file_path) {
      setArtifactContent(previewArtifact.code || '');
      return;
    }
    
    // Gunakan sessionId dari route, fallback ke sessionUuid dari store
    const activeSessionId = sessionId && sessionId !== "new" ? sessionId : useChatStore.getState().sessionUuid;
    
    setIsArtifactLoading(true);
    setArtifactContent('');
    
    const controller = new AbortController();
    
    // Siapkan header otentikasi agar backend bisa mengekstrak current_user_npp
    const headers = {};
    if (authUser?.npp) {
      headers['X-NPP-Header'] = authUser.npp;
    }
    
    fetch(`${API_BASE}/api/chat/artifacts/read?filename=${encodeURIComponent(previewArtifact.file_path)}&session_id=${encodeURIComponent(activeSessionId)}`, {
      headers,
      signal: controller.signal
    })
      .then(res => res.text())
      .then(text => setArtifactContent(text))
      .catch(err => {
        if (err.name !== 'AbortError') {
          setArtifactContent(previewArtifact.code || '// Gagal memuat konten');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsArtifactLoading(false);
        }
      });
      
    return () => controller.abort();
  }, [previewArtifact, sessionId, authUser]);

  const toggleRightSidebar = () => {
    if (showRightSidebar) {
      setShowRightSidebar(false);
      // Restore left sidebar if it was open before
      const hasSidebar = !isGuest && currentIsLoggedIn;
      if (wasLeftSidebarOpenRef.current && hasSidebar && !isMobile) {
        setSidebarOpen(true);
      }
    } else {
      wasLeftSidebarOpenRef.current = sidebarOpen;
      const hasSidebar = !isGuest && currentIsLoggedIn;
      if (sidebarOpen && hasSidebar && !isMobile) {
        setSidebarOpen(false); // Collapse left sidebar
      }
      setShowRightSidebar(true);
    }
  };

  const handleFileClick = (fileObj) => {
    // fileObj format: { type: 'file', content: file_from_attachment, title: fileName }
    const file = fileObj.content;
    const fullUrl = getUploadUrl(file.file_path);
    const isPdf = file.mime_type === 'application/pdf' || fileObj.title.toLowerCase().endsWith('.pdf');
    setPreviewDoc({
      url: fullUrl,
      name: fileObj.title || file.file_name,
      type: isPdf ? 'pdf' : 'text',
      path: file.file_path,
      size: file.file_size || 0
    });

    // Auto open right sidebar and collapse left sidebar
    if (!showRightSidebar) {
      wasLeftSidebarOpenRef.current = sidebarOpen;
      const hasSidebar = !isGuest && currentIsLoggedIn;
      if (sidebarOpen && hasSidebar && !isMobile) {
        setSidebarOpen(false); // Collapse left sidebar
      }
      setShowRightSidebar(true);
    }
  };

  // Handle open artifact in sidebar
  const handleOpenArtifact = (filename, code, file_path) => {
    setPreviewArtifact({ filename, code: code || '', file_path: file_path || null, language: detectLang(filename) });
    setPreviewDoc(null); // Tutup doc preview kalau ada
    if (!showRightSidebar) {
      wasLeftSidebarOpenRef.current = sidebarOpen;
      const hasSidebar = !isGuest && currentIsLoggedIn;
      if (sidebarOpen && hasSidebar && !isMobile) setSidebarOpen(false);
      setShowRightSidebar(true);
    }
  };

  const handleDownloadArtifact = async (filename, file_path, code) => {
    if (code) {
       const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
       const url = URL.createObjectURL(blob);
       const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
       return;
    }
    try {
      const activeSessionId = sessionId && sessionId !== "new" ? sessionId : useChatStore.getState().sessionUuid;
      const headers = {};
      if (authUser?.npp) headers['X-NPP-Header'] = authUser.npp;
      const res = await fetch(`${API_BASE}/api/chat/artifacts/read?filename=${encodeURIComponent(file_path || filename)}&session_id=${encodeURIComponent(activeSessionId)}`, { headers });
      if (!res.ok) throw new Error("Gagal mengambil file");
      const text = await res.text();
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(tToast.downloadFileFail || `Gagal mendownload ${filename}`);
    }
  };

  const handleDownloadAllArtifacts = async (artifactsToDownload) => {
    if (!artifactsToDownload || artifactsToDownload.length === 0) return;
    if (artifactsToDownload.length <= 3) {
      artifactsToDownload.forEach((art, idx) => {
        setTimeout(() => handleDownloadArtifact(art.filename, art.file_path, art.code), idx * 400);
      });
      toast.success(tToast.downloadFileSuccess || `Mendownload ${artifactsToDownload.length} file...`);
    } else {
      try {
        const activeSessionId = sessionId && sessionId !== "new" ? sessionId : useChatStore.getState().sessionUuid;
        const headers = {};
        if (authUser?.npp) headers['X-NPP-Header'] = authUser.npp;
        const res = await fetch(`${API_BASE}/api/chat/artifacts/download_all?session_id=${encodeURIComponent(activeSessionId)}`, { headers });
        if (!res.ok) throw new Error("Gagal mendownload ZIP");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `artifacts_${activeSessionId.substring(0, 8)}.zip`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success(tToast.downloadZipSuccess || "Download ZIP berhasil!");
      } catch (err) {
        toast.error(tToast.downloadZipFail || "Gagal mendownload ZIP");
      }
    }
  };

  const [rightSidebarWidth, setRightSidebarWidth] = useState(600);
  const isResizingRightSidebar = useRef(false);

  const startResizingRightSidebar = React.useCallback((e) => {
    isResizingRightSidebar.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMoveRightSidebar);
    document.addEventListener('mouseup', stopResizingRightSidebar);
  }, []);

  const handleMouseMoveRightSidebar = React.useCallback((e) => {
    if (!isResizingRightSidebar.current) return;
    const newWidth = window.innerWidth - e.clientX;
    if (newWidth > 300 && newWidth < window.innerWidth - 100) {
      setRightSidebarWidth(newWidth);
    }
  }, []);

  const stopResizingRightSidebar = React.useCallback(() => {
    isResizingRightSidebar.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', handleMouseMoveRightSidebar);
    document.removeEventListener('mouseup', stopResizingRightSidebar);
  }, []);

  const [isThinkingMode, setIsThinkingMode] = useState(false);
  const isThinkingModeRef = useRef(false);
  const handleThinkingModeChange = (val) => {
    isThinkingModeRef.current = val;
    setIsThinkingMode(val);
    useChatStore.setState({ isThinkingMode: val });
    if (sessionId && sessionId !== 'new') {
      import('../../../services/endpoints').then(endpoints => {
        endpoints.updateSessionSettings(sessionId, { chatMode: chatModeRef.current, isThinkingMode: val }).catch(() => { });
      });
    }
  };
  const [selectedMode, setSelectedMode] = useState('auto');
  // STATE: Deteksi apakah textarea sudah multi-line untuk urusan layout form
  const [isMultiLine, setIsMultiLine] = useState(false);
  // Tambah ref di bawah useState chatMode:
  // 🔒 Ambil state chatMode global dari Zustand store
  const storeChatMode = useChatStore((state) => state.chatMode || "auto");

  // Gunakan storeChatMode sebagai jaminan nilai inisialisasi saat komponen di-remount!
  const [chatMode, setChatMode] = useState(storeChatMode);
  const chatModeRef = useRef(storeChatMode);

  // Sync saat ada tombol aksi (misal Kepatuhan / Bedah / Fokus) yang mengubah storeChatMode secara eksternal
  useEffect(() => {
    if (storeChatMode && storeChatMode !== chatMode) {
      setChatMode(storeChatMode);
      chatModeRef.current = storeChatMode;
    }
  }, [storeChatMode]);
  // Buat fungsi wrapper untuk memantau perubahan chatMode:
  const handleChatModeChange = (val) => {
    chatModeRef.current = val;
    setChatMode(val);
    // Menyimpan pilihan mode langsung ke Zustand store setelah dipilih oleh pengguna
    useChatStore.setState({ chatMode: val });
    if (sessionId && sessionId !== 'new') {
      import('../../../services/endpoints').then(endpoints => {
        endpoints.updateSessionSettings(sessionId, { chatMode: val, isThinkingMode: isThinkingModeRef.current }).catch(() => { });
      });
    }
  };
  // REF: Capture tinggi baseline 1 baris saat mount pertama
  const baselineHeightRef = useRef(0);
  const singleLineWidthRef = useRef(0);

  const stagedAttachments = useChatStore((state) => state.stagedAttachments);
  const setStagedAttachments = useChatStore(
    (state) => state.setStagedAttachments,
  );

  const currentIsLoggedIn =
    propsIsLoggedIn !== undefined ? propsIsLoggedIn : isAuthenticated;
  const currentUserData = propsUserData || authUser || {
    name: "Pegawai Pindad",
    npp: "NPP ------",
    divisi: "Pegawai Resmi",
    role: "user",
    email: null,
  };

  const activeSessionId = sessionId && sessionId !== "new" ? sessionId : null;

  const removeFilePreview = (indexToRemove) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const validateFile = (file) => {
    const fileName = file.name.toLowerCase();
    const isImage = file.type.startsWith("image/");

    // Extracted from backend upload_validator.py
    const allowedExtensions = [
      '.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx', '.xls',
      '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.yaml',
      '.yml', '.xml', '.php', '.java', '.cpp', '.c', '.h', '.sh', '.bash',
      '.md', '.dart', '.swift', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'
    ];

    const hasAllowedExtension = allowedExtensions.some(ext => fileName.endsWith(ext));

    if (!isImage && !hasAllowedExtension) {
      toast.error(
        `Format file "${file.name}" tidak didukung. Format yang diizinkan: Gambar, Dokumen, dan Source Code. File SQL tidak diperbolehkan.`,
      );
      return false;
    }
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      toast.error(tToast.fileTooLarge);
      return false;
    }
    return true;
  };

  const processFilesForLines = async (filesToProcess) => {
    const processed = [];
    for (const file of filesToProcess) {
      const fileName = file.name.toLowerCase();
      const isCodeOrText = /\.(js|jsx|ts|tsx|py|php|html|css|json|cpp|c|h|sh|bash|txt|md|csv)$/i.test(fileName);
      if (isCodeOrText && file.size < 5 * 1024 * 1024) {
        try {
          // OPTIMASI: Jangan baca seluruh file jika besar, maksimal 512KB untuk hitung baris
          const chunk = file.size > 512 * 1024 ? file.slice(0, 512 * 1024) : file;
          const text = await chunk.text();
          // OPTIMASI: Jangan gunakan .split('\\n') karena membebani main thread, gunakan regex
          const lineCount = (text.match(/\n/g) || []).length + 1;
          file._lines = file.size > 512 * 1024 ? Math.max(lineCount, 2500) : lineCount;
        } catch (e) {
          console.error("Error reading lines", e);
        }
      }
      processed.push(file);
    }
    return processed;
  };

  const filterFilesBySmartLimits = async (newFiles, currentFiles) => {
    let heavyCount = currentFiles.filter(f => f.type.startsWith("image/") || f.name.toLowerCase().endsWith(".pdf")).length;
    let totalLines = currentFiles.reduce((acc, f) => acc + (f._lines || 0), 0);

    const allowed = [];
    let warningMsg = "";

    const processedNewFiles = await processFilesForLines(newFiles);

    for (const file of processedNewFiles) {
      const isHeavy = file.type.startsWith("image/") || file.name.toLowerCase().endsWith(".pdf");

      if (isHeavy) {
        if (heavyCount < 2) {
          allowed.push(file);
          heavyCount++;
        } else {
          warningMsg = tToast?.maxFileHeavy || "Maksimal 2 file berat (PDF/Gambar) diperbolehkan.";
        }
      } else {
        const lines = file._lines || 0;
        if (totalLines + lines <= 2500) {
          allowed.push(file);
          totalLines += lines;
        } else {
          warningMsg = tToast?.maxFileLines || `Total baris kode melebihi batas (Max 2500 baris). File ${file.name} dilewati.`;
        }
      }
    }

    return { allowed, warningMsg };
  };

  // 2. TAMPILKAN PRATINJAU LOKAL (TIDAK LANGSUNG DIUNGGAH KE SERVER)
  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    if (isGuest || !currentIsLoggedIn) {
      if (selectedFiles.length >= 1) {
        toast.warning("Tamu maksimal 1 file.");
        return;
      }
      const validFiles = files.filter(validateFile);
      if (validFiles.length > 0) {
        const processed = await processFilesForLines([validFiles[0]]);
        setSelectedFiles((prev) => [...prev, processed[0]]);
      }
      return;
    }

    const validFiles = files.filter(validateFile);
    if (validFiles.length === 0) return;

    const { allowed, warningMsg } = await filterFilesBySmartLimits(validFiles, selectedFiles);

    if (warningMsg) toast.warning(warningMsg);
    if (allowed.length > 0) setSelectedFiles((prev) => [...prev, ...allowed]);
  };

  // 2. TEMPEL (PASTE): Menangani teks yang sangat panjang dan gambar
  const handlePaste = async (e) => {
    // A. Tangani Paste Teks Panjang
    const pastedText = e.clipboardData?.getData("text/plain");
    if (pastedText && pastedText.length > 4000) {
      e.preventDefault();
      
      if (isGuest || !currentIsLoggedIn) {
        if (selectedFiles.length >= 1) {
          toast.warning(tToast?.maxAttachment || "Batas attachment telah tercapai");
          return;
        }
      }

      const textFile = new File(
        [pastedText],
        `pasted-text-${Date.now()}.txt`,
        { type: "text/plain" }
      );
      
      const newFiles = [textFile];
      if (isGuest || !currentIsLoggedIn) {
        const processed = await processFilesForLines([newFiles[0]]);
        setSelectedFiles((prev) => [...prev, processed[0]]);
        toast.info("Teks panjang disisipkan sebagai dokumen (.txt) 📄");
        return;
      }

      const { allowed, warningMsg } = await filterFilesBySmartLimits(newFiles, selectedFiles);
      if (warningMsg) toast.warning(warningMsg);
      if (allowed.length > 0) {
        setSelectedFiles((prev) => [...prev, ...allowed]);
        toast.info(tToast?.longTextAsDoc || "Teks panjang disisipkan sebagai dokumen (.txt) 📄");
      }
      return;
    }

    // B. Tangani Paste Gambar
    const items = e.clipboardData?.items;
    if (!items) return;
    
    const imageItems = Array.from(items).filter((item) =>
      item.type.startsWith("image/"),
    );
    if (imageItems.length === 0) return;
    e.preventDefault();

    if (isGuest || !currentIsLoggedIn) {
      if (selectedFiles.length >= 1) return;
    }

    const newFiles = [];
    for (const item of imageItems) {
      const file = item.getAsFile();
      if (file) {
        const uniqueFile = new File(
          [file],
          `pasted-image-${Date.now()}-${Math.random().toString(36).substr(2, 9)}.png`,
          {
            type: file.type,
          },
        );
        if (validateFile(uniqueFile)) {
          newFiles.push(uniqueFile);
        }
      }
    }
    if (newFiles.length === 0) return;

    if (isGuest || !currentIsLoggedIn) {
      const processed = await processFilesForLines([newFiles[0]]);
      setSelectedFiles((prev) => [...prev, processed[0]]);
      return;
    }

    const { allowed, warningMsg } = await filterFilesBySmartLimits(newFiles, selectedFiles);

    if (warningMsg) toast.warning(warningMsg);
    if (allowed.length > 0) setSelectedFiles((prev) => [...prev, ...allowed]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  // 2. SERET DAN LEPAS (DRAG & DROP): Simpan berkas secara lokal, unggah saat mengirim pesan
  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    const validFiles = files.filter(validateFile);
    if (validFiles.length === 0) return;

    if (isGuest || !currentIsLoggedIn) {
      if (selectedFiles.length >= 1) {
        toast.warning("Tamu maksimal 1 file.");
        return;
      }
      const processed = await processFilesForLines([validFiles[0]]);
      setSelectedFiles((prev) => [...prev, processed[0]]);
      return;
    }

    const { allowed, warningMsg } = await filterFilesBySmartLimits(validFiles, selectedFiles);

    if (warningMsg) toast.warning(warningMsg);
    if (allowed.length > 0) setSelectedFiles((prev) => [...prev, ...allowed]);
  };



  useEffect(() => {
    localStorage.setItem("cakra_language", language);
  }, [language]);

  const [themeSetting, setThemeSetting] = useState(() => {
    return localStorage.getItem("cakra-theme-setting") || "system";
  });

  const [darkMode, setDarkModeRaw] = useState(() => {
    const setting = localStorage.getItem("cakra-theme-setting") || "system";
    if (setting === "dark") return true;
    if (setting === "light") return false;
    if (window.matchMedia) return window.matchMedia("(prefers-color-scheme: dark)").matches;
    return false;
  });

  const setDarkMode = (val) => {
    if (val === "system") {
      setThemeSetting("system");
      localStorage.setItem("cakra-theme-setting", "system");
      if (window.matchMedia) setDarkModeRaw(window.matchMedia("(prefers-color-scheme: dark)").matches);
    } else {
      const mode = val ? "dark" : "light";
      setThemeSetting(mode);
      localStorage.setItem("cakra-theme-setting", mode);
      setDarkModeRaw(val);
    }
  };

  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 768);

  // Auto-tutup sidebar kalau pindah ke ukuran mobile, auto-buka kalau pindah ke desktop
  useEffect(() => {
    setSidebarOpen(!isMobile);
  }, [isMobile]);

  // 🔥 Auto-tutup sidebar kiri saat Document Interrogator (PDF Viewer) terbuka agar lega
  useEffect(() => {
    if (isSplitScreen && !isMobile) {
      wasLeftSidebarOpenRef.current = sidebarOpen;
      setSidebarOpen(false);
    }
  }, [isSplitScreen]);

  const [showDocumentList, setShowDocumentList] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const lastLoadedSessionRef = useRef(null);

  const [docSearchQuery, setDocSearchQuery] = useState("");
  const messageSearchInputRef = useRef(null);
  const [showMsgSearch, setShowMsgSearch] = useState(false);
  const [msgSearchQuery, setMsgSearchQuery] = useState("");

  // 🔄 W8: Sinkronisasi mode tema antar tab browser
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === "cakra-theme-setting") {
        setDarkMode(e.newValue === "system" ? "system" : e.newValue === "dark");
      } else if (e.key === "cakra_language" && e.newValue) {
        setLanguage(e.newValue);
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // ⌨️ W9: Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setShowMsgSearch((prev) => !prev);
        setTimeout(() => {
          if (!showMsgSearch) {
            messageSearchInputRef.current?.focus();
          }
        }, 100);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        handleClearChat();
      }
      if (e.key === "Escape") {
        setShowMsgSearch(false);
        setMsgSearchQuery("");
        setShowDocumentList(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showMsgSearch, chatHistory]);
  // Tangkap event update judul sesi (untuk Typing Animation)
  useEffect(() => {
    const handleTitleUpdate = (e) => {
      const { sessionUuid, title } = e.detail;
      if (!title) return;
      
      // Update state dengan _titleUpdated = true agar komponen TypewriterTitle terpicu
      setChatHistory(prev => prev.map(session => {
        if (session.session_uuid === sessionUuid) {
          // Hanya update jika judul benar-benar baru
          if (session.judul === title || session.title === title) {
            return session;
          }
          return { ...session, judul: title, _titleUpdated: true };
        }
        return session;
      }));
    };

    const handleSendPromptEvent = (e) => {
      const text = e?.detail?.text;
      if (text && typeof text === 'string') {
        const currentUserData = authUser || propsUserData;
        const sendFn = useChatStore.getState().sendMessage;
        if (typeof sendFn === 'function') {
          sendFn(
            text,
            isGuest ? null : currentUserData?.npp,
            isGuest ? null : (newSessionObj) => {
              setChatHistory((prev) => [newSessionObj, ...prev]);
              lastLoadedSessionRef.current = newSessionObj.session_uuid;
              navigate(`/chat/${newSessionObj.session_uuid}`, { replace: true });
            },
            [],
            chatModeRef.current,
            isThinkingModeRef.current,
            toast
          );
        }
      }
    };

    window.addEventListener("cakra_title_update", handleTitleUpdate);
    window.addEventListener("cakra_send_prompt", handleSendPromptEvent);
    return () => {
      window.removeEventListener("cakra_title_update", handleTitleUpdate);
      window.removeEventListener("cakra_send_prompt", handleSendPromptEvent);
    };
  }, [authUser, isGuest, navigate, propsUserData, setChatHistory, toast]);

  // Load documents when document list is opened


  // 🔥 FIX: Gunakan selector individual agar tidak subscribe ke seluruh store.
  // Jika pakai useChatStore() tanpa selector, setiap chunk stream menyebabkan
  // re-render yang membuat storeLoadChatSession menjadi referensi baru, memicu
  // useEffect berkali-kali dan bisa menyebabkan race condition navigasi.
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const isLoading = useChatStore((s) => s.isLoading);
  const currentThinking = useChatStore((s) => s.currentThinking);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const storeClearChat = useChatStore((s) => s.clearChat);

  const sessionAttachments = useMemo(() => {
    return messages.flatMap((msg) => msg.attachments || []);
  }, [messages]);

  useEffect(() => {
    // 🔥 FIX: Ambil loadChatSession dari getState() agar tidak pernah stale.
    if (!sessionId || sessionId === "new") {
      lastLoadedSessionRef.current = null;
      return;
    }
    if (lastLoadedSessionRef.current === sessionId) return;
    lastLoadedSessionRef.current = sessionId;
    useChatStore.getState().loadChatSession(sessionId);
  }, [sessionId]);

  const loadChatSession = (id) => {
    if (!id || id === "new") return;
    lastLoadedSessionRef.current = null;
    navigate(`/chat/${id}`);
  };

  const handleClearChat = () => {
    storeClearChat();
    setChatMode('auto');
    chatModeRef.current = 'auto';
    setIsThinkingMode(false);
    isThinkingModeRef.current = false;
    useChatStore.setState({ chatMode: 'auto' });
    lastLoadedSessionRef.current = null;
    navigate("/chat/new");
  };

  // SINKRONISASI: Menyelaraskan state lokal ChatPage dengan isi store setelah perubahan rute URL selesai
  useEffect(() => {
    if (sessionId && sessionId !== 'new') {
      import('../../../services/endpoints').then(endpoints => {
        endpoints.fetchSessionSettings(sessionId).then(res => {
          if (res && res.status === 'success' && res.data) {
            const savedChatMode = res.data.chatMode || 'auto';
            const savedThinkingMode = res.data.isThinkingMode || false;

            setChatMode(savedChatMode);
            chatModeRef.current = savedChatMode;
            useChatStore.setState({ chatMode: savedChatMode });

            setIsThinkingMode(savedThinkingMode);
            isThinkingModeRef.current = savedThinkingMode;
            useChatStore.setState({ isThinkingMode: savedThinkingMode });
          }
        }).catch(() => { });
      });
    } else {
      const currentGlobalMode = useChatStore.getState().chatMode || "auto";
      setChatMode(currentGlobalMode);
      chatModeRef.current = currentGlobalMode;

      setIsThinkingMode(false);
      isThinkingModeRef.current = false;
      useChatStore.setState({ isThinkingMode: false });
    }
  }, [sessionId]);

  // MIGRASI SESI GUEST: Jika auth sukses dan ada sesi berjalan, claim!
  useEffect(() => {
    if (isAuthenticated && sessionId && sessionId !== "new") {
      import("../../../services/endpoints").then((endpts) => {
        endpts.assignSession(sessionId)
          .then(() => localStorage.removeItem("cakra_last_session"))
          .catch(() => { });
      });
    }
  }, [isAuthenticated, sessionId]);

  const triggerLogout = () => {
    logout();
    window.location.href = "/login";
  };

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e) => {
      const savedTheme = localStorage.getItem("cakra-theme-setting");
      if (!savedTheme || savedTheme === "system") setDarkModeRaw(e.matches);
    };
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const theme = darkMode ? darkColors : lightColors;

  const lastAssistantIndex = [...messages]
    .reverse()
    .findIndex((m) => m.role === "assistant");
  const isThinking =
    isStreaming &&
    lastAssistantIndex === 0 &&
    messages[messages.length - 1]?.content === "";
  const isStreamingText =
    isStreaming &&
    lastAssistantIndex === 0 &&
    messages[messages.length - 1]?.content !== "";
  const isEmptyChat = messages.length === 0;
  const showWelcome = isEmptyChat && !isLoading;

  // CAPTURE BASELINE HEIGHT SEKALI SAAT MOUNT
  useEffect(() => {
    if (textareaRef.current && baselineHeightRef.current === 0) {
      const el = textareaRef.current;
      // FIX MOBILE BUG 1: Placeholder panjang sering wrap di layar sempit dan membuat scrollHeight palsu.
      // Kita kosongkan sementara untuk mendapatkan ukuran 1 baris murni.
      const originalPlaceholder = el.placeholder;
      el.placeholder = "";
      el.style.height = "auto";
      baselineHeightRef.current = el.scrollHeight;
      el.placeholder = originalPlaceholder;
      // Kembalikan height ke baseline
      el.style.height = `${baselineHeightRef.current}px`;
    }
  }, []);

  // 3. PENYESUAIAN TINGGI OTOMATIS DINAMIS: Menghitung tinggi DOM asli secara linier tanpa merender ulang komponen (MENCEGAH LOOP DAN FLUKTUASI TINGGI)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    // FIX MOBILE BUG 2: Saat input kosong (awal atau setelah kirim chat), paksa height ke baseline
    // agar tidak tenggelam karena kalkulasi scrollHeight dari placeholder yang wrap.
    if (input === "" && baselineHeightRef.current > 0) {
      el.style.height = `${baselineHeightRef.current}px`;
      el.style.overflow = "hidden";
      setIsMultiLine(false);
      return;
    }

    // SIMPAN LEBAR ASLI SAAT SINGLE LINE UNTUK REFERENSI (merespons resize/rotasi)
    if (!isMultiLine) {
      singleLineWidthRef.current = el.clientWidth;
    }

    const scrollTop = el.scrollTop;
    el.style.overflow = "hidden";
    el.style.height = "auto";

    // SIMULASI LEBAR SINGLE LINE UNTUK MENDETEKSI WRAPPING YANG AKURAT SAAT MODE MULTI-LINE
    let originalWidth = "";
    let originalFlex = "";
    if (isMultiLine && singleLineWidthRef.current > 0) {
      originalWidth = el.style.width;
      originalFlex = el.style.flex;
      el.style.flex = "none";
      el.style.width = `${singleLineWidthRef.current}px`;
    }

    const newHeight = Math.min(el.scrollHeight, 450);
    
    // KEMBALIKAN LEBAR KE SEMULA JIKA DIMODIFIKASI
    if (isMultiLine && singleLineWidthRef.current > 0) {
      el.style.width = originalWidth;
      el.style.flex = originalFlex;
    }

    el.style.height = `${newHeight}px`;

    el.style.overflow = newHeight >= 450 ? "auto" : "hidden";
    el.scrollTop = scrollTop;

    const baseline = baselineHeightRef.current;
    if (baseline > 0) {
      const hasNewlines = input.includes("\n");
      const isCurrentlyThick = newHeight > baseline + 3 || hasNewlines;

      // Gunakan variabel lokal 'isCurrentlyThick' untuk membandingkan dengan state sebelumnya melalui pembaruan fungsional untuk menghindari pembaruan langsung
      setIsMultiLine((prevIsMultiLine) => {
        if (!prevIsMultiLine) {
          // LOGIKA NAIK: Jika aslinya single, tapi sekarang mendeteksi tebal
          return isCurrentlyThick;
        } else {
          // LOGIKA TURUN: Jika aslinya multi, hanya boleh balik single kalau tidak tebal di simulasi lebar single
          if (!isCurrentlyThick) {
            return false;
          }
          return true; // Tetap mengunci multi-line
        }
      });
    }
  }, [input, isMultiLine]); // PENTING: tambahkan isMultiLine ke dependensi untuk validasi ulang lebar

  // 2. PROSES PENGUNGGAHAN BERKAS DIJALANKAN DI SINI SAAT TOMBOL KIRIM DIKLIK
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (
      (!input.trim() && selectedFiles.length === 0) ||
      isStreaming ||
      isUploadingFile
    )
      return;

    let finalStagedData = [];

    if (selectedFiles.length > 0) {
      setIsUploadingFile(true);

      let uploadSessionUuid =
        activeSessionId || useChatStore.getState().sessionUuid;
      if (!uploadSessionUuid || uploadSessionUuid === "new") {
        const created = await useChatStore
          .getState()
          .createNewSession(isGuest ? null : currentUserData?.npp, chatModeRef.current, isThinkingModeRef.current);
        if (created) {
          uploadSessionUuid = created;

          // Tambahkan sesi baru ke history agar langsung muncul di sidebar
          const newSessionObj = {
              session_uuid: created,
              judul: "Obrolan Baru",
              is_pinned: false,
              started_at: new Date().toISOString()
          };
          setChatHistory((prev) => [newSessionObj, ...prev]);

          if (!isGuest && currentIsLoggedIn) {
            lastLoadedSessionRef.current = created;
            navigate(`/chat/${created}`, { replace: true });
          }
        }
      }

      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append("files", file));
      if (uploadSessionUuid) formData.append("session_uuid", uploadSessionUuid);

      try {
        const result = await uploadDocuments(formData);

        if (result.status === "success") {
          finalStagedData = result.data;
          setStagedAttachments(result.data); // Tetap simpan ke store untuk backup state
        } else {
          throw new Error("Gagal mengunggah berkas");
        }
      } catch (err) {
        console.error(err);
        setIsUploadingFile(false);
        setInputShake(true); // Aktifkan animasi getar untuk memberi isyarat ke user
        setTimeout(() => setInputShake(false), 500);
        return; // Hentikan pipeline agar chat tidak terkirim pincang tanpa file
      } finally {
        setIsUploadingFile(false);
      }
    }

    // PERBAIKAN UTAMA: Meneruskan data berkas yang berhasil diunggah langsung ke fungsi sendMessage
    sendMessage(
      input,
      isGuest ? null : currentUserData?.npp,
      isGuest
        ? null
        : (newSessionObj) => {
          setChatHistory((prev) => [newSessionObj, ...prev]);
          lastLoadedSessionRef.current = newSessionObj.session_uuid;
          navigate(`/chat/${newSessionObj.session_uuid}`, { replace: true });
        },
      finalStagedData, // Meneruskan data lampiran berkas secara langsung
      chatModeRef.current, // PARAMETER MODE: 'auto' | 'documents' (untuk dikirim ke backend)
      isThinkingModeRef.current, // PARAMETER THINKING: true/false
      toast,
    );

    sessionStorage.removeItem("cakra_draft_new");
    if (sessionId) sessionStorage.removeItem(`cakra_draft_${sessionId}`);
    
    setInput("");
    setSelectedFiles([]);
    setStagedAttachments([]);
    setIsMultiLine(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // PAKSA SCROLL KE BAWAH KETIKA PESAN DIKIRIM (Bypass Virtuoso restrictions)
    setTimeout(() => {
      if (messagesContainerRef?.current) {
        messagesContainerRef.current.scrollTo({
          top: 9999999,
          behavior: "smooth",
        });
      }
    }, 100);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSubmit();
    }
  };

  const defaultGetGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return "SELAMAT PAGI";
    if (hour < 15) return "SELAMAT SIANG";
    if (hour < 19) return "SELAMAT SORE";
    return "SELAMAT MALAM";
  };

  const hasSidebar = !isGuest && currentIsLoggedIn;

  // LOGIKA MARGIN UTAMA: 
  // Jika mobile, sidebar adalah overlay -> margin-left selalu 0
  // Jika desktop, margin-left menyesuaikan apakah sidebar buka/tutup
  const mainMarginLeft = isMobile
    ? "0"
    : (hasSidebar ? (sidebarOpen ? "16rem" : "4rem") : "0");

  const isPreviewMode = !!(previewDoc || previewArtifact);
  const mainMarginRight = isMobile
    ? "0"
    : !showRightSidebar
      ? "0"
      : isPreviewMode
        ? (rightSidebarWidth === 9999
            ? `calc(100vw - ${sidebarOpen ? 256 : 64}px)`
            : `${rightSidebarWidth}px`)
        : "325px";


  return {
    activeIsolatedDocId,
    activeIsolatedTitle,
    activeSessionId,
    artifactContent,
    artifacts,
    authUser,
    baselineHeightRef,
    bottomRef,
    chatHistory,
    chatMode,
    chatModeRef,
    currentIsLoggedIn,
    currentThinking,
    currentUserData,
    darkMode,
    defaultGetGreeting,
    detectLang,
    docContent,
    docSearchQuery,
    documents,
    documentsTotal,
    fetchDocumentsList,
    fileInputRef,
    handleChatModeChange,
    handleClearChat,
    handleDownloadAllArtifacts,
    handleDownloadArtifact,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handleFileChange,
    handleFileClick,
    handleKeyDown,
    handleOpenArtifact,
    handlePaste,
    handleSubmit,
    handleThinkingModeChange,
    hasSidebar,
    input,
    isArtifactLoading,
    isAuthenticated,
    isDocLoading,
    isDragOver,
    isEmptyChat,
    isLoading,
    isLoadingDocuments,
    isMobile,
    isMultiLine,
    isResizingRightSidebar,
    isStreaming,
    isStreamingText,
    isThinking,
    isThinkingMode,
    isThinkingModeRef,
    isUploadingFile,
    lastAssistantIndex,
    lastLoadedSessionRef,
    loadChatSession,
    logout,
    mainMarginLeft,
    mainMarginRight,
    messages,
    messageSearchInputRef,
    messagesContainerRef,
    msgSearchQuery,
    navigate,
    previewArtifact,
    previewDoc,
    previewImage,
    removeFilePreview,
    rightSidebarWidth,
    selectedFiles,
    selectedMode,
    sessionAttachments,
    setChatHistory,
    setChatMode,
    setContextIsolation,
    setDarkMode,
    themeSetting,
    language,
    setLanguage,
    setDocContent,
    setDocSearchQuery,
    setInput,
    setIsArtifactLoading,
    setIsDocLoading,
    setIsDragOver,
    setIsMobile,
    setIsMultiLine,
    setIsThinkingMode,
    setIsUploadingFile,
    setMsgSearchQuery,
    setPreviewArtifact,
    setPreviewDoc,
    setPreviewImage,
    setRightSidebarWidth,
    setSelectedFiles,
    setSelectedMode,
    setShowDocumentList,
    setShowMsgSearch,
    setShowRightSidebar,
    setShowScrollBottom,
    setSidebarOpen,
    setStagedAttachments,
    showDocumentList,
    showMsgSearch,
    showRightSidebar,
    showScrollBottom,
    showWelcome,
    sidebarOpen,
    singleLineWidthRef,
    stagedAttachments,
    startResizingRightSidebar,
    storeChatMode,
    textareaRef,
    theme,
    toast,
    toggleRightSidebar,
    triggerLogout,
    validateFile,
    wasLeftSidebarOpenRef,
    inputShake // Export state animasi getar
  };

}
