'use client'

import { Sidebar } from '@/components/sidebar'
import { MessageCircle, Zap, BookOpen, Database } from 'lucide-react'
import { useState } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Simulate bot response
    setTimeout(() => {
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          'This is a simulated response. Your chatbot with RAG, prompt caching, and SLM is ready to be integrated!',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, botMessage])
      setIsLoading(false)
    }, 1000)
  }

  const features = [
    {
      icon: Database,
      title: 'RAG Integration',
      description: 'Retrieve Augmented Generation for context-aware responses',
    },
    {
      icon: Zap,
      title: 'Prompt Caching',
      description: 'Optimized token usage and faster response times',
    },
    {
      icon: MessageCircle,
      title: 'SLM Powered',
      description: 'Efficient Small Language Models for thesis research',
    },
    {
      icon: BookOpen,
      title: 'Research Tools',
      description: 'Built-in documentation and knowledge management',
    },
  ]

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden pl-0 lg:pl-0">
        {/* Chat Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-4 py-8">
              {/* Empty State */}
              <div className="max-w-2xl w-full text-center">
                <div className="mb-8">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mx-auto mb-4">
                    <MessageCircle size={32} className="text-primary" />
                  </div>
                  <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2">
                    Welcome to RAGChat
                  </h1>
                  <p className="text-muted-foreground text-lg mb-8">
                    Your intelligent research assistant powered by RAG, prompt caching, and Small Language Models
                  </p>
                </div>

                {/* Feature Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                  {features.map((feature, idx) => {
                    const Icon = feature.icon
                    return (
                      <div
                        key={idx}
                        className="p-4 rounded-lg bg-card border border-border hover:border-primary/50 transition-colors"
                      >
                        <Icon size={24} className="text-primary mb-2 mx-auto" />
                        <h3 className="font-semibold text-foreground mb-1">
                          {feature.title}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {feature.description}
                        </p>
                      </div>
                    )
                  })}
                </div>

                {/* Prompt Suggestions */}
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground mb-3">
                    Try asking about:
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {[
                      'How does RAG work?',
                      'Prompt caching techniques',
                      'SLM vs LLM trade-offs',
                      'Research methodology',
                    ].map((suggestion, idx) => (
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
            <div className="max-w-4xl mx-auto w-full px-4 py-8 space-y-6 pt-16 lg:pt-8">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                      <MessageCircle size={16} className="text-primary-foreground" />
                    </div>
                  )}
                  <div
                    className={`max-w-xs md:max-w-2xl px-4 py-3 rounded-lg ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-br-none'
                        : 'bg-card text-foreground border border-border rounded-bl-none'
                    }`}
                  >
                    <p className="text-sm md:text-base leading-relaxed">{message.content}</p>
                    <span
                      className={`text-xs mt-2 block ${
                        message.role === 'user'
                          ? 'text-primary-foreground/70'
                          : 'text-muted-foreground'
                      }`}
                    >
                      {message.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-4 justify-start">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                    <MessageCircle size={16} className="text-primary-foreground animate-pulse" />
                  </div>
                  <div className="bg-card border border-border rounded-lg rounded-bl-none px-4 py-3">
                    <div className="flex gap-2">
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-border bg-background/80 backdrop-blur-sm">
          <div className="max-w-4xl mx-auto w-full p-4">
            <form onSubmit={handleSendMessage} className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me about RAG, prompt caching, or SLM..."
                className="flex-1 px-4 py-3 rounded-lg bg-input border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:bg-muted disabled:cursor-not-allowed transition-colors font-medium"
              >
                Send
              </button>
            </form>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              This is a thesis project combining RAG, prompt caching, and Small Language Models
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
