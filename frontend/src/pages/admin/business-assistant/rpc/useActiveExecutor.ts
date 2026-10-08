import { useCallback, useEffect, useState } from 'react'
import {
  executorCoordinator,
  type ExecutorState,
} from './executor-coordinator.ts'

export interface UseActiveExecutorResult extends ExecutorState {
  claimExecutor: (token?: string, ttlMs?: number) => string
  releaseExecutor: (reason?: string) => void
  makeActive: (token?: string, ttlMs?: number) => string
  validateExecution: () => { allowed: boolean; reason?: string }
}

export function useActiveExecutor(): UseActiveExecutorResult {
  const [state, setState] = useState<ExecutorState>(() => executorCoordinator.getState())

  useEffect(() => {
    const unsubscribe = executorCoordinator.subscribe((nextState) => {
      setState(nextState)
    })

    // Re-check lease state when tab gains focus
    const handleFocus = () => {
      setState(executorCoordinator.getState())
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('focus', handleFocus)
    }

    return () => {
      unsubscribe()
      if (typeof window !== 'undefined') {
        window.removeEventListener('focus', handleFocus)
      }
    }
  }, [])

  const claimExecutor = useCallback((token?: string, ttlMs?: number) => {
    return executorCoordinator.claimActiveExecutor(token, ttlMs)
  }, [])

  const releaseExecutor = useCallback((reason?: string) => {
    executorCoordinator.releaseActiveExecutor(reason)
  }, [])

  const makeActive = useCallback((token?: string, ttlMs?: number) => {
    return executorCoordinator.claimActiveExecutor(token, ttlMs)
  }, [])

  const validateExecution = useCallback(() => {
    return executorCoordinator.validateExecution()
  }, [])

  return {
    ...state,
    claimExecutor,
    releaseExecutor,
    makeActive,
    validateExecution,
  }
}
