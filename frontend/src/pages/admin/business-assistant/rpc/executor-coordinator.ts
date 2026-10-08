import { defaultLeaseManager, LeaseTokenManager } from './action-catalogue.ts'

export const EXECUTOR_CHANNEL_NAME = 'fastapi_bookings_executor_channel'
export const EXECUTOR_STORAGE_KEY = 'fastapi_bookings_executor_lease'
export const DEFAULT_LEASE_TTL_MS = 10000 // 10 seconds
export const DEFAULT_HEARTBEAT_INTERVAL_MS = 3000 // 3 seconds

export type ExecutorMessageType =
  | 'CLAIM_LEASE'
  | 'HEARTBEAT'
  | 'RELEASE_LEASE'
  | 'QUERY_LEASE'
  | 'ANNOUNCE_LEASE'
  | 'MANUAL_TAKEOVER'

export interface ExecutorChannelMessage {
  type: ExecutorMessageType
  tabId: string
  leaseToken?: string
  expiresAt?: number
  controlEpoch?: number
  timestamp: number
  reason?: string
}

export interface ExecutorState {
  currentTabId: string
  activeTabId: string | null
  leaseToken: string | null
  leaseExpiresAt: number | null
  isActiveExecutor: boolean
}

export interface CoordinatorOptions {
  tabId?: string
  channelName?: string
  storageKey?: string
  leaseTtlMs?: number
  heartbeatIntervalMs?: number
  broadcastChannelFactory?: ((name: string) => any) | null
  storage?: Storage | null
  leaseManager?: LeaseTokenManager
}

export class ExecutorCoordinator {
  private currentTabId: string
  private activeTabId: string | null = null
  private leaseToken: string | null = null
  private leaseExpiresAt: number | null = null
  private isActiveExecutorState: boolean = false

  private channelName: string
  private storageKey: string
  private leaseTtlMs: number
  private heartbeatIntervalMs: number

  private channel: any = null
  private storage: Storage | null = null
  private leaseManager: LeaseTokenManager

  private heartbeatTimer: any = null
  private expiryTimer: any = null
  private storageListener: ((event: StorageEvent) => void) | null = null
  private messageListener: ((event: any) => void) | null = null
  private listeners: Set<(state: ExecutorState) => void> = new Set()

  constructor(options: CoordinatorOptions = {}) {
    this.currentTabId =
      options.tabId ||
      `tab_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`

    this.channelName = options.channelName || EXECUTOR_CHANNEL_NAME
    this.storageKey = options.storageKey || EXECUTOR_STORAGE_KEY
    this.leaseTtlMs = options.leaseTtlMs || DEFAULT_LEASE_TTL_MS
    this.heartbeatIntervalMs = options.heartbeatIntervalMs || DEFAULT_HEARTBEAT_INTERVAL_MS
    this.leaseManager = options.leaseManager || defaultLeaseManager

    // Setup Storage
    if (options.storage !== undefined) {
      this.storage = options.storage
    } else if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      try {
        this.storage = window.localStorage
      } catch {
        this.storage = null
      }
    }

    // Setup BroadcastChannel
    if (options.broadcastChannelFactory) {
      this.channel = options.broadcastChannelFactory(this.channelName)
    } else if (typeof window !== 'undefined' && typeof BroadcastChannel !== 'undefined') {
      try {
        this.channel = new BroadcastChannel(this.channelName)
      } catch {
        this.channel = null
      }
    } else if (typeof BroadcastChannel !== 'undefined') {
      try {
        this.channel = new BroadcastChannel(this.channelName)
        if (typeof (this.channel as any).unref === 'function') {
          ;(this.channel as any).unref()
        }
      } catch {
        this.channel = null
      }
    }

    this.initListeners()
    this.restoreFromStorage()
    this.queryActiveLease()
  }

  private initListeners(): void {
    // 1. Channel listener
    if (this.channel) {
      this.messageListener = (event: any) => {
        const data = event.data as ExecutorChannelMessage
        if (data && typeof data === 'object') {
          this.handleChannelMessage(data)
        }
      }

      if (typeof this.channel.addEventListener === 'function') {
        this.channel.addEventListener('message', this.messageListener)
      } else {
        this.channel.onmessage = this.messageListener
      }
    }

    // 2. LocalStorage cross-tab fallback listener
    if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
      this.storageListener = (event: StorageEvent) => {
        if (event.key === this.storageKey && event.newValue) {
          try {
            const data = JSON.parse(event.newValue) as ExecutorChannelMessage
            this.handleChannelMessage(data)
          } catch {
            // Invalid storage data ignored
          }
        } else if (event.key === this.storageKey && !event.newValue) {
          // Lease was cleared in another tab
          if (this.activeTabId && this.activeTabId !== this.currentTabId) {
            this.activeTabId = null
            this.leaseToken = null
            this.leaseExpiresAt = null
            this.notifyListeners()
          }
        }
      }
      window.addEventListener('storage', this.storageListener)
    }
  }

  private restoreFromStorage(): void {
    if (!this.storage) return
    try {
      const stored = this.storage.getItem(this.storageKey)
      if (stored) {
        const parsed = JSON.parse(stored) as ExecutorChannelMessage
        if (parsed.expiresAt && parsed.expiresAt > Date.now()) {
          this.activeTabId = parsed.tabId
          this.leaseToken = parsed.leaseToken || null
          this.leaseExpiresAt = parsed.expiresAt
          if (parsed.tabId === this.currentTabId) {
            this.isActiveExecutorState = true
            this.startHeartbeat()
          }
        } else {
          this.storage.removeItem(this.storageKey)
        }
      }
    } catch {
      // Storage unavailable or unparseable
    }
  }

  private queryActiveLease(): void {
    this.postMessage({
      type: 'QUERY_LEASE',
      tabId: this.currentTabId,
      timestamp: Date.now(),
    })
  }

  private postMessage(msg: ExecutorChannelMessage): void {
    if (this.channel) {
      try {
        this.channel.postMessage(msg)
      } catch {
        // Channel post fallback
      }
    }

    if (this.storage && msg.type !== 'QUERY_LEASE') {
      try {
        if (msg.type === 'RELEASE_LEASE') {
          this.storage.removeItem(this.storageKey)
        } else {
          this.storage.setItem(this.storageKey, JSON.stringify(msg))
        }
      } catch {
        // Storage write guard
      }
    }
  }

  public handleChannelMessage(msg: ExecutorChannelMessage): void {
    if (!msg || !msg.type || msg.tabId === this.currentTabId) {
      return
    }

    switch (msg.type) {
      case 'CLAIM_LEASE': {
        // Another tab claimed active executor
        if (this.isActiveExecutorState) {
          // Relinquish execution immediately to prevent dual-executor collision
          this.relinquishActiveState('Superseded by tab ' + msg.tabId)
        }
        this.activeTabId = msg.tabId
        this.leaseToken = msg.leaseToken || null
        this.leaseExpiresAt = msg.expiresAt || null
        this.scheduleExpiryCheck()
        this.notifyListeners()
        break
      }

      case 'HEARTBEAT': {
        if (this.isActiveExecutorState && msg.tabId !== this.currentTabId) {
          // Conflict detected: Another tab is heartbeating as active
          this.relinquishActiveState('Heartbeat collision from ' + msg.tabId)
        }
        this.activeTabId = msg.tabId
        this.leaseToken = msg.leaseToken || null
        this.leaseExpiresAt = msg.expiresAt || null
        this.scheduleExpiryCheck()
        this.notifyListeners()
        break
      }

      case 'RELEASE_LEASE': {
        if (this.activeTabId === msg.tabId) {
          this.activeTabId = null
          this.leaseToken = null
          this.leaseExpiresAt = null
          this.notifyListeners()
        }
        break
      }

      case 'QUERY_LEASE': {
        if (this.isCurrentTabActive()) {
          this.postMessage({
            type: 'ANNOUNCE_LEASE',
            tabId: this.currentTabId,
            leaseToken: this.leaseToken || undefined,
            expiresAt: this.leaseExpiresAt || undefined,
            timestamp: Date.now(),
          })
        }
        break
      }

      case 'ANNOUNCE_LEASE': {
        this.activeTabId = msg.tabId
        this.leaseToken = msg.leaseToken || null
        this.leaseExpiresAt = msg.expiresAt || null
        this.scheduleExpiryCheck()
        this.notifyListeners()
        break
      }

      case 'MANUAL_TAKEOVER': {
        // Tab initiated manual takeover
        this.notifyListeners()
        break
      }
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (!this.isActiveExecutorState) {
        this.stopHeartbeat()
        return
      }

      const nextExpiry = Date.now() + this.leaseTtlMs
      this.leaseExpiresAt = nextExpiry

      // Renew underlying LeaseTokenManager
      if (this.leaseToken) {
        this.leaseManager.acquireLease(this.leaseToken, this.leaseTtlMs)
      }

      this.postMessage({
        type: 'HEARTBEAT',
        tabId: this.currentTabId,
        leaseToken: this.leaseToken || undefined,
        expiresAt: nextExpiry,
        timestamp: Date.now(),
      })
    }, this.heartbeatIntervalMs)

    if (this.heartbeatTimer && typeof this.heartbeatTimer.unref === 'function') {
      this.heartbeatTimer.unref()
    }
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleExpiryCheck(): void {
    if (this.expiryTimer) {
      clearTimeout(this.expiryTimer)
      this.expiryTimer = null
    }
    if (!this.leaseExpiresAt) return

    const delay = Math.max(0, this.leaseExpiresAt - Date.now() + 100)
    this.expiryTimer = setTimeout(() => {
      if (this.leaseExpiresAt && Date.now() >= this.leaseExpiresAt) {
        if (this.isActiveExecutorState) {
          this.relinquishActiveState('Lease expired')
        } else {
          this.activeTabId = null
          this.leaseToken = null
          this.leaseExpiresAt = null
          this.notifyListeners()
        }
      }
    }, delay)

    if (this.expiryTimer && typeof this.expiryTimer.unref === 'function') {
      this.expiryTimer.unref()
    }
  }

  private relinquishActiveState(_reason?: string): void {
    this.stopHeartbeat()
    if (this.expiryTimer) {
      clearTimeout(this.expiryTimer)
      this.expiryTimer = null
    }
    this.isActiveExecutorState = false
    this.leaseManager.reset()
    this.notifyListeners()
  }

  /**
   * Claims active executor capability for the current tab.
   * Broadcasts lease claim to all tabs and begins heartbeat.
   */
  public claimActiveExecutor(token?: string, ttlMs?: number): string {
    const ttl = ttlMs || this.leaseTtlMs
    const assignedToken =
      token || `lease_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`

    this.isActiveExecutorState = true
    this.activeTabId = this.currentTabId
    this.leaseToken = assignedToken
    this.leaseExpiresAt = Date.now() + ttl

    // Synchronize with action catalogue LeaseTokenManager
    this.leaseManager.acquireLease(assignedToken, ttl)

    this.startHeartbeat()

    this.postMessage({
      type: 'CLAIM_LEASE',
      tabId: this.currentTabId,
      leaseToken: assignedToken,
      expiresAt: this.leaseExpiresAt,
      timestamp: Date.now(),
    })

    this.scheduleExpiryCheck()
    this.notifyListeners()

    return assignedToken
  }

  /**
   * Relinquishes active executor capability for the current tab.
   */
  public releaseActiveExecutor(reason: string = 'User released active executor'): void {
    if (!this.isActiveExecutorState) {
      return
    }

    const previousToken = this.leaseToken
    this.stopHeartbeat()
    this.isActiveExecutorState = false
    this.activeTabId = null
    this.leaseToken = null
    this.leaseExpiresAt = null

    this.leaseManager.releaseLease(previousToken || undefined)

    this.postMessage({
      type: 'RELEASE_LEASE',
      tabId: this.currentTabId,
      leaseToken: previousToken || undefined,
      timestamp: Date.now(),
      reason,
    })

    this.notifyListeners()
  }

  /**
   * Returns whether the current tab holds the active, non-expired executor lease.
   */
  public isCurrentTabActive(): boolean {
    if (!this.isActiveExecutorState) return false
    if (this.leaseExpiresAt && Date.now() > this.leaseExpiresAt) {
      this.relinquishActiveState('Lease expired during check')
      return false
    }
    return true
  }

  /**
   * Validates whether outbound execution can proceed from this tab.
   * Inactive tabs reject outbound execution if lease is held elsewhere.
   */
  public validateExecution(): { allowed: boolean; reason?: string } {
    if (this.isCurrentTabActive()) {
      return { allowed: true }
    }

    const activeInfo = this.activeTabId ? `tab '${this.activeTabId}'` : 'no active tab'
    return {
      allowed: false,
      reason: `Outbound execution rejected: Tab '${this.currentTabId}' is not the active executor lease holder. Active executor is ${activeInfo}. Click 'Make this tab active' to claim execution.`,
    }
  }

  public getCurrentTabId(): string {
    return this.currentTabId
  }

  public getActiveTabId(): string | null {
    return this.activeTabId
  }

  public getActiveLeaseToken(): string | null {
    return this.leaseToken
  }

  public getState(): ExecutorState {
    return {
      currentTabId: this.currentTabId,
      activeTabId: this.activeTabId,
      leaseToken: this.leaseToken,
      leaseExpiresAt: this.leaseExpiresAt,
      isActiveExecutor: this.isCurrentTabActive(),
    }
  }

  public subscribe(listener: (state: ExecutorState) => void): () => void {
    this.listeners.add(listener)
    listener(this.getState())
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notifyListeners(): void {
    const state = this.getState()
    for (const listener of this.listeners) {
      try {
        listener(state)
      } catch {
        // Listener error boundary
      }
    }
  }

  public destroy(): void {
    this.stopHeartbeat()
    if (this.expiryTimer) {
      clearTimeout(this.expiryTimer)
      this.expiryTimer = null
    }

    if (this.channel) {
      try {
        if (typeof this.channel.removeEventListener === 'function' && this.messageListener) {
          this.channel.removeEventListener('message', this.messageListener)
        }
        if (typeof this.channel.close === 'function') {
          this.channel.close()
        }
      } catch {
        // Cleanup guard
      }
      this.channel = null
    }

    if (typeof window !== 'undefined' && this.storageListener) {
      window.removeEventListener('storage', this.storageListener)
      this.storageListener = null
    }

    this.listeners.clear()
  }
}

export const executorCoordinator = new ExecutorCoordinator()
