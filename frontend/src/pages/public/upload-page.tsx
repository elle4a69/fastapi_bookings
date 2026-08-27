import { useState, useEffect, type ChangeEvent } from "react"
import { useSearchParams, Link } from "react-router-dom"
import { 
  Upload, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  FileText, 
  Image as ImageIcon, 
  Film, 
  Lock, 
  ArrowLeft,
  Sparkles,
  Layers,
  Send,
  User,
  Mail,
  ShieldCheck,
  X
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

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

export interface GuestQueuedFile {
  id: string
  file: File
  title: string
  type: "image" | "video"
  url: string
  fileSize: string
}

const STORAGE_KEY_PUBLIC_LINKS = "fastapi_bookings_public_upload_links_v1"
const STORAGE_KEY_MEDIA = "fastapi_bookings_media_items_v1"

export default function PublicUploadPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token") || searchParams.get("link") || ""

  const [linkConfig, setLinkConfig] = useState<PublicUploadLink | null>(null)
  const [isValidating, setIsValidating] = useState(true)
  const [isExpired, setIsExpired] = useState(false)
  const [isMaxReached, setIsMaxReached] = useState(false)

  // Upload Form State - Multi-File Queue
  const [senderName, setSenderName] = useState("")
  const [senderEmail, setSenderEmail] = useState("")
  const [senderMessage, setSenderMessage] = useState("")
  const [uploadQueue, setUploadQueue] = useState<GuestQueuedFile[]>([])

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [uploadedCount, setUploadedCount] = useState(0)

  // Validate Link Config on Load
  useEffect(() => {
    setIsValidating(true)
    const savedLinksRaw = localStorage.getItem(STORAGE_KEY_PUBLIC_LINKS)
    let links: PublicUploadLink[] = []

    if (savedLinksRaw) {
      try {
        links = JSON.parse(savedLinksRaw)
      } catch {
        links = []
      }
    }

    const foundLink = links.find(l => l.token === token || l.id === token)

    if (foundLink) {
      setLinkConfig(foundLink)

      if (foundLink.expiresAt && new Date(foundLink.expiresAt) < new Date()) {
        setIsExpired(true)
      }

      if (foundLink.maxUploads > 0 && foundLink.currentUploads >= foundLink.maxUploads) {
        setIsMaxReached(true)
      }
    } else {
      const demoLink: PublicUploadLink = {
        id: "upl-demo",
        token: "demo",
        shortUrl: "http://localhost:8002/api/v1/upl-demo",
        allowedTypes: ["image", "video"],
        maxUploads: 10,
        currentUploads: 0,
        expiresAt: null,
        createdAt: new Date().toISOString(),
        createdByName: "Admin Staff"
      }
      setLinkConfig(demoLink)
    }

    setIsValidating(false)
  }, [token])

  // Handle Multi-File Input Selection
  const handleMultiFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return

    const filesArr = Array.from(e.target.files)
    const newItems: GuestQueuedFile[] = []

    // Quota check
    if (linkConfig && linkConfig.maxUploads > 0) {
      const remainingQuota = linkConfig.maxUploads - (linkConfig.currentUploads + uploadQueue.length)
      if (filesArr.length > remainingQuota) {
        alert(`You can only upload up to ${remainingQuota} more file${remainingQuota === 1 ? "" : "s"} under this link's quota.`)
      }
    }

    filesArr.forEach((file, index) => {
      const isVideo = file.type.startsWith("video/")
      const title = file.name.replace(/\.[^/.]+$/, "")
      const size = `${(file.size / (1024 * 1024)).toFixed(1)} MB`

      const reader = new FileReader()
      reader.onload = (evt) => {
        const dataUrl = evt.target?.result as string || ""
        setUploadQueue(prev => [
          ...prev,
          {
            id: `gq-${Date.now()}-${index}-${Math.random().toString(36).substr(2, 4)}`,
            file,
            title,
            type: isVideo ? "video" : "image",
            url: dataUrl,
            fileSize: size
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

  // Handle Batch Upload Submission
  const handleSubmitUpload = () => {
    if (uploadQueue.length === 0 || !senderName.trim()) return
    setIsSubmitting(true)

    try {
      const savedMediaRaw = localStorage.getItem(STORAGE_KEY_MEDIA)
      let mediaItems: any[] = []
      if (savedMediaRaw) {
        try {
          mediaItems = JSON.parse(savedMediaRaw)
        } catch {
          mediaItems = []
        }
      }

      const createdGuestItems: any[] = []

      uploadQueue.forEach((qItem, i) => {
        const newId = `med-${Date.now()}-${i}`
        const finalUrl = qItem.url || "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=800&auto=format&fit=crop&q=80"
        const shortUrl = `http://localhost:8002/api/v1/${newId}`

        const guestNoteText = `Public Guest Upload by ${senderName}${senderEmail ? ` (${senderEmail})` : ""}.\n${senderMessage ? `Message: ${senderMessage}` : ""}`

        const newItem = {
          id: newId,
          title: qItem.title.trim() || `Uploaded File #${i + 1}`,
          type: qItem.type,
          url: finalUrl,
          fileSize: qItem.fileSize,
          mimeType: qItem.file.type,
          albumId: linkConfig?.albumId,
          providerId: linkConfig?.providerId,
          description: `Uploaded via Public Link by ${senderName}`,
          notes: [
            {
              id: `n-${Date.now()}-${i}`,
              author: senderName,
              text: guestNoteText,
              timestamp: new Date().toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
            }
          ],
          uploadedAt: new Date().toISOString(),
          shortUrl: shortUrl,
          isGuestUpload: true
        }

        createdGuestItems.push(newItem)
      })

      const updatedMediaList = [...createdGuestItems, ...mediaItems]
      localStorage.setItem(STORAGE_KEY_MEDIA, JSON.stringify(updatedMediaList))

      if (linkConfig) {
        const savedLinksRaw = localStorage.getItem(STORAGE_KEY_PUBLIC_LINKS)
        let links: PublicUploadLink[] = []
        if (savedLinksRaw) {
          try {
            links = JSON.parse(savedLinksRaw)
          } catch {
            links = []
          }
        }

        const updatedLinks = links.map(l => {
          if (l.id === linkConfig.id || l.token === linkConfig.token) {
            return { ...l, currentUploads: l.currentUploads + createdGuestItems.length }
          }
          return l
        })
        localStorage.setItem(STORAGE_KEY_PUBLIC_LINKS, JSON.stringify(updatedLinks))
      }

      setUploadedCount(createdGuestItems.length)
      setIsSuccess(true)
    } catch (err) {
      console.error("Public batch upload failed:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isValidating) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-white">
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <Clock className="h-5 w-5 animate-spin text-primary" />
          <span>Validating public upload portal link...</span>
        </div>
      </div>
    )
  }

  if (isExpired || isMaxReached) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950 text-slate-100">
        <Card className="max-w-md w-full border-slate-800 bg-slate-900/90 text-slate-100 shadow-2xl">
          <CardHeader className="text-center pb-2">
            <div className="p-3.5 rounded-full bg-destructive/10 text-destructive w-fit mx-auto mb-2">
              <Lock className="h-7 w-7" />
            </div>
            <CardTitle className="text-xl font-bold">
              {isExpired ? "Upload Link Expired" : "Upload Quota Reached"}
            </CardTitle>
            <CardDescription className="text-slate-400 text-xs">
              {isExpired 
                ? "This public upload portal link has passed its expiration time and is no longer accepting new files."
                : "This public upload link has reached its maximum allowed file upload count."}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center text-xs text-slate-400 p-6 pt-2">
            <p className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/50">
              Please contact the organization or staff member who provided this link to request a new upload link.
            </p>
          </CardContent>
          <CardFooter className="justify-center border-t border-slate-800 pt-4">
            <Link to="/admin/media">
              <Button variant="ghost" size="sm" className="text-xs text-slate-400 hover:text-white gap-1.5">
                <ArrowLeft className="h-3.5 w-3.5" /> Return to Admin Workspace
              </Button>
            </Link>
          </CardFooter>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between p-4 sm:p-6 lg:p-8">
      
      {/* Header */}
      <header className="max-w-2xl mx-auto w-full flex items-center justify-between pb-6 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-primary/20 text-primary">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-white leading-tight">Secure Public Upload Portal</h1>
            <p className="text-xs text-slate-400">Upload photographs & files directly to staff</p>
          </div>
        </div>

        <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-950/40 text-[10px] gap-1 px-2.5 py-1">
          <ShieldCheck className="h-3 w-3" /> Encrypted Portal
        </Badge>
      </header>

      {/* Main Form Container */}
      <main className="max-w-2xl mx-auto w-full my-auto py-8">
        {isSuccess ? (
          <Card className="border-slate-800 bg-slate-900/90 text-slate-100 shadow-2xl animate-fade-in">
            <CardHeader className="text-center pb-2">
              <div className="p-4 rounded-full bg-emerald-500/20 text-emerald-400 w-fit mx-auto mb-3">
                <CheckCircle2 className="h-10 w-10" />
              </div>
              <CardTitle className="text-2xl font-bold text-white">Batch Upload Complete!</CardTitle>
              <CardDescription className="text-slate-400 text-sm">
                Successfully uploaded {uploadedCount} media file{uploadedCount > 1 ? "s" : ""} to the library.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 text-center space-y-4">
              <div className="p-4 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300 flex flex-col gap-1 text-left">
                <span className="font-semibold text-white text-sm">Sender: {senderName}</span>
                {senderEmail && <span>Email: {senderEmail}</span>}
                <span className="text-slate-400 mt-1">
                  Files processed: {uploadedCount} asset{uploadedCount > 1 ? "s" : ""}
                </span>
              </div>

              <Button 
                onClick={() => {
                  setIsSuccess(false)
                  setUploadQueue([])
                  setSenderMessage("")
                }}
                className="w-full gap-2 font-semibold"
              >
                <Upload className="h-4 w-4" /> Upload More Files
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-slate-800 bg-slate-900/90 text-slate-100 shadow-2xl">
            <CardHeader className="border-b border-slate-800 pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl font-bold text-white flex items-center gap-2">
                  <Upload className="h-5 w-5 text-primary" /> Multi-File Upload
                </CardTitle>
                {linkConfig?.maxUploads ? (
                  <Badge variant="secondary" className="bg-slate-800 text-slate-300 text-xs">
                    Quota: {linkConfig.currentUploads} / {linkConfig.maxUploads} used
                  </Badge>
                ) : null}
              </div>
              <CardDescription className="text-slate-400 text-xs">
                Select one or multiple files below to upload directly to our media library.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-6 space-y-5">
              
              {/* File Dropzone */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Select Files to Upload *</span>
                  {uploadQueue.length > 0 && (
                    <span className="text-emerald-400 font-mono text-[11px]">
                      {uploadQueue.length} File{uploadQueue.length > 1 ? "s" : ""} Queued
                    </span>
                  )}
                </Label>
                <div className="border-2 border-dashed border-slate-700 hover:border-primary/60 rounded-xl p-6 text-center transition-colors bg-slate-950/60">
                  <input 
                    type="file" 
                    accept="image/*,video/*,.pdf,.doc,.docx" 
                    multiple
                    id="guest-multi-file-input" 
                    className="hidden" 
                    onChange={handleMultiFileChange}
                  />
                  <label htmlFor="guest-multi-file-input" className="cursor-pointer flex flex-col items-center gap-2.5">
                    <div className="p-3 rounded-full bg-primary/10 text-primary">
                      <Upload className="h-6 w-6" />
                    </div>
                    <div className="text-sm font-medium text-slate-200">
                      Click to select multiple photographs / videos / files
                    </div>
                    <p className="text-xs text-slate-500">
                      Supports JPG, PNG, WEBP, MP4, WEBM, PDF (Select multiple files at once)
                    </p>
                  </label>
                </div>
              </div>

              {/* Queued Items List */}
              {uploadQueue.length > 0 && (
                <div className="space-y-2 border border-slate-800 rounded-lg p-3 bg-slate-950/80 max-h-48 overflow-y-auto">
                  <span className="text-xs font-semibold text-slate-400 flex items-center justify-between">
                    <span>Queued Files ({uploadQueue.length}):</span>
                    <button onClick={() => setUploadQueue([])} className="text-rose-400 text-[11px] hover:underline">
                      Clear All
                    </button>
                  </span>
                  <div className="space-y-1.5">
                    {uploadQueue.map((item) => (
                      <div key={item.id} className="p-2 rounded bg-slate-900 border border-slate-800 text-xs flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          {item.type === "video" ? (
                            <Film className="h-4 w-4 text-primary shrink-0" />
                          ) : (
                            <ImageIcon className="h-4 w-4 text-primary shrink-0" />
                          )}
                          <span className="font-medium text-slate-200 truncate min-w-0">{item.title}</span>
                          <span className="text-[10px] text-slate-500 shrink-0">({item.fileSize})</span>
                        </div>
                        <button onClick={() => handleRemoveQueueItem(item.id)} className="text-slate-500 hover:text-rose-400">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sender Details */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="sender-name" className="text-xs font-semibold text-slate-300 flex items-center gap-1">
                    <User className="h-3.5 w-3.5 text-primary" /> Your Full Name *
                  </Label>
                  <Input 
                    id="sender-name" 
                    placeholder="e.g. Jane Doe" 
                    value={senderName}
                    onChange={(e) => setSenderName(e.target.value)}
                    className="bg-slate-950 border-slate-800 text-slate-200 text-xs"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="sender-email" className="text-xs font-semibold text-slate-300 flex items-center gap-1">
                    <Mail className="h-3.5 w-3.5 text-primary" /> Contact Email (Optional)
                  </Label>
                  <Input 
                    id="sender-email" 
                    type="email"
                    placeholder="jane@example.com" 
                    value={senderEmail}
                    onChange={(e) => setSenderEmail(e.target.value)}
                    className="bg-slate-950 border-slate-800 text-slate-200 text-xs"
                  />
                </div>
              </div>

              {/* Message Note */}
              <div className="space-y-2">
                <Label htmlFor="sender-message" className="text-xs font-semibold text-slate-300">Message / Communication Note</Label>
                <Textarea 
                  id="sender-message" 
                  placeholder="Attach a note or instructions regarding these uploads..." 
                  value={senderMessage}
                  onChange={(e) => setSenderMessage(e.target.value)}
                  className="bg-slate-950 border-slate-800 text-slate-200 text-xs resize-none"
                  rows={2}
                />
              </div>

            </CardContent>

            <CardFooter className="border-t border-slate-800 p-6 pt-4 flex items-center justify-between">
              <span className="text-[11px] text-slate-500">
                {linkConfig?.expiresAt ? `Expires: ${new Date(linkConfig.expiresAt).toLocaleDateString()}` : "No Expiration Date"}
              </span>

              <Button 
                onClick={handleSubmitUpload} 
                disabled={uploadQueue.length === 0 || !senderName.trim() || isSubmitting}
                className="gap-2 font-semibold text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                <Send className="h-3.5 w-3.5" />
                <span>{isSubmitting ? "Uploading Batch..." : `Submit ${uploadQueue.length || ""} File${uploadQueue.length > 1 ? "s" : ""} to Library`}</span>
              </Button>
            </CardFooter>
          </Card>
        )}
      </main>

      {/* Footer */}
      <footer className="max-w-2xl mx-auto w-full text-center pt-6 border-t border-slate-800/80 text-xs text-slate-500 flex items-center justify-between">
        <span>FastAPI Bookings Public Upload Utility</span>
        <Link to="/admin/media" className="hover:text-slate-300 underline">
          Admin Portal
        </Link>
      </footer>

    </div>
  )
}
