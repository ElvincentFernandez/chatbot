"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function WidgetChatInner() {
  const searchParams = useSearchParams();
  const apiKey = searchParams.get("api_key") || "";

  const [messages, setMessages] = useState<{ role: string; content: string }[]>([
    { role: "assistant", content: "Halo! Ada yang bisa saya bantu?" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !apiKey || isLoading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/widget/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, message: userMsg }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "Maaf, terjadi kesalahan." }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Gagal terhubung ke server." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-sm font-bold flex items-center gap-2 shadow-lg">
        <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
        AI Assistant
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-sm"
                  : "bg-slate-800 text-slate-200 border border-slate-700 rounded-bl-sm"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-800 border border-slate-700 px-4 py-3 rounded-2xl rounded-bl-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-800 bg-slate-900">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ketik pesan..."
            className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-xl text-sm font-semibold transition-colors"
          >
            Kirim
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WidgetPage() {
  return (
    <Suspense fallback={<div className="h-screen bg-slate-950 flex items-center justify-center"><span className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" /></div>}>
      <WidgetChatInner />
    </Suspense>
  );
}
