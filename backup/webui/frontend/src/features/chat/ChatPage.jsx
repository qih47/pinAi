import React, {useState, useEffect, useRef, useCallback} from "react";
import {useParams, useNavigate} from "react-router-dom";
import cakraLogo from "@/assets/cakra.png";
import { API_BASE } from "@/services/config";
import * as authApi from "@/services/endpoints/authApi";
import * as chatApi from "@/services/endpoints/chatApi";

import MainLayout from "@/components/layout/MainLayout";
import HeaderBar from "@/components/layout/HeaderBar";
import MessageList from "@/components/layout/MessageList";
import InputArea from "@/components/layout/InputArea";
import FloatingButtons from "@/components/layout/FloatingButtons";
import LoginModal from "@/components/modals/LoginModal";
import LogoutModal from "@/components/modals/LogoutModal";
import NotificationToast from "@/components/ui/NotificationToast";
import GuestWelcome from "@/components/ui/GuestWelcome";
function ChatPage({isNew, isGuest}) {
    const {sessionId} = useParams();
    const navigate = useNavigate();

    // =========================================================================
    // STATE MANAGEMENT
    // =========================================================================
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const abortControllerRef = useRef(null);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [chatHistory, setChatHistory] = useState([]);

    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [showPreview, setShowPreview] = useState(false);
    const [previewFile, setPreviewFile] = useState(null);
    const [tempFileId, setTempFileId] = useState(null);
    const [showDocumentList, setShowDocumentList] = useState(false);

    const [currentMode, setCurrentMode] = useState("normal");
    const [notification, setNotification] = useState(null);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [showLoginModal, setShowLoginModal] = useState(false);
    const [loginForm, setLoginForm] = useState({username: "", password: ""});
    const [loginError, setLoginError] = useState("");
    const [userData, setUserData] = useState(null);
    const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const currentRole = userData ?. role || localStorage.getItem("userRole") || "GUEST";

    const [modelList, setModelList] = useState([]);
    const [selectedModel, setSelectedModel] = useState("qwen3:8b");

    const [backendStatus, setBackendStatus] = useState("connected");
    const [isInitializing, setIsInitializing] = useState(true);

    // =========================================================================
    // REF MANAGEMENT
    // =========================================================================
    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);
    const messagesContainerRef = useRef(null);
    const autoScrollEnabled = useRef(true);
    const typingAnimationRef = useRef(null);
    const isUserScrolling = useRef(false);
    const isAiTypingRef = useRef(false);
    const [showScrollTop, setShowScrollTop] = useState(false);
    const [showScrollBottom, setShowScrollBottom] = useState(false);
    const [isAtBottom, setIsAtBottom] = useState(true);
    const [canScroll, setCanScroll] = useState(false);

    // =========================================================================
    // SHARED UTILS & HANDLERS
    // =========================================================================
    const showNotification = useCallback((message, type = "info") => {
        setNotification({id: Date.now(), message, type});
        setTimeout(() => setNotification(null), 3000);
    }, []);

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 11) 
            return "Selamat Pagi";
        


        if (hour < 15) 
            return "Selamat Siang";
        


        if (hour < 18) 
            return "Selamat Sore";
        


        return "Selamat Malam";
    };

    // =========================================================================
    // AUTO-SCROLL LOGIC - OPTIMIZED FOR STREAMING
    // =========================================================================

    // Pake fungsi internal buat eksekusi scroll instant
    const scrollToBottomInstant = () => {
        const container = messagesContainerRef.current;
        if (container && autoScrollEnabled.current && ! isUserScrolling.current) {
            container.scrollTop = container.scrollHeight;
        }
    };

    const startAutoScroll = () => {
        const container = messagesContainerRef.current;
        if (! container) 
            return;
        


        // Bersihkan interval biar gak double/tabrakan
        if (typingAnimationRef.current) {
            clearInterval(typingAnimationRef.current);
        }

        // Jalankan sekali di awal biar gak nunggu 50ms pertama
        scrollToBottomInstant();

        typingAnimationRef.current = setInterval(() => {
            if (autoScrollEnabled.current && ! isUserScrolling.current) { // Gunakan scrollTop langsung (jangan behavior smooth pas lagi ngetik/streaming)
                container.scrollTop = container.scrollHeight;
            } else {
                clearInterval(typingAnimationRef.current);
                typingAnimationRef.current = null;
            }
        }, 30); // Turunin dikit ke 30ms biar lebih "melekat"
    };

    useEffect(() => {
        const lastMessage = messages[messages.length - 1];
        if (lastMessage ?. sender === "user") {
            autoScrollEnabled.current = true;
            isUserScrolling.current = false;
            // Langsung scroll pas user kirim pesan
            setTimeout(scrollToBottomInstant, 10);
        }
    }, [messages]);

    useEffect(() => {
        const container = messagesContainerRef.current;
        if (! container) 
            return;
        


        const handleScroll = () => {
            const {scrollTop, scrollHeight, clientHeight} = container;
            const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

            setIsAtBottom(distanceFromBottom < 50);
            setShowScrollTop(scrollTop > 400);
            setShowScrollBottom(distanceFromBottom > 200);

            // User scroll ke atas
            if (distanceFromBottom > 100) {
                if (! isUserScrolling.current) {
                    isUserScrolling.current = true;
                    autoScrollEnabled.current = false;
                    // Hapus interval biar browser enteng pas user lagi scroll manual
                    if (typingAnimationRef.current) {
                        clearInterval(typingAnimationRef.current);
                        typingAnimationRef.current = null;
                    }
                }
            }

            // User scroll balik ke bawah banget
            if (distanceFromBottom < 20) {
                if (isUserScrolling.current) {
                    isUserScrolling.current = false;
                    autoScrollEnabled.current = true;
                    if (isAiTypingRef.current) {
                        startAutoScroll();
                    }
                }
            }
        };
        container.addEventListener("scroll", handleScroll);
        return() => container.removeEventListener("scroll", handleScroll);
    }, []);

    useEffect(() => {
        const container = messagesContainerRef.current;
        if (! container) 
            return;
        


        const lastMessage = messages[messages.length - 1];
        const isTypingNow = lastMessage ?. sender === "ai" && lastMessage ?. isTyping;

        // Update ref buat dipake di handleScroll
        isAiTypingRef.current = isTypingNow;

        if (isTypingNow) {
            if (autoScrollEnabled.current && ! isUserScrolling.current) { // Panggil startAutoScroll tapi dalem pengecekan interval biar gak reset terus
                if (! typingAnimationRef.current) {
                    startAutoScroll();
                } else { // Kalau interval udah jalan, kita bantu pancing satu kali scroll instant
                    scrollToBottomInstant();
                }
            }
        } else { // Berhenti ngetik
            if (typingAnimationRef.current) {
                clearInterval(typingAnimationRef.current);
                typingAnimationRef.current = null;
            }

            if (autoScrollEnabled.current && ! isUserScrolling.current) { // Final scroll pake smooth biar cakep pas udah selesai
                setTimeout(() => {
                    container.scrollTo({top: container.scrollHeight, behavior: "smooth"});
                }, 50);
            }
        }

        return() => {
            if (typingAnimationRef.current) {
                clearInterval(typingAnimationRef.current);
            }
        };
    }, [messages]); // Ini bakal ketrigger setiap chunk stream masuk

    useEffect(() => {
        return() => {
            if (typingAnimationRef.current) 
                clearInterval(typingAnimationRef.current);
            


        };
    }, []);

    const checkScrollable = () => {
        const container = messagesContainerRef.current;
        if (container) {
            const isScrollable = container.scrollHeight > container.clientHeight;
            setCanScroll(isScrollable);
        }
    };

    useEffect(() => {
        checkScrollable();
    }, [messages]);

    // =========================================================================
    // SESSION SYNC DARI URL
    // =========================================================================
    useEffect(() => {
        if (sessionId === "new" || sessionId === "guest" || (sessionId === "guest" && isGuest)) {
            setMessages([]);
            setCurrentSessionId(null);
            return;
        }
        if (sessionId && sessionId !== currentSessionId) {
            if (sessionId === currentSessionId) 
                return;
            


            loadChatSession(sessionId);
            setCurrentSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, isGuest]);

    // =========================================================================
    // INITIALIZATION & SESSION MANAGEMENT
    // =========================================================================
    useEffect(() => {
            const checkBackend = async () => {
                    try {
                        const res = await fetch(`${API_BASE}/health`);
                        setBackendStatus(res.ok ? "connected" : "error");
                    } catch {
                        setBackendStatus("disconnected");
                    }};
                checkBackend();
                loadDocuments();
            },
            []
        );

        useEffect(() => {
            const checkSession = async () => {
                const token = localStorage.getItem("session_token");
                try {
                    if (token) {
                        const response = await fetch(`${API_BASE}/api/verify-session?token=${token}`);
                        const result = await response.json();
                        if (response.ok && result.status === "success") {
                            setUserData(result.data);
                            setIsLoggedIn(true);
                        } else {
                            localStorage.clear();
                        }
                    }
                } catch (error) {
                    console.error("Initialization failed", error);
                } finally {
                    setTimeout(() => setIsInitializing(false), 500);
                }
            };
            checkSession();
        }, []);

        useEffect(() => {
            if (currentSessionId) {
                localStorage.setItem("lastSessionId", currentSessionId);
            } else {
                localStorage.removeItem("lastSessionId");
            }
        }, [currentSessionId]);

        useEffect(() => {
            const fetchModels = async () => {
                try {
                    const res = await fetch(`${API_BASE}/api/available-models`);
                    const result = await res.json();
                    if (result.status === "success") 
                        setModelList(result.data);
                    


                } catch (err) {
                    console.error("Gagal ambil model list:", err);
                }
            };
            fetchModels();
        }, []);

        // =========================================================================
        // DOCUMENT MANAGEMENT
        // =========================================================================
            const loadDocuments = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/documents`);
                if (res.ok) {
                    const data = await res.json();
                    setDocuments(data.documents || []);
                }
            } catch (err) {
                console.error("Error loading documents:", err);
            }
        };


        // =========================================================================
        // CHAT SESSION FUNCTIONS
        // =========================================================================
            const loadChatSession = async (sessionUuid) => {
            if (!sessionUuid) 
                return;
            


            setIsLoading(true);
            setCurrentSessionId(sessionUuid);
            try {
                const res = await fetch(`${API_BASE}/api/chat-messages/${sessionUuid}`);
                const result = await res.json();
                if (result.status === "success") {
                    setMessages(result.data);
                } else {
                    console.error("Sesi tidak ditemukan di database");
                }
            } catch (err) {
                console.error("Gagal ambil history pesan:", err);
            } finally {
                setIsLoading(false);
            }
        };

        const handleNewChat = () => {
            setMessages([]);
            setCurrentSessionId(null);
            setInput("");
            setSelectedFiles([]);
            setPreviews([]);
            setUploadedFiles([]);
            if (!isLoggedIn) {
                navigate("/chat/guest");
            } else {
                navigate("/chat/new");
            }
        };

        const switchMode = (mode) => {
            const nextMode = currentMode === mode ? "normal" : mode;
            setCurrentMode(nextMode);
        };

        // =========================================================================
        // MESSAGE HANDLING
        // =========================================================================
            const [expandedMessages, setExpandedMessages] = useState({});
        const toggleExpand = (id) => {
            setExpandedMessages((prev) => ({
                ...prev,
                [id]: !prev[id]
            }));
        };

        const [isDragging, setIsDragging] = useState(false);
        const [selectedFiles, setSelectedFiles] = useState([]);
        const [previews, setPreviews] = useState([]);

        const handleDragOver = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isDragging) 
                setIsDragging(true);
            


        };

        const handleDragLeave = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!e.currentTarget.contains(e.relatedTarget)) {
                setIsDragging(false);
            }
        };

        const onDrop = (e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            const files = e.dataTransfer.files;
            if (files.length > 0) 
                handleFiles(files);
            


        };

        const handleFiles = (files) => {
            const fileArray = Array.from(files);
            fileArray.forEach((file) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const base64Data = e.target.result;
                    const newFile = {
                        url: base64Data,
                        name: file.name,
                        type: file.type.startsWith("image/") ? "image" : "pdf"
                    };
                    setPreviews((prev) => [
                        ...prev,
                        newFile
                    ]);
                    setSelectedFiles((prev) => [
                        ...prev,
                        file
                    ]);
                };
                reader.readAsDataURL(file);
            });
        };

        const handleFileChange = (e) => {
            const selectedFiles = Array.from(e.target.files);
            if (selectedFiles.length > 0) 
                handleFiles(selectedFiles);
            


            e.target.value = null;
        };

        const handlePaste = (e) => {
            const items = e.clipboardData.items;
            const files = [];
            for (let i = 0; i < items.length; i++) {
                if (items[i].kind === "file") {
                    files.push(items[i].getAsFile());
                }
            }
            if (files.length > 0) 
                handleFiles(files);
            


        };

        const handleDrop = (e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            const files = e.dataTransfer.files;
            if (files.length > 0) 
                handleFiles(files);
            


        };

        const sendMessage = async () => {
            if ((!input.trim() && selectedFiles.length === 0) || isLoading) 
                return;
            

            // --- 1. ABORT PREVIOUS REQUEST ---
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            abortControllerRef.current = new AbortController();
            const {signal} = abortControllerRef.current;

            // State UI & Scrolling
            autoScrollEnabled.current = true;
            isUserScrolling.current = false;

            const userMessage = input.trim();
            const currentPreviews = [...previews];

            // Reset inputs segera agar berasa responsif
            setInput("");
            setSelectedFiles([]);
            setPreviews([]);

            const userMsgId = Date.now();
            const aiMsgId = Date.now() + 1;

            // Tambah pesan user & placeholder AI ke list
            setMessages((prev) => [
                ...prev, {
                    id: userMsgId,
                    sender: "user",
                    text: userMessage,
                    attachments: currentPreviews,
                    timestamp: new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                    })
                }, {
                    id: aiMsgId,
                    sender: "ai",
                    text: "",
                    timestamp: new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                    }),
                    isTyping: true
                },
            ]);

            // Scroll otomatis ke bawah setelah pesan baru muncul
            setTimeout(() => {
                messagesContainerRef.current ?. scrollTo({top: messagesContainerRef.current.scrollHeight, behavior: "smooth"});
            }, 50);

            setIsLoading(true);

            try {
                const payload = {
                    message: userMessage,
                    mode: currentMode,
                    model: selectedModel,
                    npp: userData ?. username || null,
                    role: currentRole,
                    session_uuid: currentSessionId,
                    fullname: userData ?. fullname,
                    attachments: currentPreviews.map((p) => ({name: p.name, type: p.type, data: p.url}))
                };

                const res = await fetch(`${API_BASE}/api/chat`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload),
                    signal: signal
                });

                if (! res.ok) 
                    throw new Error(`HTTP ${
                        res.status
                    }`);
                

                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = "";
                let finalData = null;
                let accumulatedText = "";

                // Pengendali Throttle UI (Biar gak boros render)
                let lastUpdate = Date.now();
                const THROTTLE_MS = 40; // Lebih cepat sedikit biar makin smooth

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) 
                        break;
                    

                    buffer += decoder.decode(value, {stream: true});
                    const lines = buffer.split("\n");

                    // Simpan sisa line yang belum lengkap ke buffer
                    buffer = lines.pop() || "";

                    for (const line of lines) {
                        let cleanLine = line.trim();
                        if (! cleanLine) 
                            continue;
                        

                        // Handle SSE format "data: {...}"
                        if (cleanLine.startsWith("data: ")) {
                            cleanLine = cleanLine.substring(6);
                        }

                        try {
                            const chunk = JSON.parse(cleanLine);

                            if (chunk.status === "streaming") {
                                accumulatedText += chunk.reply;

                                const now = Date.now();
                                if (now - lastUpdate > THROTTLE_MS) {
                                    setMessages((prev) => prev.map((msg) => msg.id === aiMsgId ? {
                                        ...msg,
                                        text: accumulatedText
                                    } : msg));
                                    lastUpdate = now;

                                    // Auto scroll jika user tidak sedang scrolling ke atas
                                    if (autoScrollEnabled.current && messagesContainerRef.current) {
                                        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
                                    }
                                }
                            } else if (chunk.status === "completed") {
                                finalData = chunk;
                            }
                        } catch (e) {
                            console.error("Gagal parse chunk:", cleanLine, e);
                        }
                    }
                }

                // --- FINALISASI SETELAH STREAM SELESAI ---
                const finalContent = finalData ?. reply || accumulatedText || "No response.";

                // Update Metadata Session jika ini chat baru
                if (finalData ?. session_uuid && !currentSessionId) {
                    setCurrentSessionId(finalData.session_uuid);
                    setChatHistory((prev) => [
                        {
                            session_uuid: finalData.session_uuid,
                            judul: finalData.judul || userMessage.substring(0, 30),
                            created_at: new Date().toISOString(),
                            is_pinned: false
                        },
                        ...prev
                    ]);
                    localStorage.setItem("lastSessionId", finalData.session_uuid);
                    if (isLoggedIn) {
                        window.history.replaceState(null, "", `/chat/${
                            finalData.session_uuid
                        }`);
                    }
                }

                // Final State Update (Matikan typing, masukkan pdf_info)
                setMessages((prev) => prev.map((msg) => msg.id === aiMsgId ? {
                    ...msg,
                    text: finalContent,
                    pdfInfo: finalData ?. pdf_info || null,
                    isFromDocument: finalData ?. is_from_document || false,
                    isTyping: false
                } : msg));

            } catch (err) {
                if (err.name === 'AbortError') {
                    setMessages((prev) => prev.map((msg) => msg.id === aiMsgId ? {
                        ...msg,
                        isStopped: true,
                        isTyping: false
                    } : msg));
                } else {
                    console.error("Chat Error:", err);
                    setMessages((prev) => prev.map((msg) => msg.id === aiMsgId ? {
                        ...msg,
                        text: `Error: ${
                            err.message
                        }`,
                        isTyping: false,
                        isError: true
                    } : msg));
                }
            } finally {
                setIsLoading(false);
                abortControllerRef.current = null;
            }
        };
        
        const handleKeyPress = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isLoading && input.trim()) {
                    sendMessage();
                }
            }
        };

        // =========================================================================
        // AUTHENTICATION FUNCTIONS
        // =========================================================================
            const handleLoginSubmit = async (e) => {
            e.preventDefault();
            const {username, password} = loginForm;
            try {
                const response = await fetch(`${API_BASE}/api/login`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(
                        {username, password}
                    )
                });
                const result = await response.json();
                if (response.ok && result.status === "success") {
                    const newUser = {
                        username: result.data.username,
                        fullname: result.data.fullname,
                        divisi: result.data.divisi,
                        role: result.data.role
                    };
                    setIsLoggedIn(true);
                    setUserData(newUser);
                    localStorage.setItem("session_token", result.data.token);
                    localStorage.setItem("userSession", JSON.stringify(newUser));
                    localStorage.setItem("isLoggedIn", "true");
                    localStorage.setItem("userRole", result.data.role);
                    showNotification(`Selamat datang, ${
                        newUser.fullname
                    }!`, "success");
                    setShowLoginModal(false);
                    setLoginForm({username: "", password: ""});
                    setLoginError("");
                    const currentPath = window.location.pathname;
                    if (currentPath === "/chat/guest") {
                        navigate("/chat/new");
                    }
                } else {
                    setLoginError(result.message || "Login gagal");
                }
            } catch (error) {
                console.error("Login Error:", error);
                setLoginError("Server login tidak merespon");
            }
        };

        const triggerLogout = () => {
            setIsLogoutModalOpen(true);
        };

        const handleLogout = async () => {
            const token = localStorage.getItem("session_token");
            try {
                if (token) {
                    await fetch(`${API_BASE}/api/logout`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({token})
                    });
                }
            } catch (error) {
                console.error("Gagal logout ke server:", error);
            } finally {
                localStorage.clear();
                setIsLoggedIn(false);
                setUserData(null);
                setMessages([]);
                setCurrentSessionId(null);
                setChatHistory([]);
                setInput("");
                setIsLogoutModalOpen(false);
                navigate("/chat/guest");
            }
        };

        // =========================================================================
        // COPY BUBBLE
        // =========================================================================
            const handleCopy = (text, showNotification) => {
            if (!text) 
                return;
            


            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => showNotification("Teks berhasil disalin!")).catch(() => fallbackCopyTextToClipboard(text, showNotification));
            } else {
                fallbackCopyTextToClipboard(text, showNotification);
            }
        };

        const fallbackCopyTextToClipboard = (text, showNotification) => {
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            textArea.style.top = "0";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                const successful = document.execCommand("copy");
                if (successful) {
                    showNotification("Teks berhasil disalin!");
                }
            } catch (err) {
                console.error("Fallback: Oops, unable to copy", err);
            }
            document.body.removeChild(textArea);
        };

        const stopGeneration = () => {
            if (abortControllerRef.current) { // 1. Matikan request
                abortControllerRef.current.abort();
                setIsLoading(false);

                // 2. UPDATE STATE MESSAGES (Ini kuncinya!)
                setMessages((prev) => {
                    const newMessages = [...prev];
                    // Cari index terakhir
                    const lastIndex = newMessages.length - 1;

                    // Jika pesan terakhir adalah dari AI, tambahkan flag isStopped
                    if (lastIndex >= 0 && newMessages[lastIndex].sender === "ai") {
                        newMessages[lastIndex] = {
                            ... newMessages[lastIndex],
                            isStopped: true, // Flag ini yang dibaca MessageList
                            isTyping: false // Matikan kursor juga
                        };
                    }
                    return newMessages;
                });
            }
        };

        const handleContinue = async (messageId) => {
            const targetMessage = messages.find((m) => m.id === messageId);
            if (! targetMessage || isLoading) 
                return;
            


            // Hitung apakah ada blok kode yang belum tertutup
            const codeBlockCount = (targetMessage.text.match(/```/g) || []).length;
            const isUnfinishedCode = codeBlockCount % 2 !== 0;

            // 1. Persiapan AbortController
            if (abortControllerRef.current) 
                abortControllerRef.current.abort();
            


            abortControllerRef.current = new AbortController();
            const {signal} = abortControllerRef.current;

            // 2. Set UI State
            setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
                ...msg,
                isStopped: false,
                isTyping: true
            } : msg));
            setIsLoading(true);

            try {
                const fullContext = targetMessage.text.slice(-1000);
                const lastLine = targetMessage.text.split('\n').pop();

                // Prompt dimodifikasi agar AI tidak mengirim ulang backticks jika isUnfinishedCode = true
                const continuePrompt = `
        CONTINUE MODE. 
        The user is viewing a code block that was cut off. 
        
        CONTEXT OF PREVIOUS CODE:
        \`\`\`
        ${fullContext}
        \`\`\`
        
        YOUR TASK:
        Continue the code exactly from where it stopped. 
        The last line was: "${lastLine}"
        
        STRICT RULES:
        1. START IMMEDIATELY with the remaining code.
        2. ${
                    isUnfinishedCode ? "DO NOT start with new backticks (```). Resume the raw text inside the existing block." : "Wrap your response in a code block (```)."
                }
        3. Do NOT repeat the context code.
        4. If you were in the middle of a tag or a function, complete it first.
        5. Provide ONLY the continuation. No conversational filler.
        `;

                const payload = {
                    message: continuePrompt,
                    model: selectedModel,
                    session_uuid: currentSessionId,
                    npp: userData ?. username || null,
                    fullname: userData ?. fullname,
                    attachments: []
                };

                const res = await fetch(`${API_BASE}/api/chat`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload),
                    signal: signal
                });

                if (! res.ok) 
                    throw new Error(`HTTP ${
                        res.status
                    }`);
                


                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = "";
                let accumulatedText = targetMessage.text;
                let lastUpdate = Date.now();
                const THROTTLE_MS = 60;

                while (true) {
                    if (signal.aborted) 
                        break;
                    


                    const {done, value} = await reader.read();
                    if (done) 
                        break;
                    


                    buffer += decoder.decode(value, {stream: true});
                    const lines = buffer.split("\n");
                    buffer = lines.pop() || "";

                    for (const line of lines) {
                        if (! line.trim()) 
                            continue;
                        


                        try {
                            const chunk = JSON.parse(line);

                            if (chunk.status === "streaming") {
                                let reply = chunk.reply;

                                if (isUnfinishedCode) { // 1. Bersihkan sapaan & backticks (tetap perlu)
                                    reply = reply.replace(/^(Tentu|Sure|Berikut|Here is|lanjutannya)[^]*?[:\n]*/i, "");
                                    reply = reply.replace(/^```[a-z]*\n?/i, "");

                                    // 2. LINE-BASED OVERLAP DETECTION (Lebih Galak)
                                    const existingLines = accumulatedText.split('\n');
                                    const lastLineExisting = existingLines[existingLines.length - 1].trim();

                                    // Jika AI mengirim baris yang isinya sama persis dengan baris terakhir kita
                                    if (reply.trim().startsWith(lastLineExisting) && lastLineExisting.length > 0) { // Potong reply mulai dari setelah teks yang duplikat
                                        const pattern = lastLineExisting;
                                        const index = reply.indexOf(pattern);
                                        reply = reply.slice(index + pattern.length);
                                    }

                                    // 3. CHARACTER-BY-CHARACTER SWEEP (Safety Net)
                                    // Cek apakah 20 karakter terakhir ada yang sama di awal reply
                                    const tail = accumulatedText.slice(-20);
                                    for (let i = 0; i < tail.length; i++) {
                                        const overlap = tail.slice(i);
                                        if (reply.startsWith(overlap)) {
                                            reply = reply.slice(overlap.length);
                                            break;
                                        }
                                    }
                                }

                                accumulatedText += reply;


                                const now = Date.now();
                                if (now - lastUpdate > THROTTLE_MS) {
                                    setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
                                        ...msg,
                                        text: accumulatedText
                                    } : msg));
                                    lastUpdate = now;

                                    if (autoScrollEnabled.current && messagesContainerRef.current) {
                                        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
                                    }
                                }
                            }
                        } catch (e) {
                            console.error("Parse error", e);
                        }
                    }
                }

                // Final Update
                setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
                    ...msg,
                    text: accumulatedText,
                    isTyping: false
                } : msg));

            } catch (err) {
                if (err.name === 'AbortError') {
                    setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
                        ...msg,
                        isStopped: true,
                        isTyping: false
                    } : msg));
                } else {
                    showNotification("Gagal menyambung pesan.", "error");
                    setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
                        ...msg,
                        isTyping: false
                    } : msg));
                }
            } finally {
                setIsLoading(false);
                abortControllerRef.current = null;
            }
        };
        // =========================================================================
        // PASS ALL NECESSARY PROPS TO CHILDREN
        // =========================================================================
            const sharedProps = {
            // State
            messages,
            input,
            setInput,
            isLoading,
            stopGeneration,
            handleContinue,
            currentSessionId,
            chatHistory,
            uploadedFiles,
            documents,
            showPreview,
            previewFile,
            tempFileId,
            showDocumentList,
            currentMode,
            isLoggedIn,
            userData,
            backendStatus,
            isInitializing,
            modelList,
            selectedModel,
            isSidebarOpen,
            isDropdownOpen,
            notification,
            showLoginModal,
            loginForm,
            loginError,
            showPassword,
            isLogoutModalOpen,
            messagesContainerRef,
            fileInputRef,
            isDragging,
            previews,
            selectedFiles,
            expandedMessages,
            showScrollTop,
            showScrollBottom,
            isAtBottom,
            canScroll,
            isAiTypingRef,
            // Handlers
            startAutoScroll,
            showNotification,
            getGreeting,
            handleNewChat,
            switchMode,
            toggleExpand,
            handleDragOver,
            handleDragLeave,
            onDrop,
            handleFileChange,
            handlePaste,
            handleDrop,
            sendMessage,
            handleKeyPress,
            handleLoginSubmit,
            triggerLogout,
            handleLogout,
            handleCopy,
            setShowDocumentList,
            setIsSidebarOpen,
            setIsDropdownOpen,
            setShowLoginModal,
            setLoginForm,
            setLoginError,
            setShowPassword,
            setIsLogoutModalOpen,
            setPreviews,
            setSelectedFiles,
            setExpandedMessages,
            setMessages,
            setCurrentSessionId,
            setChatHistory,
            setUploadedFiles,
            setDocuments,
            setShowPreview,
            setPreviewFile,
            setTempFileId,
            setSelectedModel,
            navigate,
            cakraLogo,
            API_BASE
        };

        return (
            <MainLayout {...sharedProps}
                stopGeneration={stopGeneration}>
                {/* 1. Header tetap di atas */}
                <HeaderBar {...sharedProps}/> {/* 2. Area Utama Chat */}
                <div className="flex-1 relative flex flex-col overflow-hidden">
                    {/* MessageList sekarang menangani kondisi kosong (GuestWelcome) di dalamnya */}
                    <MessageList {...sharedProps}
                        handleContinue={handleContinue}
                        isAiTypingRef={isAiTypingRef}
                        startAutoScroll={startAutoScroll}/> {/* FloatingButtons ditaruh sejajar dengan MessageList supaya absolute-nya bekerja */}
                    <FloatingButtons {...sharedProps}/>
                </div>

                {/* 3. Input Area di paling bawah */}
                <InputArea {...sharedProps}/> {/* 4. Overlay & Modals (Tidak memakan space layout) */}
                <LoginModal {...sharedProps}/>
                <LogoutModal {...sharedProps}/>
                <NotificationToast notification={notification}/> {/* Preview File Overlay */}
                {
                showPreview && (
                    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        {/* Masukkan logic preview file lu di sini atau buat komponen FilePreviewModal */} </div>
                )
            } </MainLayout>
        );
    }

    export default ChatPage;
