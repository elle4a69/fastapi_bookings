import React, { useState, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  CheckCircle2,
  XCircle,
  Clock,
  Ban,
  Phone,
  Mail,
  MapPin,
  Download,
  SlidersHorizontal,
  CalendarCheck,
  FileText,
  Search,
  User,
  RotateCcw,
  Edit2,
  Calendar as CalendarIcon,
  Tag,
  DollarSign
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const HOUR_HEIGHT = 64;
const HOURS = Array.from({ length: 14 }, (_, i) => i + 7); // 7am to 8pm

interface ApiBooking {
  id: number | string;
  client_id: number;
  provider_id: number;
  service_id: number;
  location_id?: number | null;
  start_time: string;
  end_time: string;
  status: string;
  notes?: string | null;
  client?: { id: number; name: string; email?: string; phone?: string } | null;
  provider?: { id: number; name: string; email?: string; color?: string } | null;
  service?: { id: number; name: string; duration: number; price?: number } | null;
  location?: { id: number; name: string } | null;
}

interface CalendarBooking {
  id: string;
  date: Date;
  endDate: Date;
  service: string;
  serviceId: number;
  provider: string;
  providerId: number;
  client: string;
  clientId: number;
  email: string;
  phone: string;
  duration: number;
  status: string;
  price: string;
  location: string;
  locationId?: number;
  notes: string;
  raw: ApiBooking;
}

const STATUS_PILL: Record<string, string> = {
  confirmed: "bg-teal-600 text-white",
  pending: "bg-amber-500 text-white",
  completed: "bg-emerald-600 text-white",
  cancelled: "bg-rose-500 text-white",
  noshow: "bg-zinc-500 text-white",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  confirmed: <CheckCircle2 className="w-3.5 h-3.5" />,
  pending: <Clock className="w-3.5 h-3.5" />,
  completed: <CheckCircle2 className="w-3.5 h-3.5" />,
  cancelled: <XCircle className="w-3.5 h-3.5" />,
  noshow: <Ban className="w-3.5 h-3.5" />,
};

const DAYS_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function fmt12(date: Date) {
  const h = date.getHours() % 12 || 12;
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${min} ${date.getHours() < 12 ? "AM" : "PM"}`;
}

function formatDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function isSameDay(d1: Date, d2: Date) {
  return d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();
}

function getStartOfWeek(date: Date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day;
  return new Date(d.setDate(diff));
}

// ─── Month Grid ───────────────────────────────────────────────────────────
function MonthGrid({
  currentDate,
  bookings,
  filterProvider,
  filterLocation,
  onSelectBooking,
  onNewBooking
}: {
  currentDate: Date;
  bookings: CalendarBooking[];
  filterProvider: string;
  filterLocation: string;
  onSelectBooking: (b: CalendarBooking) => void;
  onNewBooking: (d: Date) => void;
}) {
  const yr = currentDate.getFullYear();
  const mo = currentDate.getMonth();
  const firstDay = new Date(yr, mo, 1).getDay();
  const totalDays = new Date(yr, mo + 1, 0).getDate();

  const prevMonthDays = new Date(yr, mo, 0).getDate();
  type Cell = { day: number; thisMonth: boolean; date: Date };
  const cells: Cell[] = [];
  for (let i = firstDay - 1; i >= 0; i--) cells.push({ day: prevMonthDays - i, thisMonth: false, date: new Date(yr, mo - 1, prevMonthDays - i) });
  for (let d = 1; d <= totalDays; d++) cells.push({ day: d, thisMonth: true, date: new Date(yr, mo, d) });
  let nextDay = 1;
  while (cells.length % 7 !== 0) { cells.push({ day: nextDay, thisMonth: false, date: new Date(yr, mo + 1, nextDay) }); nextDay++; }

  const filtered = bookings.filter(b => {
    if (filterProvider !== "all" && String(b.providerId) !== filterProvider && b.provider !== filterProvider) return false;
    if (filterLocation !== "all" && String(b.locationId) !== filterLocation && b.location !== filterLocation) return false;
    return true;
  });

  const getDayBkgs = (cell: Cell) => filtered.filter(b => isSameDay(b.date, cell.date)).sort((a, b) => a.date.getTime() - b.date.getTime());

  const isToday = (cell: Cell) => isSameDay(new Date(), cell.date);
  const isWeekend = (cell: Cell) => cell.date.getDay() === 0 || cell.date.getDay() === 6;

  const weeks: Cell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* 
        Scroll container wraps both weekday headers and grid cells 
        so header grid-cols-7 matches column widths down to exact pixel
      */}
      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-7 border-b border-border sticky top-0 bg-background z-20 shadow-xs">
          {DAYS_FULL.map(d => (
            <div key={d} className="py-2.5 text-center text-xs font-bold text-muted-foreground uppercase tracking-wider border-r border-border last:border-r-0">
              {d}
            </div>
          ))}
        </div>
        <div className="flex flex-col min-h-[calc(100%-37px)]">
          {weeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 flex-1 min-h-[120px]">
              {week.map((cell, di) => {
                const dayBkgs = getDayBkgs(cell);
                const closed = isWeekend(cell) && cell.thisMonth;
                return (
                  <div
                    key={di}
                    onClick={() => onNewBooking(cell.date)}
                    className={`border-r border-b border-border last:border-r-0 flex flex-col p-1.5 cursor-pointer transition-colors hover:bg-primary/5
                      ${!cell.thisMonth ? "bg-muted/30 opacity-60" : "bg-card"}
                      ${isToday(cell) ? "bg-primary/5 ring-1 ring-primary/20" : ""}
                    `}
                    style={closed ? { backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(234,179,8,0.06) 6px, rgba(234,179,8,0.06) 12px)" } : {}}
                  >
                    <div className="flex items-center justify-between px-1 mb-1">
                      <span className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full
                        ${isToday(cell) ? "bg-primary text-primary-foreground font-bold shadow-xs" : ""}
                        ${!cell.thisMonth ? "text-muted-foreground/50" : "text-foreground"}
                      `}>
                        {cell.day}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 overflow-hidden">
                      {dayBkgs.slice(0, 4).map(b => (
                        <div
                          key={b.id}
                          onClick={(e) => { e.stopPropagation(); onSelectBooking(b); }}
                          className={`w-full text-left rounded px-1.5 py-1 text-[11px] font-medium truncate leading-tight transition-all hover:scale-[1.01] hover:shadow-xs flex items-center gap-1 shadow-2xs
                            ${STATUS_PILL[b.status] || "bg-primary text-white"}`}
                        >
                          <span className="shrink-0 font-bold">{fmt12(b.date)}</span>
                          <span className="truncate">{b.client}</span>
                          <span className="ml-auto shrink-0">{STATUS_ICON[b.status]}</span>
                        </div>
                      ))}
                      {dayBkgs.length > 4 && (
                        <span className="text-[10px] text-muted-foreground pl-1 font-medium">+{dayBkgs.length - 4} more</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Time Grid Base ───────────────────────────────────────────────────────────
function TimeGrid({
  days,
  bookings,
  onSelectBooking,
  filterProvider,
  filterLocation,
  onUpdateBooking,
  onNewBooking,
  onUpdateDuration
}: {
  days: Date[];
  bookings: CalendarBooking[];
  onSelectBooking: (b: CalendarBooking) => void;
  filterProvider: string;
  filterLocation: string;
  onUpdateBooking: (id: string, newDate: Date) => void;
  onNewBooking: (date: Date) => void;
  onUpdateDuration?: (id: string, newDuration: number) => void;
}) {
  const filtered = bookings.filter(b => {
    if (filterProvider !== "all" && String(b.providerId) !== filterProvider && b.provider !== filterProvider) return false;
    if (filterLocation !== "all" && String(b.locationId) !== filterLocation && b.location !== filterLocation) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      <div className="flex flex-1 overflow-y-auto relative">
        <div className="w-full flex flex-col min-h-full">
          {/* Header row sticky inside scroll container for exact column alignment */}
          <div className="flex border-b border-border flex-shrink-0 sticky top-0 bg-background z-30 shadow-xs">
            <div className="w-16 flex-shrink-0 border-r border-border bg-muted/20"></div>
            {days.map((d, i) => (
              <div key={i} className="flex-1 py-2 text-center border-r border-border last:border-r-0">
                <div className="text-xs font-semibold text-muted-foreground uppercase">{DAYS_FULL[d.getDay()]}</div>
                <div className={`text-base font-bold mt-0.5 ${isSameDay(d, new Date()) ? "text-primary" : "text-foreground"}`}>{d.getDate()}</div>
              </div>
            ))}
          </div>

          <div className="flex relative flex-1" style={{ height: `${HOURS.length * HOUR_HEIGHT}px` }}>
            {/* Time labels axis */}
            <div className="w-16 flex-shrink-0 border-r border-border relative bg-muted/10 z-10">
              {HOURS.map((h, i) => (
                <div key={i} className="absolute w-full text-right pr-2 text-xs font-medium text-muted-foreground transform -translate-y-1/2" style={{ top: `${i * HOUR_HEIGHT}px` }}>
                  {h > 12 ? h - 12 : h}{h >= 12 ? ' PM' : ' AM'}
                </div>
              ))}
            </div>

            {/* Grid lines and columns */}
            <div className="flex-1 flex relative">
              <div className="absolute inset-0 pointer-events-none">
                {Array.from({ length: HOURS.length * 4 }).map((_, i) => {
                  const isHour = i % 4 === 0;
                  return (
                    <div
                      key={i}
                      className={`border-t absolute w-full ${isHour ? 'border-border/80' : 'border-border/20'}`}
                      style={{ top: `${i * (HOUR_HEIGHT / 4)}px` }}
                    />
                  );
                })}
              </div>

              {/* Day columns */}
              {days.map((day, i) => {
                const dayBkgs = filtered.filter(b => isSameDay(b.date, day));
                return (
                  <div
                    key={i}
                    className="flex-1 border-r border-border last:border-r-0 relative cursor-pointer hover:bg-primary/[0.02] transition-colors"
                    onClick={(e) => {
                      if (e.target !== e.currentTarget) return;
                      const rect = e.currentTarget.getBoundingClientRect();
                      const clickY = e.clientY - rect.top;
                      const clickHour = Math.floor(clickY / HOUR_HEIGHT) + HOURS[0];
                      const clickMinute = Math.round((clickY % HOUR_HEIGHT) / (HOUR_HEIGHT / 4)) * 15;
                      const d = new Date(day);
                      d.setHours(clickHour, clickMinute, 0, 0);
                      onNewBooking(d);
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const bookingId = e.dataTransfer.getData("bookingId");
                      if (!bookingId) return;
                      const offsetY = parseFloat(e.dataTransfer.getData("offsetY") || "0");
                      const rect = e.currentTarget.getBoundingClientRect();
                      const dropY = e.clientY - rect.top - offsetY;

                      const newHour = Math.floor(dropY / HOUR_HEIGHT) + HOURS[0];
                      const newMinute = Math.round((dropY % HOUR_HEIGHT) / (HOUR_HEIGHT / 4)) * 15;

                      const newDate = new Date(day);
                      newDate.setHours(newHour, newMinute, 0, 0);
                      onUpdateBooking(bookingId, newDate);
                    }}
                  >
                    {dayBkgs.map(b => {
                      const hour = b.date.getHours();
                      const min = b.date.getMinutes();
                      if (hour < 7 || hour >= 21) return null;

                      const topPx = (hour - 7 + min / 60) * HOUR_HEIGHT;
                      const heightPx = (b.duration / 60) * HOUR_HEIGHT;

                      return (
                        <div
                          key={b.id}
                          draggable={true}
                          onDragStart={(e) => {
                            const rect = e.currentTarget.getBoundingClientRect();
                            const offset = e.clientY - rect.top;
                            e.dataTransfer.setData("bookingId", b.id);
                            e.dataTransfer.setData("offsetY", offset.toString());
                            e.currentTarget.style.opacity = '0.5';
                          }}
                          onDragEnd={(e) => {
                            e.currentTarget.style.opacity = '1';
                          }}
                          onClick={(e) => { e.stopPropagation(); onSelectBooking(b); }}
                          className={`absolute left-1 right-1 rounded-lg p-2 text-xs overflow-hidden cursor-grab active:cursor-grabbing transition-all hover:shadow-md shadow-xs group/block
                            ${STATUS_PILL[b.status] || "bg-primary text-white"}`}
                          style={{ top: `${topPx}px`, height: `${Math.max(28, heightPx - 2)}px` }}
                        >
                          <div className="font-bold pointer-events-none truncate flex items-center justify-between">
                            <span>{fmt12(b.date)} · {b.client}</span>
                            <span className="shrink-0">{STATUS_ICON[b.status]}</span>
                          </div>
                          <div className="text-[10px] opacity-90 truncate pointer-events-none mt-0.5">{b.service} ({b.duration}m)</div>

                          {/* Grab handle for duration resize */}
                          {onUpdateDuration && (
                            <div
                              className="absolute bottom-0 left-0 right-0 h-2.5 cursor-ns-resize hover:bg-black/20 dark:hover:bg-white/20 flex items-center justify-center transition-colors group/resize z-20"
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                const startY = e.clientY;
                                const startDuration = b.duration;

                                const onMouseMove = (moveEvent: MouseEvent) => {
                                  const deltaY = moveEvent.clientY - startY;
                                  const deltaMinutes = Math.round((deltaY / HOUR_HEIGHT) * 4) * 15;
                                  const newDuration = Math.max(15, startDuration + deltaMinutes);
                                  onUpdateDuration(b.id, newDuration);
                                };

                                const onMouseUp = () => {
                                  window.removeEventListener('mousemove', onMouseMove);
                                  window.removeEventListener('mouseup', onMouseUp);
                                };

                                window.addEventListener('mousemove', onMouseMove);
                                window.addEventListener('mouseup', onMouseUp);
                              }}
                            >
                              <div className="w-8 h-1 rounded-full bg-white/50 group-hover/resize:bg-white/90" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Calendar Page ───────────────────────────────────────────────────────────
export default function CalendarPage() {
  const [bookings, setBookings] = useState<CalendarBooking[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [notes, setNotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewType, setViewType] = useState<"month" | "week" | "day">("month");
  const [filterProvider, setFilterProvider] = useState("all");
  const [filterLocation, setFilterLocation] = useState("all");

  // Dialog States
  const [selectedBooking, setSelectedBooking] = useState<CalendarBooking | null>(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [createBookingOpen, setCreateBookingOpen] = useState(false);
  const [createNoteOpen, setCreateNoteOpen] = useState(false);
  const [addClientOpen, setAddClientOpen] = useState(false);
  const [allNotesOpen, setAllNotesOpen] = useState(false);
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);

  // Create/Edit Form State
  const [formDate, setFormDate] = useState<string>("");
  const [formTime, setFormTime] = useState<string>("09:00");
  const [formClientId, setFormClientId] = useState<string>("");
  const [formServiceId, setFormServiceId] = useState<string>("");
  const [formProviderId, setFormProviderId] = useState<string>("");
  const [formLocationId, setFormLocationId] = useState<string>("");
  const [formStatus, setFormStatus] = useState<string>("confirmed");
  const [formNotes, setFormNotes] = useState<string>("");

  // Create Client Form State
  const [newClientName, setNewClientName] = useState("");
  const [newClientEmail, setNewClientEmail] = useState("");
  const [newClientPhone, setNewClientPhone] = useState("");

  // Note Form State
  const [noteText, setNoteText] = useState("");
  const [noteProviderId, setNoteProviderId] = useState<string>("all");
  const [noteDate, setNoteDate] = useState<string>("");

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [bRes, sRes, pRes, lRes, cRes, nRes] = await Promise.all([
        apiClient.get<any>("/api/bookings?page_size=200").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/clients").catch(() => []),
        apiClient.get<any>("/api/admin/calendar-notes").catch(() => [])
      ]);

      const rawBookings = Array.isArray(bRes) ? bRes : (bRes?.data ?? bRes?.items ?? []);
      const rawServices = Array.isArray(sRes) ? sRes : (sRes?.data ?? sRes?.items ?? []);
      const rawProviders = Array.isArray(pRes) ? pRes : (pRes?.data ?? pRes?.items ?? []);
      const rawLocations = Array.isArray(lRes) ? lRes : (lRes?.data ?? lRes?.items ?? []);
      const rawClients = Array.isArray(cRes) ? cRes : (cRes?.data ?? cRes?.items ?? []);
      const rawNotes = Array.isArray(nRes) ? nRes : (nRes?.data ?? nRes?.items ?? []);

      setServices(rawServices);
      setProviders(rawProviders);
      setLocations(rawLocations);
      setClients(rawClients);
      setNotes(rawNotes);

      const mappedBookings: CalendarBooking[] = rawBookings.map((b: ApiBooking) => {
        const start = new Date(b.start_time);
        const end = new Date(b.end_time);
        const dur = Math.max(15, Math.round((end.getTime() - start.getTime()) / 60000));
        return {
          id: String(b.id),
          date: start,
          endDate: end,
          service: b.service?.name || "Service",
          serviceId: b.service_id,
          provider: b.provider?.name || "Unassigned",
          providerId: b.provider_id,
          client: b.client?.name || "Client",
          clientId: b.client_id,
          email: b.client?.email || "",
          phone: b.client?.phone || "",
          duration: dur,
          status: (b.status || "confirmed").toLowerCase(),
          price: b.service?.price ? `$${Number(b.service.price).toFixed(2)}` : "$0.00",
          location: b.location?.name || "Main Branch",
          locationId: b.location_id || undefined,
          notes: b.notes || "",
          raw: b
        };
      });

      setBookings(mappedBookings);
    } catch (err: any) {
      toast.error(err.message || "Failed to load calendar data.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateBooking = (d?: Date, serviceId?: string, clientId?: string) => {
    const targetDate = d || new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    setFormDate(`${targetDate.getFullYear()}-${pad(targetDate.getMonth() + 1)}-${pad(targetDate.getDate())}`);
    setFormTime(`${pad(targetDate.getHours())}:${pad(targetDate.getMinutes())}`);

    setFormClientId(clientId || (clients[0]?.id ? String(clients[0].id) : ""));
    setFormServiceId(serviceId || (services[0]?.id ? String(services[0].id) : ""));
    setFormProviderId(providers[0]?.id ? String(providers[0].id) : "");
    setFormLocationId(locations[0]?.id ? String(locations[0].id) : "");
    setFormStatus("confirmed");
    setFormNotes("");
    setCreateBookingOpen(true);
  };

  const handleSaveBooking = async () => {
    if (!formClientId || !formServiceId || !formProviderId || !formDate || !formTime) {
      toast.error("Please fill in all required fields (Client, Service, Provider, Date, Time).");
      return;
    }

    try {
      const [hours, mins] = formTime.split(':').map(Number);
      const start = new Date(formDate);
      start.setHours(hours, mins, 0, 0);

      const svc = services.find(s => String(s.id) === String(formServiceId));
      const dur = svc?.duration || 60;
      const end = new Date(start.getTime() + dur * 60000);

      const payload = {
        client_id: parseInt(formClientId),
        service_id: parseInt(formServiceId),
        provider_id: parseInt(formProviderId),
        location_id: formLocationId ? parseInt(formLocationId) : null,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: formNotes || null
      };

      await apiClient.post("/api/bookings", payload);
      toast.success("Booking created successfully!");
      setCreateBookingOpen(false);
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to create booking.");
    }
  };

  const handleOpenEditBooking = (b: CalendarBooking) => {
    setSelectedBooking(b);
    const pad = (n: number) => String(n).padStart(2, '0');
    setFormDate(`${b.date.getFullYear()}-${pad(b.date.getMonth() + 1)}-${pad(b.date.getDate())}`);
    setFormTime(`${pad(b.date.getHours())}:${pad(b.date.getMinutes())}`);

    setFormClientId(String(b.clientId));
    setFormServiceId(String(b.serviceId));
    setFormProviderId(String(b.providerId));
    setFormLocationId(b.locationId ? String(b.locationId) : "");
    setFormStatus(b.status);
    setFormNotes(b.notes || "");

    setViewDialogOpen(false);
    setEditDialogOpen(true);
  };

  const handleUpdateBookingSubmit = async () => {
    if (!selectedBooking) return;
    try {
      const [hours, mins] = formTime.split(':').map(Number);
      const start = new Date(formDate);
      start.setHours(hours, mins, 0, 0);

      const svc = services.find(s => String(s.id) === String(formServiceId));
      const dur = svc?.duration || selectedBooking.duration || 60;
      const end = new Date(start.getTime() + dur * 60000);

      const payload = {
        provider_id: parseInt(formProviderId),
        service_id: parseInt(formServiceId),
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        status: formStatus.toUpperCase(),
        notes: formNotes || null
      };

      await apiClient.put(`/api/bookings/${selectedBooking.id}`, payload);
      toast.success("Booking updated!");
      setEditDialogOpen(false);
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update booking.");
    }
  };

  const handleUpdateBookingStatus = async (b: CalendarBooking, nextStatus: string) => {
    try {
      await apiClient.put(`/api/bookings/${b.id}`, { status: nextStatus.toUpperCase() });
      toast.success(`Booking status changed to ${nextStatus}`);
      setViewDialogOpen(false);
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update status.");
    }
  };

  const handleUpdateBookingDate = async (id: string, newDate: Date) => {
    const existing = bookings.find(b => b.id === id);
    if (!existing) return;
    const dur = existing.duration || 60;
    const newEnd = new Date(newDate.getTime() + dur * 60000);

    try {
      await apiClient.put(`/api/bookings/${id}`, {
        start_time: newDate.toISOString(),
        end_time: newEnd.toISOString()
      });
      toast.success("Booking rescheduled!");
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to reschedule booking.");
    }
  };

  const handleUpdateDuration = async (id: string, newDuration: number) => {
    const existing = bookings.find(b => b.id === id);
    if (!existing) return;
    const newEnd = new Date(existing.date.getTime() + newDuration * 60000);

    try {
      await apiClient.put(`/api/bookings/${id}`, {
        end_time: newEnd.toISOString()
      });
      toast.success("Duration updated!");
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update duration.");
    }
  };

  const handleSaveClient = async () => {
    if (!newClientName) {
      toast.error("Client name is required.");
      return;
    }
    try {
      const res = await apiClient.post<any>("/api/admin/clients", {
        name: newClientName,
        email: newClientEmail || null,
        phone: newClientPhone || null
      });
      toast.success("Client added!");
      setAddClientOpen(false);
      setNewClientName("");
      setNewClientEmail("");
      setNewClientPhone("");
      const refreshed = await apiClient.get<any>("/api/admin/clients").catch(() => []);
      const raw = Array.isArray(refreshed) ? refreshed : (refreshed?.data ?? refreshed?.items ?? []);
      setClients(raw);
      if (res?.id || res?.data?.id) {
        setFormClientId(String(res.id || res.data.id));
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to create client.");
    }
  };

  const handleSaveNote = async () => {
    if (!noteText) {
      toast.error("Please enter a note.");
      return;
    }
    try {
      const pId = noteProviderId !== "all" ? parseInt(noteProviderId) : null;
      await apiClient.post("/api/admin/calendar-notes", {
        note: noteText,
        date: noteDate || new Date().toISOString().split('T')[0],
        provider_id: pId
      });
      toast.success("Calendar note saved!");
      setCreateNoteOpen(false);
      setNoteText("");
      loadAllData();
    } catch (err: any) {
      toast.error(err.message || "Failed to save note.");
    }
  };

  const navigateDate = (dir: -1 | 1) => {
    const d = new Date(currentDate);
    if (viewType === "month") d.setMonth(d.getMonth() + dir);
    else if (viewType === "week") d.setDate(d.getDate() + (dir * 7));
    else d.setDate(d.getDate() + dir);
    setCurrentDate(d);
  };

  let headingLabel = "";
  if (viewType === "month") {
    headingLabel = `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
  } else if (viewType === "week") {
    const start = getStartOfWeek(currentDate);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    headingLabel = `${MONTH_NAMES[start.getMonth()]} ${start.getDate()} - ${end.getDate()}, ${start.getFullYear()}`;
  } else {
    headingLabel = `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getDate()}, ${currentDate.getFullYear()}`;
  }

  const getStatusBadge = (status: string) => (
    <Badge className={`${STATUS_PILL[status] || "bg-primary text-white"} border-0 gap-1.5 px-2.5 py-0.5 text-xs font-semibold`}>
      {STATUS_ICON[status]}{status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* ── Header ─────────────────────────────────────── */}
      <div className="px-6 py-4 flex items-center justify-between border-b shrink-0 bg-card">
        <div className="flex items-center gap-3">
          <CalendarIcon className="w-6 h-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">Calendar</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2 h-9" onClick={() => window.location.href = '/admin/finance/payments'}>
            <FileText className="w-4 h-4" /> Transactions
          </Button>
          <Button variant="outline" size="sm" className="gap-2 h-9" onClick={() => setAllNotesOpen(true)}>
            <FileText className="w-4 h-4" /> All Notes ({notes.length})
          </Button>
        </div>
      </div>

      {/* ── Toolbar ──────────────────────────────────────── */}
      <div className="px-6 py-2.5 flex items-center gap-2 border-b shrink-0 flex-wrap bg-card/50">
        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => window.location.href = '/admin/schedule/workdays'}>
          Edit schedules <ChevronRight className="w-3 h-3" />
        </Button>
        <Button size="sm" className="h-8 gap-1.5 bg-teal-600 hover:bg-teal-700 text-white border-0" onClick={() => window.location.href = '/admin/bookings'}>
          <CalendarCheck className="w-3.5 h-3.5" /> Manage bookings
        </Button>
        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => {
          setNoteDate(new Date().toISOString().split('T')[0]);
          setCreateNoteOpen(true);
        }}>
          <Plus className="w-3.5 h-3.5" /> Add Note / Block Time
        </Button>

        <div className="flex-1" />

        {/* Provider filter */}
        <Select value={filterProvider} onValueChange={setFilterProvider}>
          <SelectTrigger className="h-8 w-[160px] text-xs">
            <SelectValue placeholder="All Providers" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Providers</SelectItem>
            {providers.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>

        {/* Location filter */}
        <Select value={filterLocation} onValueChange={setFilterLocation}>
          <SelectTrigger className="h-8 w-[150px] text-xs">
            <SelectValue placeholder="All Locations" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Locations</SelectItem>
            {locations.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>)}
          </SelectContent>
        </Select>

        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => setFilterDialogOpen(true)}>
          <SlidersHorizontal className="w-3.5 h-3.5" /> Filter
        </Button>
        <Button size="sm" className="h-8 gap-1.5" onClick={() => handleOpenCreateBooking()}>
          <Plus className="w-3.5 h-3.5" /> New Booking
        </Button>
      </div>

      {/* ── View Controls ──────────────────────────────────── */}
      <div className="px-6 py-2 flex items-center gap-3 border-b shrink-0 bg-background">
        <div className="flex items-center p-1 bg-muted rounded-lg">
          <Button
            variant={viewType === "month" ? "default" : "ghost"}
            size="sm"
            className="h-7 px-3 text-xs"
            onClick={() => setViewType("month")}
          >
            Month
          </Button>
          <Button
            variant={viewType === "week" ? "default" : "ghost"}
            size="sm"
            className="h-7 px-3 text-xs"
            onClick={() => setViewType("week")}
          >
            Week
          </Button>
          <Button
            variant={viewType === "day" ? "default" : "ghost"}
            size="sm"
            className="h-7 px-3 text-xs"
            onClick={() => setViewType("day")}
          >
            Day
          </Button>
        </div>

        <Button variant="outline" size="sm" className="h-8 px-3" onClick={() => setCurrentDate(new Date())}>
          Today
        </Button>

        <div className="flex-1" />

        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(-1)}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="font-semibold text-sm min-w-[180px] text-center">{headingLabel}</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(1)}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1" />
      </div>

      {/* ── Calendar Body ────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden relative">
        {viewType === "month" && (
          <MonthGrid
            currentDate={currentDate}
            bookings={bookings}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onSelectBooking={(b) => { setSelectedBooking(b); setViewDialogOpen(true); }}
            onNewBooking={handleOpenCreateBooking}
          />
        )}
        {viewType === "week" && (
          <TimeGrid
            days={Array.from({ length: 7 }, (_, i) => {
              const d = getStartOfWeek(currentDate);
              d.setDate(d.getDate() + i);
              return d;
            })}
            bookings={bookings}
            onSelectBooking={(b) => { setSelectedBooking(b); setViewDialogOpen(true); }}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onUpdateBooking={handleUpdateBookingDate}
            onNewBooking={handleOpenCreateBooking}
            onUpdateDuration={handleUpdateDuration}
          />
        )}
        {viewType === "day" && (
          <TimeGrid
            days={[currentDate]}
            bookings={bookings}
            onSelectBooking={(b) => { setSelectedBooking(b); setViewDialogOpen(true); }}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onUpdateBooking={handleUpdateBookingDate}
            onNewBooking={handleOpenCreateBooking}
            onUpdateDuration={handleUpdateDuration}
          />
        )}
      </div>

      {/* ── View Booking Modal (Centered Dialog) ───────────────── */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden rounded-xl">
          <DialogHeader className="p-6 pb-4 border-b bg-card">
            <div className="flex items-center justify-between pr-6">
              <div>
                <DialogTitle className="text-xl font-bold flex items-center gap-3">
                  Booking #{selectedBooking?.id}
                  {selectedBooking && getStatusBadge(selectedBooking.status)}
                </DialogTitle>
                <DialogDescription className="mt-1">
                  {selectedBooking?.date.toLocaleString("en-US", { dateStyle: "full", timeStyle: "short" })}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {selectedBooking && (
            <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
              <Tabs defaultValue="details" className="w-full">
                <TabsList className="grid grid-cols-3 w-full mb-4">
                  <TabsTrigger value="details">Appointment</TabsTrigger>
                  <TabsTrigger value="client">Client Info</TabsTrigger>
                  <TabsTrigger value="payment">Payment & Notes</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="space-y-4 pt-1">
                  <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border bg-card/60">
                    <div>
                      <Label className="text-xs text-muted-foreground">Service</Label>
                      <div className="font-semibold text-base mt-0.5">{selectedBooking.service}</div>
                      <div className="text-xs text-muted-foreground mt-1">{selectedBooking.duration} mins</div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Provider</Label>
                      <div className="font-semibold text-base mt-0.5">{selectedBooking.provider}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border bg-card/60">
                    <div>
                      <Label className="text-xs text-muted-foreground">Location</Label>
                      <div className="font-semibold text-sm mt-0.5 flex items-center gap-1.5">
                        <MapPin className="w-4 h-4 text-primary" /> {selectedBooking.location}
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Amount</Label>
                      <div className="font-semibold text-sm mt-0.5 text-emerald-600">{selectedBooking.price}</div>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="client" className="space-y-4 pt-1">
                  <div className="p-4 rounded-xl border bg-card/60 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-lg">
                        {selectedBooking.client[0]}
                      </div>
                      <div>
                        <div className="font-bold text-base">{selectedBooking.client}</div>
                        <div className="text-xs text-muted-foreground">ID #{selectedBooking.clientId}</div>
                      </div>
                    </div>
                    <Separator />
                    {selectedBooking.email && (
                      <div className="flex items-center gap-2 text-sm">
                        <Mail className="w-4 h-4 text-muted-foreground" />
                        <a href={`mailto:${selectedBooking.email}`} className="text-primary hover:underline">{selectedBooking.email}</a>
                      </div>
                    )}
                    {selectedBooking.phone && (
                      <div className="flex items-center gap-2 text-sm">
                        <Phone className="w-4 h-4 text-muted-foreground" />
                        <a href={`tel:${selectedBooking.phone}`} className="text-primary hover:underline">{selectedBooking.phone}</a>
                      </div>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="payment" className="space-y-4 pt-1">
                  <div className="p-4 rounded-xl border bg-card/60 space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-muted-foreground">Subtotal</span>
                      <span className="font-medium">{selectedBooking.price}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm font-bold pt-2 border-t">
                      <span>Total</span>
                      <span className="text-primary">{selectedBooking.price}</span>
                    </div>
                  </div>

                  <div>
                    <Label className="text-xs text-muted-foreground">Booking Notes</Label>
                    <p className="text-sm bg-muted/30 p-3 rounded-lg border mt-1 min-h-[60px]">
                      {selectedBooking.notes || "No notes provided."}
                    </p>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}

          <DialogFooter className="p-4 border-t bg-muted/20 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {selectedBooking && (
                <>
                  <Button variant="outline" size="sm" onClick={() => handleOpenEditBooking(selectedBooking)}>
                    <Edit2 className="w-3.5 h-3.5 mr-1.5" /> Edit
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => {
                    setViewDialogOpen(false);
                    handleOpenCreateBooking(undefined, String(selectedBooking.serviceId), String(selectedBooking.clientId));
                  }}>
                    <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Rebook
                  </Button>
                </>
              )}
            </div>

            <div className="flex items-center gap-2">
              {selectedBooking?.status !== 'completed' && (
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => handleUpdateBookingStatus(selectedBooking!, 'completed')}>
                  Complete
                </Button>
              )}
              {selectedBooking?.status !== 'cancelled' && (
                <Button variant="destructive" size="sm" onClick={() => handleUpdateBookingStatus(selectedBooking!, 'cancelled')}>
                  Cancel Booking
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Create Booking Modal ────────────────────────────────────── */}
      <Dialog open={createBookingOpen} onOpenChange={setCreateBookingOpen}>
        <DialogContent className="sm:max-w-[550px] p-0 overflow-hidden rounded-xl">
          <DialogHeader className="p-6 pb-3 border-b bg-card">
            <DialogTitle className="text-xl font-bold">Create New Booking</DialogTitle>
            <DialogDescription>Fill in the appointment details to create a real booking.</DialogDescription>
          </DialogHeader>

          <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
            {/* Client selection */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label htmlFor="create_client">Client *</Label>
                <Button variant="link" size="sm" className="h-auto p-0 text-xs text-primary" onClick={() => setAddClientOpen(true)}>
                  + Add New Client
                </Button>
              </div>
              <Select value={formClientId} onValueChange={setFormClientId}>
                <SelectTrigger id="create_client"><SelectValue placeholder="Select client" /></SelectTrigger>
                <SelectContent>
                  {clients.map(c => <SelectItem key={c.id} value={String(c.id)}>{c.name} ({c.email || 'No email'})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            {/* Service & Provider */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create_service">Service *</Label>
                <Select value={formServiceId} onValueChange={setFormServiceId}>
                  <SelectTrigger id="create_service"><SelectValue placeholder="Select service" /></SelectTrigger>
                  <SelectContent>
                    {services.map(s => <SelectItem key={s.id} value={String(s.id)}>{s.name} ({s.duration}m - ${s.price || 0})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create_provider">Provider *</Label>
                <Select value={formProviderId} onValueChange={setFormProviderId}>
                  <SelectTrigger id="create_provider"><SelectValue placeholder="Select provider" /></SelectTrigger>
                  <SelectContent>
                    {providers.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Location & Status */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create_location">Location</Label>
                <Select value={formLocationId} onValueChange={setFormLocationId}>
                  <SelectTrigger id="create_location"><SelectValue placeholder="Select location" /></SelectTrigger>
                  <SelectContent>
                    {locations.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create_status">Status</Label>
                <Select value={formStatus} onValueChange={setFormStatus}>
                  <SelectTrigger id="create_status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="confirmed">Confirmed</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Date and Time */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create_date">Date *</Label>
                <Input id="create_date" type="date" value={formDate} onChange={e => setFormDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create_time">Start Time *</Label>
                <Input id="create_time" type="time" value={formTime} onChange={e => setFormTime(e.target.value)} />
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="create_notes">Booking Notes</Label>
              <Textarea id="create_notes" placeholder="Optional notes for this appointment..." value={formNotes} onChange={e => setFormNotes(e.target.value)} rows={3} />
            </div>
          </div>

          <DialogFooter className="p-4 border-t bg-muted/20">
            <Button variant="outline" onClick={() => setCreateBookingOpen(false)}>Cancel</Button>
            <Button className="bg-primary text-primary-foreground font-semibold px-6" onClick={handleSaveBooking}>
              Save Booking
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Edit Booking Modal ────────────────────────────────────── */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[550px] p-0 overflow-hidden rounded-xl">
          <DialogHeader className="p-6 pb-3 border-b bg-card">
            <DialogTitle className="text-xl font-bold">Edit Booking #{selectedBooking?.id}</DialogTitle>
          </DialogHeader>

          <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Service *</Label>
                <Select value={formServiceId} onValueChange={setFormServiceId}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {services.map(s => <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Provider *</Label>
                <Select value={formProviderId} onValueChange={setFormProviderId}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {providers.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Date *</Label>
                <Input type="date" value={formDate} onChange={e => setFormDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Time *</Label>
                <Input type="time" value={formTime} onChange={e => setFormTime(e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={formStatus} onValueChange={setFormStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="confirmed">Confirmed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
                  <SelectItem value="noshow">No Show</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea value={formNotes} onChange={e => setFormNotes(e.target.value)} rows={3} />
            </div>
          </div>

          <DialogFooter className="p-4 border-t bg-muted/20">
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
            <Button className="bg-primary text-primary-foreground font-semibold px-6" onClick={handleUpdateBookingSubmit}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Add Client Dialog ────────────────────────────────────── */}
      <Dialog open={addClientOpen} onOpenChange={setAddClientOpen}>
        <DialogContent className="sm:max-w-[440px] rounded-xl">
          <DialogHeader>
            <DialogTitle>Add New Client</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="client_name">Full Name *</Label>
              <Input id="client_name" placeholder="John Doe" value={newClientName} onChange={e => setNewClientName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client_email">Email</Label>
              <Input id="client_email" type="email" placeholder="john@example.com" value={newClientEmail} onChange={e => setNewClientEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client_phone">Phone</Label>
              <Input id="client_phone" placeholder="(555) 000-0000" value={newClientPhone} onChange={e => setNewClientPhone(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddClientOpen(false)}>Cancel</Button>
            <Button className="bg-primary text-primary-foreground" onClick={handleSaveClient}>Save Client</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Create Note / Block Time Dialog ──────────────────────── */}
      <Dialog open={createNoteOpen} onOpenChange={setCreateNoteOpen}>
        <DialogContent className="sm:max-w-[480px] rounded-xl">
          <DialogHeader>
            <DialogTitle>Add Calendar Note / Block Time</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="note_date">Date *</Label>
              <Input id="note_date" type="date" value={noteDate} onChange={e => setNoteDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="note_provider">Provider</Label>
              <Select value={noteProviderId} onValueChange={setNoteProviderId}>
                <SelectTrigger id="note_provider"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Providers</SelectItem>
                  {providers.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="note_text">Note / Block Details *</Label>
              <Textarea id="note_text" placeholder="e.g. Clinic closed for staff holiday..." value={noteText} onChange={e => setNoteText(e.target.value)} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateNoteOpen(false)}>Cancel</Button>
            <Button className="bg-primary text-primary-foreground" onClick={handleSaveNote}>Save Note</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── All Notes Dialog ─────────────────────────────────────── */}
      <Dialog open={allNotesOpen} onOpenChange={setAllNotesOpen}>
        <DialogContent className="sm:max-w-[500px] rounded-xl">
          <DialogHeader>
            <DialogTitle>All Calendar Notes</DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-3 max-h-[60vh] overflow-y-auto">
            {notes.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">No calendar notes found.</p>
            ) : (
              notes.map((n: any) => (
                <div key={n.id} className="p-3 border rounded-xl bg-card space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-xs text-primary">{n.date}</span>
                    {n.provider_id && <Badge variant="outline" className="text-[10px]">Provider #{n.provider_id}</Badge>}
                  </div>
                  <p className="text-sm text-foreground">{n.note}</p>
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setAllNotesOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Filter Dialog ──────────────────────────────────────── */}
      <Dialog open={filterDialogOpen} onOpenChange={setFilterDialogOpen}>
        <DialogContent className="sm:max-w-[320px] rounded-xl">
          <DialogHeader>
            <DialogTitle>Filter Statuses</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-3">
            {Object.keys(STATUS_PILL).map(status => (
              <div key={status} className="flex items-center justify-between p-2 border rounded-lg">
                <span className="text-sm font-medium capitalize">{status}</span>
                {STATUS_ICON[status]}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button onClick={() => setFilterDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
