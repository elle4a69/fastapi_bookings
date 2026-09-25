import { useState, useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import {
  Compass,
  MapPin,
  Search,
  Navigation,
  Star,
  ShieldCheck,
  Calendar,
  Globe,
  ArrowRight,
  Sparkles,
  Bot,
  X,
  Send,
  Loader2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  SlidersHorizontal,
  Clock,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/theme-toggle";

export interface DirectoryTenantCardData {
  id: number;
  name: string;
  subdomain: string;
  description?: string;
  rating: number;
  review_count: number;
  starting_price: number;
  location_name: string;
  address: string;
  latitude: number;
  longitude: number;
  distance_km?: number | null;
  website_url: string;
  booking_url: string;
  featured_services: Array<{
    id: number;
    name: string;
    duration: number;
    price: number;
    category?: string | null;
  }>;
}

interface DirectorySearchResponse {
  ok: boolean;
  count: number;
  search_center?: {
    lat: number;
    lng: number;
    label: string;
  } | null;
  radius_km: number;
  tenants: DirectoryTenantCardData[];
}

interface DirectoryTriageResponse {
  ok: boolean;
  reply: string;
  matched_tenants: DirectoryTenantCardData[];
}

interface ChatMessage {
  id: string;
  sender: "user" | "bot";
  text: string;
  recommendations?: DirectoryTenantCardData[];
  timestamp: string;
}

const QUICK_LOCATIONS = [
  { label: "Sydney 2000", query: "2000" },
  { label: "North Sydney 2060", query: "2060" },
  { label: "Bondi 2026", query: "2026" },
  { label: "Parramatta 2150", query: "2150" },
  { label: "Melbourne 3000", query: "3000" },
];

const RADIUS_OPTIONS = [5, 15, 25, 50];

const CATEGORY_CHIPS = ["All", "Consultations", "Wellness", "Triage"];

export default function UmbrellaDirectoryPage() {
  // Search parameters
  const [queryInput, setQueryInput] = useState("Sydney 2000");
  const [selectedRadius, setSelectedRadius] = useState<number>(25);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [isLocating, setIsLocating] = useState(false);

  // Search Results
  const [loading, setLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState<DirectorySearchResponse | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);

  // Map Controls
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // AI Concierge State
  const [conciergeOpen, setConciergeOpen] = useState(false);
  const [triageInput, setTriageInput] = useState("");
  const [triageLoading, setTriageLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      sender: "bot",
      text: "👋 Welcome to the National Booking Network! I'm your AI Concierge. Tell me what specialist care you need (e.g., 'Need standard consultation in Sydney under 15km') and I'll find verified specialists for you.",
      timestamp: "Just now",
    },
  ]);

  // Initial Search
  useEffect(() => {
    executeSearch({ query: "2000", radius: 25 });
  }, []);

  const executeSearch = async (opts?: {
    query?: string;
    lat?: number;
    lng?: number;
    radius?: number;
  }) => {
    const q = opts?.query !== undefined ? opts.query : queryInput;
    const r = opts?.radius !== undefined ? opts.radius : selectedRadius;
    const lat = opts?.lat !== undefined ? opts.lat : userCoords?.lat;
    const lng = opts?.lng !== undefined ? opts.lng : userCoords?.lng;

    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.append("query", q);
      if (lat !== undefined && lng !== undefined) {
        params.append("lat", lat.toString());
        params.append("lng", lng.toString());
      }
      params.append("radius_km", r.toString());

      const res = await apiClient.get<DirectorySearchResponse>(
        `/api/public/directory/search?${params.toString()}`
      );
      setSearchResponse(res);
      if (res.tenants.length > 0) {
        setSelectedTenantId(res.tenants[0].id);
      } else {
        setSelectedTenantId(null);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to query directory.");
    } finally {
      setLoading(false);
    }
  };

  const handleNearMe = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by your browser.");
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setUserCoords(coords);
        setQueryInput("Near Current Location");
        executeSearch({ lat: coords.lat, lng: coords.lng, query: "" });
        toast.success("GPS location locked!");
      },
      (err) => {
        setIsLocating(false);
        toast.error(`Unable to get location: ${err.message}`);
      },
      { timeout: 8000 }
    );
  };

  const handleSelectTenant = (id: number) => {
    setSelectedTenantId(id);
    const cardEl = cardRefs.current[id];
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  // Filter tenants by category chip
  const filteredTenants = useMemo(() => {
    if (!searchResponse) return [];
    if (selectedCategory === "All") return searchResponse.tenants;

    return searchResponse.tenants.filter((tenant) => {
      const services = tenant.featured_services || [];
      return services.some(
        (s) =>
          s.name.toLowerCase().includes(selectedCategory.toLowerCase()) ||
          (s.category && s.category.toLowerCase().includes(selectedCategory.toLowerCase()))
      );
    });
  }, [searchResponse, selectedCategory]);

  // Map Coordinates & Projection Helpers
  const mapBounds = useMemo(() => {
    if (!searchResponse || searchResponse.tenants.length === 0) {
      return {
        minLat: -33.95,
        maxLat: -33.80,
        minLng: 150.95,
        maxLng: 151.30,
      };
    }

    const centerLat = searchResponse.search_center?.lat ?? -33.8688;
    const centerLng = searchResponse.search_center?.lng ?? 151.2093;

    let minLat = centerLat;
    let maxLat = centerLat;
    let minLng = centerLng;
    let maxLng = centerLng;

    searchResponse.tenants.forEach((t) => {
      if (t.latitude < minLat) minLat = t.latitude;
      if (t.latitude > maxLat) maxLat = t.latitude;
      if (t.longitude < minLng) minLng = t.longitude;
      if (t.longitude > maxLng) maxLng = t.longitude;
    });

    const latPad = Math.max((maxLat - minLat) * 0.25, 0.04);
    const lngPad = Math.max((maxLng - minLng) * 0.25, 0.04);

    return {
      minLat: minLat - latPad,
      maxLat: maxLat + latPad,
      minLng: minLng - lngPad,
      maxLng: maxLng + lngPad,
    };
  }, [searchResponse]);

  const projectCoords = (lat: number, lng: number) => {
    const { minLat, maxLat, minLng, maxLng } = mapBounds;
    const latSpan = maxLat - minLat || 0.1;
    const lngSpan = maxLng - minLng || 0.1;

    // SVG coordinate system: X from 5% to 95%, Y from 5% to 95% (inverted Y for latitude)
    const x = ((lng - minLng) / lngSpan) * 90 + 5;
    const y = ((maxLat - lat) / latSpan) * 90 + 5;

    return { x: Math.min(Math.max(x, 4), 96), y: Math.min(Math.max(y, 4), 96) };
  };

  // AI Concierge Bot Submit
  const handleTriageSubmit = async (customQuery?: string) => {
    const q = customQuery || triageInput;
    if (!q.trim()) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: "user",
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setTriageInput("");
    setTriageLoading(true);

    try {
      const payload = {
        query: q,
        user_lat: userCoords?.lat,
        user_lng: userCoords?.lng,
        postcode_or_suburb: queryInput !== "Near Current Location" ? queryInput : undefined,
      };

      const res = await apiClient.post<DirectoryTriageResponse>(
        "/api/public/directory/bot/triage",
        payload
      );

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: "bot",
        text: res.reply,
        recommendations: res.matched_tenants,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, botMsg]);

      // If matched tenants found, highlight first in map
      if (res.matched_tenants && res.matched_tenants.length > 0) {
        setSelectedTenantId(res.matched_tenants[0].id);
      }
    } catch (err: any) {
      toast.error("AI Concierge request failed.");
      const errorMsg: ChatMessage = {
        id: `bot-err-${Date.now()}`,
        sender: "bot",
        text: "I experienced an error analyzing your request. Please try selecting a location or service directly.",
        timestamp: "Just now",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setTriageLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary/20">
      {/* Top Header */}
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur-md px-4 sm:px-8 py-3.5 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-xs">
            <Compass className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-base sm:text-lg">
                National Booking Network
              </span>
              <Badge variant="outline" className="hidden sm:inline-flex text-[11px] border-primary/30 text-primary bg-primary/5">
                Verified Directory
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground hidden sm:block">
              Multi-Tenant Healthcare & Specialist Marketplace
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-10 min-h-[44px] gap-1.5 border-primary/30 hover:bg-primary/10 touch-manipulation"
            onClick={() => setConciergeOpen(true)}
          >
            <Bot className="h-4 w-4 text-primary" />
            <span className="hidden sm:inline">AI Concierge</span>
          </Button>
          <ThemeToggle />
          <Link to="/admin">
            <Button size="sm" variant="default" className="text-xs h-10 min-h-[44px] touch-manipulation px-3">
              Provider Login
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative border-b bg-gradient-to-b from-muted/40 via-background to-background pt-10 pb-8 px-4 sm:px-8">
        <div className="max-w-5xl mx-auto text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-primary text-xs font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>100% Accredited & Verified Specialists Across Australia</span>
          </div>

          <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-foreground max-w-3xl mx-auto leading-tight">
            Find & Book Verified Local Specialists Near You
          </h1>

          <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto">
            Search top-tier medical consultants, allied health, and clinical triage providers by postcode, radius, or instant AI matching.
          </p>

          {/* Search Controls Card */}
          <div className="mt-6 p-3 sm:p-4 rounded-2xl border bg-card/90 shadow-md backdrop-blur-sm max-w-3xl mx-auto">
            <div className="flex flex-col sm:flex-row gap-2.5">
              {/* Postcode / Suburb Input */}
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Postcode or Suburb (e.g. 2000, Parramatta, 3000)..."
                  className="pl-10 h-11 bg-background text-sm"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      executeSearch({ query: queryInput });
                    }
                  }}
                />
                {queryInput && (
                  <button
                    onClick={() => setQueryInput("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              {/* GPS Near Me Button */}
              <Button
                variant="outline"
                className="h-11 gap-1.5 text-xs font-medium shrink-0 px-3.5 border-primary/30 hover:bg-primary/10"
                onClick={handleNearMe}
                disabled={isLocating}
              >
                {isLocating ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Navigation className="h-4 w-4 text-primary" />
                )}
                <span>Near Me</span>
              </Button>

              {/* Search Submit */}
              <Button
                className="h-11 px-6 font-semibold shadow-sm shrink-0"
                onClick={() => executeSearch({ query: queryInput })}
                disabled={loading}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
                <span>Search Network</span>
              </Button>
            </div>

            {/* Sub-bar: Radius selector & Quick Postcodes */}
            <div className="mt-3.5 pt-3 border-t flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-medium flex items-center gap-1">
                  <SlidersHorizontal className="h-3 w-3" /> Radius:
                </span>
                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-lg border">
                  {RADIUS_OPTIONS.map((r) => (
                    <button
                      key={r}
                      onClick={() => {
                        setSelectedRadius(r);
                        executeSearch({ radius: r });
                      }}
                      className={`px-2.5 py-1 rounded-md transition-all font-medium ${
                        selectedRadius === r
                          ? "bg-primary text-primary-foreground shadow-xs"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {r} km
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick suggestion chips */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-muted-foreground hidden sm:inline">Popular:</span>
                {QUICK_LOCATIONS.map((loc) => (
                  <button
                    key={loc.query}
                    onClick={() => {
                      setQueryInput(loc.label);
                      executeSearch({ query: loc.query });
                    }}
                    className="px-2 py-0.5 rounded-md border text-[11px] bg-background hover:bg-accent transition-colors"
                  >
                    {loc.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Category Chips Bar */}
          <div className="flex items-center justify-center gap-2 pt-2 flex-wrap">
            {CATEGORY_CHIPS.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3.5 py-1 rounded-full text-xs font-medium border transition-all ${
                  selectedCategory === cat
                    ? "bg-primary/10 text-primary border-primary/40 shadow-xs font-semibold"
                    : "bg-background/80 text-muted-foreground border-border hover:border-primary/30"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Main Split Layout: Interactive Map & Directory Cards */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight">
              {searchResponse?.search_center ? (
                <>Verified Specialists near {searchResponse.search_center.label}</>
              ) : (
                <>Verified Network Specialists</>
              )}
            </h2>
            <p className="text-xs text-muted-foreground">
              Showing {filteredTenants.length} available provider(s) within {selectedRadius} km
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (5 cols): Interactive Map Component */}
          <div className="lg:col-span-5 w-full sticky top-20">
            <Card className="overflow-hidden border shadow-sm">
              <CardHeader className="p-3.5 border-b bg-muted/20 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm font-semibold">Interactive Network Map</CardTitle>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 2.0))}
                    title="Zoom in"
                  >
                    <ZoomIn className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 0.75))}
                    title="Zoom out"
                  >
                    <ZoomOut className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    onClick={() => setZoomLevel(1)}
                    title="Reset view"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>

              {/* Map Canvas / SVG Area */}
              <div className="relative h-80 sm:h-96 w-full bg-slate-950/5 dark:bg-slate-900/40 overflow-hidden select-none">
                {/* SVG Visual Map Grid & Geometry */}
                <svg
                  className="w-full h-full"
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  style={{
                    transform: `scale(${zoomLevel})`,
                    transformOrigin: "center center",
                    transition: "transform 0.2s ease-out",
                  }}
                >
                  <defs>
                    <radialGradient id="radiusGradient" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.15" />
                      <stop offset="90%" stopColor="rgb(59, 130, 246)" stopOpacity="0.05" />
                      <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0" />
                    </radialGradient>
                    <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                      <path
                        d="M 10 0 L 0 0 0 10"
                        fill="none"
                        stroke="currentColor"
                        strokeOpacity="0.06"
                        strokeWidth="0.5"
                      />
                    </pattern>
                  </defs>

                  {/* Grid background */}
                  <rect width="100" height="100" fill="url(#grid)" />

                  {/* Search Center Radius Circle */}
                  {searchResponse?.search_center && (
                    <circle
                      cx={projectCoords(searchResponse.search_center.lat, searchResponse.search_center.lng).x}
                      cy={projectCoords(searchResponse.search_center.lat, searchResponse.search_center.lng).y}
                      r="32"
                      fill="url(#radiusGradient)"
                      stroke="#3b82f6"
                      strokeWidth="0.5"
                      strokeDasharray="2,2"
                      className="animate-pulse"
                    />
                  )}

                  {/* Connecting dashed lines from center to pins */}
                  {searchResponse?.search_center &&
                    filteredTenants.map((t) => {
                      const cPos = projectCoords(searchResponse.search_center!.lat, searchResponse.search_center!.lng);
                      const tPos = projectCoords(t.latitude, t.longitude);
                      const isSelected = t.id === selectedTenantId;
                      return (
                        <line
                          key={`line-${t.id}`}
                          x1={cPos.x}
                          y1={cPos.y}
                          x2={tPos.x}
                          y2={tPos.y}
                          stroke={isSelected ? "#2563eb" : "#94a3b8"}
                          strokeWidth={isSelected ? "0.8" : "0.3"}
                          strokeDasharray={isSelected ? "none" : "1,1"}
                          strokeOpacity={isSelected ? 0.8 : 0.4}
                        />
                      );
                    })}
                </svg>

                {/* Search Center Origin Marker */}
                {searchResponse?.search_center && (
                  <div
                    className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-none z-10"
                    style={{
                      left: `${projectCoords(searchResponse.search_center.lat, searchResponse.search_center.lng).x}%`,
                      top: `${projectCoords(searchResponse.search_center.lat, searchResponse.search_center.lng).y}%`,
                    }}
                  >
                    <div className="relative flex items-center justify-center">
                      <div className="h-6 w-6 rounded-full bg-blue-500/20 animate-ping absolute" />
                      <div className="h-3 w-3 rounded-full bg-blue-600 border-2 border-white shadow-md z-10" />
                      <span className="absolute top-4 whitespace-nowrap bg-background/90 text-foreground border px-1.5 py-0.5 rounded text-[10px] font-semibold shadow-xs">
                        Search Center
                      </span>
                    </div>
                  </div>
                )}

                {/* Location Pins for each tenant */}
                {filteredTenants.map((t, idx) => {
                  const pos = projectCoords(t.latitude, t.longitude);
                  const isSelected = t.id === selectedTenantId;

                  return (
                    <div
                      key={t.id}
                      className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer z-20 group"
                      style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                      onClick={() => handleSelectTenant(t.id)}
                    >
                      <div className="relative flex flex-col items-center">
                        <div
                          className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-all shadow-md ${
                            isSelected
                              ? "bg-primary text-primary-foreground ring-4 ring-primary/30 scale-125"
                              : "bg-card text-foreground border-2 border-primary hover:scale-110"
                          }`}
                        >
                          {idx + 1}
                        </div>

                        {/* Pin Point */}
                        <div
                          className={`w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[5px] ${
                            isSelected ? "border-t-primary" : "border-t-primary/70"
                          }`}
                        />

                        {/* Floating Tooltip Label */}
                        <div
                          className={`absolute bottom-8 whitespace-nowrap px-2 py-1 rounded-md text-[11px] font-semibold shadow-lg border backdrop-blur-md transition-opacity pointer-events-none ${
                            isSelected
                              ? "bg-foreground text-background opacity-100 scale-100 z-30"
                              : "bg-background/95 text-foreground opacity-0 group-hover:opacity-100"
                          }`}
                        >
                          <div className="font-bold">{t.name}</div>
                          <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                            <span>{t.distance_km != null ? `📍 ${t.distance_km} km` : ""}</span>
                            <span>•</span>
                            <span>From ${t.starting_price.toFixed(0)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Map Bottom Info Legend */}
                <div className="absolute bottom-2 left-2 right-2 bg-background/80 backdrop-blur-xs border rounded-lg px-2.5 py-1.5 text-[11px] flex items-center justify-between text-muted-foreground">
                  <span>📍 Click pins to highlight specialist</span>
                  <span>{filteredTenants.length} pins active</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Column (7 cols): Directory Tenant Cards List */}
          <div className="lg:col-span-7 space-y-4">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-12 border rounded-2xl bg-card">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
                <p className="text-sm font-medium">Scanning verified provider network...</p>
              </div>
            ) : filteredTenants.length === 0 ? (
              <div className="text-center p-12 border rounded-2xl bg-card space-y-3">
                <Compass className="h-10 w-10 text-muted-foreground mx-auto" />
                <h3 className="text-base font-semibold">No specialists found in this radius</h3>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                  Try expanding your search radius to 50 km or clearing the category filter.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSelectedRadius(50);
                    setSelectedCategory("All");
                    executeSearch({ radius: 50 });
                  }}
                >
                  Expand to 50 km Radius
                </Button>
              </div>
            ) : (
              filteredTenants.map((tenant, idx) => {
                const isSelected = tenant.id === selectedTenantId;

                return (
                  <div
                    key={tenant.id}
                    ref={(el) => {
                      cardRefs.current[tenant.id] = el;
                    }}
                  >
                    <Card
                      className={`overflow-hidden transition-all duration-200 cursor-pointer border ${
                        isSelected
                          ? "ring-2 ring-primary border-primary bg-primary/[0.02] shadow-md"
                          : "hover:border-primary/40 hover:shadow-xs"
                      }`}
                      onClick={() => setSelectedTenantId(tenant.id)}
                    >
                      <CardContent className="p-4 sm:p-5">
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                          <div className="space-y-1 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="h-5 w-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[11px] font-bold">
                                {idx + 1}
                              </span>
                              <h3 className="font-bold text-base sm:text-lg text-foreground hover:text-primary transition-colors">
                                {tenant.name}
                              </h3>
                              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                                {tenant.subdomain}
                              </Badge>
                              <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-[10px] gap-1 py-0">
                                <ShieldCheck className="h-3 w-3" /> Verified
                              </Badge>
                            </div>

                            <p className="text-xs text-muted-foreground flex items-center gap-1.5 pt-0.5">
                              <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" />
                              <span>{tenant.address}</span>
                              {tenant.distance_km != null && (
                                <span className="font-semibold text-foreground bg-muted px-1.5 py-0.5 rounded text-[11px]">
                                  📍 {tenant.distance_km} km away
                                </span>
                              )}
                            </p>

                            <p className="text-xs text-muted-foreground line-clamp-2 pt-1">
                              {tenant.description ||
                                "Verified national provider offering in-clinic consultations and specialist appointments."}
                            </p>
                          </div>

                          {/* Price & Rating Badge */}
                          <div className="flex sm:flex-col items-baseline sm:items-end justify-between sm:justify-start gap-1 shrink-0">
                            <div className="flex items-center gap-1 text-xs font-bold text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded">
                              <Star className="h-3.5 w-3.5 fill-amber-500" />
                              <span>{tenant.rating.toFixed(1)}</span>
                              <span className="text-[10px] text-muted-foreground font-normal">
                                ({tenant.review_count})
                              </span>
                            </div>

                            <div className="text-right">
                              <span className="text-[11px] text-muted-foreground">Starting from</span>
                              <div className="text-base sm:text-lg font-extrabold text-foreground">
                                ${tenant.starting_price.toFixed(0)}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Featured Services Badges */}
                        {tenant.featured_services && tenant.featured_services.length > 0 && (
                          <div className="mt-3.5 pt-3 border-t flex flex-wrap items-center gap-1.5">
                            <span className="text-[11px] text-muted-foreground font-medium mr-1">
                              Services:
                            </span>
                            {tenant.featured_services.map((svc) => (
                              <span
                                key={svc.id}
                                className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-muted/60 border text-foreground"
                              >
                                <Clock className="h-2.5 w-2.5 text-muted-foreground" />
                                {svc.name} (${svc.price.toFixed(0)})
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Actions */}
                        <div className="mt-4 flex items-center justify-between gap-2 pt-2 border-t">
                          <Link
                            to={tenant.website_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
                          >
                            <Globe className="h-3.5 w-3.5" />
                            <span>Visit Website</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>

                          <div className="flex items-center gap-2">
                            <Link to={tenant.booking_url}>
                              <Button size="sm" className="h-10 min-h-[44px] text-xs font-semibold gap-1.5 shadow-xs touch-manipulation px-4">
                                <Calendar className="h-4 w-4" />
                                <span>Book Online</span>
                                <ArrowRight className="h-3.5 w-3.5" />
                              </Button>
                            </Link>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>

      {/* Floating Umbrella AI Triage Concierge Widget */}
      <div className="fixed bottom-5 right-5 z-50">
        {!conciergeOpen ? (
          <Button
            onClick={() => setConciergeOpen(true)}
            size="lg"
            className="rounded-full h-14 px-5 shadow-2xl bg-primary text-primary-foreground hover:bg-primary/95 flex items-center gap-2.5 border-2 border-primary-foreground/20 hover:scale-105 transition-all"
          >
            <div className="relative">
              <Bot className="h-6 w-6" />
              <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-background animate-pulse" />
            </div>
            <div className="text-left leading-tight hidden sm:block">
              <div className="text-xs font-extrabold tracking-wide uppercase">AI Concierge</div>
              <div className="text-[11px] opacity-90">Find Specialist Now</div>
            </div>
          </Button>
        ) : (
          <Card className="w-[92vw] sm:w-96 shadow-2xl border-2 border-primary/30 rounded-2xl overflow-hidden flex flex-col h-[520px] max-h-[85vh] animate-in fade-in slide-in-from-bottom-5">
            {/* Header */}
            <div className="p-3.5 border-b bg-primary text-primary-foreground flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-7 w-7 rounded-lg bg-primary-foreground/15 flex items-center justify-center">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider">Directory AI Concierge</h4>
                  <p className="text-[10px] opacity-80 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    Online • Instant Triage & Booking
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-primary-foreground hover:bg-primary-foreground/10 rounded-full"
                onClick={() => setConciergeOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Quick Suggestion Prompts */}
            <div className="p-2 border-b bg-muted/40 flex items-center gap-1.5 overflow-x-auto text-[11px] no-scrollbar">
              <button
                onClick={() => handleTriageSubmit("Find closest to Sydney CBD")}
                className="whitespace-nowrap px-2.5 py-1 rounded-full bg-background border hover:border-primary transition-colors"
              >
                Closest to Sydney CBD
              </button>
              <button
                onClick={() => handleTriageSubmit("Same-day rapid triage")}
                className="whitespace-nowrap px-2.5 py-1 rounded-full bg-background border hover:border-primary transition-colors"
              >
                Same-day triage
              </button>
              <button
                onClick={() => handleTriageSubmit("Best rated consultation under 15km")}
                className="whitespace-nowrap px-2.5 py-1 rounded-full bg-background border hover:border-primary transition-colors"
              >
                Best rated (&lt;15km)
              </button>
            </div>

            {/* Chat Thread */}
            <div className="flex-1 p-3 overflow-y-auto space-y-3 text-xs">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-xl p-3 shadow-xs ${
                      msg.sender === "user"
                        ? "bg-primary text-primary-foreground rounded-br-none"
                        : "bg-muted text-foreground border rounded-bl-none whitespace-pre-line"
                    }`}
                  >
                    {msg.text}
                  </div>

                  {/* Recommendation Cards if returned */}
                  {msg.recommendations && msg.recommendations.length > 0 && (
                    <div className="mt-2 space-y-1.5 w-full max-w-[90%]">
                      {msg.recommendations.map((rec) => (
                        <div
                          key={rec.id}
                          className="p-2.5 rounded-lg border bg-card text-foreground shadow-xs flex items-center justify-between gap-2"
                        >
                          <div className="min-w-0">
                            <div className="font-bold text-xs truncate">{rec.name}</div>
                            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                              <span>📍 {rec.distance_km} km</span>
                              <span>•</span>
                              <span>From ${rec.starting_price}</span>
                              <span>•</span>
                              <span className="text-amber-500 font-semibold">{rec.rating} ★</span>
                            </div>
                          </div>
                          <Link to={rec.booking_url}>
                            <Button size="sm" className="h-7 text-[11px] px-2.5 font-bold shrink-0">
                              Book
                            </Button>
                          </Link>
                        </div>
                      ))}
                    </div>
                  )}

                  <span className="text-[9px] text-muted-foreground mt-0.5 px-1">
                    {msg.timestamp}
                  </span>
                </div>
              ))}

              {triageLoading && (
                <div className="flex items-center gap-2 text-muted-foreground bg-muted p-2 rounded-xl text-xs w-fit">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span>Searching national verified network...</span>
                </div>
              )}
            </div>

            {/* Input Bar */}
            <div className="p-2.5 border-t bg-background flex items-center gap-2">
              <Input
                placeholder="Ask e.g. Need standard consultation in Sydney under 15km..."
                className="h-9 text-xs"
                value={triageInput}
                onChange={(e) => setTriageInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTriageSubmit();
                }}
                disabled={triageLoading}
              />
              <Button
                size="icon"
                className="h-9 w-9 shrink-0"
                onClick={() => handleTriageSubmit()}
                disabled={triageLoading || !triageInput.trim()}
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t bg-muted/20 mt-auto py-6 px-4 text-center text-xs text-muted-foreground">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© {new Date().getFullYear()} National Booking Network. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link to="/directory" className="hover:text-foreground">
              Umbrella Directory
            </Link>
            <Link to="/admin" className="hover:text-foreground">
              Provider Portal
            </Link>
            <Link to="/book" className="hover:text-foreground">
              Direct Booking
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
