'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Menu, X, Plus, MessageSquare, History, Settings, BookOpen, LogOut } from 'lucide-react'

interface ChatSession {
  id: string
  title: string
  timestamp: Date
}

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(true)
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([
    {
      id: '1',
      title: 'RAG Implementation Overview',
      timestamp: new Date(Date.now() - 3600000),
    },
    {
      id: '2',
      title: 'Prompt Caching Strategies',
      timestamp: new Date(Date.now() - 7200000),
    },
    {
      id: '3',
      title: 'SLM Optimization Techniques',
      timestamp: new Date(Date.now() - 86400000),
    },
  ])

  const formatTime = (date: Date) => {
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
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <MessageSquare size={20} className="text-primary-foreground" />
            </div>
            <span className="font-semibold text-sidebar-foreground group-hover:text-primary transition-colors">
              RAGChat
            </span>
          </Link>
          <p className="text-xs text-sidebar-foreground/60 mt-2">Thesis Research Tool</p>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium">
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
                <Link
                  key={session.id}
                  href={`/chat/${session.id}`}
                  className="block p-3 rounded-lg bg-sidebar-accent/50 hover:bg-sidebar-accent transition-colors group"
                >
                  <p className="text-sm text-sidebar-foreground truncate group-hover:text-primary transition-colors">
                    {session.title}
                  </p>
                  <p className="text-xs text-sidebar-foreground/50 mt-1">
                    {formatTime(session.timestamp)}
                  </p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <History size={32} className="mx-auto text-sidebar-foreground/30 mb-2" />
              <p className="text-xs text-sidebar-foreground/50">No chat history yet</p>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="border-t border-sidebar-border p-4 space-y-2">
          <Link
            href="/documentation"
            className="flex items-center gap-3 px-4 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <BookOpen size={18} />
            <span className="text-sm">Documentation</span>
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-3 px-4 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <Settings size={18} />
            <span className="text-sm">Settings</span>
          </Link>
          <button className="w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors">
            <LogOut size={18} />
            <span className="text-sm">Logout</span>
          </button>
        </div>
      </aside>
    </>
  )
}
