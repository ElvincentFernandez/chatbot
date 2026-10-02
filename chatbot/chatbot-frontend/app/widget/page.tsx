"use client";

import { useState, useEffect, useRef } from "react";
import { 
  MessageSquare, 
  Send, 
  X, 
  User, 
  Mail, 
  ShieldCheck,
  Bot,
  RotateCcw
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export default function EmbeddedWidgetPage() {
  const [apiKey, setApiKey] = useState("");
  const [clientName, setClientName] = useState("AI Assistant");
  const [view, setView] = useState<"form" | "chat">("form");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const key = params.get("api_key") || "";
      setApiKey(key);

      if (key) {
        fetch(`http://localhost:8000/api/widget/info?api_key=${encodeURIComponent(key)}`)
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data && data.name) {
              setClientName(data.name);
            }
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

  const handleStartChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !question.trim()) return;

    const newSessionId = `WIDGET-${Date.now()}`;
    setSessionId(newSessionId);

    const timeString = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    const initialUserMsg: Message = {
      role: "user",
      content: question.trim(),
      timestamp: timeString
    };

    setMessages([initialUserMsg]);
    setView("chat");
    setIsLoading(true);

    try {
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

      let responseText = "Maaf, terjadi kendala saat memproses jawaban.";
      if (res.ok) {
        const data = await res.json();
        responseText = data.response;
      } else {
        const err = await res.json();
        responseText = `Gagal: ${err.detail || "Terjadi kesalahan pada server."}`;
      }

      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: responseText,
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Tidak dapat terhubung ke server RAG. Pastikan server backend berjalan.",
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isLoading) return;

    const userText = chatInput.trim();
    setChatInput("");

    const timeString = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [
      ...prev,
      { role: "user", content: userText, timestamp: timeString }
    ]);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/widget/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-KEY": apiKey.trim()
        },
        body: JSON.stringify({
          message: userText,
          session_id: sessionId,
          document: null,
          general_mode: false
        })
      });

      let responseText = "Maaf, terjadi kendala.";
      if (res.ok) {
        const data = await res.json();
        responseText = data.response;
      } else {
        const err = await res.json();
        responseText = `Gagal: ${err.detail || "Terjadi kesalahan."}`;
      }

      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: responseText,
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Koneksi ke backend terputus.",
          timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full h-screen bg-slate-900 text-slate-100 flex flex-col justify-between overflow-hidden font-sans border border-slate-800">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md flex items-center justify-between shrink-0 shadow-md">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white shadow-sm">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-slate-100 line-clamp-1">
              {clientName}
            </h2>
            <p className="text-[10px] text-emerald-400 flex items-center gap-1 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Online • RAG Knowledge
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {view === "chat" && (
            <button
              onClick={() => {
                setView("form");
                setMessages([]);
              }}
              title="Mulai obrolan baru"
              className="text-slate-400 hover:text-slate-200 p-1.5 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <RotateCcw size={14} />
            </button>
          )}
          <button 
            onClick={handleClose}
            title="Tutup obrolan"
            className="text-slate-400 hover:text-slate-200 p-1.5 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
        {view === "form" ? (
          <form onSubmit={handleStartChat} className="space-y-3.5 pt-1">
            <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-[11px] text-indigo-300">
              👋 Halo! Silakan isi pertanyaan Anda untuk mendapatkan jawaban langsung dari basis pengetahuan kami.
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <User className="w-3 h-3 text-indigo-400" /> Nama Anda
              </label>
              <input
                type="text"
                required
                placeholder="Misal: Andi"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-indigo-500 text-xs placeholder-slate-600 transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Mail className="w-3 h-3 text-indigo-400" /> Email (Opsional)
              </label>
              <input
                type="email"
                placeholder="nama@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-indigo-500 text-xs placeholder-slate-600 transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <MessageSquare className="w-3 h-3 text-indigo-400" /> Pertanyaan
              </label>
              <textarea
                required
                rows={3}
                placeholder="Tuliskan hal yang ingin ditanyakan..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-indigo-500 text-xs placeholder-slate-600 resize-none transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white font-bold text-xs transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-indigo-500/20 active:scale-98"
            >
              {isLoading ? "Menghubungkan..." : "Mulai Obrolan"}
              <Send className="w-3 h-3" />
            </button>
          </form>
        ) : (
          <div className="space-y-3">
            {messages.map((m, idx) => (
              <div key={idx} className={`flex items-start gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
                {m.role === "assistant" && (
                  <div className="w-6 h-6 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                    <Bot className="w-3 h-3 text-purple-400" />
                  </div>
                )}
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[11px] leading-relaxed shadow-sm ${
                  m.role === "user" 
                    ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white" 
                    : "bg-slate-950 border border-slate-800/80 text-slate-300"
                }`}>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  <span className="block text-[8px] text-slate-400/80 mt-1 text-right">
                    {m.timestamp}
                  </span>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-start gap-2">
                <div className="w-6 h-6 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                  <Bot className="w-3 h-3 text-purple-400" />
                </div>
                <div className="bg-slate-950 border border-slate-800/80 rounded-2xl px-3 py-2 text-[11px] text-indigo-300 flex items-center gap-2 shadow-sm">
                  <span className="w-3 h-3 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                  <span>Menganalisis dokumen RAG...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Footer / Input (Chat View only) */}
      {view === "chat" ? (
        <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-800 bg-slate-950/80 flex items-center gap-2 shrink-0">
          <input 
            type="text" 
            placeholder="Ketik pesan..." 
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            disabled={isLoading}
            className="flex-1 px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500 placeholder-slate-600 transition-colors"
          />
          <button 
            type="submit" 
            disabled={isLoading || !chatInput.trim()}
            className="p-2 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white rounded-xl disabled:opacity-40 transition-all shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      ) : (
        <div className="p-2 border-t border-slate-800/60 text-center shrink-0">
          <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold flex items-center justify-center gap-1">
            <ShieldCheck className="w-3 h-3 text-indigo-400" />
            Powered by RAG Local Provider
          </span>
        </div>
      )}
    </div>
  );
}
