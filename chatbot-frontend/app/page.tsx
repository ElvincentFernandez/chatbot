"use client";

import { Sidebar } from "@/components/sidebar";
import { MessageCircle, Zap, BookOpen, Database, Send, Square, Building2, School, Landmark, ChevronRight } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useRouter } from "next/navigation";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface Client {
  id: number;
  name: string;
  type: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  
  // Client selection states
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | string | null>(null);
  const [userClientId, setUserClientId] = useState<number | null>(null);
  const [userClientName, setUserClientName] = useState<string | null>(null);
  
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  
  // Ref to track if user is near bottom of chat container
  const isNearBottomRef = useRef(true);
  
  // AbortController Ref for cancelling fetch requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Ref to track session that was just created to prevent race condition
  const justCreatedSessionRef = useRef<string | null>(null);

  // Authentication check & initial fetches
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    const role = localStorage.getItem("role");
    const uname = localStorage.getItem("username");
    const uClientId = localStorage.getItem("client_id");
    const uClientName = localStorage.getItem("client_name");

    setUserRole(role);
    setUsername(uname);

    if (uClientId) {
      const cid = parseInt(uClientId);
      setUserClientId(cid);
      setUserClientName(uClientName);
      setSelectedClientId(cid); // Auto select for admin_client
    } else {
      // Fetch clients list if user is global (user, admin, superadmin)
      fetchClients(token);
    }
  }, [router]);

  const fetchClients = async (token: string) => {
    try {
      const res = await fetch("http://localhost:8000/api/clients", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
      }
    } catch (err) {
      console.error("Gagal memuat daftar client:", err);
    }
  };

  // Handle scroll events to detect if user scrolls up
  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    
    // If user is within 150px of the bottom, consider them "near bottom"
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
      // Reset selected client only if user is global (not bound to client)
      const uClientId = localStorage.getItem("client_id");
      if (!uClientId) {
        setSelectedClientId(null);
      }
      return;
    }

    const fetchMessages = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        const res = await fetch(`http://localhost:8000/api/chat/sessions/${currentSessionId}`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (res.ok) {
          const data = await res.json();
          const mappedMessages = data.map((msg: any) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: new Date(msg.timestamp)
          }));
          
          // Set client ID based on session client
          // Find this session in localStorage or local sidebar list to get its client
          const sidebarRes = await fetch("http://localhost:8000/api/chat/sessions", {
            headers: {
              "Authorization": `Bearer ${token}`
            }
          });
          if (sidebarRes.ok) {
            const sessionsData = await sidebarRes.json();
            const currentSession = sessionsData.find((s: any) => s.id === currentSessionId);
            if (currentSession) {
              setSelectedClientId(currentSession.client_id);
            }
          }

          // If we just created this session locally, preserve the local
          // placeholder assistant message so streaming can start and the
          // typing indicator remains visible. Subsequent fetches will behave
          // normally.
          if (justCreatedSessionRef.current === currentSessionId) {
            justCreatedSessionRef.current = null;
          } else {
            isNearBottomRef.current = true;
            setMessages(mappedMessages);
          }
        }
      } catch (err) {
        console.error("Gagal memuat pesan:", err);
      }
    };

    fetchMessages();
  }, [currentSessionId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedClientId) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`http://localhost:8000/api/upload?client_id=${selectedClientId}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal upload.");
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: `Sip! Aku udah membaca file "${file.name}" untuk basis data RAG client ini.`,
          timestamp: new Date(),
        },
      ]);
    } catch (err: any) {
      alert(err.message || "Gagal upload file ke backend.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    handleStopGeneration();
    setCurrentSessionId(null);
    setMessages([]);
    const uClientId = localStorage.getItem("client_id");
    if (!uClientId) {
      setSelectedClientId(null);
    }
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

      // Ambil teks chat terakhir yang berhasil digenerate
      const lastMessage = messages[messages.length - 1];
      if (lastMessage && lastMessage.role === "assistant" && lastMessage.content.trim() && currentSessionId) {
        const token = localStorage.getItem("token");
        if (token) {
          try {
            await fetch("http://localhost:8000/api/chat/save_partial", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
              },
              body: JSON.stringify({
                session_id: currentSessionId,
                content: lastMessage.content
              })
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
    if (!input.trim() || isLoading || !selectedClientId) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    let sessionId = currentSessionId;

    // Create session automatically if none exists
    if (!sessionId) {
      try {
        const createRes = await fetch("http://localhost:8000/api/chat/sessions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ 
            title: input.substring(0, 30) + (input.length > 30 ? "..." : ""),
            client_id: selectedClientId === "global" ? null : selectedClientId
          })
        });
        if (!createRes.ok) throw new Error("Gagal membuat sesi chat baru.");
        const sessionData = await createRes.json();
        sessionId = sessionData.id;
        justCreatedSessionRef.current = sessionId;
        setCurrentSessionId(sessionId);
        
        // Trigger sidebar sync
        window.dispatchEvent(new Event('sync-sessions'));
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
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ message: currentInput, session_id: sessionId }),
        signal: controller.signal
      });

      if (!response.ok) throw new Error("Gagal konek ke model AI");
      if (!response.body) throw new Error("Tidak ada stream dari backend!");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullText = "";
      let receivedFirstNonWhitespace = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        // Ignore purely-whitespace flush chunks until we receive the first
        // meaningful token. This keeps the assistant placeholder empty so the
        // typing indicator is shown, and prevents visual noise from the
        // backend's initial flush.
        if (!receivedFirstNonWhitespace && chunk.trim().length === 0) {
          continue;
        }

        receivedFirstNonWhitespace = true;
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

  const getClientIcon = (type: string) => {
    switch (type) {
      case "Perbankan": return <Landmark className="w-8 h-8 text-indigo-400" />;
      case "Kampus": return <School className="w-8 h-8 text-purple-400" />;
      default: return <Building2 className="w-8 h-8 text-cyan-400" />;
    }
  };

  const activeClientName = selectedClientId === "global" 
    ? "General Assistant" 
    : (clients.find(c => c.id === selectedClientId)?.name || userClientName || "");

  return (
    <div className="flex h-screen bg-background">
      <Sidebar 
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden pl-0 lg:pl-0">
        
        {/* Top Navbar */}
        <header className="h-16 border-b border-border bg-card/50 backdrop-blur-md flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-foreground text-sm lg:text-base">
              {currentSessionId ? (
                <span className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{activeClientName}</span>
                  Active Chat Session
                </span>
              ) : "New Chat Session"}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 font-mono capitalize">
              Role: {userRole === "admin_client" ? `Admin - ${userClientName}` : userRole}
            </span>
            <span className="text-sm font-medium text-muted-foreground hidden sm:inline">
              Hi, {username}
            </span>
          </div>
        </header>

        {/* Chat Messages Area */}
        <div 
          ref={chatContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto"
        >
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-4 py-8">
              <div className="max-w-2xl w-full text-center">
                
                {/* Brand Header */}
                <div className="mb-8">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mx-auto mb-4 animate-pulse">
                    <MessageCircle size={32} className="text-primary" />
                  </div>
                  <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                    RAGChat Portal
                  </h1>
                  <p className="text-muted-foreground text-sm max-w-md mx-auto">
                    Pilih client untuk menghubungkan AI dengan database RAG spesifik dari instansi tersebut.
                  </p>
                </div>

                {!userClientId ? (
                  <div className="mb-8 text-left">
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">PILIH CLIENT DATA RAG</h3>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {clients.map((c) => (
                        <div
                          key={c.id}
                          onClick={() => setSelectedClientId(c.id)}
                          className={`p-5 rounded-2xl border cursor-pointer transition-all hover:scale-[1.02] flex flex-col items-center text-center relative overflow-hidden ${
                            selectedClientId === c.id 
                              ? "bg-indigo-500/10 border-indigo-500 shadow-lg shadow-indigo-500/5" 
                              : "bg-card border-border hover:border-slate-700"
                          }`}
                        >
                          <div className="p-3 bg-slate-900 rounded-xl mb-3">
                            {getClientIcon(c.type)}
                          </div>
                          <h4 className="font-bold text-slate-100">{c.name}</h4>
                          <span className="text-[10px] uppercase font-bold text-slate-500 mt-1 tracking-wider">{c.type}</span>
                          {selectedClientId === c.id && (
                            <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-indigo-400" />
                          )}
                        </div>
                      ))}
                      
                      {/* General AI Card Option */}
                      <div
                        onClick={() => setSelectedClientId("global")}
                        className={`p-5 rounded-2xl border cursor-pointer transition-all hover:scale-[1.02] flex flex-col items-center text-center relative overflow-hidden ${
                          selectedClientId === "global" 
                            ? "bg-indigo-500/10 border-indigo-500 shadow-lg shadow-indigo-500/5" 
                            : "bg-card border-border hover:border-slate-700"
                        }`}
                      >
                        <div className="p-3 bg-slate-900 rounded-xl mb-3">
                          <Zap className="w-8 h-8 text-yellow-400" />
                        </div>
                        <h4 className="font-bold text-slate-100">General AI</h4>
                        <span className="text-[10px] uppercase font-bold text-slate-500 mt-1 tracking-wider">Asisten Umum</span>
                        {selectedClientId === "global" && (
                          <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-indigo-400" />
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-6 bg-indigo-500/5 border border-indigo-500/20 rounded-2xl max-w-md mx-auto mb-8 flex items-center gap-4 text-left">
                    <div className="p-3 bg-slate-900 rounded-xl">
                      {getClientIcon(clients.find(c => c.id === userClientId)?.type || "Umum")}
                    </div>
                    <div>
                      <h4 className="font-bold text-indigo-300">{userClientName}</h4>
                      <p className="text-xs text-slate-400 mt-0.5">Sesi chat Anda otomatis terhubung ke basis data client ini.</p>
                    </div>
                  </div>
                )}

                {/* Info Text */}
                {selectedClientId && (
                  <div className="p-4 bg-slate-900/60 border border-border rounded-xl text-xs text-slate-400 max-w-md mx-auto animate-fade-in flex items-center justify-between">
                    <span>Terhubung ke **{activeClientName}** RAG Database.</span>
                    <button 
                      onClick={() => setInput("Halo, jelaskan data apa saja yang tersedia")}
                      className="text-primary hover:underline font-semibold flex items-center gap-1"
                    >
                      Mulai <ChevronRight size={14} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full px-4 py-8 space-y-6">
              {messages.map((message) => {
                const cleanContent = message.content
                  .replace(/<think>[\s\S]*?<\/think>/g, '')
                  .replace(/Thinking Process:[\s\S]*?(?=\n\n|\n[A-Z]|$)/gi, '')
                  .trim();

                if (message.role === "assistant" && cleanContent === "") {
                  return null;
                }

                return (
                  <div
                    key={message.id}
                    className={`flex gap-4 ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {message.role === "assistant" && (
                      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                        <MessageCircle
                          size={16}
                          className="text-primary-foreground"
                        />
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
                      <span
                        className={`text-xs mt-2 block ${
                          message.role === "user"
                            ? "text-primary-foreground/70"
                            : "text-muted-foreground"
                        }`}
                      >
                        {message.timestamp.toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>
                );
              })}
              
              {isLoading && messages[messages.length - 1]?.content === "" && (
                <div className="flex gap-4 justify-start animate-fade-in">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                    <MessageCircle
                      size={16}
                      className="text-primary-foreground animate-pulse"
                    />
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
            <form
              onSubmit={handleSendMessage}
              className="flex gap-3 items-center"
            >
              {/* Upload from chat input removed - use Admin Dashboard instead */}

              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={selectedClientId ? `Ketik pesan untuk ${activeClientName}...` : "Silakan pilih client terlebih dahulu..."}
                className="flex-1 px-4 py-3 rounded-lg bg-input border border-border text-foreground focus:outline-none focus:border-primary transition-colors disabled:opacity-50"
                disabled={isLoading || !selectedClientId}
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
                  disabled={!input.trim() || !selectedClientId}
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
