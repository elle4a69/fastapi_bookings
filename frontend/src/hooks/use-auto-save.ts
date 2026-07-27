import { useCallback, useEffect, useRef, useState } from "react";

export type SaveState = "idle" | "saving" | "saved" | "failed";

interface UseAutoSaveOptions<T> {
  onSave: (payload: T) => Promise<any>;
  debounceMs?: number;
}

export function useAutoSave<T>({ onSave, debounceMs = 500 }: UseAutoSaveOptions<T>) {
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const onSaveRef = useRef(onSave);
  const lastPayloadRef = useRef<T | null>(null);
  const failedPayloadRef = useRef<T | null>(null);
  const activeRequestIdRef = useRef<number>(0);

  // Keep onSave callback fresh
  useEffect(() => {
    onSaveRef.current = onSave;
  }, [onSave]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const executeSave = useCallback(async (payload: T) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    const requestId = ++activeRequestIdRef.current;
    setSaveState("saving");
    try {
      await onSaveRef.current(payload);
      if (requestId === activeRequestIdRef.current) {
        setSaveState("saved");
        failedPayloadRef.current = null;
      }
    } catch (error) {
      console.error("AutoSave failed:", error);
      if (requestId === activeRequestIdRef.current) {
        setSaveState("failed");
        failedPayloadRef.current = payload;
      }
    }
  }, []);

  const triggerSave = useCallback((payload: T, immediate = false) => {
    lastPayloadRef.current = payload;
    
    // Clear any existing timer
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    if (immediate) {
      executeSave(payload);
    } else {
      // In text editing, transition back to 'idle' while typing (unsaved changes pending)
      setSaveState("idle");
      timeoutRef.current = setTimeout(() => {
        executeSave(payload);
      }, debounceMs);
    }
  }, [executeSave, debounceMs]);

  const retry = useCallback(() => {
    if (failedPayloadRef.current !== null) {
      executeSave(failedPayloadRef.current);
    } else if (lastPayloadRef.current !== null) {
      executeSave(lastPayloadRef.current);
    }
  }, [executeSave]);

  return {
    saveState,
    triggerSave,
    retry,
    hasFailedPayload: failedPayloadRef.current !== null,
  };
}
