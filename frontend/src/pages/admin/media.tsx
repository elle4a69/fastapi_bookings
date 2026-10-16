import { useState, useEffect, useMemo, useCallback, type ChangeEvent } from "react"
import { 
  Upload, 
  FolderPlus, 
  Search, 
  Grid, 
  List, 
  Image as ImageIcon, 
  Film, 
  UserRoundCog, 
  Folder, 
  MoreVertical, 
  Trash2, 
  Download, 
  MessageSquare, 
  X, 
  FileText,
  Layers,
  Link as LinkIcon, 
  Copy, 
  Share2, 
  Clock, 
  Lock,
  Globe,
  AlertCircle,
  RefreshCw,
  FileCheck
} from "lucide-react"

import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { apiClient } from "@/lib/api"
import {
  type BackendMediaItem,
  type MediaListParams,
  listMedia,
  uploadMedia,
  updateMediaEligibility,
  deleteMedia,
  getAdminMediaStreamUrl,
  formatMediaFileSize,
  validateMediaUploadFile,
  fetchMediaBlobUrl
} from "@/api/media"

export interface ServiceProvider {
  id: string | number
  name: string
  title?: string
  email?: string
  avatar_url?: string
}

export interface MediaAlbum {
  id: string
  name: string
  description?: string
  providerId?: string
  createdAt: string
  coverUrl?: string
  shortUrl?: string
}

export interface PublicUploadLink {
  id: string
  token: string
  shortUrl: string
  albumId?: string
  providerId?: string
  senderNote?: string
  allowedTypes: ("image" | "video" | "document")[]
  maxUploads: number
  currentUploads: number
  expiresAt: string | null
  createdAt: string
  createdByName: string
}

export interface QueuedUploadItem {
  id: string
  file: File
  title: string
  description?: string
  notes?: string
  providerId?: string
  isEligible: boolean
  type: "image" | "video" | "document"
  previewUrl: string
  fileSize: string
  error?: string
}

const STORAGE_KEY_ALBUMS = "fastapi_bookings_media_albums_v1"
const STORAGE_KEY_PUBLIC_LINKS = "fastapi_bookings_public_upload_links_v1"

const DEFAULT_PROVIDERS: ServiceProvider[] = [
  { id: "prov-1", name: "Dr. Sarah Jenkins", title: "Lead Dermatologist" },
  { id: "prov-2", name: "Alex Rivera", title: "Senior Esthetician" },
  { id: "prov-3", name: "Elena Rostova", title: "Laser Specialist" },
  { id: "prov-4", name: "Marcus Vance", title: "Wellness Specialist" },
]

const INITIAL_ALBUMS: MediaAlbum[] = [
  {
    id: "alb-1",
    name: "Treatment Clinical Results",
    description: "Before & After high-resolution clinical documentation photographs.",
    providerId: "prov-1",
    createdAt: "2026-07-15T10:00:00Z",
    coverUrl: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&auto=format&fit=crop&q=80",
    shortUrl: "http://localhost:8002/api/v1/alb-1"
  },
  {
    id: "alb-2",
    name: "Facial Care & Skin Therapy",
    description: "Hydrafacial and deep skin cleansing session recordings.",
    providerId: "prov-2",
    createdAt: "2026-07-20T14:30:00Z",
    coverUrl: "https://images.unsplash.com/photo-1512290900673-7002fffe935a?w=600&auto=format&fit=crop&q=80",
    shortUrl: "http://localhost:8002/api/v1/alb-2"
  },
  {
    id: "alb-3",
    name: "Facility & Provider Showcase",
    description: "Provider profile media, studio ambiance, and promotional clips.",
    providerId: "prov-3",
    createdAt: "2026-08-01T09:15:00Z",
    coverUrl: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=600&auto=format&fit=crop&q=80",
    shortUrl: "http://localhost:8002/api/v1/alb-3"
  }
]

// Short URL Service Generator Helper
async function createShortUrl(longUrl: string, _resourceId?: string, _prefix?: "med" | "alb" | "upl"): Promise<string> {
  try {
    const res = await fetch("http://localhost:8002/api/v1/shorten/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ long_url: longUrl }),
    })
    if (res.ok) {
      const data = await res.json()
      if (data?.short_url) {
        const shortCode = data.short_url.split("/").pop()
        return `http://localhost:8002/api/v1/${shortCode}`
      }
    }
  } catch (err) {
    console.warn("ShortURL service offline, fallback generated:", err)
  }

  return longUrl
}

// Media Item Preview Component
function MediaPreviewThumbnail({ item }: { item: BackendMediaItem }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [hasError, setHasError] = useState(false)

  const handleImageError = () => {
    if (!blobUrl && !hasError) {
      fetchMediaBlobUrl(item.id)
        .then((url) => setBlobUrl(url))
        .catch(() => setHasError(true))
    } else {
      setHasError(true)
    }
  }

  if (item.media_type === "video") {
    return (
      <div className="relative w-full h-full flex items-center justify-center bg-slate-900 text-white">
        <Film className="h-10 w-10 opacity-75 group-hover:scale-110 transition-transform" />
        <Badge className="absolute top-2.5 right-2.5 bg-black/70 backdrop-blur-sm gap-1 text-[10px]">
          <Film className="h-3 w-3" /> VIDEO
        </Badge>
      </div>
    )
  }

  if (hasError) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-muted text-muted-foreground p-2 text-center text-xs">
        <ImageIcon className="h-8 w-8 mb-1 opacity-50" />
        <span className="truncate max-w-[120px]">{item.filename}</span>
      </div>
    )
  }

  const src = blobUrl || item.url || getAdminMediaStreamUrl(item.id)

  return (
    <img 
      src={src} 
      alt={item.title || item.filename} 
      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
      onError={handleImageError}
    />
  )
}

export default function MediaPage() {
  const [providers, setProviders] = useState<ServiceProvider[]>(DEFAULT_PROVIDERS)
  const [albums, setAlbums] = useState<MediaAlbum[]>([])
  const [mediaItems, setMediaItems] = useState<BackendMediaItem[]>([])
  const [publicLinks, setPublicLinks] = useState<PublicUploadLink[]>([])
  const [isLoadingMedia, setIsLoadingMedia] = useState<boolean>(true)
  const [mediaError, setMediaError] = useState<string | null>(null)

  // Filtering state
  const [selectedAlbumId, setSelectedAlbumId] = useState<string>("all")
  const [selectedProviderId, setSelectedProviderId] = useState<string>("all")
  const [eligibilityFilter, setEligibilityFilter] = useState<"all" | "eligible" | "ineligible">("all")
  const [mediaTypeFilter, setMediaTypeFilter] = useState<"all" | "image" | "video" | "document">("all")
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [activeTab, setActiveTab] = useState<string>("all-media")

  // Modal & Detail state
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [isNewAlbumOpen, setIsNewAlbumOpen] = useState(false)
  const [isPublicLinkOpen, setIsPublicLinkOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<BackendMediaItem | null>(null)
  const [togglingEligibilityId, setTogglingEligibilityId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  // Public Link Generator State
  const [linkExpiryDuration, setLinkExpiryDuration] = useState<string>("24h")
  const [linkMaxUploads, setLinkMaxUploads] = useState<string>("5")
  const [linkTargetAlbumId, setLinkTargetAlbumId] = useState<string>("none")
  const [linkTargetProviderId, setLinkTargetProviderId] = useState<string>("none")
  const [createdPublicLink, setCreatedPublicLink] = useState<PublicUploadLink | null>(null)

  // Multi-File Upload Queue State
  const [uploadQueue, setUploadQueue] = useState<QueuedUploadItem[]>([])
  const [uploadAlbumId, setUploadAlbumId] = useState<string>("none")
  const [uploadProviderId, setUploadProviderId] = useState<string>("none")
  const [uploadDescription, setUploadDescription] = useState("")
  const [uploadNote, setUploadNote] = useState("")
  const [uploadIsEligible, setUploadIsEligible] = useState<boolean>(false)
  const [isBatchUploading, setIsBatchUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number }>({ current: 0, total: 0 })

  // New Album Form state
  const [albumName, setAlbumName] = useState("")
  const [albumDescription, setAlbumDescription] = useState("")
  const [albumProviderId, setAlbumProviderId] = useState<string>("none")
  const [albumCoverUrl, setAlbumCoverUrl] = useState("")

  // Load Providers from API
  useEffect(() => {
    async function loadProviders() {
      try {
        const res = await apiClient.get<any>("/api/admin/providers").catch(() => null)
        const raw = Array.isArray(res) ? res : res?.data ?? res?.items ?? []
        if (raw && raw.length > 0) {
          const mapped: ServiceProvider[] = raw.map((p: any) => ({
            id: String(p.id),
            name: p.name || p.full_name || `Provider #${p.id}`,
            title: p.title || p.specialty || "Service Provider",
            email: p.email
          }))
          setProviders(mapped)
        }
      } catch (err) {
        console.warn("Using fallback service providers list.", err)
      }
    }
    loadProviders()
  }, [])

  // Load Media Items from Real Backend API
  const fetchMediaItems = useCallback(async () => {
    setIsLoadingMedia(true)
    setMediaError(null)
    try {
      const params: MediaListParams = {}
      if (eligibilityFilter === "eligible") {
        params.is_public_website_eligible = true
      } else if (eligibilityFilter === "ineligible") {
        params.is_public_website_eligible = false
      }

      if (selectedProviderId !== "all" && selectedProviderId !== "unassigned") {
        const provNum = parseInt(selectedProviderId, 10)
        if (!isNaN(provNum)) {
          params.provider_id = provNum
        }
      }

      const res = await listMedia(params)
      setMediaItems(res.data || [])
    } catch (err: any) {
      console.error("Failed to load media items:", err)
      setMediaError(err?.message || "Failed to load media items from server.")
      toast.error("Failed to load media items from server.")
    } finally {
      setIsLoadingMedia(false)
    }
  }, [eligibilityFilter, selectedProviderId])

  useEffect(() => {
    fetchMediaItems()
  }, [fetchMediaItems])

  // Load Albums & Public Links from Storage
  useEffect(() => {
    async function initAuxData() {
      let loadedAlbums: MediaAlbum[] = INITIAL_ALBUMS
      const savedAlbums = localStorage.getItem(STORAGE_KEY_ALBUMS)
      if (savedAlbums) {
        try {
          loadedAlbums = JSON.parse(savedAlbums)
        } catch {
          loadedAlbums = INITIAL_ALBUMS
        }
      }
      setAlbums(loadedAlbums)

      const savedLinksRaw = localStorage.getItem(STORAGE_KEY_PUBLIC_LINKS)
      if (savedLinksRaw) {
        try {
          setPublicLinks(JSON.parse(savedLinksRaw))
        } catch {
          setPublicLinks([])
        }
      }
    }

    initAuxData()
  }, [])

  // Copy Short Link to Clipboard
  const handleCopyShortUrl = (shortUrl: string, label: string) => {
    navigator.clipboard.writeText(shortUrl)
    toast.success(`${label} link copied to clipboard!`)
  }

  // Generate Ad-Hoc Public Upload Link
  const handleGeneratePublicUploadLink = async () => {
    const linkId = `upl-${Date.now()}`
    const token = Math.random().toString(36).substring(2, 10)
    const longUrl = `http://localhost:7070/public/upload?token=${token}`
    
    let expiresAt: string | null = null
    const now = new Date()
    if (linkExpiryDuration === "1h") {
      expiresAt = new Date(now.getTime() + 60 * 60 * 1000).toISOString()
    } else if (linkExpiryDuration === "24h") {
      expiresAt = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString()
    } else if (linkExpiryDuration === "3d") {
      expiresAt = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString()
    } else if (linkExpiryDuration === "7d") {
      expiresAt = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString()
    }

    const maxUploads = linkMaxUploads === "unlimited" ? 0 : parseInt(linkMaxUploads, 10)
    const shortUrl = await createShortUrl(longUrl, linkId, "upl")

    const newLink: PublicUploadLink = {
      id: linkId,
      token,
      shortUrl,
      albumId: linkTargetAlbumId !== "none" ? linkTargetAlbumId : undefined,
      providerId: linkTargetProviderId !== "none" ? linkTargetProviderId : undefined,
      allowedTypes: ["image", "video", "document"],
      maxUploads,
      currentUploads: 0,
      expiresAt,
      createdAt: now.toISOString(),
      createdByName: "Admin User"
    }

    const updated = [newLink, ...publicLinks]
    setPublicLinks(updated)
    localStorage.setItem(STORAGE_KEY_PUBLIC_LINKS, JSON.stringify(updated))
    setCreatedPublicLink(newLink)
    toast.success("Public Upload Portal Link generated with expiry protection!")
  }

  // Revoke Public Link
  const handleRevokePublicLink = (linkId: string) => {
    const updated = publicLinks.filter(l => l.id !== linkId)
    setPublicLinks(updated)
    localStorage.setItem(STORAGE_KEY_PUBLIC_LINKS, JSON.stringify(updated))
    toast.success("Public upload link revoked.")
  }

  // Handle Multi-File Selection with validation
  const handleMultiFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return

    const filesArr = Array.from(e.target.files)

    filesArr.forEach((file, index) => {
      const validation = validateMediaUploadFile(file)
      const isVideo = file.type.startsWith("video/")
      const isDoc = file.type === "application/pdf"
      const itemTitle = file.name.replace(/\.[^/.]+$/, "")
      const itemSize = formatMediaFileSize(file.size)

      let mediaType: "image" | "video" | "document" = "image"
      if (isVideo) mediaType = "video"
      else if (isDoc) mediaType = "document"

      const previewUrl = URL.createObjectURL(file)

      setUploadQueue(prev => [
        ...prev,
        {
          id: `q-${Date.now()}-${index}-${Math.random().toString(36).substring(2, 6)}`,
          file,
          title: itemTitle,
          description: uploadDescription,
          notes: uploadNote,
          providerId: uploadProviderId !== "none" ? uploadProviderId : undefined,
          isEligible: uploadIsEligible,
          type: mediaType,
          previewUrl,
          fileSize: itemSize,
          error: validation.valid ? undefined : validation.error
        }
      ])
    })

    e.target.value = ""
  }

  // Remove Item from Queue
  const handleRemoveQueueItem = (id: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== id))
  }

  // Update Title of Queued Item
  const handleUpdateQueueTitle = (id: string, newTitle: string) => {
    setUploadQueue(prev => prev.map(item => item.id === id ? { ...item, title: newTitle } : item))
  }

  // Create New Album
  const handleCreateAlbum = async () => {
    if (!albumName.trim()) return

    const newId = `alb-${Date.now()}`
    const cover = albumCoverUrl.trim() || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"
    const generatedShortUrl = await createShortUrl(cover, newId, "alb")

    const newAlbum: MediaAlbum = {
      id: newId,
      name: albumName.trim(),
      description: albumDescription.trim() || undefined,
      providerId: albumProviderId !== "none" ? albumProviderId : undefined,
      createdAt: new Date().toISOString(),
      coverUrl: cover,
      shortUrl: generatedShortUrl
    }

    const updated = [newAlbum, ...albums]
    setAlbums(updated)
    localStorage.setItem(STORAGE_KEY_ALBUMS, JSON.stringify(updated))
    toast.success(`Album "${newAlbum.name}" created!`)

    setAlbumName("")
    setAlbumDescription("")
    setAlbumProviderId("none")
    setAlbumCoverUrl("")
    setIsNewAlbumOpen(false)
  }

  // Submit Multi-File Batch Upload to Real Backend API
  const handleBatchUploadSubmit = async () => {
    const validItems = uploadQueue.filter(q => !q.error)
    if (validItems.length === 0) {
      toast.error("Please add valid files to upload.")
      return
    }

    setIsBatchUploading(true)
    setUploadProgress({ current: 0, total: validItems.length })

    let successCount = 0
    let failureCount = 0

    try {
      for (let i = 0; i < validItems.length; i++) {
        const qItem = validItems[i]
        setUploadProgress({ current: i + 1, total: validItems.length })

        let finalProviderId: number | null = null
        if (qItem.providerId && qItem.providerId !== "none") {
          const parsed = parseInt(qItem.providerId, 10)
          if (!isNaN(parsed)) finalProviderId = parsed
        } else if (uploadProviderId !== "none") {
          const parsed = parseInt(uploadProviderId, 10)
          if (!isNaN(parsed)) finalProviderId = parsed
        }

        try {
          await uploadMedia({
            file: qItem.file,
            title: qItem.title.trim() || undefined,
            description: (uploadDescription.trim() || qItem.description?.trim()) || undefined,
            notes: (uploadNote.trim() || qItem.notes?.trim()) || undefined,
            provider_id: finalProviderId,
            is_public_website_eligible: uploadIsEligible || qItem.isEligible
          })
          successCount++
        } catch (err: any) {
          console.error(`Failed to upload ${qItem.file.name}:`, err)
          failureCount++
          toast.error(`Upload failed for ${qItem.file.name}: ${err?.message || "Server error"}`)
        }
      }

      if (successCount > 0) {
        toast.success(`Successfully uploaded ${successCount} media asset${successCount > 1 ? "s" : ""} to storage!`)
        await fetchMediaItems()
        setUploadQueue([])
        setUploadDescription("")
        setUploadNote("")
        setUploadIsEligible(false)
        setIsUploadOpen(false)
      }
    } finally {
      setIsBatchUploading(false)
    }
  }

  // Toggle Public Website Eligibility via API
  const handleToggleEligibility = async (item: BackendMediaItem) => {
    setTogglingEligibilityId(item.id)
    const targetState = !item.is_public_website_eligible

    try {
      const res = await updateMediaEligibility(item.id, targetState)
      setMediaItems(prev => prev.map(m => m.id === item.id ? res.data : m))
      if (selectedItem?.id === item.id) {
        setSelectedItem(res.data)
      }
      toast.success(
        targetState 
          ? `Asset marked public website eligible.` 
          : `Asset restricted to internal/private use.`
      )
    } catch (err: any) {
      console.error("Failed to update eligibility:", err)
      toast.error(err?.message || "Failed to update eligibility state.")
    } finally {
      setTogglingEligibilityId(null)
    }
  }

  // Delete Item via Real API
  const handleDeleteItem = async (id: number) => {
    setDeletingId(id)
    try {
      await deleteMedia(id)
      setMediaItems(prev => prev.filter(m => m.id !== id))
      if (selectedItem?.id === id) {
        setSelectedItem(null)
      }
      toast.success("Media asset deleted permanently from storage.")
    } catch (err: any) {
      console.error("Failed to delete media asset:", err)
      toast.error(err?.message || "Failed to delete media asset.")
    } finally {
      setDeletingId(null)
    }
  }

  // Delete Album
  const handleDeleteAlbum = (albumId: string) => {
    const updatedAlbums = albums.filter(a => a.id !== albumId)
    setAlbums(updatedAlbums)
    localStorage.setItem(STORAGE_KEY_ALBUMS, JSON.stringify(updatedAlbums))
    toast.success("Album deleted.")
  }

  // Filtered Media Items (Search & local filters)
  const filteredMediaItems = useMemo(() => {
    return mediaItems.filter(item => {
      // Album filter
      if (selectedAlbumId !== "all") {
        const targetAlbum = albums.find(a => a.id === selectedAlbumId)
        if (targetAlbum?.providerId && String(item.provider_id) !== targetAlbum.providerId) {
          return false
        }
      }

      // Local Provider filter
      if (selectedProviderId !== "all") {
        if (selectedProviderId === "unassigned" && item.provider_id) return false
        if (selectedProviderId !== "unassigned" && String(item.provider_id) !== selectedProviderId) return false
      }

      // Local Eligibility filter
      if (eligibilityFilter === "eligible" && !item.is_public_website_eligible) return false
      if (eligibilityFilter === "ineligible" && item.is_public_website_eligible) return false

      // Media Type filter
      if (mediaTypeFilter !== "all" && item.media_type !== mediaTypeFilter) return false

      // Search Query filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        const matchTitle = (item.title || "").toLowerCase().includes(query)
        const matchFilename = (item.filename || "").toLowerCase().includes(query)
        const matchDesc = (item.description || "").toLowerCase().includes(query)
        const matchNotes = (item.notes || "").toLowerCase().includes(query)
        if (!matchTitle && !matchFilename && !matchDesc && !matchNotes) return false
      }

      return true
    })
  }, [mediaItems, selectedAlbumId, albums, selectedProviderId, eligibilityFilter, mediaTypeFilter, searchQuery])

  // Get Provider Name Helper
  const getProviderName = (providerId?: number | string | null) => {
    if (!providerId) return "Unassigned Provider"
    const p = providers.find(prov => String(prov.id) === String(providerId))
    return p ? p.name : `Provider #${providerId}`
  }

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 min-w-0">
      
      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-primary font-medium text-xs tracking-wider uppercase mb-1">
            <Layers className="h-3.5 w-3.5" />
            <span>Media Management</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground truncate">
            Media & Asset Library
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Durable tenant-scoped storage. Manage photographs, videos, eligibility for public website publication, and private notes.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          {/* Refresh Button */}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => fetchMediaItems()} 
            disabled={isLoadingMedia}
            className="gap-1.5 text-xs"
            title="Refresh Media Items"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoadingMedia ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>

          {/* Public Upload Link Dialog */}
          <Dialog open={isPublicLinkOpen} onOpenChange={setIsPublicLinkOpen}>
            <DialogTrigger asChild>
              <Button variant="secondary" size="sm" className="gap-1.5 text-xs">
                <Share2 className="h-4 w-4 text-emerald-500" />
                <span>Public Upload Portal Link</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[550px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Share2 className="h-5 w-5 text-emerald-500" />
                  Generate Ad-Hoc Public Upload Link
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Create a self-destructing public upload portal link for clients or third parties to upload photos or files securely without login access.
                </DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 py-2 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="link-expiry" className="text-xs font-semibold flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-primary" /> Auto-Destruct / Expiry Period
                    </Label>
                    <Select value={linkExpiryDuration} onValueChange={setLinkExpiryDuration}>
                      <SelectTrigger id="link-expiry" className="h-9" aria-label="Auto-destruct / expiry period">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1h">1 Hour (Quick Pass)</SelectItem>
                        <SelectItem value="24h">24 Hours (1 Day)</SelectItem>
                        <SelectItem value="3d">3 Days</SelectItem>
                        <SelectItem value="7d">7 Days (1 Week)</SelectItem>
                        <SelectItem value="never">No Expiration Date</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-1.5">
                    <Label htmlFor="link-max-uploads" className="text-xs font-semibold flex items-center gap-1">
                      <Lock className="h-3.5 w-3.5 text-primary" /> Max Upload File Quota
                    </Label>
                    <Select value={linkMaxUploads} onValueChange={setLinkMaxUploads}>
                      <SelectTrigger id="link-max-uploads" className="h-9" aria-label="Max upload file quota">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1 File Only</SelectItem>
                        <SelectItem value="3">3 Files Max</SelectItem>
                        <SelectItem value="5">5 Files Max</SelectItem>
                        <SelectItem value="10">10 Files Max</SelectItem>
                        <SelectItem value="unlimited">Unlimited Uploads</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="link-target-album" className="text-xs font-semibold">Pre-Assign to Album</Label>
                    <Select value={linkTargetAlbumId} onValueChange={setLinkTargetAlbumId}>
                      <SelectTrigger id="link-target-album" className="h-9" aria-label="Pre-assign to album">
                        <SelectValue placeholder="Select Album" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Unassigned (Root)</SelectItem>
                        {albums.map((a) => (
                          <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-1.5">
                    <Label htmlFor="link-target-provider" className="text-xs font-semibold">Pre-Assign to Provider</Label>
                    <Select value={linkTargetProviderId} onValueChange={setLinkTargetProviderId}>
                      <SelectTrigger id="link-target-provider" className="h-9" aria-label="Pre-assign to provider">
                        <SelectValue placeholder="Select Provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Unassigned</SelectItem>
                        {providers.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Button 
                  onClick={handleGeneratePublicUploadLink}
                  className="gap-2 font-semibold bg-emerald-600 hover:bg-emerald-700 text-white mt-1"
                >
                  <Share2 className="h-4 w-4" /> Generate Protected Upload Link
                </Button>

                {createdPublicLink && (
                  <div className="p-3 rounded-lg border bg-emerald-950/30 border-emerald-500/30 flex flex-col gap-2 mt-2">
                    <div className="flex items-center justify-between font-semibold text-emerald-400">
                      <span>Public Short Upload Link</span>
                      <Badge variant="outline" className="text-[9px] border-emerald-500/40 text-emerald-400">
                        {createdPublicLink.expiresAt ? `Expires ${new Date(createdPublicLink.expiresAt).toLocaleDateString()}` : "Never Expires"}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-2">
                      <Input 
                        readOnly 
                        value={createdPublicLink.shortUrl} 
                        className="font-mono text-xs h-8 bg-slate-900 border-slate-700 text-emerald-300" 
                      />
                      <Button 
                        size="sm" 
                        className="h-8 text-xs gap-1 shrink-0"
                        onClick={() => handleCopyShortUrl(createdPublicLink.shortUrl, "Public Upload")}
                      >
                        <Copy className="h-3 w-3" /> Copy Link
                      </Button>
                    </div>
                  </div>
                )}

                {publicLinks.length > 0 && (
                  <div className="border-t pt-3 flex flex-col gap-2">
                    <span className="font-semibold text-xs text-muted-foreground">Active Public Upload Links ({publicLinks.length}):</span>
                    <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                      {publicLinks.map((l) => (
                        <div key={l.id} className="p-2 rounded border bg-card text-[11px] flex items-center justify-between gap-2">
                          <div className="flex flex-col min-w-0">
                            <span className="font-mono text-primary truncate">{l.shortUrl}</span>
                            <span className="text-muted-foreground text-[10px]">
                              {l.currentUploads} / {l.maxUploads || "∞"} used • {l.expiresAt ? `Expires ${new Date(l.expiresAt).toLocaleDateString()}` : "No Expiry"}
                            </span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <Button 
                              variant="ghost" 
                              size="icon-sm"
                              className="h-6 w-6 text-primary"
                              onClick={() => handleCopyShortUrl(l.shortUrl, "Upload Link")}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon-sm"
                              className="h-6 w-6 text-destructive"
                              onClick={() => handleRevokePublicLink(l.id)}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsPublicLinkOpen(false)}>Close</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Create Album Dialog */}
          <Dialog open={isNewAlbumOpen} onOpenChange={setIsNewAlbumOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                <FolderPlus className="h-4 w-4 text-primary" />
                <span>New Album</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FolderPlus className="h-5 w-5 text-primary" />
                  Create New Media Library / Album
                </DialogTitle>
                <DialogDescription>
                  Group photos and videos into structured collections and assign default service providers.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-3">
                <div className="grid gap-2">
                  <Label htmlFor="album-name">Album Name *</Label>
                  <Input 
                    id="album-name" 
                    placeholder="e.g. Clinical Before & After Photos" 
                    value={albumName}
                    onChange={(e) => setAlbumName(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="album-desc">Description</Label>
                  <Textarea 
                    id="album-desc" 
                    placeholder="Optional details about this collection..." 
                    value={albumDescription}
                    onChange={(e) => setAlbumDescription(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="album-provider">Assign Service Provider</Label>
                  <Select value={albumProviderId} onValueChange={setAlbumProviderId}>
                    <SelectTrigger id="album-provider" aria-label="Assign service provider">
                      <SelectValue placeholder="Select Service Provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No Provider Assigned</SelectItem>
                      {providers.map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>
                          {p.name} {p.title ? `(${p.title})` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="album-cover">Cover Image URL (Optional)</Label>
                  <Input 
                    id="album-cover" 
                    placeholder="https://images.unsplash.com/..." 
                    value={albumCoverUrl}
                    onChange={(e) => setAlbumCoverUrl(e.target.value)}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsNewAlbumOpen(false)}>Cancel</Button>
                <Button onClick={handleCreateAlbum} disabled={!albumName.trim()}>Create Album</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Multi-File Upload Media Dialog */}
          <Dialog open={isUploadOpen} onOpenChange={setIsUploadOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="gap-2 shadow-sm">
                <Upload className="h-4 w-4" />
                <span>Upload Media</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Upload className="h-5 w-5 text-primary" />
                  Upload Media Asset
                </DialogTitle>
                <DialogDescription>
                  Upload files directly to durable backend tenant storage. Validated for safe MIME types and 25MB maximum size.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-2">
                
                {/* Drag and Drop Zone */}
                <div className="grid gap-2">
                  <Label className="flex items-center justify-between">
                    <span>Select Photographs or Video Files *</span>
                    {uploadQueue.length > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {uploadQueue.length} File{uploadQueue.length > 1 ? "s" : ""} Queued
                      </Badge>
                    )}
                  </Label>
                  <div className="border-2 border-dashed rounded-xl p-5 text-center hover:border-primary/60 transition-colors bg-muted/20">
                    <input 
                      type="file" 
                      accept="image/jpeg,image/png,image/webp,image/gif,image/svg+xml,video/mp4,video/webm,video/quicktime,application/pdf" 
                      multiple
                      id="media-multi-file-input" 
                      className="hidden" 
                      onChange={handleMultiFileChange}
                    />
                    <label htmlFor="media-multi-file-input" className="cursor-pointer flex flex-col items-center gap-2">
                      <div className="p-3 rounded-full bg-primary/10 text-primary">
                        <Upload className="h-6 w-6" />
                      </div>
                      <div className="text-sm font-semibold">
                        Click to select files or drag & drop here
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Supports JPG, PNG, WEBP, GIF, SVG, MP4, WEBM, QuickTime, PDF (Max 25MB per file)
                      </p>
                    </label>
                  </div>
                </div>

                {/* Queue Preview List */}
                {uploadQueue.length > 0 && (
                  <div className="space-y-2 border rounded-lg p-3 bg-muted/10 max-h-56 overflow-y-auto">
                    <span className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
                      <span>Queued Files ({uploadQueue.length}):</span>
                      <button 
                        onClick={() => setUploadQueue([])}
                        className="text-destructive text-[11px] hover:underline"
                      >
                        Clear All
                      </button>
                    </span>

                    <div className="space-y-2">
                      {uploadQueue.map((item, idx) => (
                        <div key={item.id} className={`p-2.5 rounded-md bg-card border flex items-center gap-3 text-xs ${item.error ? "border-destructive/60 bg-destructive/5" : ""}`}>
                          <div className="h-10 w-12 rounded bg-muted overflow-hidden shrink-0 flex items-center justify-center">
                            {item.type === "video" ? (
                              <Film className="h-5 w-5 text-primary" />
                            ) : item.type === "document" ? (
                              <FileText className="h-5 w-5 text-primary" />
                            ) : (
                              <img src={item.previewUrl} alt={item.title} className="w-full h-full object-cover" />
                            )}
                          </div>

                          <div className="flex-1 min-w-0 grid gap-1">
                            <Input 
                              value={item.title} 
                              onChange={(e) => handleUpdateQueueTitle(item.id, e.target.value)}
                              className="h-7 text-xs font-medium"
                              placeholder={`File #${idx + 1} Title`}
                            />
                            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                              <Badge variant="outline" className="uppercase py-0 h-3.5 text-[9px]">{item.type}</Badge>
                              <span>{item.fileSize}</span>
                              {item.error ? (
                                <span className="text-destructive font-medium flex items-center gap-1">
                                  <AlertCircle className="h-3 w-3" /> {item.error}
                                </span>
                              ) : (
                                <span className="text-emerald-500 flex items-center gap-0.5">
                                  <FileCheck className="h-3 w-3" /> Valid
                                </span>
                              )}
                            </div>
                          </div>

                          <Button 
                            variant="ghost" 
                            size="icon-sm"
                            className="h-7 w-7 text-destructive hover:bg-destructive/10 shrink-0"
                            onClick={() => handleRemoveQueueItem(item.id)}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Batch Options */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="grid gap-2">
                    <Label htmlFor="upload-provider">Assign Service Provider</Label>
                    <Select value={uploadProviderId} onValueChange={setUploadProviderId}>
                      <SelectTrigger id="upload-provider" aria-label="Assigned service provider">
                        <SelectValue placeholder="Select Service Provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No Provider Assigned</SelectItem>
                        {providers.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="upload-album">Pre-Assign to Album (Optional)</Label>
                    <Select value={uploadAlbumId} onValueChange={setUploadAlbumId}>
                      <SelectTrigger id="upload-album" aria-label="Pre-assign to album">
                        <SelectValue placeholder="Select Album" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Unassigned</SelectItem>
                        {albums.map((a) => (
                          <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="upload-desc">Description</Label>
                  <Input 
                    id="upload-desc" 
                    placeholder="Safe descriptive summary of the media asset..." 
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                  />
                </div>

                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="upload-note" className="flex items-center gap-1.5">
                      <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Internal / Clinical Notes</span>
                    </Label>
                    <span className="text-[10px] text-muted-foreground">Excluded from AI & public website</span>
                  </div>
                  <Textarea 
                    id="upload-note" 
                    placeholder="Internal staff notes, clinical observations, or handling instructions..." 
                    value={uploadNote}
                    onChange={(e) => setUploadNote(e.target.value)}
                    rows={2}
                  />
                </div>

                {/* Public Website Eligibility Checkbox */}
                <div className="p-3 rounded-lg border bg-muted/20 flex items-start gap-3">
                  <input
                    type="checkbox"
                    id="upload-eligible"
                    checked={uploadIsEligible}
                    onChange={(e) => setUploadIsEligible(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <label htmlFor="upload-eligible" className="text-xs cursor-pointer select-none">
                    <span className="font-semibold text-foreground flex items-center gap-1.5">
                      <Globe className="h-3.5 w-3.5 text-emerald-500" />
                      Approve for Public Website Use
                    </span>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      When checked, this asset becomes eligible to be included in public website galleries and AI assistant recommendations. Leave unchecked for private or clinical-only assets.
                    </p>
                  </label>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsUploadOpen(false)} disabled={isBatchUploading}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleBatchUploadSubmit} 
                  disabled={uploadQueue.filter(q => !q.error).length === 0 || isBatchUploading}
                  className="gap-1.5 font-semibold"
                >
                  <Upload className="h-4 w-4" />
                  <span>
                    {isBatchUploading 
                      ? `Uploading (${uploadProgress.current}/${uploadProgress.total})...` 
                      : `Upload ${uploadQueue.filter(q => !q.error).length} Asset${uploadQueue.filter(q => !q.error).length > 1 ? "s" : ""}`}
                  </span>
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* ── Main Content Area ────────────────────────────────────────────── */}
      <Tabs defaultValue="all-media" value={activeTab} onValueChange={setActiveTab} className="w-full flex flex-col gap-4">
        
        {/* Navigation & Controls Bar */}
        <div className="flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <TabsList className="w-full sm:w-auto grid grid-cols-2">
              <TabsTrigger value="all-media" className="gap-2">
                <ImageIcon className="h-4 w-4" />
                <span>All Media ({filteredMediaItems.length})</span>
              </TabsTrigger>
              <TabsTrigger value="albums" className="gap-2">
                <Folder className="h-4 w-4" />
                <span>Libraries & Albums ({albums.length})</span>
              </TabsTrigger>
            </TabsList>

            <div className="border rounded-md p-0.5 flex items-center bg-card gap-1 h-9 self-end sm:self-auto">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="icon"
                className="h-7 w-7"
                onClick={() => setViewMode("grid")}
                title="Grid View"
              >
                <Grid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="icon"
                className="h-7 w-7"
                onClick={() => setViewMode("list")}
                title="List View"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <Card className="border shadow-2xs">
            <CardContent className="p-3 flex flex-wrap items-center gap-3">
              {/* Search input */}
              <div className="relative flex-1 min-w-[200px] max-w-md">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search media by title, filename, notes..."
                  className="pl-8 text-xs h-9"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button 
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Public Website Eligibility Filter */}
              <div className="w-full sm:w-auto min-w-[180px]">
                <Select value={eligibilityFilter} onValueChange={(val: any) => setEligibilityFilter(val)}>
                  <SelectTrigger className="h-9 text-xs" aria-label="Filter by website eligibility">
                    <Globe className="h-3.5 w-3.5 mr-1.5 text-emerald-500 shrink-0" />
                    <SelectValue placeholder="All Eligibility" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Eligibility</SelectItem>
                    <SelectItem value="eligible">Website Eligible (Public)</SelectItem>
                    <SelectItem value="ineligible">Internal Only (Private)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Provider Filter */}
              <div className="w-full sm:w-auto min-w-[160px]">
                <Select value={selectedProviderId} onValueChange={setSelectedProviderId}>
                  <SelectTrigger className="h-9 text-xs" aria-label="Filter by provider">
                    <UserRoundCog className="h-3.5 w-3.5 mr-1.5 text-muted-foreground shrink-0" />
                    <SelectValue placeholder="All Providers" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Providers</SelectItem>
                    <SelectItem value="unassigned">Unassigned</SelectItem>
                    {providers.map(p => (
                      <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Media Type Filter */}
              <div className="w-full sm:w-auto min-w-[130px]">
                <Select value={mediaTypeFilter} onValueChange={(val: any) => setMediaTypeFilter(val)}>
                  <SelectTrigger className="h-9 text-xs" aria-label="Filter by media type">
                    <SelectValue placeholder="All Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="image">Photos Only</SelectItem>
                    <SelectItem value="video">Videos Only</SelectItem>
                    <SelectItem value="document">Documents</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── TAB 1: ALL MEDIA ITEMS ────────────────────────────────────── */}
        <TabsContent value="all-media" className="mt-0">
          
          {(selectedAlbumId !== "all" || selectedProviderId !== "all" || eligibilityFilter !== "all" || mediaTypeFilter !== "all" || searchQuery) && (
            <div className="flex items-center gap-2 mb-4 flex-wrap text-xs bg-muted/20 p-2.5 rounded-lg border">
              <span className="text-muted-foreground font-medium">Active Filters:</span>
              {selectedAlbumId !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs">
                  Album: {albums.find(a => a.id === selectedAlbumId)?.name || selectedAlbumId}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setSelectedAlbumId("all")} />
                </Badge>
              )}
              {eligibilityFilter !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs">
                  Eligibility: {eligibilityFilter === "eligible" ? "Public Website" : "Internal Only"}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setEligibilityFilter("all")} />
                </Badge>
              )}
              {selectedProviderId !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs">
                  Provider: {selectedProviderId === "unassigned" ? "Unassigned" : getProviderName(selectedProviderId)}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setSelectedProviderId("all")} />
                </Badge>
              )}
              {mediaTypeFilter !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs capitalize">
                  Type: {mediaTypeFilter}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setMediaTypeFilter("all")} />
                </Badge>
              )}
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-6 text-xs text-muted-foreground hover:text-foreground ml-auto"
                onClick={() => {
                  setSelectedAlbumId("all")
                  setSelectedProviderId("all")
                  setEligibilityFilter("all")
                  setMediaTypeFilter("all")
                  setSearchQuery("")
                }}
              >
                Reset All Filters
              </Button>
            </div>
          )}

          {isLoadingMedia ? (
            <div className="rounded-xl border border-dashed p-12 text-center flex flex-col items-center gap-3 bg-muted/10">
              <RefreshCw className="h-8 w-8 text-primary animate-spin" />
              <h3 className="text-base font-semibold">Loading media assets from storage...</h3>
              <p className="text-xs text-muted-foreground">Connecting to tenant durable media storage.</p>
            </div>
          ) : mediaError ? (
            <div className="rounded-xl border border-destructive/40 p-8 text-center flex flex-col items-center gap-3 bg-destructive/5">
              <AlertCircle className="h-8 w-8 text-destructive" />
              <h3 className="text-base font-semibold text-destructive">Failed to Load Media</h3>
              <p className="text-xs text-muted-foreground max-w-md">{mediaError}</p>
              <Button variant="outline" size="sm" onClick={() => fetchMediaItems()} className="gap-1.5 mt-2">
                <RefreshCw className="h-3.5 w-3.5" /> Try Again
              </Button>
            </div>
          ) : filteredMediaItems.length === 0 ? (
            <div className="rounded-xl border border-dashed p-12 text-center flex flex-col items-center gap-3 bg-muted/10">
              <div className="p-4 rounded-full bg-muted">
                <ImageIcon className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold">No media items found</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                No photographs or videos match your current filter options. Try uploading a new media file or adjusting your filters.
              </p>
              <Button onClick={() => setIsUploadOpen(true)} className="gap-2 mt-2">
                <Upload className="h-4 w-4" />
                <span>Upload Media Asset</span>
              </Button>
            </div>
          ) : viewMode === "grid" ? (
            /* Grid View */
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 w-full min-w-0">
              {filteredMediaItems.map((item) => (
                <Card 
                  key={item.id} 
                  className="group overflow-hidden flex flex-col justify-between hover:shadow-md transition-all border-muted cursor-pointer min-w-0 w-full"
                  onClick={() => setSelectedItem(item)}
                >
                  <div className="relative h-44 w-full overflow-hidden bg-muted flex items-center justify-center shrink-0">
                    <MediaPreviewThumbnail item={item} />

                    {/* Eligibility Badge */}
                    <div className="absolute top-2.5 left-2.5 flex items-center gap-1">
                      {item.is_public_website_eligible ? (
                        <Badge className="bg-emerald-600 text-white gap-1 text-[9px] shadow-sm">
                          <Globe className="h-2.5 w-2.5" /> Website Eligible
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-background/80 backdrop-blur-xs border-amber-500/50 text-amber-600 dark:text-amber-400 gap-1 text-[9px] shadow-sm">
                          <Lock className="h-2.5 w-2.5" /> Internal Only
                        </Badge>
                      )}
                    </div>

                    {/* MIME Type & Size Badge */}
                    <div className="absolute bottom-2.5 left-2.5 flex items-center gap-1.5">
                      <Badge className="bg-black/75 backdrop-blur-sm text-white font-mono text-[9px] py-0 h-4">
                        {formatMediaFileSize(item.file_size)}
                      </Badge>
                      {item.notes && (
                        <Badge className="bg-primary/90 text-primary-foreground gap-1 text-[9px] py-0 h-4">
                          <MessageSquare className="h-2.5 w-2.5" /> Notes
                        </Badge>
                      )}
                    </div>
                  </div>

                  <CardContent className="p-3.5 flex flex-col gap-2 flex-1 min-w-0 w-full">
                    <div className="flex items-center justify-between gap-2 min-w-0 w-full">
                      <h4 className="font-semibold text-sm truncate min-w-0 flex-1 group-hover:text-primary transition-colors">
                        {item.title || item.filename}
                      </h4>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0" aria-label="More options">
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setSelectedItem(item); }}>
                            <FileText className="h-3.5 w-3.5 mr-2" /> View Details & Notes
                          </DropdownMenuItem>
                          <DropdownMenuItem 
                            onClick={(e) => { e.stopPropagation(); handleToggleEligibility(item); }}
                            disabled={togglingEligibilityId === item.id}
                          >
                            <Globe className="h-3.5 w-3.5 mr-2 text-emerald-500" />
                            {item.is_public_website_eligible ? "Make Internal Only" : "Approve for Website"}
                          </DropdownMenuItem>
                          <DropdownMenuItem 
                            onClick={(e) => { 
                              e.stopPropagation(); 
                              const a = document.createElement("a");
                              a.href = getAdminMediaStreamUrl(item.id);
                              a.download = item.filename;
                              a.click();
                            }}
                          >
                            <Download className="h-3.5 w-3.5 mr-2" /> Download Binary
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            className="text-destructive focus:text-destructive"
                            onClick={(e) => { e.stopPropagation(); handleDeleteItem(item.id); }}
                            disabled={deletingId === item.id}
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-2" /> Delete Asset
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    {item.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2 min-w-0">
                        {item.description}
                      </p>
                    )}

                    <div className="flex flex-col gap-1.5 mt-auto pt-2.5 border-t text-xs min-w-0 w-full">
                      <div className="flex items-center justify-between text-muted-foreground text-[11px] min-w-0 w-full">
                        <span className="font-mono text-[10px] truncate max-w-[130px]">{item.content_type}</span>
                        <span>{new Date(item.created_at).toLocaleDateString()}</span>
                      </div>

                      <div className="flex items-center gap-1.5 text-muted-foreground min-w-0 w-full">
                        <UserRoundCog className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground truncate min-w-0 flex-1">
                          {getProviderName(item.provider_id)}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            /* List View */
            <div className="rounded-xl border overflow-hidden bg-card w-full min-w-0">
              <div className="divide-y min-w-0">
                {filteredMediaItems.map((item) => (
                  <div 
                    key={item.id} 
                    className="p-3 flex items-center justify-between gap-3 hover:bg-muted/30 transition-colors cursor-pointer min-w-0 w-full"
                    onClick={() => setSelectedItem(item)}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="h-12 w-16 rounded overflow-hidden bg-muted shrink-0 relative flex items-center justify-center">
                        <MediaPreviewThumbnail item={item} />
                      </div>

                      <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                        <div className="flex items-center gap-2 min-w-0 flex-wrap">
                          <h4 className="font-semibold text-sm truncate min-w-0">{item.title || item.filename}</h4>
                          <Badge variant="outline" className="text-[9px] uppercase py-0 h-4 font-mono shrink-0">
                            {item.content_type}
                          </Badge>
                          {item.is_public_website_eligible ? (
                            <Badge className="bg-emerald-600 text-white text-[9px] py-0 h-4 gap-1">
                              <Globe className="h-2.5 w-2.5" /> Website Eligible
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-amber-500 border-amber-500/40 text-[9px] py-0 h-4 gap-1">
                              <Lock className="h-2.5 w-2.5" /> Internal
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate min-w-0">
                          {item.description || item.filename}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span className="font-mono text-xs text-muted-foreground hidden sm:inline">
                        {formatMediaFileSize(item.file_size)}
                      </span>

                      {item.notes && (
                        <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground" title="Internal notes attached">
                          <MessageSquare className="h-3.5 w-3.5 text-primary" />
                        </div>
                      )}

                      <div className="hidden md:flex flex-col text-right text-xs max-w-[150px] min-w-0">
                        <span className="font-medium text-foreground truncate min-w-0">{getProviderName(item.provider_id)}</span>
                        <span className="text-muted-foreground text-[10px] truncate min-w-0">{new Date(item.created_at).toLocaleDateString()}</span>
                      </div>

                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="h-7 text-xs"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleToggleEligibility(item)
                        }}
                        disabled={togglingEligibilityId === item.id}
                      >
                        {item.is_public_website_eligible ? "Make Private" : "Approve"}
                      </Button>

                      <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setSelectedItem(item); }}>
                        View
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </TabsContent>

        {/* ── TAB 2: LIBRARIES & ALBUMS ─────────────────────────────────── */}
        <TabsContent value="albums" className="mt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 w-full min-w-0">
            {albums.map((album) => {
              const provider = providers.find(p => String(p.id) === String(album.providerId))

              return (
                <Card key={album.id} className="overflow-hidden flex flex-col justify-between hover:shadow-md transition-all border-muted min-w-0 w-full">
                  <div className="relative h-44 w-full bg-slate-900 overflow-hidden shrink-0">
                    <img 
                      src={album.coverUrl || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"} 
                      alt={album.name}
                      className="w-full h-full object-cover opacity-85 hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
                    
                    <div className="absolute bottom-3 left-3 right-3 text-white flex items-end justify-between min-w-0">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-bold text-lg leading-tight truncate min-w-0">{album.name}</h3>
                      </div>
                    </div>
                  </div>

                  <CardContent className="p-4 flex flex-col gap-3 flex-1 min-w-0 w-full">
                    <p className="text-xs text-muted-foreground line-clamp-2 min-w-0">
                      {album.description || "No album description provided."}
                    </p>

                    {album.shortUrl && (
                      <div className="p-2 rounded bg-muted/40 border flex items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-1.5 min-w-0 text-muted-foreground font-mono text-[11px] truncate">
                          <LinkIcon className="h-3.5 w-3.5 text-primary shrink-0" />
                          <span className="truncate">{album.shortUrl}</span>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="icon-sm"
                          className="h-6 w-6 text-primary hover:bg-primary/10 shrink-0"
                          onClick={() => handleCopyShortUrl(album.shortUrl!, album.name)}
                          title="Copy Album Short Link"
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    )}

                    <div className="mt-auto pt-3 border-t flex items-center justify-between text-xs min-w-0 w-full">
                      <div className="flex items-center gap-1.5 text-muted-foreground min-w-0 flex-1">
                        <UserRoundCog className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground truncate min-w-0 flex-1">
                          {provider ? provider.name : "Unassigned Provider"}
                        </span>
                      </div>

                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-7 text-xs gap-1 shrink-0"
                        onClick={() => {
                          setSelectedAlbumId(album.id)
                          setActiveTab("all-media")
                        }}
                      >
                        View Items &rarr;
                      </Button>
                    </div>
                  </CardContent>

                  <CardFooter className="bg-muted/20 px-4 py-2 flex items-center justify-between border-t text-[11px] text-muted-foreground shrink-0">
                    <span>Created: {new Date(album.createdAt).toLocaleDateString()}</span>
                    <button 
                      onClick={() => handleDeleteAlbum(album.id)}
                      className="text-destructive hover:underline flex items-center gap-1"
                    >
                      <Trash2 className="h-3 w-3" /> Remove Album
                    </button>
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        </TabsContent>
      </Tabs>

      {/* ── MEDIA DETAIL & PREVIEW DIALOG ──────────────────────────────────── */}
      {selectedItem && (
        <Dialog open={!!selectedItem} onOpenChange={(open) => !open && setSelectedItem(null)}>
          <DialogContent className="sm:max-w-3xl max-h-[92vh] overflow-y-auto flex flex-col gap-4">
            <DialogHeader className="text-left border-b pb-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="uppercase text-[10px]">
                    {selectedItem.media_type}
                  </Badge>
                  {selectedItem.is_public_website_eligible ? (
                    <Badge className="bg-emerald-600 text-white gap-1 text-[10px]">
                      <Globe className="h-3 w-3" /> Public Website Eligible
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="border-amber-500/50 text-amber-500 gap-1 text-[10px]">
                      <Lock className="h-3 w-3" /> Internal Only (Private)
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    Uploaded {new Date(selectedItem.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <DialogTitle className="text-xl font-bold mt-1">
                {selectedItem.title || selectedItem.filename}
              </DialogTitle>
              {selectedItem.description && (
                <DialogDescription className="text-xs">
                  {selectedItem.description}
                </DialogDescription>
              )}
            </DialogHeader>

            {/* Quick Actions Card inside Modal */}
            <div className="p-3 rounded-lg border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shadow-2xs">
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5 text-primary" /> Stored Asset Reference
                </span>
                <span className="font-mono text-xs text-foreground truncate">
                  {selectedItem.filename} ({formatMediaFileSize(selectedItem.file_size)} • {selectedItem.content_type})
                </span>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button 
                  variant={selectedItem.is_public_website_eligible ? "secondary" : "default"}
                  size="sm" 
                  className="h-8 text-xs gap-1.5"
                  onClick={() => handleToggleEligibility(selectedItem)}
                  disabled={togglingEligibilityId === selectedItem.id}
                >
                  <Globe className="h-3.5 w-3.5 text-emerald-500" />
                  <span>{selectedItem.is_public_website_eligible ? "Revoke Website Approval" : "Approve for Public Website"}</span>
                </Button>
              </div>
            </div>

            {/* Full Image / Video Display Container with Backend Streaming */}
            <div className="rounded-xl overflow-hidden bg-slate-950/95 border p-2 flex items-center justify-center min-h-[300px] max-h-[500px] w-full relative shadow-inner">
              {selectedItem.media_type === "video" ? (
                <video 
                  src={selectedItem.url || getAdminMediaStreamUrl(selectedItem.id)} 
                  controls 
                  className="w-full max-h-[460px] object-contain rounded"
                />
              ) : selectedItem.media_type === "document" ? (
                <div className="flex flex-col items-center justify-center gap-3 p-8 text-center text-white">
                  <FileText className="h-16 w-16 text-primary opacity-80" />
                  <p className="text-sm font-semibold">{selectedItem.filename}</p>
                  <p className="text-xs text-muted-foreground">PDF Document ({formatMediaFileSize(selectedItem.file_size)})</p>
                  <Button 
                    variant="outline" 
                    size="sm"
                    className="mt-2 text-xs gap-1.5"
                    onClick={() => {
                      window.open(getAdminMediaStreamUrl(selectedItem.id), "_blank")
                    }}
                  >
                    <Download className="h-3.5 w-3.5" /> Open / Download Document
                  </Button>
                </div>
              ) : (
                <div className="relative flex items-center justify-center overflow-hidden max-w-full max-h-[460px]">
                  <img 
                    src={selectedItem.url || getAdminMediaStreamUrl(selectedItem.id)} 
                    alt={selectedItem.title || selectedItem.filename} 
                    className="max-w-full max-h-[460px] w-auto h-auto object-contain rounded" 
                    onError={(e) => {
                      // If public URL fails due to privacy, stream through admin endpoint
                      fetchMediaBlobUrl(selectedItem.id).then((url) => {
                        (e.target as HTMLImageElement).src = url
                      }).catch(() => {
                        // ignore
                      })
                    }}
                  />
                </div>
              )}
            </div>

            {/* Provider and Metadata */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-lg border bg-muted/20 text-xs">
              <div className="grid gap-1">
                <span className="font-semibold text-muted-foreground flex items-center gap-1">
                  <UserRoundCog className="h-3.5 w-3.5 text-primary" /> Associated Provider
                </span>
                <span className="font-medium text-foreground">
                  {getProviderName(selectedItem.provider_id)}
                </span>
              </div>

              <div className="grid gap-1">
                <span className="font-semibold text-muted-foreground flex items-center gap-1">
                  <Globe className="h-3.5 w-3.5 text-emerald-500" /> Public Website URL
                </span>
                {selectedItem.is_public_website_eligible ? (
                  <span className="font-mono text-emerald-500 truncate" title={selectedItem.url}>
                    {selectedItem.url}
                  </span>
                ) : (
                  <span className="text-muted-foreground italic">
                    Not public (URL inactive until marked eligible)
                  </span>
                )}
              </div>
            </div>

            {/* Private Notes Section */}
            <div className="flex flex-col gap-2 border-t pt-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  Internal / Clinical Notes
                </h3>
                <Badge variant="outline" className="text-[10px] text-muted-foreground border-slate-700">
                  <Lock className="h-2.5 w-2.5 mr-1" /> Confidential
                </Badge>
              </div>

              {selectedItem.notes ? (
                <div className="p-3 rounded-lg bg-card border text-xs whitespace-pre-wrap leading-relaxed">
                  {selectedItem.notes}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic p-3 border border-dashed rounded text-center">
                  No internal notes attached to this media asset.
                </p>
              )}
              <p className="text-[10px] text-muted-foreground">
                Notes are confidential and strictly excluded from assistant tool context and public website rendering.
              </p>
            </div>

            <DialogFooter className="border-t pt-3 flex items-center justify-between sm:justify-between w-full">
              <Button 
                variant="destructive" 
                size="sm" 
                onClick={() => handleDeleteItem(selectedItem.id)} 
                disabled={deletingId === selectedItem.id}
                className="gap-1.5 text-xs"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>{deletingId === selectedItem.id ? "Deleting..." : "Delete Asset"}</span>
              </Button>

              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setSelectedItem(null)}
                  className="text-xs"
                >
                  Close
                </Button>
                <Button 
                  variant="default" 
                  size="sm" 
                  onClick={() => {
                    const a = document.createElement("a")
                    a.href = getAdminMediaStreamUrl(selectedItem.id)
                    a.download = selectedItem.filename
                    a.click()
                  }}
                  className="gap-1.5 text-xs"
                >
                  <Download className="h-3.5 w-3.5" /> Download
                </Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

    </div>
  )
}
