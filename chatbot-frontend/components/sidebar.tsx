'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Menu, X, Plus, MessageSquare, History, LogOut, LayoutDashboard, Trash2 } from 'lucide-react'

interface ChatSession {
  id: string
  title: string
  created_at: string
}

interface SidebarProps {
  currentSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
}

export function Sidebar({ currentSessionId, onSelectSession, onNewChat }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true)
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [role, setRole] = useState<string | null>(null)
  const router = useRouter()

  const fetchSessions = async () => {
    const token = localStorage.getItem("token")
    if (!token) return

    try {
      const res = await fetch("http://localhost:8000/api/chat/sessions", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      })
      if (res.ok) {
        const data = await res.json()
        setChatSessions(data)
      }
    } catch (err) {
      console.error("Gagal mengambil riwayat chat:", err)
    }
  }

  useEffect(() => {
    fetchSessions()
    setRole(localStorage.getItem("role"))
    
    // Poll or sync sessions when custom event triggers
    const handleSync = () => {
      fetchSessions()
    }
    window.addEventListener('sync-sessions', handleSync)
    return () => window.removeEventListener('sync-sessions', handleSync)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("username")
    localStorage.removeItem("role")
    router.push("/login")
  }

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    const token = localStorage.getItem("token")
    if (!token) return

    if (confirm("Apakah Anda yakin ingin menghapus sesi chat ini?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/chat/sessions/${id}`, {
          method: "DELETE",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        })
        if (res.ok) {
          fetchSessions()
          if (currentSessionId === id) {
            onNewChat()
          }
        }
      } catch (err) {
        console.error("Gagal menghapus sesi chat:", err)
      }
    }
  }

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)
      const diffDays = Math.floor(diffMs / 86400000)

      if (diffMins < 1) return 'just now'
      if (diffMins < 60) return `${diffMins}m ago`
      if (diffHours < 24) return `${diffHours}h ago`
      if (diffDays < 7) return `${diffDays}d ago`
      return date.toLocaleDateString()
    } catch (e) {
      return ''
    }
  }

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg bg-sidebar-accent hover:bg-sidebar-accent/80 transition-colors"
        aria-label="Toggle menu"
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 lg:hidden z-40"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen bg-sidebar border-r border-sidebar-border transition-transform duration-300 flex flex-col z-40 lg:z-auto lg:relative lg:translate-x-0 ${
          isOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64'
        }`}
      >
        {/* Header */}
        <div className="p-6 border-b border-sidebar-border">
          <div onClick={() => router.push("/")} className="flex items-center gap-2 group cursor-pointer">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <MessageSquare size={20} className="text-primary-foreground" />
            </div>
            <span className="font-semibold text-sidebar-foreground group-hover:text-primary transition-colors">
              RAGChat
            </span>
          </div>
          <p className="text-xs text-sidebar-foreground/60 mt-2">
            Thesis Research Tool
          </p>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button 
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium"
          >
            <Plus size={18} />
            New Chat
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
          <p className="text-xs font-semibold text-sidebar-foreground/50 uppercase tracking-wider px-2 mb-3">
            Chat History
          </p>

          {chatSessions.length > 0 ? (
            <div className="space-y-2">
              {chatSessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => onSelectSession(session.id)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors group ${
                    currentSessionId === session.id 
                      ? 'bg-primary/20 border border-primary/30' 
                      : 'bg-sidebar-accent/50 hover:bg-sidebar-accent'
                  }`}
                >
                  <div className="truncate flex-1">
                    {session.client_name && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/10 font-bold inline-block mb-1">
                        {session.client_name}
                      </span>
                    )}
                    <p className={`text-sm truncate transition-colors ${
                      currentSessionId === session.id ? 'text-primary font-medium' : 'text-sidebar-foreground group-hover:text-primary'
                    }`}>
                      {session.title}
                    </p>
                    <p className="text-xs text-sidebar-foreground/50 mt-1">
                      {formatTime(session.created_at)}
                    </p>
                  </div>
                  <button 
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="p-1 rounded text-sidebar-foreground/30 hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all ml-2"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <History
                size={32}
                className="mx-auto text-sidebar-foreground/30 mb-2"
              />
              <p className="text-xs text-sidebar-foreground/50">
                No chat history yet
              </p>
            </div>
          )}
        </div>

        {/* Navigation for Admin/Superadmin */}
        {(role === 'admin' || role === 'superadmin') && (
          <div className="px-4 py-2 border-t border-sidebar-border">
            <Link 
              href="/admin" 
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sidebar-foreground bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 transition-all"
            >
              <LayoutDashboard size={18} className="text-purple-400" />
              <span className="text-sm font-semibold text-purple-300">Admin Dashboard</span>
            </Link>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-sidebar-border p-4">
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <LogOut size={18} />
            <span className="text-sm">Logout</span>
          </button>
        </div>
      </aside>
    </>
  )
}