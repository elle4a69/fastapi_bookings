import React, { useState, useRef, useEffect } from 'react'
import {
  ArrowUp,
  Paperclip,
  Mic,
  Radio,
  Square
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { VoiceState } from '../../types'

export interface ComposerBarProps {
  onSendMessage: (message: string) => void
  onStopStreaming?: () => void
  isStreaming?: boolean
  disabled?: boolean
  placeholder?: string
  voiceState?: VoiceState
  onToggleVoice?: () => void
  onAttach?: () => void
  className?: string
}

export const ComposerBar: React.FC<ComposerBarProps> = ({
  onSendMessage,
  onStopStreaming,
  isStreaming = false,
  disabled = false,
  placeholder = 'Ask Codex, steer execution, or assign a goal...',
  voiceState = 'idle',
  onToggleVoice,
  onAttach,
  className,
}) => {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollHeight = textareaRef.current.scrollHeight
      textareaRef.current.style.height = `${Math.min(Math.max(scrollHeight, 40), 160)}px`
    }
  }, [input])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled || isStreaming) return
    onSendMessage(trimmed)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '40px'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const renderVoiceIndicator = () => {
    switch (voiceState) {
      case 'listening':
        return (
          <button
            type="button"
            onClick={onToggleVoice}
            title="Listening... tap to mute"
            className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 active:scale-95 transition-all cursor-pointer"
          >
            <span className="absolute inset-0 rounded-xl bg-rose-500/20 animate-ping opacity-75" />
            <Radio className="w-4 h-4 animate-pulse relative z-10" />
          </button>
        )
      case 'thinking':
        return (
          <button
            type="button"
            onClick={onToggleVoice}
            title="Transcribing audio..."
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 active:scale-95 transition-all cursor-pointer"
          >
            <Mic className="w-4 h-4 animate-bounce" />
          </button>
        )
      case 'speaking':
        return (
          <button
            type="button"
            onClick={onToggleVoice}
            title="Codex is speaking"
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-500/10 text-violet-500 hover:bg-violet-500/20 active:scale-95 transition-all cursor-pointer"
          >
            <Radio className="w-4 h-4 animate-pulse" />
          </button>
        )
      case 'idle':
      default:
        return (
          <button
            type="button"
            onClick={onToggleVoice}
            title="Start voice session"
            className="flex items-center justify-center w-10 h-10 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/60 active:scale-95 transition-all cursor-pointer"
          >
            <Mic className="w-4 h-4" />
          </button>
        )
    }
  }

  return (
    <div
      className={cn(
        'w-full bg-card/95 backdrop-blur-md border border-border/80 rounded-2xl shadow-lg p-2 transition-all',
        'focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10',
        className
      )}
    >
      <div className="flex items-end gap-1.5">
        {/* Attachment Button */}
        <button
          type="button"
          onClick={onAttach}
          title="Attach file or context"
          className="flex items-center justify-center w-10 h-10 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/60 active:scale-95 transition-all cursor-pointer shrink-0"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        {/* Text Input Area */}
        <div className="flex-1 min-w-0 py-1">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="w-full bg-transparent border-0 outline-hidden focus:outline-hidden ring-0 focus:ring-0 p-1.5 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground resize-none leading-relaxed min-h-[38px] max-h-40"
          />
        </div>

        {/* Voice Control */}
        <div className="shrink-0">{renderVoiceIndicator()}</div>

        {/* Send / Stop Streaming Button */}
        <div className="shrink-0">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStopStreaming}
              title="Stop generation"
              className="flex items-center justify-center w-10 h-10 rounded-xl bg-rose-500 text-white hover:bg-rose-600 active:scale-95 transition-all cursor-pointer shadow-xs"
            >
              <Square className="w-4 h-4 fill-white" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={disabled || !input.trim()}
              title="Send message"
              className={cn(
                'flex items-center justify-center w-10 h-10 rounded-xl transition-all cursor-pointer shadow-xs',
                input.trim() && !disabled
                  ? 'bg-primary text-primary-foreground hover:opacity-90 active:scale-95'
                  : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
              )}
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
export default ComposerBar
