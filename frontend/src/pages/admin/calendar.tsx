import React, { useState } from "react";
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
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "../../components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Card, CardContent } from "../../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../../components/ui/select";
import { Separator } from "../../components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../../components/ui/dialog";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import { Checkbox } from "../../components/ui/checkbox";

const HOUR_HEIGHT = 64;

// ─── Mock Data ──────────────────────────────────────────────────────────
const today = new Date();
const y = today.getFullYear();
const m = today.getMonth();



const mockBookings = [
  { id: "B-1001", date: new Date(y, m, today.getDate(), 10, 0),     service: "Swedish Massage",   provider: "Sarah Jenkins", client: "Michael Chen",    email: "m.chen@example.com",    phone: "(555) 123-4567", duration: 60,  status: "confirmed",  price: "$120.00", location: "Main Clinic", notes: "Client requested deep pressure on lower back." },
  { id: "B-1002", date: new Date(y, m, today.getDate(), 11, 30),    service: "Deep Tissue",        provider: "David Ross",    client: "Emma Watson",     email: "emma.w@example.com",    phone: "(555) 987-6543", duration: 90,  status: "pending",    price: "$160.00", location: "City Branch", notes: "First time client." },
  { id: "B-1003", date: new Date(y, m, today.getDate(), 14, 0),     service: "Acupuncture",        provider: "Dr. Lin",       client: "James Smith",     email: "jsmith99@example.com",  phone: "(555) 456-7890", duration: 45,  status: "completed",  price: "$95.00",  location: "Online", notes: "" },
  { id: "B-1004", date: new Date(y, m, today.getDate() + 1, 9, 0),  service: "Sports Massage",     provider: "Sarah Jenkins", client: "Alex Johnson",    email: "alexj@example.com",     phone: "(555) 222-3333", duration: 60,  status: "cancelled",  price: "$130.00", location: "Main Clinic", notes: "Cancelled due to illness." },
  { id: "B-1005", date: new Date(y, m, today.getDate() + 1, 16, 30),service: "Swedish Massage",    provider: "David Ross",    client: "Olivia Brown",    email: "olivia.b@example.com",  phone: "(555) 444-5555", duration: 60,  status: "noshow",     price: "$120.00", location: "City Branch", notes: "Client did not call." },
  { id: "B-1006", date: new Date(y, m, today.getDate() + 3, 9, 0),  service: "Deep Tissue",        provider: "Dr. Lin",       client: "Sophie Williams", email: "sophie.w@example.com",  phone: "(555) 777-8888", duration: 60,  status: "confirmed",  price: "$140.00", location: "Main Clinic", notes: "" },
  { id: "B-1007", date: new Date(y, m, today.getDate() + 5, 11, 0), service: "Acupuncture",        provider: "Sarah Jenkins", client: "Tom Baker",       email: "tbaker@example.com",    phone: "(555) 333-4444", duration: 45,  status: "pending",    price: "$90.00",  location: "Main Clinic", notes: "" },
  { id: "B-1008", date: new Date(y, m, today.getDate() + 5, 14, 0), service: "Hot Stone Massage",  provider: "David Ross",    client: "Rachel Green",    email: "rgreen@example.com",    phone: "(555) 555-1234", duration: 75,  status: "confirmed",  price: "$175.00", location: "City Branch", notes: "" },
  { id: "B-1009", date: new Date(y, m, today.getDate() + 7, 10, 0), service: "Reflexology",        provider: "Dr. Lin",       client: "Monica Geller",   email: "mgeller@example.com",   phone: "(555) 888-9999", duration: 60,  status: "confirmed",  price: "$110.00", location: "Main Clinic", notes: "" },
];

const MOCK_SERVICES = ["Swedish Massage", "Deep Tissue", "Acupuncture", "Sports Massage", "Hot Stone Massage", "Reflexology"];
const MOCK_PROVIDERS = ["Sarah Jenkins", "David Ross", "Dr. Lin"];
const MOCK_LOCATIONS = ["Main Clinic", "City Branch", "Online"];

const STATUS_PILL: Record<string, string> = {
  confirmed:  "bg-teal-500 text-white",
  pending:    "bg-amber-400 text-white",
  completed:  "bg-emerald-600 text-white",
  cancelled:  "bg-red-400 text-white",
  noshow:     "bg-zinc-400 text-white",
};
const STATUS_ICON: Record<string, React.ReactNode> = {
  confirmed:  <CheckCircle2 className="w-3 h-3" />,
  pending:    <Clock className="w-3 h-3" />,
  completed:  <CheckCircle2 className="w-3 h-3" />,
  cancelled:  <XCircle className="w-3 h-3" />,
  noshow:     <Ban className="w-3 h-3" />,
};

const DAYS_FULL   = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function fmt12(date: Date) {
  const h = date.getHours() % 12 || 12;
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${min} ${date.getHours() < 12 ? "AM" : "PM"}`;
}

const HOURS = Array.from({ length: 14 }, (_, i) => i + 7); // 7am to 8pm

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
  currentDate, bookings, filterProvider, filterLocation, onSelectBooking, onNewBooking
}: {
  currentDate: Date;
  bookings: typeof mockBookings;
  filterProvider: string;
  filterLocation: string;
  onSelectBooking: (b: any) => void;
  onNewBooking: (d: Date) => void;
}) {
  const yr = currentDate.getFullYear();
  const mo = currentDate.getMonth();
  const firstDay  = new Date(yr, mo, 1).getDay();
  const totalDays = new Date(yr, mo + 1, 0).getDate();

  const prevMonthDays = new Date(yr, mo, 0).getDate();
  type Cell = { day: number; thisMonth: boolean; date: Date };
  const cells: Cell[] = [];
  for (let i = firstDay - 1; i >= 0; i--) cells.push({ day: prevMonthDays - i, thisMonth: false, date: new Date(yr, mo - 1, prevMonthDays - i) });
  for (let d = 1; d <= totalDays; d++) cells.push({ day: d, thisMonth: true, date: new Date(yr, mo, d) });
  let nextDay = 1;
  while (cells.length % 7 !== 0) { cells.push({ day: nextDay, thisMonth: false, date: new Date(yr, mo + 1, nextDay) }); nextDay++; }

  const filtered = bookings.filter(b => {
    if (filterProvider !== "all" && b.provider !== filterProvider) return false;
    if (filterLocation !== "all" && b.location !== filterLocation) return false;
    return true;
  });

  const getDayBkgs = (cell: Cell) => filtered.filter(b => isSameDay(b.date, cell.date)).sort((a, b) => a.date.getTime() - b.date.getTime());

  const isToday = (cell: Cell) => isSameDay(new Date(), cell.date);
  const isWeekend = (cell: Cell) => cell.date.getDay() === 0 || cell.date.getDay() === 6;

  const weeks: Cell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="grid grid-cols-7 border-b border-border flex-shrink-0 sticky top-0 bg-background z-10">
        {DAYS_FULL.map(d => (
          <div key={d} className="py-2 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wide border-r border-border last:border-r-0">
            {d}
          </div>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col min-h-full">
          {weeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 flex-1 min-h-[120px]">
              {week.map((cell, di) => {
                const dayBkgs = getDayBkgs(cell);
                const closed = isWeekend(cell) && cell.thisMonth;
                return (
                  <div
                    key={di}
                    onClick={() => onNewBooking(cell.date)}
                    className={`border-r border-b border-border last:border-r-0 flex flex-col p-1 cursor-pointer transition-colors hover:bg-muted/10
                      ${!cell.thisMonth ? "bg-muted/30" : ""}
                      ${isToday(cell) ? "bg-primary/5" : ""}
                    `}
                    style={closed ? { backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(234,179,8,0.10) 6px, rgba(234,179,8,0.10) 12px)" } : {}}
                  >
                    <div className="flex items-center justify-between px-1 mb-1">
                      <span className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full
                        ${isToday(cell) ? "ring-2 ring-primary/40 ring-inset bg-primary text-primary-foreground font-bold" : ""}
                        ${!cell.thisMonth ? "text-muted-foreground/50" : "text-muted-foreground"}
                      `}>
                        {cell.day}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 overflow-hidden">
                      {dayBkgs.slice(0, 4).map(b => (
                        <div
                          key={b.id}
                          onClick={(e) => { e.stopPropagation(); onSelectBooking(b); }}
                          className={`w-full text-left rounded px-1.5 py-0.5 text-[10px] font-medium truncate leading-tight transition-opacity hover:opacity-80 flex items-center gap-1
                            ${STATUS_PILL[b.status]}`}
                        >
                          <span className="flex-shrink-0">{fmt12(b.date)}</span>
                          <span className="truncate">{b.client}</span>
                          <span className="ml-auto flex-shrink-0">{STATUS_ICON[b.status]}</span>
                        </div>
                      ))}
                      {dayBkgs.length > 4 && (
                        <span className="text-[10px] text-muted-foreground pl-1 leading-tight">+{dayBkgs.length - 4} more</span>
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
  days, bookings, onSelectBooking, filterProvider, filterLocation, onUpdateBooking, onNewBooking, onUpdateDuration
}: {
  days: Date[];
  bookings: typeof mockBookings;
  onSelectBooking: (b: any) => void;
  filterProvider: string;
  filterLocation: string;
  onUpdateBooking: (id: string, newDate: Date) => void;
  onNewBooking: (date: Date) => void;
  onUpdateDuration?: (id: string, newDuration: number) => void;
}) {
  const filtered = bookings.filter(b => {
    if (filterProvider !== "all" && b.provider !== filterProvider) return false;
    if (filterLocation !== "all" && b.location !== filterLocation) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      <div className="flex border-b border-border flex-shrink-0 sticky top-0 bg-background z-10">
        <div className="w-16 flex-shrink-0 border-r border-border"></div>
        {days.map((d, i) => (
          <div key={i} className="flex-1 py-2 text-center border-r border-border last:border-r-0">
            <div className="text-xs font-semibold text-muted-foreground uppercase">{DAYS_FULL[d.getDay()]}</div>
            <div className={`text-lg mt-0.5 ${isSameDay(d, new Date()) ? "text-primary font-bold" : ""}`}>{d.getDate()}</div>
          </div>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="flex relative" style={{ height: `${HOURS.length * HOUR_HEIGHT}px` }}>
          {/* Time labels axis */}
          <div className="w-16 flex-shrink-0 border-r border-border relative bg-background z-10">
            {HOURS.map((h, i) => (
              <div key={i} className="absolute w-full text-right pr-2 text-xs text-muted-foreground transform -translate-y-1/2" style={{ top: `${i * HOUR_HEIGHT}px` }}>
                {h > 12 ? h - 12 : h}{h >= 12 ? ' PM' : ' AM'}
              </div>
            ))}
          </div>
          
          {/* Grid lines and columns */}
          <div className="flex-1 flex relative">
            {/* Horizontal lines (15-min intervals) */}
            <div className="absolute inset-0 pointer-events-none">
              {Array.from({ length: HOURS.length * 4 }).map((_, i) => {
                const isHour = i % 4 === 0;
                return (
                  <div 
                    key={i} 
                    className={`border-t absolute w-full ${isHour ? 'border-border' : 'border-border/20'}`} 
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
                  className="flex-1 border-r border-border last:border-r-0 relative cursor-text"
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
                        className={`absolute left-1 right-1 rounded p-1.5 text-xs overflow-hidden cursor-grab active:cursor-grabbing transition-opacity hover:opacity-90 shadow-sm group/block
                          ${STATUS_PILL[b.status]}`}
                        style={{ top: `${topPx}px`, height: `${heightPx - 2}px` }}
                      >
                        <div className="font-semibold pointer-events-none">{fmt12(b.date)} - {b.client}</div>
                        <div className="text-[10px] opacity-90 truncate pointer-events-none">{b.service} ({b.duration}m)</div>
                        
                        {/* Bottom edge grab handle for duration resizing */}
                        <div
                          className="absolute bottom-0 left-0 right-0 h-3 cursor-ns-resize hover:bg-black/20 dark:hover:bg-white/20 flex items-center justify-center transition-colors group/resize z-20"
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            const startY = e.clientY;
                            const startDuration = b.duration;
                            
                            const onMouseMove = (moveEvent: MouseEvent) => {
                              const deltaY = moveEvent.clientY - startY;
                              const deltaMinutes = Math.round((deltaY / HOUR_HEIGHT) * 4) * 15;
                              const newDuration = Math.max(15, startDuration + deltaMinutes);
                              if (onUpdateDuration) {
                                onUpdateDuration(b.id, newDuration);
                              }
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
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────
export default function CalendarPage() {
  const [localBookings, setLocalBookings] = useState(mockBookings);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewType, setViewType] = useState<"month" | "week" | "day">("month");
  const [filterProvider, setFilterProvider] = useState("all");
  const [filterLocation, setFilterLocation] = useState("all");
  const [selectedBooking, setSelectedBooking] = useState<any | null>(null);
  
  // Dialogs
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [bookingDialogOpen, setBookingDialogOpen] = useState(false);
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [allNotesDialogOpen, setAllNotesDialogOpen] = useState(false);
  
  // New Booking State
  const [dialogMode, setDialogMode] = useState<"booking"|"note">("booking");
  const [newBookingTab, setNewBookingTab] = useState("details");
  const [addClientDialogOpen, setAddClientDialogOpen] = useState(false);
  const [addClientTab, setAddClientTab] = useState("details");
  const [newBookingDate, setNewBookingDate] = useState(new Date());
  const [clientSearch, setClientSearch] = useState("");
  const [selectedClient] = useState<any | null>(null);
  const [selectedService, setSelectedService] = useState("");

  const openBooking = (b: any) => { setSelectedBooking(b); setIsSheetOpen(true); };
  
  const handleNewBooking = (d?: Date, tab: string = "booking") => {
    setNewBookingDate(d || new Date());
    setNewBookingTab(tab);
    setBookingDialogOpen(true);
  };

  const handleUpdateBooking = (id: string, newDate: Date) => {
    setLocalBookings(prev => prev.map(b => b.id === id ? { ...b, date: newDate } : b));
  };

  const handleUpdateDuration = (id: string, newDuration: number) => {
    setLocalBookings(prev => prev.map(b => b.id === id ? { ...b, duration: newDuration } : b));
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
    if (start.getMonth() === end.getMonth()) {
      headingLabel = `${MONTH_NAMES[start.getMonth()]} ${start.getDate()} - ${end.getDate()}, ${start.getFullYear()}`;
    } else {
      headingLabel = `${MONTH_NAMES[start.getMonth()]} ${start.getDate()} - ${MONTH_NAMES[end.getMonth()]} ${end.getDate()}, ${start.getFullYear()}`;
    }
  } else {
    headingLabel = `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getDate()}, ${currentDate.getFullYear()}`;
  }

  const getStatusBadge = (status: string) => (
    <Badge className={`${STATUS_PILL[status]} border-0 gap-1`}>
      {STATUS_ICON[status]}{status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">

      {/* ── Page Header ─────────────────────────────────────── */}
      <div className="px-6 py-4 flex items-center justify-between border-b flex-shrink-0">
        <h1 className="text-2xl font-bold tracking-tight">Calendar</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2 h-8" onClick={() => window.location.href = '/admin/finance/payments'}>
            <FileText className="w-3.5 h-3.5" /> Transactions
          </Button>
          <Button variant="outline" size="sm" className="gap-2 h-8" onClick={() => setAllNotesDialogOpen(true)}>
            <FileText className="w-3.5 h-3.5" /> All notes
          </Button>
        </div>
      </div>

      {/* ── Action Bar ──────────────────────────────────────── */}
      <div className="px-6 py-2.5 flex items-center gap-2 border-b flex-shrink-0 flex-wrap">
        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => window.location.href = '/admin/schedule/workdays'}>
          Edit schedules <ChevronRight className="w-3 h-3" />
        </Button>
        <Button size="sm" className="h-8 gap-1.5 bg-teal-600 hover:bg-teal-700 text-white border-0" onClick={() => window.location.href = '/admin/bookings'}>
          <CalendarCheck className="w-3.5 h-3.5" /> Manage bookings
        </Button>
        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => handleNewBooking(new Date(), "notes")}>
          <Plus className="w-3.5 h-3.5" /> Add note / Block time
        </Button>

        <div className="flex-1" />

        {/* Provider filter */}
        <Select value={filterProvider} onValueChange={setFilterProvider}>
          <SelectTrigger className="h-8 w-[160px] text-xs">
            <SelectValue placeholder="All Providers" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Providers</SelectItem>
            {MOCK_PROVIDERS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
          </SelectContent>
        </Select>

        {/* Location filter */}
        <Select value={filterLocation} onValueChange={setFilterLocation}>
          <SelectTrigger className="h-8 w-[150px] text-xs">
            <SelectValue placeholder="All Locations" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Locations</SelectItem>
            {MOCK_LOCATIONS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
          </SelectContent>
        </Select>

        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => setFilterDialogOpen(true)}>
          <SlidersHorizontal className="w-3.5 h-3.5" /> Show filter
        </Button>
        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => toast.success('Exporting bookings...')}>
          <Download className="w-3.5 h-3.5" /> Export
        </Button>
        <Button size="sm" className="h-8 gap-1.5" onClick={() => handleNewBooking()}>
          <Plus className="w-3.5 h-3.5" /> New Booking
        </Button>
      </div>

      {/* ── Navigation Bar ──────────────────────────────────── */}
      <div className="px-6 py-2 flex items-center gap-3 border-b flex-shrink-0">
        <div className="flex items-center p-1 bg-muted rounded-md">
          <Button 
            variant={viewType === "month" ? "default" : "ghost"} 
            size="sm" 
            className={`h-7 px-3 text-xs ${viewType !== "month" && "text-muted-foreground"}`}
            onClick={() => setViewType("month")}
          >
            Month
          </Button>
          <Button 
            variant={viewType === "week" ? "default" : "ghost"} 
            size="sm" 
            className={`h-7 px-3 text-xs ${viewType !== "week" && "text-muted-foreground"}`}
            onClick={() => setViewType("week")}
          >
            Week
          </Button>
          <Button 
            variant={viewType === "day" ? "default" : "ghost"} 
            size="sm" 
            className={`h-7 px-3 text-xs ${viewType !== "day" && "text-muted-foreground"}`}
            onClick={() => setViewType("day")}
          >
            Day
          </Button>
        </div>
        
        <Button variant="outline" size="sm" className="h-8 px-3 ml-2" onClick={() => setCurrentDate(new Date())}>
          Today
        </Button>

        <div className="flex-1" />

        {/* Date navigation */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(-1)}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="font-semibold text-sm w-48 text-center">{headingLabel}</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(1)}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1" />
      </div>

      {/* ── Calendar Grid ────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden flex flex-col relative bg-muted/10">
        {viewType === "month" && (
          <MonthGrid
            currentDate={currentDate}
            bookings={localBookings}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onSelectBooking={openBooking}
            onNewBooking={handleNewBooking}
          />
        )}
        {viewType === "week" && (
          <TimeGrid
            days={Array.from({length: 7}, (_, i) => {
              const d = getStartOfWeek(currentDate);
              d.setDate(d.getDate() + i);
              return d;
            })}
            bookings={localBookings}
            onSelectBooking={openBooking}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onUpdateBooking={handleUpdateBooking}
            onNewBooking={handleNewBooking}
            onUpdateDuration={handleUpdateDuration}
          />
        )}
        {viewType === "day" && (
          <TimeGrid
            days={[currentDate]}
            bookings={localBookings}
            onSelectBooking={openBooking}
            filterProvider={filterProvider}
            filterLocation={filterLocation}
            onUpdateBooking={handleUpdateBooking}
            onNewBooking={handleNewBooking}
            onUpdateDuration={handleUpdateDuration}
          />
        )}
      </div>

      {/* ── Booking Detail Sheet ──────────────────────────────── */}
      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent side="right" className="max-w-[440px] w-[440px] overflow-y-auto sm:max-w-[440px]">
          <SheetHeader className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <SheetTitle className="text-xl flex items-center gap-3">
                  Booking {selectedBooking?.id}
                  {selectedBooking && getStatusBadge(selectedBooking.status)}
                </SheetTitle>
                <SheetDescription>
                  {selectedBooking?.date.toLocaleString("en-US", { dateStyle: "long", timeStyle: "short" })}
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          {selectedBooking && (
            <Tabs defaultValue="booking" className="w-full">
              <TabsList className="grid w-full grid-cols-3 mb-6">
                <TabsTrigger value="booking">Booking</TabsTrigger>
                <TabsTrigger value="client">Client</TabsTrigger>
                <TabsTrigger value="finance">Finance</TabsTrigger>
              </TabsList>

              <TabsContent value="booking" className="space-y-4">
                <Card><CardContent className="p-4 space-y-3">
                  <div className="flex justify-between items-center">
                    <h4 className="font-semibold flex items-center text-muted-foreground text-sm"><Clock className="w-4 h-4 mr-2" /> Date & Time</h4>
                  </div>
                  <div>
                    <div className="font-medium text-sm">{selectedBooking.date.toLocaleDateString("en-US", { dateStyle: "full" })}</div>
                    <div className="text-sm text-muted-foreground">{fmt12(selectedBooking.date)} · {selectedBooking.duration} min</div>
                  </div>
                </CardContent></Card>
                <Card><CardContent className="p-4 space-y-3">
                  <div className="flex justify-between items-center">
                    <h4 className="font-semibold flex items-center text-muted-foreground text-sm"><MapPin className="w-4 h-4 mr-2" /> Location</h4>
                  </div>
                  <div>
                    <div className="font-medium text-sm">{selectedBooking.location}</div>
                  </div>
                </CardContent></Card>
                <Card><CardContent className="p-4 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-semibold text-muted-foreground mb-1">Service</h4>
                      <div className="text-sm font-medium">{selectedBooking.service}</div>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-muted-foreground mb-1">Provider</h4>
                      <div className="text-sm font-medium">{selectedBooking.provider}</div>
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <h4 className="text-sm font-semibold text-muted-foreground mb-2">Booking Notes</h4>
                    <p className="text-sm bg-muted/50 p-2 rounded min-h-[60px]">{selectedBooking.notes || "No notes provided."}</p>
                  </div>
                </CardContent></Card>
                <div className="flex flex-col gap-2 pt-2">
                  <Button variant="outline" className="text-emerald-600 border-emerald-200">Complete Session</Button>
                  <Button variant="outline">Mark No-show</Button>
                  <Button variant="destructive">Cancel Booking</Button>
                </div>
              </TabsContent>

              <TabsContent value="client" className="space-y-4">
                <Card><CardContent className="p-4">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="h-12 w-12 bg-primary/10 text-primary rounded-full flex items-center justify-center text-lg font-bold">
                      {selectedBooking.client.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold leading-none">{selectedBooking.client}</h3>
                      <Badge variant="outline" className="mt-1">New Client</Badge>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-2 bg-muted/30 rounded">
                      <Mail className="w-4 h-4 text-muted-foreground" />
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-muted-foreground">Email</div>
                        <a href={`mailto:${selectedBooking.email}`} className="text-sm text-primary hover:underline truncate block">{selectedBooking.email}</a>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-2 bg-muted/30 rounded">
                      <Phone className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <div className="text-xs font-medium text-muted-foreground">Phone</div>
                        <a href={`tel:${selectedBooking.phone}`} className="text-sm text-primary hover:underline">{selectedBooking.phone}</a>
                      </div>
                    </div>
                  </div>
                </CardContent></Card>
              </TabsContent>

              <TabsContent value="finance" className="space-y-4">
                <Card><CardContent className="p-4 space-y-4">
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="font-semibold">Payment</h3>
                    <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">Unpaid</Badge>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-muted-foreground">{selectedBooking.service}</span><span>{selectedBooking.price}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Tax</span><span>$0.00</span></div>
                    <Separator />
                    <div className="flex justify-between font-bold"><span>Total</span><span>{selectedBooking.price}</span></div>
                  </div>
                  <Button className="w-full mt-2">Process Payment</Button>
                </CardContent></Card>
              </TabsContent>
            </Tabs>
          )}
        </SheetContent>
      </Sheet>

      {/* ── New Booking / Note Dialog ──────────────────────────────── */}
      <Dialog open={bookingDialogOpen} onOpenChange={setBookingDialogOpen}>
        <DialogContent className="sm:max-w-[550px] p-0 gap-0">
          <div className="flex bg-muted/30 border-b">
            <button 
              className={`flex-1 py-3 text-sm font-medium transition-colors ${dialogMode === 'booking' ? 'bg-background border-b-2 border-primary text-primary' : 'text-muted-foreground hover:bg-muted/50'}`}
              onClick={() => setDialogMode('booking')}
            >
              Create booking
            </button>
            <button 
              className={`flex-1 py-3 text-sm font-medium transition-colors ${dialogMode === 'note' ? 'bg-background border-b-2 border-primary text-primary' : 'text-muted-foreground hover:bg-muted/50'}`}
              onClick={() => setDialogMode('note')}
            >
              Create note
            </button>
          </div>

          <div className="p-6">
            {dialogMode === 'booking' ? (
              <Tabs value={newBookingTab} onValueChange={setNewBookingTab} className="w-full">
                <TabsList className="w-full justify-start border-b rounded-none h-auto p-0 bg-transparent mb-4 space-x-6">
                  <TabsTrigger value="details" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Details</TabsTrigger>
                  <TabsTrigger value="client" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Client</TabsTrigger>
                  <TabsTrigger value="products" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Products for sale</TabsTrigger>
                  <TabsTrigger value="addons" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Add-ons</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="space-y-4">
                  <div className="grid gap-2 relative">
                    <Label>Client</Label>
                    <div className="relative flex items-center gap-2">
                      <div className="relative flex-1">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input 
                          placeholder="Search or select client" 
                          className="pl-9"
                          value={clientSearch}
                          onChange={(e) => setClientSearch(e.target.value)}
                        />
                      </div>
                      <Button variant="outline" onClick={() => setAddClientDialogOpen(true)}>
                        <Plus className="h-4 w-4 mr-2" /> Add
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label>Location</Label>
                      <Select>
                        <SelectTrigger><SelectValue placeholder="Select location" /></SelectTrigger>
                        <SelectContent>
                          {MOCK_LOCATIONS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>Service category</Label>
                      <Select>
                        <SelectTrigger><SelectValue placeholder="Select category" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="massage">Massage</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label>Service provider *</Label>
                      <Select>
                        <SelectTrigger><SelectValue placeholder="Select provider" /></SelectTrigger>
                        <SelectContent>
                          {MOCK_PROVIDERS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>Service *</Label>
                      <Select value={selectedService} onValueChange={setSelectedService}>
                        <SelectTrigger><SelectValue placeholder="Select service" /></SelectTrigger>
                        <SelectContent>
                          {MOCK_SERVICES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid gap-2">
                    <Label>Number of participants *</Label>
                    <Select defaultValue="1">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1</SelectItem>
                        <SelectItem value="2">2</SelectItem>
                        <SelectItem value="3">3</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label>Start time *</Label>
                    <div className="text-sm font-medium text-primary hover:underline cursor-pointer">
                      {newBookingDate.toLocaleDateString('en-US', {month:'2-digit', day:'2-digit', year:'numeric'}).replace(/\//g, '.')} {fmt12(newBookingDate)}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 pt-2">
                    <Checkbox id="recurring" />
                    <Label htmlFor="recurring" className="font-normal">Make recurring booking</Label>
                  </div>

                  <div className="flex items-center space-x-2 pt-1">
                    <Checkbox id="custom_q" />
                    <Label htmlFor="custom_q" className="font-normal">Like to massage outside, weather permitting? *</Label>
                  </div>

                  <div className="grid gap-2 pt-2">
                    <Label>Status</Label>
                    <Select defaultValue="confirmed">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="confirmed">Confirmed</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </TabsContent>

                <TabsContent value="client" className="space-y-4">
                  {selectedClient ? (
                    <div className="space-y-4">
                      <div><Label className="text-muted-foreground text-xs">Name</Label><div className="font-medium">{selectedClient.name}</div></div>
                      <div><Label className="text-muted-foreground text-xs">Email</Label><div className="font-medium">{selectedClient.email}</div></div>
                      <div><Label className="text-muted-foreground text-xs">Phone</Label><div className="font-medium">{selectedClient.phone}</div></div>
                    </div>
                  ) : <div className="text-sm text-muted-foreground">No client selected.</div>}
                </TabsContent>

                <TabsContent value="products" className="space-y-4">
                  <div className="text-sm text-muted-foreground">Select products to add to this booking.</div>
                </TabsContent>
                <TabsContent value="addons" className="space-y-4">
                  <div className="text-sm text-muted-foreground">Select optional add-ons.</div>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-2">
                  <Label>Start/end date time *</Label>
                  <div className="flex items-center gap-4 text-sm font-medium text-primary">
                    <span className="hover:underline cursor-pointer">
                      {newBookingDate.toLocaleDateString('en-US', {month:'2-digit', day:'2-digit', year:'numeric'}).replace(/\//g, '.')} {fmt12(newBookingDate)}
                    </span>
                    <span className="text-muted-foreground no-underline">-</span>
                    <span className="hover:underline cursor-pointer">
                      {newBookingDate.toLocaleDateString('en-US', {month:'2-digit', day:'2-digit', year:'numeric'}).replace(/\//g, '.')} {
                        fmt12(new Date(newBookingDate.getTime() + 15 * 60000))
                      }
                    </span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 pt-2">
                  <Checkbox id="block_time" defaultChecked />
                  <Label htmlFor="block_time" className="font-normal">Time is blocked</Label>
                </div>

                <div className="grid gap-2 pt-2">
                  <Label>Note</Label>
                  <Textarea placeholder="Type note here..." rows={4} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>This note is for *</Label>
                    <Select defaultValue="everyone">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="everyone">Everyone</SelectItem>
                        {MOCK_PROVIDERS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>Note type *</Label>
                    <div className="flex items-center gap-2">
                      <Select defaultValue="note">
                        <SelectTrigger className="flex-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="note">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full bg-orange-500"></div> Note
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <Button variant="outline" size="icon"><FileText className="w-4 h-4" /></Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 p-4 border-t bg-muted/10">
            <Button variant="outline" onClick={() => setBookingDialogOpen(false)}>Cancel</Button>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white rounded-full px-6" onClick={() => {
              toast.success(dialogMode === 'note' ? "Note saved" : "Booking saved");
              setBookingDialogOpen(false);
            }}>
              {dialogMode === 'note' ? "Save and close" : "Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Add Client Dialog ────────────────────────────────────── */}
      <Dialog open={addClientDialogOpen} onOpenChange={setAddClientDialogOpen}>
        <DialogContent className="sm:max-w-[450px] p-0 overflow-hidden">
          <DialogHeader className="p-6 pb-2 border-b">
            <DialogTitle>Add client</DialogTitle>
          </DialogHeader>
          <div className="p-6 pt-2">
            <Tabs value={addClientTab} onValueChange={setAddClientTab} className="w-full">
              <TabsList className="w-full justify-start border-b rounded-none h-auto p-0 bg-transparent mb-4 space-x-6">
                <TabsTrigger value="details" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Details</TabsTrigger>
                <TabsTrigger value="address" className="data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-0 py-2">Address</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="space-y-4">
                <div className="grid gap-2">
                  <Label>Name *</Label>
                  <Input placeholder="Enter name" />
                </div>
                <div className="grid gap-2">
                  <Label>Email *</Label>
                  <Input type="email" placeholder="Enter email" />
                </div>
                <div className="grid gap-2">
                  <Label>Phone *</Label>
                  <div className="flex">
                    <Select defaultValue="au">
                      <SelectTrigger className="w-[100px] rounded-r-none border-r-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="au">🇦🇺 +61</SelectItem>
                        <SelectItem value="us">🇺🇸 +1</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input className="rounded-l-none" placeholder="0000 000 000" />
                  </div>
                </div>
                <div className="flex items-center space-x-2 pt-2">
                  <Checkbox id="block_login" />
                  <Label htmlFor="block_login" className="font-normal">Client is blocked from login</Label>
                </div>
              </TabsContent>

              <TabsContent value="address" className="space-y-4">
                <div className="grid gap-2">
                  <Label>Country</Label>
                  <Select defaultValue="au">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="au">Australia</SelectItem>
                      <SelectItem value="us">United States</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Address 1</Label>
                  <Input />
                </div>
                <div className="grid gap-2">
                  <Label>Address 2</Label>
                  <Input />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>Zip</Label>
                    <Input />
                  </div>
                  <div className="grid gap-2">
                    <Label>City</Label>
                    <Input />
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
          <div className="flex justify-end gap-2 p-4 border-t bg-muted/10">
            <Button variant="outline" onClick={() => setAddClientDialogOpen(false)}>Cancel</Button>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white rounded-full px-6" onClick={() => {
              toast.success("Client added");
              setAddClientDialogOpen(false);
            }}>
              Save
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Filter Dialog ─────────────────────────────────────── */}
      <Dialog open={filterDialogOpen} onOpenChange={setFilterDialogOpen}>
        <DialogContent className="sm:max-w-[300px]">
          <DialogHeader>
            <DialogTitle>Filter Status</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-4">
            {Object.keys(STATUS_PILL).map(status => (
              <div key={status} className="flex items-center space-x-2">
                <Checkbox id={`filter-${status}`} defaultChecked />
                <label htmlFor={`filter-${status}`} className="text-sm font-medium leading-none capitalize">
                  {status}
                </label>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFilterDialogOpen(false)}>Reset</Button>
            <Button onClick={() => setFilterDialogOpen(false)}>Apply</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── All Notes Dialog ──────────────────────────────────── */}
      <Dialog open={allNotesDialogOpen} onOpenChange={setAllNotesDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>All Blocked Time & Notes</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div className="p-3 border rounded text-sm bg-muted/30">
              <div className="font-semibold text-primary mb-1">{today.toLocaleDateString()}</div>
              <div>Team training session block 2pm-4pm</div>
            </div>
            <div className="p-3 border rounded text-sm bg-muted/30">
              <div className="font-semibold text-primary mb-1">Tomorrow</div>
              <div>Clinic closes early at 4pm for maintenance.</div>
            </div>
            <div className="text-sm text-muted-foreground text-center pt-4">
              No other notes found for this month.
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setAllNotesDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
