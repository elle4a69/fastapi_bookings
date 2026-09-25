import React, { useState, useEffect, useRef } from 'react'
import { 
  Send, 
  Square, 
  Play, 
  Cpu, 
  Shield, 
  Brain, 
  Compass 
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import type { ReasoningEffort, PermissionProfile } from '../../types/workbench'
import { Button } from '../ui/button'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuRadioGroup, 
  DropdownMenuRadioItem, 
  DropdownMenuTrigger 
} from '../ui/dropdown-menu'
import { TooltipProvider } from '../ui/tooltip'

export const Composer: React.FC = () => {
  const { 
    activeThread, 
    sendUserMessage, 
    stopActiveTurn,
    steerActiveTurn,
    state 
  } = useWorkbenchStore()

  const [message, setMessage] = useState('')
  const [selectedModel, setSelectedModel] = useState(activeThread?.model || 'gpt-4o')
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>(activeThread?.reasoningEffort || 'medium')
  const [permission, setPermission] = useState<PermissionProfile>(activeThread?.permissionProfile || 'workspace_write')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Load draft from localStorage when thread changes
  useEffect(() => {
    if (activeThread) {
      const savedDraft = localStorage.getItem(`draft_${activeThread.id}`) || ''
      setMessage(savedDraft)
      setSelectedModel(activeThread.model || 'gpt-4o')
      setReasoningEffort(activeThread.reasoningEffort || 'medium')
      setPermission(activeThread.permissionProfile || 'workspace_write')
    }
  }, [activeThread?.id])

  // Save draft to localStorage as user types
  const handleMessageChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setMessage(val)
    if (activeThread) {
      if (val.trim()) {
        localStorage.setItem(`draft_${activeThread.id}`, val)
      } else {
        localStorage.removeItem(`draft_${activeThread.id}`)
      }
    }
  }

  const handleSteer = () => {
    if (!message.trim()) return
    steerActiveTurn(message.trim())
    setMessage('')
    if (activeThread) {
      localStorage.removeItem(`draft_${activeThread.id}`)
    }
  }

  const handleSend = () => {
    if (!message.trim()) return
    if (state.isStreaming) {
      handleSteer()
      return
    }
    sendUserMessage(message.trim())
    setMessage('')
    if (activeThread) {
      localStorage.removeItem(`draft_${activeThread.id}`)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    }
  }

  const isThreadInterrupted = activeThread?.status === 'interrupted' || activeThread?.status === 'failed'

  return (
    <TooltipProvider delayDuration={150}>
      <div className="p-3 bg-[var(--surface-primary)] border-t border-[var(--border)] max-w-4xl mx-auto w-full">
        <div className="border border-[var(--border)] rounded-xl bg-[var(--surface-primary)] shadow-xs focus-within:border-[var(--accent)] focus-within:ring-1 focus-within:ring-[var(--accent)] transition-all">
          {/* Main Textarea */}
          <textarea
            id="composer-message-input"
            aria-label="Message prompt or instruction for Codex"
            ref={textareaRef}
            value={message}
            onChange={handleMessageChange}
            onKeyDown={handleKeyDown}
            placeholder={
              state.isStreaming
                ? 'Codex is executing tasks... type here to add follow-up guidance or steer.'
                : 'Give instruction to Codex... (Cmd+Enter to send, Shift+Enter for new line)'
            }
            rows={2}
            className="w-full resize-none bg-transparent p-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-subtle)] focus:outline-none leading-relaxed"
          />

          {/* Bottom Toolbar & Action Bar */}
          <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--border)]/60 bg-[var(--surface-secondary)]/30 rounded-b-xl gap-2">
            {/* Left Controls: Model, Reasoning, Permissions */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {/* Model Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-[var(--surface-primary)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-strong)] transition-colors cursor-pointer"
                    aria-label="Select Model"
                  >
                    <Cpu className="w-3 h-3 text-[var(--accent)]" />
                    <span>{selectedModel}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48 text-xs">
                  <DropdownMenuRadioGroup value={selectedModel} onValueChange={setSelectedModel}>
                    <DropdownMenuRadioItem value="gpt-4o">gpt-4o (Default)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="o3-mini">o3-mini (Reasoning)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="o1">o1 (Deep Synthesis)</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Reasoning Level Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-[var(--surface-primary)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-strong)] transition-colors cursor-pointer"
                    aria-label="Select Reasoning Effort"
                  >
                    <Brain className="w-3 h-3 text-[var(--accent)]" />
                    <span className="capitalize">{reasoningEffort} effort</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-40 text-xs">
                  <DropdownMenuRadioGroup
                    value={reasoningEffort}
                    onValueChange={(val) => setReasoningEffort(val as ReasoningEffort)}
                  >
                    <DropdownMenuRadioItem value="low">Low Effort</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="medium">Medium Effort</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="high">High Effort</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Permission Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="hidden sm:flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-[var(--surface-primary)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-strong)] transition-colors cursor-pointer"
                    aria-label="Select Permissions"
                  >
                    <Shield className="w-3 h-3 text-[var(--accent)]" />
                    <span className="capitalize">{permission.replace('_', ' ')}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48 text-xs">
                  <DropdownMenuRadioGroup
                    value={permission}
                    onValueChange={(val) => setPermission(val as PermissionProfile)}
                  >
                    <DropdownMenuRadioItem value="workspace_write">Workspace Write</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="read_only">Read Only</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="managed">Managed Profile</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Right Action: Morphing Button (Send / Stop / Resume / Steer) */}
            <div className="flex items-center gap-2">
              {state.isStreaming ? (
                <>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={stopActiveTurn}
                    className="h-7 px-3 text-xs gap-1 font-medium shadow-xs"
                  >
                    <Square className="w-3 h-3 fill-current" />
                    Stop Turn
                  </Button>

                  {message.trim() && (
                    <Button
                      size="sm"
                      variant="default"
                      onClick={handleSend}
                      className="h-7 px-3 text-xs gap-1 font-medium bg-[var(--accent)] text-[var(--accent-foreground)]"
                    >
                      <Compass className="w-3 h-3" />
                      Steer Work
                    </Button>
                  )}
                </>
              ) : isThreadInterrupted ? (
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => sendUserMessage('Resume previous task and verify remaining checklist items.')}
                    className="h-7 px-3 text-xs gap-1 font-medium text-[var(--accent)]"
                  >
                    <Play className="w-3 h-3 fill-current" />
                    Resume
                  </Button>

                  <Button
                    size="sm"
                    variant="default"
                    onClick={handleSend}
                    disabled={!message.trim()}
                    className="h-7 px-3 text-xs gap-1 font-medium"
                  >
                    <Send className="w-3 h-3" />
                    Send
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleSend}
                  disabled={!message.trim()}
                  className="h-7 px-3 text-xs gap-1 font-medium"
                >
                  <Send className="w-3 h-3" />
                  <span>Send</span>
                  <kbd className="hidden sm:inline text-[9px] font-mono opacity-70 bg-black/20 px-1 py-0.5 rounded ml-0.5">
                    ⌘↵
                  </kbd>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}
