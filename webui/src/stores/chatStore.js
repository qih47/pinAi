import { create } from "zustand";
import * as endpoints from "../services/endpoints";
import { createChatSlice } from "./slices/chatSlice";
import { createStreamSlice } from "./slices/streamSlice";
import { createDocumentSlice } from "./slices/documentSlice";
import { createAttachmentSlice } from "./slices/attachmentSlice";

export const API_BASE = endpoints.getApiBase();
export const getUploadUrl = endpoints.getUploadUrl;

export const useChatStore = create((set, get) => ({
    // Initial State
    messages: [],
    isLoading: false,
    isStreaming: false,
    isThinking: false,
    isThinkingMode: false,
    currentThinking: '',
    sessionUuid: null,
    activeStreams: {}, // Track background streams: { [sessionUuid]: { isStreaming: true, messages: [], ... } }
    stagedAttachments: [],
    activeIsolatedDocId: null,
    activeIsolatedTitle: null,
    documents: [],
    isLoadingDocuments: false,
    abortController: null,
    artifacts: [],
    isSplitScreen: false,
    activePdfUrl: null,
    showGhostWriter: false,
    ghostWriterContent: "",

    // Slices
    ...createChatSlice(set, get),
    ...createStreamSlice(set, get),
    ...createDocumentSlice(set, get),
    ...createAttachmentSlice(set, get)
}));