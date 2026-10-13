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
  const [selectedModel, setSelectedModel] = useState(activeThread?.model || 'gpt-5.6-sol')
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>(activeThread?.reasoningEffort || 'medium')
  const [permission, setPermission] = useState<PermissionProfile>(activeThread?.permissionProfile || 'workspace_write')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Load draft from localStorage when thread changes
  useEffect(() => {
    if (activeThread) {
      const savedDraft = localStorage.getItem(`draft_${activeThread.id}`) || ''
      setMessage(savedDraft)
      setSelectedModel(activeThread.model || 'gpt-5.6-sol')
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
    sendUserMessage(message.trim(), { model: selectedModel, reasoningEffort })
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
      <div className="p-2 sm:p-3 bg-slate-900 border-t border-slate-800 max-w-4xl mx-auto w-full">
        <div className="border border-slate-700/80 rounded-xl bg-slate-950/80 shadow-xs focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 transition-all">
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
            className="w-full resize-none bg-transparent p-2.5 sm:p-3 text-xs sm:text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none leading-relaxed"
          />

          {/* Bottom Toolbar & Action Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-2.5 py-2 sm:px-3 sm:py-2 border-t border-slate-800 bg-slate-900/60 rounded-b-xl gap-2">
            {/* Left Controls: Model, Reasoning, Permissions */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {/* Model Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="min-h-[44px] flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-slate-900 border border-slate-700 text-slate-200 hover:text-white hover:border-slate-500 transition-colors cursor-pointer"
                    aria-label="Select Model"
                  >
                    <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{selectedModel}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-52 text-xs bg-slate-900 border-slate-800 text-slate-200">
                  <DropdownMenuRadioGroup value={selectedModel} onValueChange={setSelectedModel}>
                    <DropdownMenuRadioItem value="gpt-5.6-sol">gpt-5.6-sol (Default)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="gpt-5.5">gpt-5.5 (Fast)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="gpt-5.6-terra">gpt-5.6-terra (Balanced)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="o3-mini">o3-mini (Reasoning)</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="gpt-4o">gpt-4o (API Tier)</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Reasoning Level Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="min-h-[44px] flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-slate-900 border border-slate-700 text-slate-200 hover:text-white hover:border-slate-500 transition-colors cursor-pointer"
                    aria-label="Select Reasoning Effort"
                  >
                    <Brain className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="capitalize">{reasoningEffort} effort</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-40 text-xs bg-slate-900 border-slate-800 text-slate-200">
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
                    className="min-h-[44px] flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-slate-900 border border-slate-700 text-slate-200 hover:text-white hover:border-slate-500 transition-colors cursor-pointer"
                    aria-label="Select Permissions"
                  >
                    <Shield className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="capitalize">{permission.replace('_', ' ')}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48 text-xs bg-slate-900 border-slate-800 text-slate-200">
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
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end flex-wrap sm:flex-nowrap">
              {state.isStreaming ? (
                <>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={stopActiveTurn}
                    className="min-h-[44px] px-3.5 text-xs gap-1.5 font-medium shadow-xs flex-1 sm:flex-initial"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    Stop Turn
                  </Button>

                  {message.trim() && (
                    <Button
                      size="sm"
                      variant="default"
                      onClick={handleSend}
                      className="min-h-[44px] px-3.5 text-xs gap-1.5 font-medium bg-[var(--accent)] text-[var(--accent-foreground)] flex-1 sm:flex-initial"
                    >
                      <Compass className="w-3.5 h-3.5" />
                      Steer Work
                    </Button>
                  )}
                </>
              ) : isThreadInterrupted ? (
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => sendUserMessage('Resume previous task and verify remaining checklist items.', { model: selectedModel, reasoningEffort })}
                    className="min-h-[44px] px-3 text-xs gap-1.5 font-medium text-[var(--accent)] flex-1 sm:flex-initial"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Resume
                  </Button>

                  <Button
                    size="sm"
                    variant="default"
                    onClick={handleSend}
                    disabled={!message.trim()}
                    className="min-h-[44px] px-4 text-xs gap-1.5 font-medium flex-1 sm:flex-initial"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Send
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleSend}
                  disabled={!message.trim()}
                  className="min-h-[44px] px-4 text-xs gap-1.5 font-medium w-full sm:w-auto justify-center"
                >
                  <Send className="w-3.5 h-3.5" />
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
