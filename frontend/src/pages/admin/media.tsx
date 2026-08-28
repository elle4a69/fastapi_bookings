import { useState, useEffect, useMemo, type ChangeEvent } from "react"
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
  Wand2,
  RotateCcw,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
  Sun,
  Contrast,
  Undo,
  Save,
  Crop,
  Link as LinkIcon,
  Copy,
  Share2,
  Clock,
  Lock
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

export interface MediaNote {
  id: string
  author: string
  text: string
  timestamp: string
}

export interface MediaItem {
  id: string
  title: string
  type: "image" | "video"
  url: string
  fileSize?: string
  mimeType?: string
  albumId?: string
  providerId?: string
  description?: string
  notes: MediaNote[]
  uploadedAt: string
  shortUrl?: string
  isGuestUpload?: boolean
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
  type: "image" | "video"
  url: string
  fileSize: string
}

const STORAGE_KEY_MEDIA = "fastapi_bookings_media_items_v1"
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

const INITIAL_MEDIA_ITEMS: MediaItem[] = [
  {
    id: "med-1",
    title: "Post-Treatment Dermal Scan",
    type: "image",
    url: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800&auto=format&fit=crop&q=80",
    fileSize: "2.4 MB",
    mimeType: "image/jpeg",
    albumId: "alb-1",
    providerId: "prov-1",
    description: "High-resolution dermal imaging captured after session #3.",
    notes: [
      { id: "n-1", author: "Dr. Sarah Jenkins", text: "Notice significant collagen improvement in targeted cheek zone.", timestamp: "2026-08-02 11:20 AM" },
      { id: "n-2", author: "Client Coordinator", text: "Approved by client for clinical tracking portfolio.", timestamp: "2026-08-03 04:15 PM" }
    ],
    uploadedAt: "2026-08-02T11:00:00Z",
    shortUrl: "http://localhost:8002/api/v1/med-1"
  },
  {
    id: "med-2",
    title: "Laser Skin Resurfacing Walkthrough",
    type: "video",
    url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    fileSize: "14.8 MB",
    mimeType: "video/mp4",
    albumId: "alb-2",
    providerId: "prov-2",
    description: "Video recording explaining proper post-laser skincare routine.",
    notes: [
      { id: "n-3", author: "Alex Rivera", text: "Video tutorial sent to client via notification email.", timestamp: "2026-08-05 09:45 AM" }
    ],
    uploadedAt: "2026-08-05T09:30:00Z",
    shortUrl: "http://localhost:8002/api/v1/med-2"
  },
  {
    id: "med-3",
    title: "HydraFacial Glow Session",
    type: "image",
    url: "https://images.unsplash.com/photo-1512290900673-7002fffe935a?w=800&auto=format&fit=crop&q=80",
    fileSize: "1.8 MB",
    mimeType: "image/png",
    albumId: "alb-2",
    providerId: "prov-2",
    description: "Hydration treatment completion photography.",
    notes: [],
    uploadedAt: "2026-08-06T15:10:00Z",
    shortUrl: "http://localhost:8002/api/v1/med-3"
  },
  {
    id: "med-4",
    title: "Provider Studio Workspace Showcase",
    type: "image",
    url: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800&auto=format&fit=crop&q=80",
    fileSize: "3.1 MB",
    mimeType: "image/jpeg",
    albumId: "alb-3",
    providerId: "prov-3",
    description: "Sterile treatment room layout for wellness consultations.",
    notes: [
      { id: "n-4", author: "Elena Rostova", text: "Updated for updated website booking page banner.", timestamp: "2026-08-07 02:00 PM" }
    ],
    uploadedAt: "2026-08-07T13:45:00Z",
    shortUrl: "http://localhost:8002/api/v1/med-4"
  }
]

// Short URL Service Generator Helper
export async function createShortUrl(longUrl: string, _resourceId?: string, _prefix?: "med" | "alb" | "upl"): Promise<string> {
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

export default function MediaPage() {
  const [providers, setProviders] = useState<ServiceProvider[]>(DEFAULT_PROVIDERS)
  const [albums, setAlbums] = useState<MediaAlbum[]>([])
  const [mediaItems, setMediaItems] = useState<MediaItem[]>([])
  const [publicLinks, setPublicLinks] = useState<PublicUploadLink[]>([])

  // Filtering state
  const [selectedAlbumId, setSelectedAlbumId] = useState<string>("all")
  const [selectedProviderId, setSelectedProviderId] = useState<string>("all")
  const [mediaTypeFilter, setMediaTypeFilter] = useState<"all" | "image" | "video">("all")
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [activeTab, setActiveTab] = useState<string>("all-media")

  // Modal & Editor state
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [isNewAlbumOpen, setIsNewAlbumOpen] = useState(false)
  const [isPublicLinkOpen, setIsPublicLinkOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<MediaItem | null>(null)
  const [newNoteText, setNewNoteText] = useState("")

  // Public Link Generator State
  const [linkExpiryDuration, setLinkExpiryDuration] = useState<string>("24h")
  const [linkMaxUploads, setLinkMaxUploads] = useState<string>("5")
  const [linkTargetAlbumId, setLinkTargetAlbumId] = useState<string>("none")
  const [linkTargetProviderId, setLinkTargetProviderId] = useState<string>("none")
  const [createdPublicLink, setCreatedPublicLink] = useState<PublicUploadLink | null>(null)

  // Image Editor States
  const [isEditingImage, setIsEditingImage] = useState(false)
  const [rotation, setRotation] = useState<number>(0)
  const [flipH, setFlipH] = useState<boolean>(false)
  const [flipV, setFlipV] = useState<boolean>(false)
  const [brightness, setBrightness] = useState<number>(100)
  const [contrast, setContrast] = useState<number>(100)
  const [saturation, setSaturation] = useState<number>(100)
  const [grayscale, setGrayscale] = useState<number>(0)
  const [sepia, setSepia] = useState<number>(0)

  // Aspect Ratio & Crop States
  const [cropAspect, setCropAspect] = useState<"free" | "1:1" | "4:3" | "16:9" | "3:4" | "9:16">("free")
  const [cropScale, setCropScale] = useState<number>(100)
  const [cropPosition, setCropPosition] = useState<"center" | "top" | "bottom" | "left" | "right">("center")
  const [isSavingEdits, setIsSavingEdits] = useState(false)

  // Form states - Multi-File Upload Queue
  const [uploadQueue, setUploadQueue] = useState<QueuedUploadItem[]>([])
  const [uploadAlbumId, setUploadAlbumId] = useState<string>("none")
  const [uploadProviderId, setUploadProviderId] = useState<string>("none")
  const [uploadDescription, setUploadDescription] = useState("")
  const [uploadNote, setUploadNote] = useState("")
  const [isBatchUploading, setIsBatchUploading] = useState(false)

  // Form states - New Album
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

  // Load Albums, Media Items, & Public Links from localStorage
  useEffect(() => {
    async function initData() {
      let loadedAlbums: MediaAlbum[] = INITIAL_ALBUMS
      const savedAlbums = localStorage.getItem(STORAGE_KEY_ALBUMS)
      if (savedAlbums) {
        try {
          loadedAlbums = JSON.parse(savedAlbums)
        } catch {
          loadedAlbums = INITIAL_ALBUMS
        }
      }

      const updatedAlbums = await Promise.all(
        loadedAlbums.map(async (alb) => {
          if (!alb.shortUrl) {
            const shortUrl = await createShortUrl(alb.coverUrl || `http://localhost:7070/admin/media?album=${alb.id}`, alb.id, "alb")
            return { ...alb, shortUrl }
          }
          return alb
        })
      )
      setAlbums(updatedAlbums)
      localStorage.setItem(STORAGE_KEY_ALBUMS, JSON.stringify(updatedAlbums))

      let loadedMedia: MediaItem[] = INITIAL_MEDIA_ITEMS
      const savedMedia = localStorage.getItem(STORAGE_KEY_MEDIA)
      if (savedMedia) {
        try {
          loadedMedia = JSON.parse(savedMedia)
        } catch {
          loadedMedia = INITIAL_MEDIA_ITEMS
        }
      }

      const updatedMedia = await Promise.all(
        loadedMedia.map(async (item) => {
          if (!item.shortUrl) {
            const shortUrl = await createShortUrl(item.url, item.id, "med")
            return { ...item, shortUrl }
          }
          return item
        })
      )
      setMediaItems(updatedMedia)
      localStorage.setItem(STORAGE_KEY_MEDIA, JSON.stringify(updatedMedia))

      const savedLinksRaw = localStorage.getItem(STORAGE_KEY_PUBLIC_LINKS)
      if (savedLinksRaw) {
        try {
          setPublicLinks(JSON.parse(savedLinksRaw))
        } catch {
          setPublicLinks([])
        }
      }
    }

    initData()
  }, [])

  // Reset Editor States when Selected Item changes
  useEffect(() => {
    if (selectedItem) {
      setIsEditingImage(false)
      resetEditorParams()
    }
  }, [selectedItem?.id])

  const resetEditorParams = () => {
    setRotation(0)
    setFlipH(false)
    setFlipV(false)
    setBrightness(100)
    setContrast(100)
    setSaturation(100)
    setGrayscale(0)
    setSepia(0)
    setCropAspect("free")
    setCropScale(100)
    setCropPosition("center")
  }

  // Persist Changes
  const saveAlbums = (updated: MediaAlbum[]) => {
    setAlbums(updated)
    localStorage.setItem(STORAGE_KEY_ALBUMS, JSON.stringify(updated))
  }

  const saveMediaItems = (updated: MediaItem[]) => {
    setMediaItems(updated)
    localStorage.setItem(STORAGE_KEY_MEDIA, JSON.stringify(updated))
  }

  const savePublicLinks = (updated: PublicUploadLink[]) => {
    setPublicLinks(updated)
    localStorage.setItem(STORAGE_KEY_PUBLIC_LINKS, JSON.stringify(updated))
  }

  // Copy Short Link to Clipboard
  const handleCopyShortUrl = (shortUrl: string, label: string) => {
    navigator.clipboard.writeText(shortUrl)
    toast.success(`${label} short link copied to clipboard!`)
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
    savePublicLinks(updated)
    setCreatedPublicLink(newLink)
    toast.success("Public Upload Portal Link generated with expiry protection!")
  }

  // Revoke Public Link
  const handleRevokePublicLink = (linkId: string) => {
    const updated = publicLinks.filter(l => l.id !== linkId)
    savePublicLinks(updated)
    toast.success("Public upload link revoked.")
  }

  // Handle Multi-File Selection
  const handleMultiFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return

    const filesArr = Array.from(e.target.files)

    filesArr.forEach((file, index) => {
      const isVideo = file.type.startsWith("video/")
      const itemTitle = file.name.replace(/\.[^/.]+$/, "")
      const itemSize = `${(file.size / (1024 * 1024)).toFixed(1)} MB`

      const reader = new FileReader()
      reader.onload = (evt) => {
        const dataUrl = evt.target?.result as string || ""
        setUploadQueue(prev => [
          ...prev,
          {
            id: `q-${Date.now()}-${index}-${Math.random().toString(36).substr(2, 4)}`,
            file,
            title: itemTitle,
            type: isVideo ? "video" : "image",
            url: dataUrl,
            fileSize: itemSize
          }
        ])
      }
      reader.readAsDataURL(file)
    })
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
    saveAlbums(updated)
    toast.success(`Album "${newAlbum.name}" created with assigned Short Link!`)

    setAlbumName("")
    setAlbumDescription("")
    setAlbumProviderId("none")
    setAlbumCoverUrl("")
    setIsNewAlbumOpen(false)
  }

  // Submit Multi-File Batch Upload
  const handleBatchUploadSubmit = async () => {
    if (uploadQueue.length === 0) return
    setIsBatchUploading(true)

    try {
      let finalProviderId = uploadProviderId !== "none" ? uploadProviderId : undefined
      if (!finalProviderId && uploadAlbumId !== "none") {
        const targetAlbum = albums.find(a => a.id === uploadAlbumId)
        if (targetAlbum?.providerId) {
          finalProviderId = targetAlbum.providerId
        }
      }

      const createdItems: MediaItem[] = []

      for (let i = 0; i < uploadQueue.length; i++) {
        const qItem = uploadQueue[i]
        const newId = `med-${Date.now()}-${i}`
        const finalUrl = qItem.url || (qItem.type === "video" 
          ? "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
          : "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800&auto=format&fit=crop&q=80")

        const generatedShortUrl = await createShortUrl(finalUrl, newId, "med")

        const initialNotesList: MediaNote[] = []
        if (uploadNote.trim()) {
          initialNotesList.push({
            id: `n-${Date.now()}-${i}`,
            author: "Admin User",
            text: uploadNote.trim(),
            timestamp: new Date().toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
          })
        }

        const newItem: MediaItem = {
          id: newId,
          title: qItem.title.trim() || `Uploaded File #${i + 1}`,
          type: qItem.type,
          url: finalUrl,
          fileSize: qItem.fileSize,
          mimeType: qItem.file.type || (qItem.type === "video" ? "video/mp4" : "image/jpeg"),
          albumId: uploadAlbumId !== "none" ? uploadAlbumId : undefined,
          providerId: finalProviderId,
          description: uploadDescription.trim() || undefined,
          notes: initialNotesList,
          uploadedAt: new Date().toISOString(),
          shortUrl: generatedShortUrl
        }

        createdItems.push(newItem)
      }

      const updated = [...createdItems, ...mediaItems]
      saveMediaItems(updated)
      toast.success(`Successfully uploaded ${createdItems.length} media asset${createdItems.length > 1 ? "s" : ""}!`)

      // Update album cover if needed
      if (uploadAlbumId !== "none") {
        const firstPhoto = createdItems.find(i => i.type === "image")
        if (firstPhoto) {
          const albumIdx = albums.findIndex(a => a.id === uploadAlbumId)
          if (albumIdx !== -1 && !albums[albumIdx].coverUrl) {
            const updatedAlbums = [...albums]
            updatedAlbums[albumIdx].coverUrl = firstPhoto.url
            saveAlbums(updatedAlbums)
          }
        }
      }

      // Reset Form
      setUploadQueue([])
      setUploadAlbumId("none")
      setUploadProviderId("none")
      setUploadDescription("")
      setUploadNote("")
      setIsUploadOpen(false)
    } catch (err) {
      console.error("Batch upload failed:", err)
      toast.error("Failed to upload files.")
    } finally {
      setIsBatchUploading(false)
    }
  }

  // Add Note to Item
  const handleAddNote = () => {
    if (!selectedItem || !newNoteText.trim()) return

    const newNote: MediaNote = {
      id: `n-${Date.now()}`,
      author: "Admin User",
      text: newNoteText.trim(),
      timestamp: new Date().toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
    }

    const updatedItem = {
      ...selectedItem,
      notes: [...selectedItem.notes, newNote]
    }

    const updatedList = mediaItems.map(m => m.id === selectedItem.id ? updatedItem : m)
    saveMediaItems(updatedList)
    setSelectedItem(updatedItem)
    setNewNoteText("")
  }

  // Delete Item
  const handleDeleteItem = (id: string) => {
    const updated = mediaItems.filter(m => m.id !== id)
    saveMediaItems(updated)
    if (selectedItem?.id === id) {
      setSelectedItem(null)
    }
  }

  // Delete Album
  const handleDeleteAlbum = (albumId: string) => {
    const updatedAlbums = albums.filter(a => a.id !== albumId)
    saveAlbums(updatedAlbums)

    const updatedItems = mediaItems.map(m => m.albumId === albumId ? { ...m, albumId: undefined } : m)
    saveMediaItems(updatedItems)
  }

  // Update Media Provider / Album Assignment
  const handleUpdateItemAssignment = (itemId: string, field: "providerId" | "albumId", value: string) => {
    const targetValue = value === "none" ? undefined : value
    const updatedList = mediaItems.map(m => {
      if (m.id === itemId) {
        return { ...m, [field]: targetValue }
      }
      return m
    })
    saveMediaItems(updatedList)
    if (selectedItem?.id === itemId) {
      setSelectedItem(prev => prev ? { ...prev, [field]: targetValue } : null)
    }
  }

  // Save Canvas Image Edits + Aspect Ratio Cropping
  const handleSaveImageEdits = async () => {
    if (!selectedItem || selectedItem.type !== "image") return
    setIsSavingEdits(true)

    try {
      const img = new Image()
      img.crossOrigin = "anonymous"
      
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve()
        img.onerror = () => reject()
        img.src = selectedItem.url
      })

      const tempCanvas = document.createElement("canvas")
      const tempCtx = tempCanvas.getContext("2d")
      if (!tempCtx) {
        setIsSavingEdits(false)
        return
      }

      const isQuarterTurn = Math.abs(rotation / 90) % 2 === 1
      tempCanvas.width = isQuarterTurn ? img.height : img.width
      tempCanvas.height = isQuarterTurn ? img.width : img.height

      tempCtx.save()
      tempCtx.translate(tempCanvas.width / 2, tempCanvas.height / 2)
      tempCtx.rotate((rotation * Math.PI) / 180)
      tempCtx.scale(flipH ? -1 : 1, flipV ? -1 : 1)
      tempCtx.filter = `brightness(${brightness}%) contrast(${contrast}%) saturate(${saturation}%) grayscale(${grayscale}%) sepia(${sepia}%)`
      tempCtx.drawImage(img, -img.width / 2, -img.height / 2)
      tempCtx.restore()

      let cropWidth = tempCanvas.width * (cropScale / 100)
      let cropHeight = tempCanvas.height * (cropScale / 100)

      if (cropAspect !== "free") {
        let targetRatio = 1
        if (cropAspect === "1:1") targetRatio = 1
        else if (cropAspect === "4:3") targetRatio = 4 / 3
        else if (cropAspect === "16:9") targetRatio = 16 / 9
        else if (cropAspect === "3:4") targetRatio = 3 / 4
        else if (cropAspect === "9:16") targetRatio = 9 / 16

        if (cropWidth / cropHeight > targetRatio) {
          cropWidth = cropHeight * targetRatio
        } else {
          cropHeight = cropWidth / targetRatio
        }
      }

      let srcX = (tempCanvas.width - cropWidth) / 2
      let srcY = (tempCanvas.height - cropHeight) / 2

      if (cropPosition === "top") srcY = 0
      else if (cropPosition === "bottom") srcY = tempCanvas.height - cropHeight
      else if (cropPosition === "left") srcX = 0
      else if (cropPosition === "right") srcX = tempCanvas.width - cropWidth

      const finalCanvas = document.createElement("canvas")
      finalCanvas.width = cropWidth
      finalCanvas.height = cropHeight
      const finalCtx = finalCanvas.getContext("2d")
      if (!finalCtx) {
        setIsSavingEdits(false)
        return
      }

      finalCtx.drawImage(
        tempCanvas,
        srcX, srcY, cropWidth, cropHeight,
        0, 0, cropWidth, cropHeight
      )

      const editedDataUrl = finalCanvas.toDataURL("image/jpeg", 0.92)
      
      const updatedItem = { ...selectedItem, url: editedDataUrl }
      const updatedList = mediaItems.map(m => m.id === selectedItem.id ? updatedItem : m)
      saveMediaItems(updatedList)
      setSelectedItem(updatedItem)
      setIsEditingImage(false)
      resetEditorParams()
      toast.success("Image crop & filters saved!")
    } catch (err) {
      console.error("Failed to render canvas image edits:", err)
      toast.error("Failed to save image edits.")
    } finally {
      setIsSavingEdits(false)
    }
  }

  // Filtered Items
  const filteredMediaItems = useMemo(() => {
    return mediaItems.filter(item => {
      if (selectedAlbumId !== "all") {
        if (selectedAlbumId === "unassigned" && item.albumId) return false
        if (selectedAlbumId !== "unassigned" && item.albumId !== selectedAlbumId) return false
      }

      if (selectedProviderId !== "all") {
        if (selectedProviderId === "unassigned" && item.providerId) return false
        if (selectedProviderId !== "unassigned" && item.providerId !== selectedProviderId) return false
      }

      if (mediaTypeFilter !== "all" && item.type !== mediaTypeFilter) return false

      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        const matchTitle = item.title.toLowerCase().includes(query)
        const matchDesc = item.description?.toLowerCase().includes(query)
        const matchNotes = item.notes.some(n => n.text.toLowerCase().includes(query) || n.author.toLowerCase().includes(query))
        if (!matchTitle && !matchDesc && !matchNotes) return false
      }

      return true
    })
  }, [mediaItems, selectedAlbumId, selectedProviderId, mediaTypeFilter, searchQuery])

  // Get Provider Name Helper
  const getProviderName = (providerId?: string) => {
    if (!providerId) return "Unassigned Provider"
    const p = providers.find(prov => String(prov.id) === String(providerId))
    return p ? p.name : `Provider #${providerId}`
  }

  // Get Album Name Helper
  const getAlbumName = (albumId?: string) => {
    if (!albumId) return "Unassigned Library"
    const a = albums.find(alb => alb.id === albumId)
    return a ? a.name : "Unknown Library"
  }

  // CSS Filter string for preview
  const cssFilterPreview = `brightness(${brightness}%) contrast(${contrast}%) saturate(${saturation}%) grayscale(${grayscale}%) sepia(${sepia}%)`

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
            Manage photographs, multi-file uploads, organize into albums, generate public upload links with auto-destruction rules, and assign items to service providers.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
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
                      <SelectTrigger id="link-expiry" className="h-9">
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
                      <SelectTrigger id="link-max-uploads" className="h-9">
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
                      <SelectTrigger id="link-target-album" className="h-9">
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
                      <SelectTrigger id="link-target-provider" className="h-9">
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
                    <SelectTrigger id="album-provider">
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
                  Multi-File Media Upload
                </DialogTitle>
                <DialogDescription>
                  Select multiple photographs or videos to upload in batch. Each file receives its own short URL.
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
                      accept="image/*,video/*" 
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
                        Click to select multiple files or drag & drop here
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Supports JPG, PNG, WEBP, MP4, WEBM (Upload multiple items at once)
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
                        <div key={item.id} className="p-2.5 rounded-md bg-card border flex items-center gap-3 text-xs">
                          <div className="h-10 w-12 rounded bg-muted overflow-hidden shrink-0 flex items-center justify-center">
                            {item.type === "video" ? (
                              <Film className="h-5 w-5 text-primary" />
                            ) : (
                              <img src={item.url} alt={item.title} className="w-full h-full object-cover" />
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
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-2">
                    <Label htmlFor="upload-album">Target Library / Album</Label>
                    <Select value={uploadAlbumId} onValueChange={setUploadAlbumId}>
                      <SelectTrigger id="upload-album">
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

                  <div className="grid gap-2">
                    <Label htmlFor="upload-provider">Assigned Service Provider</Label>
                    <Select value={uploadProviderId} onValueChange={setUploadProviderId}>
                      <SelectTrigger id="upload-provider">
                        <SelectValue placeholder="Select Service Provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Default / Inherit from Album</SelectItem>
                        {providers.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="upload-desc">Description (Applies to Batch)</Label>
                  <Input 
                    id="upload-desc" 
                    placeholder="Brief description for these media assets..." 
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="upload-note">Communication Note (Applies to Batch)</Label>
                  <Textarea 
                    id="upload-note" 
                    placeholder="Add text notes or instructions for staff..." 
                    value={uploadNote}
                    onChange={(e) => setUploadNote(e.target.value)}
                    rows={2}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsUploadOpen(false)}>Cancel</Button>
                <Button 
                  onClick={handleBatchUploadSubmit} 
                  disabled={uploadQueue.length === 0 || isBatchUploading}
                  className="gap-1.5 font-semibold"
                >
                  <Upload className="h-4 w-4" />
                  <span>{isBatchUploading ? "Uploading Batch..." : `Upload ${uploadQueue.length} Asset${uploadQueue.length > 1 ? "s" : ""}`}</span>
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
              <div className="relative flex-1 min-w-[200px] max-w-md">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search media, notes, text..."
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

              <div className="w-full sm:w-auto min-w-[160px]">
                <Select value={selectedProviderId} onValueChange={setSelectedProviderId}>
                  <SelectTrigger className="h-9 text-xs">
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

              <div className="w-full sm:w-auto min-w-[170px]">
                <Select value={selectedAlbumId} onValueChange={setSelectedAlbumId}>
                  <SelectTrigger className="h-9 text-xs">
                    <Folder className="h-3.5 w-3.5 mr-1.5 text-muted-foreground shrink-0" />
                    <SelectValue placeholder="All Libraries" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Libraries</SelectItem>
                    <SelectItem value="unassigned">Unassigned</SelectItem>
                    {albums.map(a => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="w-full sm:w-auto min-w-[130px]">
                <Select value={mediaTypeFilter} onValueChange={(val: any) => setMediaTypeFilter(val)}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="All Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Media</SelectItem>
                    <SelectItem value="image">Photos Only</SelectItem>
                    <SelectItem value="video">Videos Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── TAB 1: ALL MEDIA ITEMS ────────────────────────────────────── */}
        <TabsContent value="all-media" className="mt-0">
          
          {(selectedAlbumId !== "all" || selectedProviderId !== "all" || mediaTypeFilter !== "all" || searchQuery) && (
            <div className="flex items-center gap-2 mb-4 flex-wrap text-xs bg-muted/20 p-2.5 rounded-lg border">
              <span className="text-muted-foreground font-medium">Active Filters:</span>
              {selectedAlbumId !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs">
                  Library: {selectedAlbumId === "unassigned" ? "Unassigned" : getAlbumName(selectedAlbumId)}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setSelectedAlbumId("all")} />
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
                  setMediaTypeFilter("all")
                  setSearchQuery("")
                }}
              >
                Reset All Filters
              </Button>
            </div>
          )}

          {filteredMediaItems.length === 0 ? (
            <div className="rounded-xl border border-dashed p-12 text-center flex flex-col items-center gap-3 bg-muted/10">
              <div className="p-4 rounded-full bg-muted">
                <ImageIcon className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold">No media items found</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                No photographs or videos match your current filter options. Try uploading a new media file or adjusting your search.
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
                    {item.type === "video" ? (
                      <div className="relative w-full h-full flex items-center justify-center bg-slate-900 text-white">
                        <Film className="h-10 w-10 opacity-75 group-hover:scale-110 transition-transform" />
                        <Badge className="absolute top-2.5 right-2.5 bg-black/70 backdrop-blur-sm gap-1 text-[10px]">
                          <Film className="h-3 w-3" /> VIDEO
                        </Badge>
                      </div>
                    ) : (
                      <img 
                        src={item.url} 
                        alt={item.title} 
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=600&auto=format&fit=crop&q=80"
                        }}
                      />
                    )}

                    {item.isGuestUpload && (
                      <Badge className="absolute top-2.5 left-2.5 bg-emerald-600 text-white gap-1 text-[9px] shadow-sm">
                        <Upload className="h-2.5 w-2.5" /> Public Upload
                      </Badge>
                    )}

                    {item.notes.length > 0 && (
                      <Badge className="absolute bottom-2.5 left-2.5 bg-primary/90 text-primary-foreground gap-1 text-[10px]">
                        <MessageSquare className="h-3 w-3" />
                        <span>{item.notes.length} note{item.notes.length > 1 ? "s" : ""}</span>
                      </Badge>
                    )}
                  </div>

                  <CardContent className="p-3.5 flex flex-col gap-2 flex-1 min-w-0 w-full">
                    <div className="flex items-center justify-between gap-2 min-w-0 w-full">
                      <h4 className="font-semibold text-sm truncate min-w-0 flex-1 group-hover:text-primary transition-colors">
                        {item.title}
                      </h4>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0">
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setSelectedItem(item); }}>
                            <FileText className="h-3.5 w-3.5 mr-2" /> View & Add Notes
                          </DropdownMenuItem>
                          {item.shortUrl && (
                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleCopyShortUrl(item.shortUrl!, item.title); }}>
                              <LinkIcon className="h-3.5 w-3.5 mr-2 text-primary" /> Copy Short Link
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            className="text-destructive focus:text-destructive"
                            onClick={(e) => { e.stopPropagation(); handleDeleteItem(item.id); }}
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
                      <div className="flex items-center gap-1.5 text-muted-foreground min-w-0 w-full">
                        <UserRoundCog className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground truncate min-w-0 flex-1">
                          {getProviderName(item.providerId)}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-1 text-muted-foreground text-[11px] min-w-0 w-full">
                        <div className="flex items-center gap-1 truncate min-w-0">
                          <Folder className="h-3 w-3 shrink-0" />
                          <span className="truncate min-w-0">{getAlbumName(item.albumId)}</span>
                        </div>
                        {item.shortUrl && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleCopyShortUrl(item.shortUrl!, item.title); }}
                            className="text-primary hover:underline font-mono text-[10px] flex items-center gap-1 shrink-0 bg-primary/10 px-1.5 py-0.5 rounded"
                            title="Copy Short URL"
                          >
                            <LinkIcon className="h-2.5 w-2.5" />
                            <span>Short Link</span>
                          </button>
                        )}
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
                        {item.type === "video" ? (
                          <div className="w-full h-full bg-slate-900 flex items-center justify-center text-white">
                            <Film className="h-5 w-5" />
                          </div>
                        ) : (
                          <img src={item.url} alt={item.title} className="w-full h-full object-cover" />
                        )}
                      </div>

                      <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                        <div className="flex items-center gap-2 min-w-0">
                          <h4 className="font-semibold text-sm truncate min-w-0">{item.title}</h4>
                          <Badge variant="outline" className="text-[10px] uppercase py-0 h-4 shrink-0">
                            {item.type}
                          </Badge>
                          {item.isGuestUpload && (
                            <Badge className="bg-emerald-600 text-white text-[9px] py-0 h-4">
                              Guest Upload
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate min-w-0">
                          {item.description || "No description provided."}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {item.shortUrl && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 text-xs font-mono gap-1 text-primary"
                          onClick={(e) => { e.stopPropagation(); handleCopyShortUrl(item.shortUrl!, item.title); }}
                        >
                          <LinkIcon className="h-3 w-3" />
                          <span className="hidden sm:inline">Short Link</span>
                        </Button>
                      )}

                      <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground">
                        <MessageSquare className="h-3.5 w-3.5" />
                        <span>{item.notes.length} notes</span>
                      </div>

                      <div className="hidden md:flex flex-col text-right text-xs max-w-[150px] min-w-0">
                        <span className="font-medium text-foreground truncate min-w-0">{getProviderName(item.providerId)}</span>
                        <span className="text-muted-foreground text-[11px] truncate min-w-0">{getAlbumName(item.albumId)}</span>
                      </div>

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
              const albumItems = mediaItems.filter(m => m.albumId === album.id)
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
                        <Badge className="bg-primary/90 text-primary-foreground text-[10px] mb-1">
                          {albumItems.length} {albumItems.length === 1 ? "Item" : "Items"}
                        </Badge>
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

      {/* ── MEDIA DETAIL & EDITING DIALOG ──────────────────────────────────── */}
      {selectedItem && (
        <Dialog open={!!selectedItem} onOpenChange={(open) => !open && setSelectedItem(null)}>
          <DialogContent className="sm:max-w-3xl max-h-[92vh] overflow-y-auto flex flex-col gap-4">
            <DialogHeader className="text-left border-b pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="uppercase text-[10px]">
                    {selectedItem.type}
                  </Badge>
                  {selectedItem.isGuestUpload && (
                    <Badge className="bg-emerald-600 text-white text-[9px]">
                      Guest Upload
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    Uploaded {new Date(selectedItem.uploadedAt).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <DialogTitle className="text-xl font-bold mt-1">{selectedItem.title}</DialogTitle>
              {selectedItem.description && (
                <DialogDescription className="text-xs">
                  {selectedItem.description}
                </DialogDescription>
              )}
            </DialogHeader>

            {/* Dynamic Short URL & Image Editing Toolbar Card inside Modal */}
            <div className="p-3 rounded-lg border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shadow-2xs">
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                  <LinkIcon className="h-3.5 w-3.5 text-primary" /> Assigned Dynamic Short Link
                </span>
                <span className="font-mono text-xs text-primary truncate">
                  {selectedItem.shortUrl || `http://localhost:8002/api/v1/med-${selectedItem.id}`}
                </span>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 text-xs gap-1"
                  onClick={() => handleCopyShortUrl(selectedItem.shortUrl || `http://localhost:8002/api/v1/med-${selectedItem.id}`, selectedItem.title)}
                >
                  <Copy className="h-3 w-3" /> Copy Link
                </Button>

                {selectedItem.type === "image" && (
                  <Button 
                    variant={isEditingImage ? "secondary" : "default"} 
                    size="sm"
                    className="h-7 text-xs gap-1.5"
                    onClick={() => setIsEditingImage(!isEditingImage)}
                  >
                    <Wand2 className="h-3.5 w-3.5" />
                    <span>{isEditingImage ? "Done Editing" : "Edit & Crop Image"}</span>
                  </Button>
                )}
              </div>
            </div>

            {/* Full Image / Video Display Container with Crop Overlay */}
            <div className="rounded-xl overflow-hidden bg-slate-950/95 border p-2 flex items-center justify-center min-h-[300px] max-h-[500px] w-full relative shadow-inner">
              {selectedItem.type === "video" ? (
                <video 
                  src={selectedItem.url} 
                  controls 
                  className="w-full max-h-[460px] object-contain rounded"
                  poster="https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=600&auto=format&fit=crop&q=80"
                />
              ) : (
                <div className="relative flex items-center justify-center overflow-hidden max-w-full max-h-[460px]">
                  <img 
                    src={selectedItem.url} 
                    alt={selectedItem.title} 
                    className="max-w-full max-h-[460px] w-auto h-auto object-contain rounded transition-all duration-150" 
                    style={{
                      filter: cssFilterPreview,
                      transform: `rotate(${rotation}deg) scaleX(${flipH ? -1 : 1}) scaleY(${flipV ? -1 : 1})`
                    }}
                  />

                  {isEditingImage && cropScale < 100 && (
                    <div 
                      className="absolute border-2 border-dashed border-primary bg-primary/10 pointer-events-none transition-all duration-200"
                      style={{
                        width: `${cropScale}%`,
                        height: cropAspect === "1:1" ? `${cropScale}%` : cropAspect === "4:3" ? `${cropScale * 0.75}%` : cropAspect === "16:9" ? `${cropScale * 0.5625}%` : `${cropScale}%`,
                        maxHeight: "95%",
                        maxWidth: "95%"
                      }}
                    >
                      <Badge className="absolute top-1 left-1 bg-primary text-primary-foreground text-[9px] py-0 px-1">
                        Crop Area ({cropAspect})
                      </Badge>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── IMAGE EDITING & CROP TOOLBAR ─────────────────────────────────── */}
            {selectedItem.type === "image" && isEditingImage && (
              <div className="p-3.5 rounded-lg border bg-muted/30 flex flex-col gap-3 text-xs animate-fade-in">
                <div className="flex items-center justify-between border-b pb-2">
                  <span className="font-semibold flex items-center gap-1.5">
                    <Crop className="h-4 w-4 text-primary" /> Aspect Ratio Cropping & Image Editing
                  </span>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 text-[11px] gap-1 text-muted-foreground hover:text-foreground"
                    onClick={resetEditorParams}
                  >
                    <Undo className="h-3 w-3" /> Reset All
                  </Button>
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                    <Crop className="h-3 w-3" /> Aspect Ratio Crop Presets:
                  </Label>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Button 
                      variant={cropAspect === "free" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("free")}
                    >
                      Freeform
                    </Button>
                    <Button 
                      variant={cropAspect === "1:1" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("1:1")}
                    >
                      1:1 (Square)
                    </Button>
                    <Button 
                      variant={cropAspect === "4:3" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("4:3")}
                    >
                      4:3 (Photo)
                    </Button>
                    <Button 
                      variant={cropAspect === "16:9" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("16:9")}
                    >
                      16:9 (Widescreen)
                    </Button>
                    <Button 
                      variant={cropAspect === "3:4" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("3:4")}
                    >
                      3:4 (Portrait)
                    </Button>
                    <Button 
                      variant={cropAspect === "9:16" ? "default" : "outline"} 
                      size="sm" 
                      className="h-7 text-xs px-2.5"
                      onClick={() => setCropAspect("9:16")}
                    >
                      9:16 (Story)
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 border-t">
                  <div className="grid gap-1">
                    <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                      <span>Crop Frame Size</span>
                      <span>{cropScale}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="40" 
                      max="100" 
                      value={cropScale}
                      onChange={(e) => setCropScale(Number(e.target.value))}
                      className="w-full accent-primary h-1.5 rounded bg-muted cursor-pointer"
                    />
                  </div>

                  <div className="grid gap-1">
                    <Label className="text-[11px] font-medium text-muted-foreground">Crop Position Alignment</Label>
                    <Select value={cropPosition} onValueChange={(val: any) => setCropPosition(val)}>
                      <SelectTrigger className="h-7 text-xs bg-card">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="center">Center</SelectItem>
                        <SelectItem value="top">Top Focus</SelectItem>
                        <SelectItem value="bottom">Bottom Focus</SelectItem>
                        <SelectItem value="left">Left Focus</SelectItem>
                        <SelectItem value="right">Right Focus</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-7 text-xs gap-1"
                    onClick={() => setRotation((prev) => (prev - 90) % 360)}
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Rotate -90°
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-7 text-xs gap-1"
                    onClick={() => setRotation((prev) => (prev + 90) % 360)}
                  >
                    <RotateCw className="h-3.5 w-3.5" /> Rotate +90°
                  </Button>
                  <Button 
                    variant={flipH ? "secondary" : "outline"} 
                    size="sm" 
                    className="h-7 text-xs gap-1"
                    onClick={() => setFlipH(!flipH)}
                  >
                    <FlipHorizontal className="h-3.5 w-3.5" /> Flip Horiz
                  </Button>
                  <Button 
                    variant={flipV ? "secondary" : "outline"} 
                    size="sm" 
                    className="h-7 text-xs gap-1"
                    onClick={() => setFlipV(!flipV)}
                  >
                    <FlipVertical className="h-3.5 w-3.5" /> Flip Vert
                  </Button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 border-t">
                  <div className="grid gap-1">
                    <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                      <span className="flex items-center gap-1"><Sun className="h-3 w-3" /> Brightness</span>
                      <span>{brightness}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="50" 
                      max="150" 
                      value={brightness}
                      onChange={(e) => setBrightness(Number(e.target.value))}
                      className="w-full accent-primary h-1.5 rounded bg-muted cursor-pointer"
                    />
                  </div>

                  <div className="grid gap-1">
                    <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                      <span className="flex items-center gap-1"><Contrast className="h-3 w-3" /> Contrast</span>
                      <span>{contrast}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="50" 
                      max="150" 
                      value={contrast}
                      onChange={(e) => setContrast(Number(e.target.value))}
                      className="w-full accent-primary h-1.5 rounded bg-muted cursor-pointer"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-7 text-xs"
                    onClick={() => setIsEditingImage(false)}
                  >
                    Cancel
                  </Button>
                  <Button 
                    size="sm" 
                    className="h-7 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={handleSaveImageEdits}
                    disabled={isSavingEdits}
                  >
                    <Save className="h-3.5 w-3.5" />
                    <span>{isSavingEdits ? "Applying Crop & Edits..." : "Apply Crop & Save"}</span>
                  </Button>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-lg border bg-muted/20">
              <div className="grid gap-1.5">
                <Label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <UserRoundCog className="h-3.5 w-3.5 text-primary" /> Service Provider Assignment
                </Label>
                <Select 
                  value={selectedItem.providerId || "none"} 
                  onValueChange={(val) => handleUpdateItemAssignment(selectedItem.id, "providerId", val)}
                >
                  <SelectTrigger className="h-8 text-xs bg-card">
                    <SelectValue placeholder="Assign Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Unassigned</SelectItem>
                    {providers.map(p => (
                      <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-1.5">
                <Label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Folder className="h-3.5 w-3.5 text-primary" /> Library / Album Assignment
                </Label>
                <Select 
                  value={selectedItem.albumId || "none"} 
                  onValueChange={(val) => handleUpdateItemAssignment(selectedItem.id, "albumId", val)}
                >
                  <SelectTrigger className="h-8 text-xs bg-card">
                    <SelectValue placeholder="Assign Album" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Unassigned (Root)</SelectItem>
                    {albums.map(a => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t pt-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  Text Communication & Staff Notes ({selectedItem.notes.length})
                </h3>
              </div>

              <div className="flex flex-col gap-2.5 max-h-52 overflow-y-auto pr-1">
                {selectedItem.notes.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic p-3 border border-dashed rounded text-center">
                    No communication notes attached yet. Use the field below to add instructions or notes for this media item.
                  </p>
                ) : (
                  selectedItem.notes.map((note) => (
                    <div key={note.id} className="p-3 rounded-lg bg-card border text-xs flex flex-col gap-1 shadow-2xs">
                      <div className="flex items-center justify-between font-medium">
                        <span className="text-primary">{note.author}</span>
                        <span className="text-[10px] text-muted-foreground">{note.timestamp}</span>
                      </div>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap">{note.text}</p>
                    </div>
                  ))
                )}
              </div>

              <div className="flex flex-col gap-2 mt-1">
                <Textarea 
                  placeholder="Write a message or clinical note regarding this media asset..."
                  value={newNoteText}
                  onChange={(e) => setNewNoteText(e.target.value)}
                  className="text-xs resize-none"
                  rows={2}
                />
                <Button 
                  size="sm" 
                  onClick={handleAddNote} 
                  disabled={!newNoteText.trim()}
                  className="self-end gap-1.5 text-xs"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  Post Communication Note
                </Button>
              </div>
            </div>

            <DialogFooter className="border-t pt-3 flex items-center justify-between sm:justify-between w-full">
              <Button 
                variant="destructive" 
                size="sm" 
                onClick={() => handleDeleteItem(selectedItem.id)} 
                className="gap-1.5 text-xs"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete Asset
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
                    a.href = selectedItem.url
                    a.download = selectedItem.title
                    a.target = "_blank"
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
