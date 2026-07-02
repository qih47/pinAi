import React, { useState, useRef, useEffect, useMemo } from "react";
import { useChatStore, API_BASE, getUploadUrl } from "../../stores/chatStore";
import { uploadDocuments } from "../../services/endpoints";
import useToast from "../../hooks/useToast";
import cakraLogo from "../../assets/cakra.png";
import { styles, lightColors, darkColors } from "./chatPage.styles";
import ChatArea from "./components/ChatArea";
import GuestWelcome from "../../components/ui/GuestWelcome";
import Sidebar from "./components/Sidebar";
import { useNavigate, useParams } from "react-router-dom";
import { useChatAuthStore } from "../../stores/authStore";
import HeaderDropdownMenu from "./components/HeaderDropdownMenu";
import NotificationBell from "../../components/NotificationBell"; // 👈 W16: Notification center
import PreviewImageModal from "./components/modals/PreviewImageModal";
import ContextIsolationModal from "./components/modals/ContextIsolationModal";
import RightSidebar from "./components/RightSidebar";
import ChatInputArea from "./components/ChatInputArea";

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function ChatPage({
  isGuest,
  isLoggedIn: propsIsLoggedIn,
  userData: propsUserData,
  getGreeting,
}) {
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
  const fetchDocumentsList = useChatStore((state) => state.fetchDocumentsList);
  const artifacts = useChatStore((state) => state.artifacts || []);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
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
    if (previewDoc) {
      setIsDocLoading(true);
      setDocContent("");

      const endpoint = `${API_BASE}/api/chat/documents/extract?path=${encodeURIComponent(previewDoc.path)}`;

      fetch(endpoint)
        .then(res => res.json())
        .then(data => {
          if (data.content) {
            setDocContent(data.content);
          } else {
            setDocContent("Gagal mengekstrak isi dokumen.");
          }
        })
        .catch(err => setDocContent("Error saat membaca dokumen dari server."))
        .finally(() => setIsDocLoading(false));
    }
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
    
    // Siapkan header otentikasi agar backend bisa mengekstrak current_user_npp
    const headers = {};
    if (authUser?.npp) {
      headers['X-NPP-Header'] = authUser.npp;
    }
    
    fetch(`${API_BASE}/api/chat/artifacts/read?filename=${encodeURIComponent(previewArtifact.file_path)}&session_id=${encodeURIComponent(activeSessionId)}`, {
      headers
    })
      .then(res => res.text())
      .then(text => setArtifactContent(text))
      .catch(() => setArtifactContent(previewArtifact.code || '// Gagal memuat konten'))
      .finally(() => setIsArtifactLoading(false));
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
      toast.error(`Gagal mendownload ${filename}`);
    }
  };

  const handleDownloadAllArtifacts = async (artifactsToDownload) => {
    if (!artifactsToDownload || artifactsToDownload.length === 0) return;
    if (artifactsToDownload.length <= 3) {
      artifactsToDownload.forEach((art, idx) => {
        setTimeout(() => handleDownloadArtifact(art.filename, art.file_path, art.code), idx * 400);
      });
      toast.success(`Mendownload ${artifactsToDownload.length} file...`);
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
        toast.success("Download ZIP berhasil!");
      } catch (err) {
        toast.error("Gagal mendownload ZIP");
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
      import('../../services/endpoints').then(endpoints => {
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
  // Buat fungsi wrapper untuk memantau perubahan chatMode:
  const handleChatModeChange = (val) => {
    chatModeRef.current = val;
    setChatMode(val);
    // Menyimpan pilihan mode langsung ke Zustand store setelah dipilih oleh pengguna
    useChatStore.setState({ chatMode: val });
    if (sessionId && sessionId !== 'new') {
      import('../../services/endpoints').then(endpoints => {
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
  const currentUserData = propsUserData || {
    name: authUser?.name || "Pegawai Pindad",
    npp: authUser?.npp || "NPP ------",
    divisi: authUser?.divisi || "Pegawai Resmi",
    role: authUser?.role || "user",
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
      toast.error(`Ukuran file "${file.name}" melebihi batas 10 MB.`);
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
          const text = await file.text();
          file._lines = text.split('\n').length;
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
          warningMsg = "Maksimal 2 file berat (PDF/Gambar) diperbolehkan.";
        }
      } else {
        const lines = file._lines || 0;
        if (totalLines + lines <= 2500) {
          allowed.push(file);
          totalLines += lines;
        } else {
          warningMsg = `Total baris kode melebihi batas (Max 2500 baris). File ${file.name} dilewati.`;
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

  // 2. TEMPEL GAMBAR (PASTE): Masuk ke state lokal untuk pratinjau, bukan ke port API langsung
  const handlePaste = async (e) => {
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

  const [darkMode, setDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem("cakra-theme");
    if (savedTheme !== null) return savedTheme === "dark";
    if (window.matchMedia)
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    return false;
  });

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
      if (e.key === "cakra-theme") {
        setDarkMode(e.newValue === "dark");
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
      
      // Lakukan animasi typing pada sidebar dengan mengupdate chatHistory per karakter
      let i = 0;
      const animateTitle = setInterval(() => {
        setChatHistory(prev => prev.map(session => {
          if (session.session_uuid === sessionUuid) {
            return { ...session, judul: title.substring(0, i + 1) };
          }
          return session;
        }));
        
        i++;
        if (i >= title.length) clearInterval(animateTitle);
      }, 50); // Kecepatan ketik
    };

    window.addEventListener("cakra_title_update", handleTitleUpdate);
    return () => window.removeEventListener("cakra_title_update", handleTitleUpdate);
  }, []);

  // Load documents when document list is opened
  useEffect(() => {
    if (showDocumentList) {
      fetchDocumentsList();
    }
  }, [showDocumentList, fetchDocumentsList]);

  const {
    messages,
    isStreaming,
    isLoading,
    currentThinking,
    sendMessage,
    clearChat: storeClearChat,
    loadChatSession: storeLoadChatSession,
  } = useChatStore();

  const sessionAttachments = useMemo(() => {
    return messages.flatMap((msg) => msg.attachments || []);
  }, [messages]);

  useEffect(() => {
    if (isStreaming) return; // 🛡️ GUARD TAMBAHAN: Cegah mutasi apa pun jika stream aktif
    if (!sessionId || sessionId === "new") {
      lastLoadedSessionRef.current = null;
      return;
    }
    if (lastLoadedSessionRef.current === sessionId) return;
    lastLoadedSessionRef.current = sessionId;
    storeLoadChatSession(sessionId);
  }, [sessionId, isStreaming, storeLoadChatSession]);

  const loadChatSession = (id) => {
    if (!id || id === "new" || id === sessionId) return;
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
      import('../../services/endpoints').then(endpoints => {
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
      import("../../services/endpoints").then((endpts) => {
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
      const savedTheme = localStorage.getItem("cakra-theme");
      if (savedTheme === null) setDarkMode(e.matches);
    };
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    localStorage.setItem("cakra-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

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
        toast.info("Mengunggah berkas...");
        const result = await uploadDocuments(formData);

        if (result.status === "success") {
          finalStagedData = result.data;
          setStagedAttachments(result.data); // Tetap simpan ke store untuk backup state
          toast.success("Berkas berhasil diunggah!");
        } else {
          throw new Error("Gagal mengunggah berkas");
        }
      } catch (err) {
        console.error(err);
        toast.error(
          "Gagal memproses pengiriman karena terjadi kesalahan saat mengunggah berkas.",
        );
        setIsUploadingFile(false);
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
    : (hasSidebar ? (sidebarOpen ? "18rem" : "4rem") : "0");

  const mainMarginRight = isMobile
    ? "0"
    : (showRightSidebar ? (previewDoc ? "45vw" : "320px") : "0");

  return (
    <div style={{ ...styles.root, background: theme.rootBg }}>
      {/* ── BACKDROP MOBILE ── */}
      {isMobile && hasSidebar && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            backdropFilter: "blur(4px)",
            zIndex: 35, // Sidebar adalah 40
            animation: "fadeInUp 0.3s ease-out",
          }}
        />
      )}

      {/* 1. KEMBALIKAN ANIMASI CAKRA BERPIKIR & STREAMING REVEAL */}
      <style>{`
        @keyframes cakraSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes logoFloat {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-6px) rotate(3deg); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes geminiReveal {
          from { opacity: 0; transform: translateY(3px); filter: blur(2px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        /* Kelas pulse/kedut berpikir asisten */
        .thinking-pulse {
          animation: geminiReveal 0.6s ease-in-out infinite alternate;
          opacity: 0.6;
        }
        .assistant-content-container p, .assistant-content-container pre {
          animation: geminiReveal 0.35s ease-out forwards;
        }
        textarea {
        }
        textarea::-webkit-scrollbar {
          width: 6px;
          background: transparent;
        }
        textarea::-webkit-scrollbar-track {
          background: transparent;
        }
        textarea::-webkit-scrollbar-thumb {
          background: ${darkMode ? "#4b5563" : "#cbd5e1"};
          border-radius: 3px;
        }
        textarea::-webkit-scrollbar-thumb:hover {
          background: ${darkMode ? "#6b7280" : "#94a3b8"};
        }
        textarea::-webkit-scrollbar-button {
          display: none !important;
          width: 0 !important;
          height: 0 !important;
          -webkit-appearance: none !important;
        }
        * { box-sizing: border-box; }
        .custom-scroll-gemini::-webkit-scrollbar { width: 8px; background-color: transparent; }
        .custom-scroll-gemini::-webkit-scrollbar-thumb {
          background-color: ${darkMode ? "rgba(255, 255, 255, 0.15)" : "rgba(0, 0, 0, 0.15)"};
          border-radius: 20px;
        }
        .custom-scroll-gemini::-webkit-scrollbar-button { display: none !important; width: 0 !important; height: 0 !important; -webkit-appearance: none !important; }
        .custom-scroll-gemini::-webkit-scrollbar-corner { background: transparent; }

        /* ── ANIMASI SHIMMER & BOUNCE ── */
        @keyframes skeletonShimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .skeleton-shimmer {
          background: ${darkMode ? "linear-gradient(90deg, #1e1e20 25%, #2a2a2d 50%, #1e1e20 75%)" : "linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)"};
          background-size: 200% 100%;
          animation: skeletonShimmer 1.5s infinite linear;
        }
        @keyframes dotBounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1.0); }
        }
        @keyframes shimmerFlow {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {!isGuest && currentIsLoggedIn && (
        <Sidebar
          isOpen={sidebarOpen}
          setIsOpen={setSidebarOpen}
          isMobile={isMobile}
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          theme={theme}
          clearChat={handleClearChat}
          showDocumentList={showDocumentList}
          setShowDocumentList={setShowDocumentList}
          userData={currentUserData}
          triggerLogout={triggerLogout}
          loadChatSession={loadChatSession}
          currentSessionId={activeSessionId}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          cakraLogo={cakraLogo}
          navigate={navigate}
        />
      )}

      <main
        style={{
          ...styles.main,
          background: theme.mainBg,
          marginLeft: mainMarginLeft,
          transition: "margin-left 0.3s ease-in-out",
        }}
      >
        <header style={{
          ...styles.header,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          paddingLeft: "12px",
          paddingRight: "12px",

          // 🔥 KUNCI TRANSPARAN: Gak ada background, gak ada border sama sekali!
          background: "transparent",
          borderBottom: "none",
          boxShadow: "none",

          // Posisi tetap di atas melayang
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 30,
          height: "56px",
          transition: "width 0.3s ease-in-out",
        }}>

          {/* ── BLOK KIRI: Hamburger Menu ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0px' }}>
            {/* ☰ HAMBURGER MENU MOBILE */}
            {isMobile && hasSidebar && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: theme.iconColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "6px",
                  borderRadius: "8px",
                }}
                title="Buka Menu"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="4" width="18" height="16" rx="2.5" />
                  <rect x="3" y="4" width="6" height="16" rx="2.5" />
                </svg>
              </button>
            )}

            {!hasSidebar && (
              <img
                // src={cakraLogo}
                // alt="CAKRA AI"
                style={{ height: "40px", width: "auto", objectFit: "contain" }}
              />
            )}
          </div>
          {/* 🔥 MODIFIKASI HEADER ACTIONS: Bungkus tombol login & tema ke dalam Kebab Dropdown */}
          <div
            style={{
              ...styles.headerActions,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {/* ✚ TOMBOL NEW CHAT MOBILE */}
            {isMobile && hasSidebar && (
              <button
                onClick={handleClearChat}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: theme.iconColor,
                  transition: "background 0.2s",
                  outline: "none",
                }}
                title="Chat Baru"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
            )}

            {/* 🔍 TOMBOL CARI (Dipindah ke kiri File) */}
            {messages.length > 0 && (
              <button
                onClick={() => {
                  setShowMsgSearch((prev) => !prev);
                  setTimeout(() => {
                    if (!showMsgSearch) messageSearchInputRef.current?.focus();
                  }, 100);
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: theme.iconColor,
                  transition: "background 0.2s",
                  outline: "none",
                }}
                onMouseEnter={(e) =>
                (e.currentTarget.style.background = darkMode
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(0,0,0,0.05)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
                title="Cari kata kunci dalam percakapan ini (Ctrl+F)"
              >
                {/* 🔥 ICON SVG MINIMALIS MODERN */}
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor" // ← SAKTI: Otomatis ngikutin warna theme.iconColor dari button parent-nya
                  strokeWidth="2.3"      // ← Tingkat ketebalan garis biar makin tegas
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ opacity: 0.85 }} // Biar gak terlalu mencolok benderang
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
              </button>
            )}

            {/* 📁 TOMBOL SESSION FILES (Dipindah ke kanan Search) */}
            {messages.length > 0 && (
              <button
                onClick={toggleRightSidebar}
                style={{
                  background: showRightSidebar ? (darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)") : "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: showRightSidebar ? "#6366f1" : theme.iconColor,
                  transition: "all 0.2s",
                  outline: "none",
                }}
                onMouseEnter={(e) => {
                  if (!showRightSidebar) e.currentTarget.style.background = darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
                }}
                onMouseLeave={(e) => {
                  if (!showRightSidebar) e.currentTarget.style.background = "transparent";
                }}
                title="File Sesi Ini"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
              </button>
            )}
            {/* 👇 W16: Notification Bell */}
            {!isGuest}
            <HeaderDropdownMenu
              isGuest={isGuest}
              onLogin={() => {
                const currentSession = useChatStore.getState().sessionUuid;
                if (currentSession && currentSession !== "new") {
                  localStorage.setItem("cakra_last_session", currentSession);
                }
                navigate("/login");
              }}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
              theme={theme}
            />
          </div>
        </header>

        <div
          style={{
            flex: 1,
            position: "relative",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
            marginRight: mainMarginRight,
            transition: "margin-right 0.3s ease-in-out",
          }}
        >
          <div
            style={{
              flex: 1,
              minHeight: 0,
              opacity: showWelcome ? 0 : 1,
              transition: "opacity 0.2s ease",
              pointerEvents: showWelcome ? "none" : "auto",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* 🔍 Message Search Bar */}
            {showMsgSearch && (
              <div
                style={{
                  ...styles.msgSearchContainer,
                  background: theme.inputBg,
                  borderBottomColor: theme.borderColor,
                }}
              >
                <span style={{ fontSize: "14px", color: theme.secondaryText }}>
                  🔍
                </span>
                <input
                  ref={messageSearchInputRef}
                  type="text"
                  placeholder="Cari kata kunci dalam percakapan ini..."
                  value={msgSearchQuery}
                  onChange={(e) => setMsgSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    border: "none",
                    background: "transparent",
                    outline: "none",
                    color: theme.textColor,
                    fontSize: "14px",
                  }}
                />
                <button
                  onClick={() => {
                    setShowMsgSearch(false);
                    setMsgSearchQuery("");
                  }}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: theme.secondaryText,
                    cursor: "pointer",
                    fontSize: "14px",
                    fontWeight: "bold",
                    padding: "4px 8px",
                  }}
                >
                  ✕
                </button>
              </div>
            )}

            <ChatArea
              messages={messages}
              isStreaming={isStreaming}
              theme={theme}
              darkMode={darkMode}
              bottomRef={bottomRef}
              messagesContainerRef={messagesContainerRef}
              setInput={setInput}
              isThinking={isThinking}
              currentThinking={currentThinking}
              isStreamingText={isStreamingText}
              lastAssistantIndex={lastAssistantIndex}
              searchQuery={msgSearchQuery}
              isLoading={isLoading}
              onAtBottomChange={(isAtBottom) => setShowScrollBottom(!isAtBottom)}
              onFileClick={handleFileClick}
              setPreviewImage={setPreviewImage}
              onOpenArtifact={handleOpenArtifact}
              handleDownloadAllArtifacts={handleDownloadAllArtifacts}
            />
          </div>

          {showWelcome && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                transform: "translateY(-8%)",
                zIndex: 10,
                animation: "fadeInUp 0.4s ease-out",
                pointerEvents: "none",
              }}
            >
              <div style={{ pointerEvents: "auto" }}>
                <GuestWelcome
                  isLoggedIn={currentIsLoggedIn}
                  userData={{
                    fullname:
                      currentUserData?.name ||
                      currentUserData?.fullname ||
                      "Pegawai",
                    npp: currentUserData?.npp || "NPP -----",
                  }}
                  getGreeting={getGreeting || defaultGetGreeting}
                  theme={theme}
                  darkMode={darkMode}
                  isMobile={isMobile}
                />
              </div>
              <div
                style={{
                  width: "100%",
                  maxWidth: "700px",
                  padding: "0 20px",
                  marginTop: "0px",
                  pointerEvents: "auto",
                }}
              >
                <ChatInputArea
                  theme={theme}
                  darkMode={darkMode}
                  isBottom={true}
                  showScrollBottom={showScrollBottom}
                  showWelcome={showWelcome}
                  messages={messages}
                  messagesContainerRef={messagesContainerRef}
                  activeIsolatedTitle={activeIsolatedTitle}
                  setContextIsolation={setContextIsolation}
                  selectedFiles={selectedFiles}
                  removeFilePreview={removeFilePreview}
                  handleSubmit={handleSubmit}
                  handlePaste={handlePaste}
                  handleDragOver={handleDragOver}
                  handleDragLeave={handleDragLeave}
                  handleDrop={handleDrop}
                  isDragOver={isDragOver}
                  fileInputRef={fileInputRef}
                  handleFileChange={handleFileChange}
                  isGuest={isGuest}
                  currentIsLoggedIn={currentIsLoggedIn}
                  isMultiLine={isMultiLine}
                  isStreaming={isStreaming}
                  isUploadingFile={isUploadingFile}
                  textareaRef={textareaRef}
                  input={input}
                  setInput={setInput}
                  handleKeyDown={handleKeyDown}
                  chatMode={chatMode}
                  handleChatModeChange={handleChatModeChange}
                  isThinkingMode={isThinkingMode}
                  handleThinkingModeChange={handleThinkingModeChange}
                  styles={styles}
                />
              </div>
            </div>
          )}

          {/* Hanya render input di bawah jika chat sudah ada */}
          {!showWelcome && (
            <ChatInputArea
              theme={theme}
              darkMode={darkMode}
              isBottom={true}
              showScrollBottom={showScrollBottom}
              showWelcome={showWelcome}
              messages={messages}
              messagesContainerRef={messagesContainerRef}
              activeIsolatedTitle={activeIsolatedTitle}
              setContextIsolation={setContextIsolation}
              selectedFiles={selectedFiles}
              removeFilePreview={removeFilePreview}
              handleSubmit={handleSubmit}
              handlePaste={handlePaste}
              handleDragOver={handleDragOver}
              handleDragLeave={handleDragLeave}
              handleDrop={handleDrop}
              isDragOver={isDragOver}
              fileInputRef={fileInputRef}
              handleFileChange={handleFileChange}
              isGuest={isGuest}
              currentIsLoggedIn={currentIsLoggedIn}
              isMultiLine={isMultiLine}
              isStreaming={isStreaming}
              isUploadingFile={isUploadingFile}
              textareaRef={textareaRef}
              input={input}
              setInput={setInput}
              handleKeyDown={handleKeyDown}
              chatMode={chatMode}
              handleChatModeChange={handleChatModeChange}
              isThinkingMode={isThinkingMode}
              handleThinkingModeChange={handleThinkingModeChange}
              styles={styles}
            />
          )}
        </div>

      </main>

      {/* 🔒 W7: Modal Pilihan Dokumen Regulasi (Context Isolation) */}
      <ContextIsolationModal
        showModal={showDocumentList}
        onClose={() => setShowDocumentList(false)}
        documents={documents}
        isLoadingDocuments={isLoadingDocuments}
        activeIsolatedDocId={activeIsolatedDocId}
        onSelectDocument={setContextIsolation}
        theme={theme}
        darkMode={darkMode}
      />
      {false && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.5)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "fadeInUp 0.2s ease-out",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: darkMode ? "#1e1e20" : "#ffffff",
              color: theme.textColor,
              width: "100%",
              maxWidth: "550px",
              borderRadius: "16px",
              border: `1px solid ${theme.borderColor}`,
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.3)",
              display: "flex",
              flexDirection: "column",
              maxHeight: "80vh",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: `1px solid ${theme.borderColor}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
                Daftar Dokumen Regulasi
              </h3>
              <button
                onClick={() => setShowDocumentList(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: theme.secondaryText,
                  cursor: "pointer",
                  fontSize: "18px",
                  fontWeight: "bold",
                }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                padding: "16px 20px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                flex: 1,
                overflowY: "auto",
              }}
            >
              <input
                type="text"
                placeholder="Cari nama dokumen atau nomor..."
                value={docSearchQuery}
                onChange={(e) => setDocSearchQuery(e.target.value)}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: `1px solid ${theme.inputBorder}`,
                  background: theme.inputBg,
                  color: theme.textColor,
                  outline: "none",
                  fontSize: "14px",
                  width: "100%",
                }}
              />

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  marginTop: "4px",
                }}
                className="custom-scroll-gemini"
              >
                {isLoadingDocuments ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      color: theme.secondaryText,
                    }}
                  >
                    Memuat dokumen...
                  </div>
                ) : documents.filter(
                  (doc) =>
                    (doc.title || "")
                      .toLowerCase()
                      .includes(docSearchQuery.toLowerCase()) ||
                    (doc.nomor || "")
                      .toLowerCase()
                      .includes(docSearchQuery.toLowerCase()),
                ).length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      color: theme.secondaryText,
                    }}
                  >
                    Tidak ada dokumen ditemukan.
                  </div>
                ) : (
                  documents
                    .filter(
                      (doc) =>
                        (doc.title || "")
                          .toLowerCase()
                          .includes(docSearchQuery.toLowerCase()) ||
                        (doc.nomor || "")
                          .toLowerCase()
                          .includes(docSearchQuery.toLowerCase()),
                    )
                    .map((doc) => {
                      const isIsolated = activeIsolatedDocId === doc.id;
                      return (
                        <div
                          key={doc.id}
                          style={{
                            padding: "12px 16px",
                            borderRadius: "10px",
                            background: isIsolated
                              ? darkMode
                                ? "rgba(99, 102, 241, 0.15)"
                                : "rgba(37, 99, 235, 0.08)"
                              : darkMode
                                ? "#2a2a2d"
                                : "#f9fafb",
                            border: `1px solid ${isIsolated ? (darkMode ? "#6366f1" : "#2563eb") : theme.borderColor}`,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: "12px",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <div
                            style={{ minWidth: 0, flex: 1, textAlign: "left" }}
                          >
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: "13.5px",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {doc.title}
                            </div>
                            <div
                              style={{
                                fontSize: "11px",
                                color: theme.secondaryText,
                                marginTop: "2px",
                              }}
                            >
                              No: {doc.nomor || "-"} | Tipe: {doc.jenis_dokumen || "-"}
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              setContextIsolation(doc.id, doc.title);
                              setShowDocumentList(false);
                            }}
                            style={{
                              padding: "6px 12px",
                              borderRadius: "20px",
                              border: "none",
                              background: isIsolated ? "#ef4444" : "#6366f1",
                              color: "#ffffff",
                              fontSize: "12px",
                              fontWeight: 600,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                              flexShrink: 0,
                            }}
                          >
                            {isIsolated ? "Batal Fokus" : "Fokus"}
                          </button>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {/* 📁 RIGHT SIDEBAR SESSION FILES */}
      <RightSidebar
        isMobile={isMobile}
        theme={theme}
        darkMode={darkMode}
        previewDoc={previewDoc}
        setPreviewDoc={setPreviewDoc}
        docContent={docContent}
        isDocLoading={isDocLoading}
        previewArtifact={previewArtifact}
        setPreviewArtifact={setPreviewArtifact}
        artifactContent={artifactContent}
        isArtifactLoading={isArtifactLoading}
        rightSidebarWidth={rightSidebarWidth}
        showRightSidebar={showRightSidebar}
        isResizingRightSidebar={isResizingRightSidebar}
        startResizingRightSidebar={startResizingRightSidebar}
        artifacts={artifacts}
        sessionAttachments={sessionAttachments}
        handleOpenArtifact={handleOpenArtifact}
        handleDownloadArtifact={handleDownloadArtifact}
        handleDownloadAllArtifacts={handleDownloadAllArtifacts}
        setPreviewImage={setPreviewImage}
        setShowRightSidebar={setShowRightSidebar}
      />

      {/* 🖼️ IMAGE PREVIEW MODAL */}
      <PreviewImageModal
        previewImage={previewImage}
        onClose={() => setPreviewImage(null)}
      />
    </div>
  );
}
