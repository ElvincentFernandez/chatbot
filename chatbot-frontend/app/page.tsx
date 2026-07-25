"use client";

import { Sidebar } from "@/components/sidebar";
import { MessageCircle, Zap, BookOpen, Database, Send, Square, FileText, X, ChevronDown, Unlock, Lock } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useRouter } from "next/navigation";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  // --- State untuk fitur dokumen aktif (Parent Document Retriever scoping) ---
  const [documents, setDocuments] = useState<string[]>([]);
  const [activeDocument, setActiveDocument] = useState<string | null>(null);
  const [isDocMenuOpen, setIsDocMenuOpen] = useState(false);

  // --- State untuk toggle mode jawaban (strict vs general) ---
  const [generalMode, setGeneralMode] = useState(false);

  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Ref to track if user is near bottom of chat container
  const isNearBottomRef = useRef(true);

  // AbortController Ref for cancelling fetch requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Ref to track session that was just created to prevent race condition
  const justCreatedSessionRef = useRef<string | null>(null);

  const authHeader = () => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // Authentication check
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
    } else {
      setUserRole(localStorage.getItem("role"));
      setUsername(localStorage.getItem("username"));
    }
  }, [router]);

  const fetchDocuments = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch("http://localhost:8000/api/documents", {
        headers: { ...authHeader() },
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents ?? []);
      }
    } catch (err) {
      console.error("Gagal ambil daftar dokumen:", err);
    }
  };

  useEffect(() => {
    if (localStorage.getItem("token")) {
      fetchDocuments();
    }
  }, []);

  const handleDeleteDocument = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`http://localhost:8000/api/documents/${encodeURIComponent(filename)}`, {
        method: "DELETE",
        headers: { ...authHeader() },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal hapus dokumen.");
      }
      if (activeDocument === filename) setActiveDocument(null);
      fetchDocuments();
    } catch (err: any) {
      alert(err.message || "Gagal hapus dokumen.");
    }
  };

  // Handle scroll events to detect if user scrolls up
  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 150;
    isNearBottomRef.current = isAtBottom;
  };

  // Scroll to bottom only if user was already at the bottom
  useEffect(() => {
    if (isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Fetch messages when session changes
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }

    if (justCreatedSessionRef.current === currentSessionId) {
      justCreatedSessionRef.current = null;
      return;
    }

    const fetchMessages = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        const res = await fetch(`http://localhost:8000/api/chat/sessions/${currentSessionId}`, {
          headers: { ...authHeader() },
        });
        if (res.ok) {
          const data = await res.json();
          const mappedMessages = data.map((msg: any) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: new Date(msg.timestamp),
          }));

          isNearBottomRef.current = true;
          setMessages(mappedMessages);
        }
      } catch (err) {
        console.error("Gagal memuat pesan:", err);
      }
    };

    fetchMessages();
  }, [currentSessionId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        headers: { ...authHeader() },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal upload.");
      }

      await fetchDocuments();
      setActiveDocument(file.name); // otomatis jadiin dokumen baru sebagai dokumen aktif

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: `Sip! Aku udah baca file "${file.name}". Sekarang kamu bisa tanya-tanya soal isinya ya!`,
          timestamp: new Date(),
        },
      ]);
    } catch (err: any) {
      alert(err.message || "Gagal upload file ke backend.");
    } finally {
      setIsLoading(false);
      e.target.value = "";
    }
  };

  const handleNewChat = () => {
    handleStopGeneration();
    setCurrentSessionId(null);
    setMessages([]);
  };

  const handleSelectSession = (id: string) => {
    handleStopGeneration();
    setCurrentSessionId(id);
  };

  const handleStopGeneration = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);

      const lastMessage = messages[messages.length - 1];
      if (lastMessage && lastMessage.role === "assistant" && lastMessage.content.trim() && currentSessionId) {
        const token = localStorage.getItem("token");
        if (token) {
          try {
            await fetch("http://localhost:8000/api/chat/save_partial", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                ...authHeader(),
              },
              body: JSON.stringify({
                session_id: currentSessionId,
                content: lastMessage.content,
              }),
            });
          } catch (e) {
            console.error("Gagal mengirim sinyal simpan parsial:", e);
          }
        }
      }
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    let sessionId = currentSessionId;

    if (!sessionId) {
      try {
        const createRes = await fetch("http://localhost:8000/api/chat/sessions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeader(),
          },
          body: JSON.stringify({ title: input.substring(0, 30) + (input.length > 30 ? "..." : "") }),
        });
        if (!createRes.ok) throw new Error("Gagal membuat sesi chat baru.");
        const sessionData = await createRes.json();
        sessionId = sessionData.id;
        justCreatedSessionRef.current = sessionId;
        setCurrentSessionId(sessionId);

        window.dispatchEvent(new Event("sync-sessions"));
      } catch (err: any) {
        alert(err.message);
        return;
      }
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    const currentInput = input;
    setInput("");

    const assistantMessageId = (Date.now() + 1).toString();
    const initialAssistantMessage: Message = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };

    isNearBottomRef.current = true;
    setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeader(),
        },
        body: JSON.stringify({
          message: currentInput,
          session_id: sessionId,
          document: activeDocument,
          general_mode: generalMode,
        }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error("Gagal konek ke model AI");
      if (!response.body) throw new Error("Tidak ada stream dari backend!");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        fullText += chunk;

        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;
          if (updated[lastIndex].id === assistantMessageId) {
            updated[lastIndex] = { ...updated[lastIndex], content: fullText };
          }
          return updated;
        });
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Generasi teks dihentikan oleh user.");
      } else {
        console.error("Error:", error);
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: "assistant",
            content: `Aduh sorry, terjadi masalah: ${error.message || "koneksi terputus."}`,
            timestamp: new Date(),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const features = [
    { icon: Database, title: "RAG Integration", description: "Retrieve Augmented Generation for context-aware responses" },
    { icon: Zap, title: "Prompt Caching", description: "Optimized token usage and faster response times" },
    { icon: MessageCircle, title: "SLM Powered", description: "Efficient Small Language Models for thesis research" },
    { icon: BookOpen, title: "Research Tools", description: "Built-in documentation and knowledge management" },
  ];

  return (
    <div className="flex h-screen bg-background">
      <Sidebar currentSessionId={currentSessionId} onSelectSession={handleSelectSession} onNewChat={handleNewChat} />

      <main className="flex-1 flex flex-col overflow-hidden pl-0 lg:pl-0">
        <header className="h-16 border-b border-border bg-card/50 backdrop-blur-md flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-foreground text-sm lg:text-base">
              {currentSessionId ? "Active Chat Session" : "New Chat Session"}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 font-mono capitalize">
              Role: {userRole}
            </span>
            <span className="text-sm font-medium text-muted-foreground hidden sm:inline">Hi, {username}</span>
          </div>
        </header>

        <div ref={chatContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-4 py-8">
              <div className="max-w-2xl w-full text-center">
                <div className="mb-8">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mx-auto mb-4 animate-pulse">
                    <MessageCircle size={32} className="text-primary" />
                  </div>
                  <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                    Welcome to RAGChat
                  </h1>
                  <p className="text-muted-foreground text-lg mb-8">
                    Your intelligent research assistant powered by RAG, prompt caching, and Small Language Models
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                  {features.map((feature, idx) => {
                    const Icon = feature.icon;
                    return (
                      <div key={idx} className="p-4 rounded-lg bg-card border border-border hover:border-primary/50 transition-colors text-center">
                        <Icon size={24} className="text-primary mb-2 mx-auto" />
                        <h3 className="font-semibold text-foreground mb-1">{feature.title}</h3>
                        <p className="text-sm text-muted-foreground">{feature.description}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground mb-3">Try asking about:</p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {["How does RAG work?", "Prompt caching techniques", "SLM vs LLM trade-offs", "Research methodology"].map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => setInput(suggestion)}
                        className="px-4 py-2 rounded-full bg-secondary hover:bg-secondary/80 text-secondary-foreground transition-colors text-sm"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full px-4 py-8 space-y-6">
              {messages.map((message) => {
                const cleanContent = message.content
                  .replace(/<think>[\s\S]*?<\/think>/g, "")
                  .replace(/Thinking Process:[\s\S]*?(?=\n\n|\n[A-Z]|$)/gi, "")
                  .trim();

                if (message.role === "assistant" && cleanContent === "") {
                  return null;
                }

                return (
                  <div key={message.id} className={`flex gap-4 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    {message.role === "assistant" && (
                      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                        <MessageCircle size={16} className="text-primary-foreground" />
                      </div>
                    )}
                    <div
                      className={`max-w-[90%] md:max-w-3xl px-4 py-3 rounded-lg ${
                        message.role === "user"
                          ? "bg-primary text-primary-foreground rounded-br-none"
                          : "bg-card text-foreground border border-border rounded-bl-none shadow-sm"
                      }`}
                    >
                      <div className="text-sm md:text-base leading-relaxed">
                        {message.role === "assistant" ? (
                          <div className="[&>p]:mb-2 [&>ul]:list-disc [&>ul]:ml-5 [&>ol]:list-decimal [&>ol]:ml-5 [&>li]:mb-1 markdown-content">
                            <ReactMarkdown>{cleanContent}</ReactMarkdown>
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap">{message.content}</p>
                        )}
                      </div>
                      <span className={`text-xs mt-2 block ${message.role === "user" ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                        {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                );
              })}

              {isLoading && messages[messages.length - 1]?.content === "" && (
                <div className="flex gap-4 justify-start animate-fade-in">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                    <MessageCircle size={16} className="text-primary-foreground animate-pulse" />
                  </div>
                  <div className="bg-card border border-border rounded-lg rounded-bl-none px-4 py-3 shadow-sm">
                    <div className="flex gap-2">
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-border bg-background/80 backdrop-blur-sm">
          <div className="max-w-4xl mx-auto w-full p-4">
            {/* Bar kontrol: dokumen aktif + toggle mode jawaban */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              {documents.length > 0 && (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setIsDocMenuOpen((open) => !open)}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary hover:bg-secondary/80 text-secondary-foreground text-xs transition-colors"
                  >
                    <FileText size={14} />
                    <span className="max-w-[220px] truncate">{activeDocument ?? "Semua dokumen"}</span>
                    <ChevronDown size={14} />
                  </button>

                  {isDocMenuOpen && (
                    <div className="absolute bottom-full mb-2 left-0 w-72 rounded-lg border border-border bg-card shadow-lg overflow-hidden z-10">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveDocument(null);
                          setIsDocMenuOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-secondary transition-colors ${
                          activeDocument === null ? "bg-secondary/60 font-medium" : ""
                        }`}
                      >
                        Semua dokumen
                      </button>
                      <div className="max-h-56 overflow-y-auto">
                        {documents.map((docName) => (
                          <div
                            key={docName}
                            onClick={() => {
                              setActiveDocument(docName);
                              setIsDocMenuOpen(false);
                            }}
                            className={`flex items-center justify-between gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-secondary transition-colors ${
                              activeDocument === docName ? "bg-secondary/60 font-medium" : ""
                            }`}
                          >
                            <span className="truncate flex-1">{docName}</span>
                            {(userRole === "admin" || userRole === "superadmin") && (
                              <button
                                type="button"
                                onClick={(e) => handleDeleteDocument(docName, e)}
                                className="p-1 rounded hover:bg-muted flex-shrink-0"
                                title="Hapus dokumen"
                              >
                                <X size={14} className="text-muted-foreground" />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Toggle mode jawaban: default ketat (sesuai dokumen), bisa dilonggarkan manual */}
              <button
                type="button"
                onClick={() => setGeneralMode((v) => !v)}
                title={
                  generalMode
                    ? "Mode bebas: AI boleh jawab dari pengetahuan umum di luar dokumen"
                    : "Mode ketat: AI hanya jawab dari dokumen (default, sesuai metodologi skripsi)"
                }
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition-colors ${
                  generalMode
                    ? "bg-amber-500/15 text-amber-500 border border-amber-500/30 hover:bg-amber-500/20"
                    : "bg-secondary hover:bg-secondary/80 text-secondary-foreground"
                }`}
              >
                {generalMode ? <Unlock size={14} /> : <Lock size={14} />}
                {generalMode ? "Mode Bebas" : "Mode Ketat (Dokumen)"}
              </button>
            </div>

            <form onSubmit={handleSendMessage} className="flex gap-3 items-center">
              {userRole === "admin" || userRole === "superadmin" ? (
                <label className="cursor-pointer p-2 hover:bg-secondary rounded-full transition-colors flex-shrink-0" title="Upload PDF to RAG Database">
                  <Database size={24} className="text-purple-400 hover:text-purple-300" />
                  <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
                </label>
              ) : (
                <div className="p-2 cursor-not-allowed opacity-40 flex-shrink-0" title="User cannot upload PDF to RAG Database">
                  <Database size={24} className="text-muted-foreground" />
                </div>
              )}

              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Tanya soal dokumen atau AI..."
                className="flex-1 px-4 py-3 rounded-lg bg-input border border-border text-foreground focus:outline-none focus:border-primary transition-colors"
                disabled={isLoading}
              />

              {isLoading ? (
                <button
                  type="button"
                  onClick={handleStopGeneration}
                  className="px-6 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium flex items-center gap-2"
                >
                  <Square size={16} fill="white" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:bg-muted transition-colors font-medium flex items-center gap-2"
                >
                  <Send size={16} />
                  <span className="hidden sm:inline">Send</span>
                </button>
              )}
            </form>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              This is a thesis project combining RAG, prompt caching, and Small Language Models
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
