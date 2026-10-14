import { useCallback, useEffect, useState } from 'react'
import type { ReasoningEffort } from './types/workbench'

export const CODEX_MODEL_STORAGE_KEY = 'codex_last_used_model'
export const CODEX_MODEL_CHANGE_EVENT = 'codex:model-change'
export const DEFAULT_CODEX_MODEL = 'gpt-6.1-sol'

export interface CodexModelOption {
  id: string
  label: string
  description: string
  defaultReasoningEffort: ReasoningEffort
  supportedReasoningEfforts: ReasoningEffort[]
}

const FULL_REASONING: ReasoningEffort[] = ['low', 'medium', 'high', 'xhigh', 'max', 'ultra']
const LUNA_REASONING: ReasoningEffort[] = ['low', 'medium', 'high', 'xhigh', 'max']

export const CODEX_MODELS: CodexModelOption[] = [
  {
    id: 'gpt-6.1-sol',
    label: 'GPT-6.1 Sol',
    description: 'Latest workhorse model for coding and everyday work.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: FULL_REASONING,
  },
  {
    id: 'gpt-6-astra',
    label: 'GPT-6 Astra',
    description: 'Frontier intelligence for the most demanding work.',
    defaultReasoningEffort: 'high',
    supportedReasoningEfforts: FULL_REASONING,
  },
  {
    id: 'gpt-6-sol',
    label: 'GPT-6 Sol',
    description: 'Previous-generation workhorse model.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: FULL_REASONING,
  },
  {
    id: 'gpt-6-luna',
    label: 'GPT-6 Luna',
    description: 'Fast and affordable model for easier tasks.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: LUNA_REASONING,
  },
  {
    id: 'gpt-5.6-sol',
    label: 'GPT-5.6 Sol',
    description: 'Older-generation workhorse model.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: FULL_REASONING,
  },
  {
    id: 'gpt-5.6-terra',
    label: 'GPT-5.6 Terra',
    description: 'Older balanced model for straightforward work.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: FULL_REASONING,
  },
  {
    id: 'gpt-5.6-luna',
    label: 'GPT-5.6 Luna',
    description: 'Older fast and efficient model.',
    defaultReasoningEffort: 'medium',
    supportedReasoningEfforts: LUNA_REASONING,
  },
]

const CODEX_MODEL_IDS = new Set(CODEX_MODELS.map(model => model.id))

export function resolveCodexModel(model: string | null | undefined): string {
  return model && CODEX_MODEL_IDS.has(model) ? model : DEFAULT_CODEX_MODEL
}

export function getLastUsedCodexModel(): string {
  try {
    if (typeof localStorage !== 'undefined') {
      return resolveCodexModel(localStorage.getItem(CODEX_MODEL_STORAGE_KEY))
    }
  } catch {
    // Browser privacy settings can deny storage access.
  }
  return DEFAULT_CODEX_MODEL
}

export function setLastUsedCodexModel(model: string): string {
  const resolved = resolveCodexModel(model)
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(CODEX_MODEL_STORAGE_KEY, resolved)
    }
  } catch {
    // Keep the in-memory selection usable when storage is unavailable.
  }
  try {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent<string>(CODEX_MODEL_CHANGE_EVENT, { detail: resolved }))
    }
  } catch {
    // The calling selector still updates even when custom events are unavailable.
  }
  return resolved
}

export function getCodexModelOption(model: string): CodexModelOption {
  return CODEX_MODELS.find(option => option.id === resolveCodexModel(model)) ?? CODEX_MODELS[0]
}

export function useCodexModelPreference(): [string, (model: string) => void] {
  const [model, setModel] = useState(getLastUsedCodexModel)

  useEffect(() => {
    const syncFromStorage = () => setModel(getLastUsedCodexModel())
    const syncFromSelection = (event: Event) => {
      setModel(resolveCodexModel((event as CustomEvent<string>).detail))
    }

    window.addEventListener('storage', syncFromStorage)
    window.addEventListener(CODEX_MODEL_CHANGE_EVENT, syncFromSelection)
    return () => {
      window.removeEventListener('storage', syncFromStorage)
      window.removeEventListener(CODEX_MODEL_CHANGE_EVENT, syncFromSelection)
    }
  }, [])

  const selectModel = useCallback((nextModel: string) => {
    setModel(setLastUsedCodexModel(nextModel))
  }, [])

  return [model, selectModel]
}
