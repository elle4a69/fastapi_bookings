import { useState, useEffect, useCallback } from "react"

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed"
    platform: string
  }>
  prompt(): Promise<void>
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent
  }
}

export function usePwaInstall() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isInstalled, setIsInstalled] = useState(false)
  const [isIOS, setIsIOS] = useState(false)
  const [showIosInstructions, setShowIosInstructions] = useState(false)

  useEffect(() => {
    // Check if already running in standalone PWA mode
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as unknown as { standalone?: boolean }).standalone === true

    setIsInstalled(isStandalone)

    // Detect iOS (iPhone, iPad, iPod, or iPadOS masquerading as Mac)
    const userAgent = window.navigator.userAgent.toLowerCase()
    const isIosDevice =
      /iphone|ipad|ipod/.test(userAgent) ||
      (window.navigator.platform === "MacIntel" && window.navigator.maxTouchPoints > 1)
    setIsIOS(isIosDevice)

    const handleBeforeInstallPrompt = (e: BeforeInstallPromptEvent) => {
      // Prevent automatic prompt display
      e.preventDefault()
      // Stash event so user can trigger it with a UI button
      setDeferredPrompt(e)
    }

    const handleAppInstalled = () => {
      setDeferredPrompt(null)
      setIsInstalled(true)
      setShowIosInstructions(false)
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt)
    window.addEventListener("appinstalled", handleAppInstalled)

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt)
      window.removeEventListener("appinstalled", handleAppInstalled)
    }
  }, [])

  const install = useCallback(async () => {
    if (isIOS) {
      setShowIosInstructions(true)
      return false
    }

    if (!deferredPrompt) {
      return false
    }

    await deferredPrompt.prompt()
    const choiceResult = await deferredPrompt.userChoice
    if (choiceResult.outcome === "accepted") {
      setDeferredPrompt(null)
      setIsInstalled(true)
      return true
    }
    return false
  }, [deferredPrompt, isIOS])

  return {
    canInstall: (!isInstalled && !!deferredPrompt) || (!isInstalled && isIOS),
    isInstalled,
    isIOS,
    showIosInstructions,
    setShowIosInstructions,
    openIosInstructions: () => setShowIosInstructions(true),
    closeIosInstructions: () => setShowIosInstructions(false),
    install,
  }
}
