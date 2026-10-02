"use client";

import { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Home,
  Send,
  X,
  ArrowLeft,
  ChevronRight,
  User,
  Mail,
  Phone,
  HelpCircle,
  ShieldCheck,
  Bot,
  RotateCcw
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface ChatSession {
  id: string;
  name: string;
  email: string;
  phone: string;
  question: string;
  date: string;
  messages: Message[];
}

export default function EmbeddedWidgetPage() {
  // Widget Views: "form" (Formulir), "chat" (Canvas Obrolan), "history" (Pesan Terbaru)
  const [widgetView, setWidgetView] = useState<"form" | "chat" | "history">("form");
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [clientName, setClientName] = useState("RAGChat");

  // Form states
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");

  // Session history list
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (widgetView === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeSession?.messages, widgetView]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const key = params.get("api_key") || "";
      setApiKey(key);

      if (key) {
        fetch(`http://localhost:8000/api/widget/info?api_key=${encodeURIComponent(key)}`)
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data && data.name) setClientName(data.name);
          })
          .catch(() => {});
      }
    }
  }, []);

  const handleClose = () => {
    if (typeof window !== "undefined" && window.parent) {
      window.parent.postMessage({ type: "CLOSE_RAGCHAT_WIDGET" }, "*");
    }
  };

  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !question.trim()) return;

    setIsLoading(true);
    const newSessionId = `SEC-${Math.floor(1000 + Math.random() * 9000)}`;
    const timeString = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    const dateString = new Date().toLocaleDateString("id-ID", { day: "2-digit", month: "2-digit", year: "numeric" });

    const newSession: ChatSession = {
      id: newSessionId,
      name: name.trim(),
      email: email.trim(),
      phone: phone.trim(),
      question: question.trim(),
      date: dateString,
      messages: [
        {
          role: "user",
          content: question.trim(),
          timestamp: timeString
        }
      ]
    };

    setActiveSession(newSession);
    setWidgetView("chat");

    // Clear form fields
    setName("");
    setEmail("");
    setPhone("");
    setQuestion("");

    try {
      let responseText = "Terima kasih telah menghubungi kami. Pertanyaan Anda sedang kami proses.";

      const res = await fetch("http://localhost:8000/api/widget/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-KEY": apiKey.trim()
        },
        body: JSON.stringify({
          message: question.trim(),
          session_id: newSessionId,
          document: null,
          general_mode: false
        })
      });

      if (res.ok) {
        const chatData = await res.json();
        responseText = chatData.response;
      } else {
        const err = await res.json();
        responseText = `Error API Widget: ${err.detail || "Gagal memproses query RAG."}`;
      }

      setTimeout(() => {
        newSession.messages.push({
          role: "assistant",
          content: responseText,
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        });
        setActiveSession({ ...newSession });
        setSessions(prev => [newSession, ...prev]);
        setIsLoading(false);
      }, 1500);

    } catch {
      setTimeout(() => {
        newSession.messages.push({
          role: "assistant",
          content: "Tidak dapat terhubung ke server RAG. Pastikan backend berjalan.",
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        });
        setActiveSession({ ...newSession });
        setSessions(prev => [newSession, ...prev]);
        setIsLoading(false);
      }, 1000);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeSession || isLoading) return;

    const userMsg = chatInput.trim();
    setChatInput("");
    setIsLoading(true);

    const timeString = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });

    const updatedMessages = [
      ...activeSession.messages,
      { role: "user" as const, content: userMsg, timestamp: timeString }
    ];

    const updatedSession = { ...activeSession, messages: updatedMessages };
    setActiveSession(updatedSession);

    try {
      let responseText = "Gagal memproses query RAG.";

      const res = await fetch("http://localhost:8000/api/widget/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-KEY": apiKey.trim()
        },
        body: JSON.stringify({
          message: userMsg,
          session_id: activeSession.id,
          document: null,
          general_mode: false
        })
      });

      if (res.ok) {
        const chatData = await res.json();
        responseText = chatData.response;
      } else {
        const err = await res.json();
        responseText = `Error API Widget: ${err.detail || "Gagal memproses query RAG."}`;
      }

      const timeStringAss = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
      const finalSession = {
        ...updatedSession,
        messages: [
          ...updatedMessages,
          { role: "assistant" as const, content: responseText, timestamp: timeStringAss }
        ]
      };

      setActiveSession(finalSession);
      setSessions(prev => prev.map(s => s.id === activeSession.id ? finalSession : s));
    } catch {
      console.error("Koneksi ke backend terputus.");
    } finally {
      setIsLoading(false);
    }
  };

  const selectHistorySession = (session: ChatSession) => {
    setActiveSession(session);
    setWidgetView("chat");
  };

  return (
    <div className="w-full h-screen bg-slate-900 text-slate-100 flex flex-col justify-between overflow-hidden font-sans">

      {/* Header — sama persis dengan /livechat widget header */}
      <div className="p-4 border-b border-slate-800/80 flex items-center justify-between bg-slate-950/40 shrink-0">
        <div>
          <h2 className="text-xs font-bold text-slate-100">
            Welcome to RAGChat
          </h2>
          <p className="text-[10px] text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {clientName} • Online
          </p>
        </div>
        <div className="flex items-center gap-1">
          {widgetView === "chat" && (
            <button
              onClick={() => {
                setActiveSession(null);
                setWidgetView("form");
              }}
              title="Mulai obrolan baru"
              className="text-slate-500 hover:text-slate-300 p-1 hover:bg-slate-800 rounded transition-colors"
            >
              <RotateCcw size={13} />
            </button>
          )}
          <button
            onClick={handleClose}
            className="text-slate-500 hover:text-slate-350 p-1 hover:bg-slate-800 rounded transition-colors"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Widget Dynamic Screen Views */}
      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">

        {widgetView === "form" && (
          /* VIEW 1: Form / Context Panel */
          <form onSubmit={handleSubmitForm} className="space-y-3.5">
            <div>
              <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <User className="w-2.5 h-2.5" /> Nama
              </label>
              <input
                type="text"
                required
                placeholder="Masukkan nama lengkap"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-850 rounded-xl text-slate-200 focus:outline-none focus:border-purple-500 text-xs placeholder-slate-700"
              />
            </div>

            <div>
              <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <Mail className="w-2.5 h-2.5" /> Email
              </label>
              <input
                type="email"
                required
                placeholder="Masukkan alamat email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-850 rounded-xl text-slate-200 focus:outline-none focus:border-purple-500 text-xs placeholder-slate-700"
              />
            </div>

            <div>
              <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <Phone className="w-2.5 h-2.5" /> Nomor handphone
              </label>
              <input
                type="tel"
                placeholder="Masukkan nomor handphone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-850 rounded-xl text-slate-200 focus:outline-none focus:border-purple-500 text-xs placeholder-slate-700"
              />
            </div>

            <div>
              <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <HelpCircle className="w-2.5 h-2.5" /> Pertanyaan (Question)
              </label>
              <textarea
                required
                rows={3}
                placeholder="Pesan..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-850 rounded-xl text-slate-200 focus:outline-none focus:border-purple-500 text-xs placeholder-slate-700 resize-none font-sans"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors flex items-center justify-center gap-1.5 shadow-lg shadow-purple-600/20 disabled:opacity-60"
            >
              {isLoading ? "Memproses..." : "Submit to RAG System"}
              <Send className="w-3 h-3" />
            </button>
          </form>
        )}

        {widgetView === "chat" && activeSession && (
          /* VIEW 2: Chat History Canvas */
          <div className="h-full flex flex-col justify-between space-y-4">
            {/* Active Session Label */}
            <div className="border-b border-slate-800 pb-2 mb-2 flex items-center justify-between">
              <div>
                <h3 className="text-[10px] font-bold text-slate-200 flex items-center gap-1">
                  <MessageSquare className="w-3 h-3 text-purple-400" />
                  Active Session: #{activeSession.id}
                </h3>
                <p className="text-[8px] text-slate-500">
                  End-to-End Encrypted RAG Retrieval
                </p>
              </div>
              <button
                onClick={() => {
                  setActiveSession(null);
                  setWidgetView("form");
                }}
                className="px-2 py-0.5 text-[8px] bg-slate-800 hover:bg-slate-700 text-slate-400 rounded transition-colors"
              >
                Batal
              </button>
            </div>

            {/* Messages Panel */}
            <div className="flex-1 space-y-3 overflow-y-auto pr-1">
              {activeSession.messages.map((m, idx) => (
                <div key={idx} className={`flex items-start gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
                  {m.role === "assistant" && (
                    <div className="w-6 h-6 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                      <Bot className="w-3 h-3 text-purple-400" />
                    </div>
                  )}
                  <div className={`max-w-[85%] rounded-xl p-3 text-[11px] leading-relaxed ${
                    m.role === "user"
                      ? "bg-slate-800 border border-slate-750 text-slate-200"
                      : "bg-purple-950/20 border border-purple-500/20 text-slate-350"
                  }`}>
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    <span className="block text-[8px] text-slate-500 mt-1 text-right">{m.timestamp}</span>
                  </div>
                  {m.role === "user" && (
                    <div className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                      <User className="w-3 h-3 text-slate-300" />
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                    <Bot className="w-3 h-3 text-purple-400" />
                  </div>
                  <div className="bg-purple-950/10 border border-purple-500/10 rounded-xl p-2.5 text-[11px] text-purple-300 flex items-center gap-1.5">
                    <span className="w-3 h-3 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                    <span>RAG System processing...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input */}
            <form onSubmit={handleSendChat} className="relative pt-2 border-t border-slate-800/60">
              <input
                type="text"
                placeholder="Tulis pesan..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isLoading}
                className="w-full pl-3 pr-10 py-2.5 bg-slate-950 border border-slate-850 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-purple-500 placeholder-slate-700"
              />
              <button
                type="submit"
                disabled={isLoading}
                className="absolute right-3 top-[18px] text-purple-400 hover:text-purple-300 disabled:opacity-40"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        )}

        {widgetView === "history" && (
          /* VIEW 3: Message History */
          <div className="space-y-3.5">
            <button
              onClick={() => setWidgetView("form")}
              className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition-colors mb-1"
            >
              <ArrowLeft className="w-3 h-3" />
              Pesan
            </button>

            <div className="space-y-2.5">
              <h3 className="text-[10px] font-bold text-slate-500 tracking-wide uppercase">Terbaru</h3>

              {sessions.length === 0 && (
                <p className="text-[11px] text-slate-600 text-center py-6">Belum ada riwayat percakapan.</p>
              )}

              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => selectHistorySession(s)}
                  className="w-full p-3.5 rounded-xl bg-slate-950 hover:bg-slate-850 border border-slate-850 hover:border-slate-750 transition-all cursor-pointer flex items-center justify-between group"
                >
                  <div className="space-y-0.5 truncate flex-1 mr-2 text-left">
                    <span className="text-xs font-bold text-slate-200 group-hover:text-purple-400 transition-colors">
                      {s.name}
                    </span>
                    <p className="text-[10px] text-slate-500 truncate">
                      {s.question}
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5 text-slate-500 shrink-0">
                    <span className="text-[9px]">{s.date}</span>
                    <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* Footer Navigation Tabs — sama persis dengan /livechat */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40 space-y-2.5 shrink-0">
        <div className="flex items-center justify-around bg-purple-500/5 border border-purple-500/10 rounded-xl p-1">
          <button
            onClick={() => setWidgetView("form")}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center text-xs transition-all ${
              widgetView === "form" || widgetView === "chat" ? "bg-purple-600/90 text-white shadow" : "text-purple-400 hover:text-purple-300"
            }`}
          >
            <Home className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setWidgetView("history")}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center text-xs transition-all ${
              widgetView === "history" ? "bg-purple-600/90 text-white shadow" : "text-purple-400 hover:text-purple-300"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="text-center">
          <span className="text-[8px] uppercase tracking-wider text-slate-500 font-bold flex items-center justify-center gap-1">
            <ShieldCheck className="w-3 h-3 text-purple-500/60" />
            End-to-End Encrypted
          </span>
        </div>
      </div>

    </div>
  );
}
