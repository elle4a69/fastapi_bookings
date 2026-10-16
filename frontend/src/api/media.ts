/**
 * Media API Client for durable tenant-scoped media assets.
 * 
 * Interacts with backend endpoints:
 * - POST   /api/admin/media/upload        - Safe upload & persist media
 * - GET    /api/admin/media               - List tenant media with optional eligibility filtering
 * - GET    /api/admin/media/{id}          - Retrieve media details
 * - DELETE /api/admin/media/{id}          - Delete media item
 * - PATCH  /api/admin/media/{id}/eligibility - Update public website eligibility
 * - GET    /api/admin/media/{id}/file     - Download/stream media file for admin
 */

import { authenticatedAdminFetch, ApiError } from "../lib/api.ts"

export interface BackendMediaItem {
  id: number
  tenant_id: number
  provider_id: number | null
  filename: string
  file_path: string
  url: string
  content_type: string
  file_size: number
  title: string | null
  description: string | null
  alt_text: string | null
  media_type: "image" | "video" | "document"
  is_public_website_eligible: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface MediaListParams {
  is_public_website_eligible?: boolean
  provider_id?: number | null
  limit?: number
  offset?: number
}

export interface MediaListResponse {
  ok: boolean
  data: BackendMediaItem[]
  total: number
}

export interface MediaDetailResponse {
  ok: boolean
  data: BackendMediaItem
}

export interface MediaDeleteResponse {
  ok: boolean
  message: string
  id: number
}

export interface MediaUploadPayload {
  file: File
  title?: string
  description?: string
  notes?: string
  provider_id?: number | null
  is_public_website_eligible?: boolean
}

export const ALLOWED_MIME_TYPES = new Set([
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/svg+xml",
  "video/mp4",
  "video/webm",
  "video/quicktime",
  "application/pdf",
])

export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024 // 25MB

export function validateMediaUploadFile(file: File): { valid: boolean; error?: string } {
  if (!file) {
    return { valid: false, error: "Please select a file to upload." }
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: `File size exceeds the 25MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).` }
  }
  if (file.type && !ALLOWED_MIME_TYPES.has(file.type)) {
    return { valid: false, error: `MIME type "${file.type}" is not supported. Permitted types: JPG, PNG, WEBP, GIF, SVG, MP4, WEBM, QuickTime, PDF.` }
  }
  return { valid: true }
}

export function formatMediaFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * List tenant-scoped media assets with optional eligibility and provider filters.
 */
export async function listMedia(params?: MediaListParams): Promise<MediaListResponse> {
  const query = new URLSearchParams()
  if (params?.is_public_website_eligible !== undefined) {
    query.set("is_public_website_eligible", String(params.is_public_website_eligible))
  }
  if (params?.provider_id !== undefined && params.provider_id !== null) {
    query.set("provider_id", String(params.provider_id))
  }
  if (params?.limit !== undefined) {
    query.set("limit", String(params.limit))
  }
  if (params?.offset !== undefined) {
    query.set("offset", String(params.offset))
  }
  const queryString = query.toString()
  const endpoint = `/api/admin/media${queryString ? `?${queryString}` : ""}`
  const response = await authenticatedAdminFetch(endpoint)
  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    throw new ApiError(response.status, errorData?.detail || errorData?.message || "Failed to list media items.", errorData)
  }
  return response.json()
}

/**
 * Retrieve single media item detail by ID.
 */
export async function getMediaDetail(id: number): Promise<MediaDetailResponse> {
  const response = await authenticatedAdminFetch(`/api/admin/media/${id}`)
  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    throw new ApiError(response.status, errorData?.detail || errorData?.message || `Failed to get media item ${id}.`, errorData)
  }
  return response.json()
}

/**
 * Upload a media binary file to backend storage.
 */
export async function uploadMedia(payload: MediaUploadPayload): Promise<MediaDetailResponse> {
  const validation = validateMediaUploadFile(payload.file)
  if (!validation.valid) {
    throw new Error(validation.error)
  }

  const formData = new FormData()
  formData.append("file", payload.file)
  if (payload.title?.trim()) {
    formData.append("title", payload.title.trim())
  }
  if (payload.description?.trim()) {
    formData.append("description", payload.description.trim())
  }
  if (payload.notes?.trim()) {
    formData.append("notes", payload.notes.trim())
  }
  if (payload.provider_id !== undefined && payload.provider_id !== null) {
    formData.append("provider_id", String(payload.provider_id))
  }
  formData.append("is_public_website_eligible", String(Boolean(payload.is_public_website_eligible)))

  const response = await authenticatedAdminFetch("/api/admin/media/upload", {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    const message = errorData?.detail || errorData?.message || `Upload failed with status ${response.status}.`
    throw new ApiError(response.status, message, errorData)
  }

  return response.json()
}

/**
 * Update public website eligibility for a media item.
 */
export async function updateMediaEligibility(id: number, is_public_website_eligible: boolean): Promise<MediaDetailResponse> {
  const response = await authenticatedAdminFetch(`/api/admin/media/${id}/eligibility`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_public_website_eligible }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    throw new ApiError(response.status, errorData?.detail || errorData?.message || `Failed to update eligibility for media item ${id}.`, errorData)
  }

  return response.json()
}

/**
 * Delete a media item by ID.
 */
export async function deleteMedia(id: number): Promise<MediaDeleteResponse> {
  const response = await authenticatedAdminFetch(`/api/admin/media/${id}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    throw new ApiError(response.status, errorData?.detail || errorData?.message || `Failed to delete media item ${id}.`, errorData)
  }

  return response.json()
}

/**
 * Return the backend URL for streaming the media file binary for authorized tenant admin.
 */
export function getAdminMediaStreamUrl(id: number): string {
  return `/api/admin/media/${id}/file`
}

const blobCache = new Map<number, string>()

/**
 * Fetch and return an object URL for admin preview of private or eligible media assets.
 */
export async function fetchMediaBlobUrl(id: number): Promise<string> {
  if (blobCache.has(id)) {
    return blobCache.get(id)!
  }
  const response = await authenticatedAdminFetch(getAdminMediaStreamUrl(id))
  if (!response.ok) {
    throw new Error(`Failed to stream media asset ${id}: ${response.statusText}`)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  blobCache.set(id, url)
  return url
}
