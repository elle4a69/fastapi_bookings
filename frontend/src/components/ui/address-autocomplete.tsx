import React, { useState, useEffect, useRef, useCallback } from "react"
import { apiClient } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  MapPin,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  Compass,
  Info,
} from "lucide-react"

export interface AddressStructuredData {
  formatted_address: string
  street_address?: string | null
  suburb?: string | null
  state?: string | null
  postcode?: string | null
  country?: string | null
  latitude?: number | null
  longitude?: number | null
  source?: string
  is_verified?: boolean
}

export interface AddressAutocompleteProps {
  id?: string
  label?: string
  value?: string
  onChange: (value: string, structuredData?: AddressStructuredData) => void
  placeholder?: string
  disabled?: boolean
  required?: boolean
  className?: string
  noticeText?: string
  helperText?: string
  showVerificationBadge?: boolean
  defaultVerified?: boolean
  onAddressSelect?: (item: AddressStructuredData) => void
}

export function AddressAutocomplete({
  id = "address-autocomplete",
  label,
  value = "",
  onChange,
  placeholder = "Search verified street address, suburb, or postcode...",
  disabled = false,
  required = false,
  className = "",
  noticeText,
  helperText,
  showVerificationBadge = true,
  defaultVerified = false,
  onAddressSelect,
}: AddressAutocompleteProps) {
  const [inputValue, setInputValue] = useState(value)
  const [suggestions, setSuggestions] = useState<AddressStructuredData[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [isVerified, setIsVerified] = useState<boolean>(defaultVerified || (!!value && value.trim().length > 5))
  const [selectedIndex, setSelectedIndex] = useState<number>(-1)

  const containerRef = useRef<HTMLDivElement>(null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep internal input value in sync when value prop changes externally
  useEffect(() => {
    setInputValue(value || "")
    if (value && value.trim().length > 5) {
      // If initialized with a value, consider it baseline-verified or manual
      setIsVerified((prev) => (prev ? true : defaultVerified))
    } else {
      setIsVerified(false)
    }
  }, [value, defaultVerified])

  // Click outside listener to close suggestions
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  const fetchSuggestions = useCallback(async (query: string) => {
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setSuggestions([])
      setIsOpen(false)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    try {
      // First try dedicated standardized address lookup
      const res: any = await apiClient.get(
        `/api/public/travel/addresses?q=${encodeURIComponent(trimmed)}&limit=6`
      )
      const data = Array.isArray(res) ? res : res?.data || []

      if (data.length > 0) {
        setSuggestions(data)
        setIsOpen(true)
      } else {
        // Fallback to suburbs lookup if addresses returned empty
        const suburbRes: any = await apiClient.get(
          `/api/public/travel/suburbs?q=${encodeURIComponent(trimmed)}&limit=6`
        )
        const suburbData = Array.isArray(suburbRes) ? suburbRes : suburbRes?.data || []
        const formattedFallback: AddressStructuredData[] = suburbData.map((s: any) => ({
          formatted_address: `${s.suburb} ${s.state} ${s.postcode}, Australia`,
          suburb: s.suburb,
          state: s.state,
          postcode: s.postcode,
          country: "Australia",
          latitude: s.latitude,
          longitude: s.longitude,
          source: "au_postcodes",
          is_verified: true,
        }))
        setSuggestions(formattedFallback)
        setIsOpen(formattedFallback.length > 0)
      }
    } catch (err) {
      console.warn("Address autocomplete search error:", err)
      setSuggestions([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVal = e.target.value
    setInputValue(newVal)
    setIsVerified(false) // Editing manually revokes verified flag until an option is selected
    onChange(newVal)

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    if (newVal.trim().length >= 2) {
      debounceTimerRef.current = setTimeout(() => {
        fetchSuggestions(newVal)
      }, 250)
    } else {
      setSuggestions([])
      setIsOpen(false)
      setIsLoading(false)
    }
  }

  const handleSelectSuggestion = (item: AddressStructuredData) => {
    const formatted = item.formatted_address
    setInputValue(formatted)
    setIsVerified(true)
    setIsOpen(false)
    setSuggestions([])
    setSelectedIndex(-1)
    onChange(formatted, item)
    onAddressSelect?.(item)
  }

  const handleClear = () => {
    setInputValue("")
    setIsVerified(false)
    setSuggestions([])
    setIsOpen(false)
    onChange("")
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || suggestions.length === 0) return

    if (e.key === "ArrowDown") {
      e.preventDefault()
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === "Enter" && selectedIndex >= 0) {
      e.preventDefault()
      handleSelectSuggestion(suggestions[selectedIndex])
    } else if (e.key === "Escape") {
      setIsOpen(false)
    }
  }

  return (
    <div ref={containerRef} className={`relative space-y-1.5 ${className}`}>
      {label && (
        <div className="flex items-center justify-between">
          <Label htmlFor={id} className="text-sm font-medium">
            {label} {required && <span className="text-destructive">*</span>}
          </Label>
          {showVerificationBadge && inputValue.trim().length > 0 && (
            <div>
              {isVerified ? (
                <Badge
                  variant="outline"
                  className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800 text-[11px] gap-1 py-0.5"
                >
                  <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                  ✓ Verified via Address Search
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-300 dark:border-amber-800 text-[11px] gap-1 py-0.5"
                >
                  <AlertCircle className="h-3 w-3 text-amber-600 dark:text-amber-400" />
                  Manual Entry / Unverified
                </Badge>
              )}
            </div>
          )}
        </div>
      )}

      <div className="relative">
        <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          id={id}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true)
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className="pl-9 pr-14 text-sm"
        />

        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground mr-1" />
          ) : inputValue ? (
            <button
              type="button"
              onClick={handleClear}
              disabled={disabled}
              className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
              title="Clear address"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>

      {/* Floating Suggestions Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-popover text-popover-foreground border rounded-md shadow-lg overflow-hidden max-h-64 overflow-y-auto">
          <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground bg-muted/40 border-b flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Compass className="h-3 w-3" /> Standardized Address Suggestions
            </span>
            <span className="text-[10px] text-muted-foreground font-normal">Select to verify</span>
          </div>
          <ul className="divide-y divide-border/40">
            {suggestions.map((item, idx) => {
              const isSelected = idx === selectedIndex
              return (
                <li
                  key={`${item.formatted_address}-${idx}`}
                  onClick={() => handleSelectSuggestion(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`p-2.5 text-xs cursor-pointer transition-colors flex items-start gap-2.5 ${
                    isSelected ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"
                  }`}
                >
                  <MapPin className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">{item.formatted_address}</p>
                    <div className="flex items-center gap-1.5 mt-1 text-[11px] text-muted-foreground">
                      {item.suburb && <span>{item.suburb}</span>}
                      {item.state && <Badge variant="secondary" className="px-1 py-0 text-[10px]">{item.state}</Badge>}
                      {item.postcode && <span>{item.postcode}</span>}
                      {item.source && (
                        <span className="text-[10px] opacity-70 ml-auto capitalize">
                          via {item.source.replace("_", " ")}
                        </span>
                      )}
                    </div>
                  </div>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0 mt-1" />
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* Helper text or verification reminder if badge header was omitted */}
      {!label && showVerificationBadge && inputValue.trim().length > 0 && (
        <div className="flex items-center justify-between pt-0.5">
          {isVerified ? (
            <Badge
              variant="outline"
              className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800 text-[11px] gap-1 py-0.5"
            >
              <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
              ✓ Verified via Address Search
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-300 dark:border-amber-800 text-[11px] gap-1 py-0.5"
            >
              <AlertCircle className="h-3 w-3 text-amber-600 dark:text-amber-400" />
              Manual Entry / Unverified
            </Badge>
          )}
        </div>
      )}

      {/* Provider Travel Calculation Notice */}
      {noticeText && (
        <div className="flex items-start gap-1.5 p-2 rounded-md bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-900/60 text-blue-900 dark:text-blue-200 text-xs mt-1">
          <Info className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <p className="leading-relaxed">{noticeText}</p>
        </div>
      )}

      {helperText && !noticeText && (
        <p className="text-xs text-muted-foreground">{helperText}</p>
      )}
    </div>
  )
}
export default AddressAutocomplete
