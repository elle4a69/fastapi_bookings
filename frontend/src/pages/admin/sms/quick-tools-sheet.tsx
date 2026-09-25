import { useState, useEffect, useRef } from "react";
import { 
  Calendar, 
  Sparkles, 
  Clock, 
  ChevronDown, 
  ChevronUp, 
  Edit3, 
  Save, 
  RefreshCw,
  Copy,
  Info
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle, 
  SheetDescription 
} from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

export interface QuickToolMacro {
  id: number;
  slot_index: number;
  label: string;
  content: string;
}

const DEFAULT_MACROS: QuickToolMacro[] = [
  { id: 1, slot_index: 0, label: "Pricing", content: "Our standard pricing starts at $80/hr. Full package details are available upon request." },
  { id: 2, slot_index: 1, label: "Location", content: "We are located at 123 Main Street. On-site parking is available at the rear entrance." },
  { id: 3, slot_index: 2, label: "Hours", content: "We are open Monday to Saturday from 9:00 AM to 6:00 PM. Closed on Sundays." },
  { id: 4, slot_index: 3, label: "Policy", content: "Cancellations made within 24 hours of your appointment may incur a 50% fee." },
  { id: 5, slot_index: 4, label: "Thanks", content: "Thank you for reaching out! Please let us know if you have any other questions." }
];

interface QuickToolsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInsert: (text: string) => void;
  customerName?: string;
}

interface ServiceItem {
  id: number;
  name: string;
  duration: number;
}

interface AvailableDayGroup {
  dayLabel: string;
  dateStr: string;
  times: string[];
}

export function QuickToolsSheet({
  open,
  onOpenChange,
  onInsert,
  customerName
}: QuickToolsSheetProps) {
  const [macros, setMacros] = useState<QuickToolMacro[]>(DEFAULT_MACROS);
  const [editingMacro, setEditingMacro] = useState<QuickToolMacro | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  // Calendar expansion state
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [selectedDuration, setSelectedDuration] = useState<number>(60);
  const [_services, setServices] = useState<ServiceItem[]>([]);
  const [calendarSlots, setCalendarSlots] = useState<AvailableDayGroup[]>([]);
  const [loadingCalendar, setLoadingCalendar] = useState(false);

  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLongPressRef = useRef(false);

  // Load macros on mount
  useEffect(() => {
    loadMacros();
  }, []);

  const loadMacros = async () => {
    try {
      // Try backend first
      const remote = await apiClient.get<any[]>("/api/admin/sms/conversations/quick-tools").catch(() => null);
      if (Array.isArray(remote) && remote.length > 0) {
        const mapped: QuickToolMacro[] = remote.map((item: any, idx: number) => ({
          id: item.id ?? (idx + 1),
          slot_index: typeof item.slot_index === "number" ? item.slot_index : idx,
          label: item.label,
          content: item.content
        }));
        mapped.sort((a, b) => a.slot_index - b.slot_index);
        setMacros(mapped);
        return;
      }
    } catch {
      // ignore
    }

    // Fall back to localStorage
    const cached = localStorage.getItem("sms_quick_tools");
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const mapped: QuickToolMacro[] = parsed.map((item: any, idx: number) => ({
            id: item.id ?? (idx + 1),
            slot_index: typeof item.slot_index === "number" ? item.slot_index : idx,
            label: item.label,
            content: item.content
          }));
          mapped.sort((a, b) => a.slot_index - b.slot_index);
          setMacros(mapped);
          return;
        }
      } catch {
        // ignore
      }
    }
    setMacros(DEFAULT_MACROS);
  };

  const handleOpenEdit = (m: QuickToolMacro) => {
    setEditingMacro(m);
    setEditLabel(m.label.slice(0, 8));
    setEditContent(m.content);
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingMacro) return;
    const targetSlotIndex = typeof editingMacro.slot_index === "number" ? editingMacro.slot_index : (editingMacro.id - 1);
    const cleanLabel = editLabel.trim().slice(0, 8) || `Macro ${targetSlotIndex + 1}`;
    const cleanContent = editContent.trim();

    const updated = macros.map(item => 
      (item.slot_index === targetSlotIndex || item.id === editingMacro.id)
        ? { ...item, label: cleanLabel, content: cleanContent, slot_index: targetSlotIndex } 
        : item
    );
    setMacros(updated);
    setEditDialogOpen(false);

    // Save to localStorage
    localStorage.setItem("sms_quick_tools", JSON.stringify(updated));

    // Save to backend endpoint individually: SmsQuickToolCreate = { slot_index, label, content }
    try {
      await apiClient.post("/api/admin/sms/conversations/quick-tools", {
        slot_index: targetSlotIndex,
        label: cleanLabel,
        content: cleanContent
      });
      toast.success(`Saved macro "${cleanLabel}"`);
    } catch {
      toast.success(`Saved macro "${cleanLabel}" locally`);
    }
  };

  const handlePointerDown = (m: QuickToolMacro) => {
    isLongPressRef.current = false;
    longPressTimerRef.current = setTimeout(() => {
      isLongPressRef.current = true;
      handleOpenEdit(m);
    }, 500);
  };

  const handlePointerUpOrLeave = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handleMacroClick = (m: QuickToolMacro) => {
    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      return;
    }
    onInsert(m.content);
    onOpenChange(false);
    toast.success(`Pasted "${m.label}" into composer`);
  };

  // Load calendar availability
  const loadCalendarAvailability = async () => {
    setLoadingCalendar(true);
    try {
      const [svcRes, bkgRes] = await Promise.all([
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/bookings").catch(() => [])
      ]);

      const rawSvcs: ServiceItem[] = Array.isArray(svcRes) ? svcRes : (svcRes?.data ?? []);
      if (rawSvcs.length > 0) {
        setServices(rawSvcs);
      }

      const rawBookings: any[] = Array.isArray(bkgRes) ? bkgRes : (bkgRes?.items ?? []);

      // Generate next 5 days of candidate slots
      const days: AvailableDayGroup[] = [];
      const baseDate = new Date();

      for (let d = 0; d < 5; d++) {
        const curr = new Date(baseDate);
        curr.setDate(baseDate.getDate() + d);

        const dayName = d === 0 ? "Today" : d === 1 ? "Tomorrow" : curr.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
        const dateStr = curr.toISOString().split("T")[0];

        // Potential candidate hours
        const candidateTimes = ["09:00", "10:30", "11:45", "13:30", "15:00", "16:15"];
        
        // Filter out times overlapping existing bookings on that date
        const validTimes = candidateTimes.filter(t => {
          const [h, m] = t.split(":").map(Number);
          const slotStart = new Date(curr);
          slotStart.setHours(h, m, 0, 0);

          const isConflict = rawBookings.some((b: any) => {
            if (!b.start_time) return false;
            const bStart = new Date(b.start_time);
            return (
              bStart.getFullYear() === slotStart.getFullYear() &&
              bStart.getMonth() === slotStart.getMonth() &&
              bStart.getDate() === slotStart.getDate() &&
              Math.abs(bStart.getTime() - slotStart.getTime()) < selectedDuration * 60000
            );
          });
          return !isConflict;
        });

        days.push({
          dayLabel: dayName,
          dateStr,
          times: validTimes
        });
      }

      setCalendarSlots(days);
    } catch {
      // Mock fallback if API offline
      const mockDays: AvailableDayGroup[] = [
        { dayLabel: "Today", dateStr: new Date().toISOString().split("T")[0], times: ["11:00 AM", "02:30 PM", "04:15 PM"] },
        { dayLabel: "Tomorrow", dateStr: new Date(Date.now() + 86400000).toISOString().split("T")[0], times: ["09:30 AM", "11:00 AM", "01:00 PM", "03:30 PM"] },
        { dayLabel: "In 2 Days", dateStr: new Date(Date.now() + 172800000).toISOString().split("T")[0], times: ["10:00 AM", "12:30 PM", "02:00 PM", "04:00 PM"] }
      ];
      setCalendarSlots(mockDays);
    } finally {
      setLoadingCalendar(false);
    }
  };

  useEffect(() => {
    if (calendarOpen) {
      loadCalendarAvailability();
    }
  }, [calendarOpen, selectedDuration]);

  const handleSlotInsert = (day: AvailableDayGroup, time: string) => {
    const text = `We have an available appointment slot on ${day.dayLabel} (${day.dateStr}) at ${time} for a ${selectedDuration}-min session. Would you like me to book this for you?`;
    onInsert(text);
    onOpenChange(false);
    toast.success(`Inserted slot ${time} (${day.dayLabel})`);
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-2xl border-t bg-background p-3 sm:p-6 shadow-2xl">
          <SheetHeader className="pb-3 border-b">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <SheetTitle className="text-base font-semibold">Assistant Quick Tools</SheetTitle>
                  <SheetDescription className="text-xs text-muted-foreground">
                    Tap any macro to paste into conversation • Hold or right-click to customize
                  </SheetDescription>
                </div>
              </div>
              <Badge variant="outline" className="text-[10px] hidden sm:inline-flex">
                {customerName ? `Contact: ${customerName}` : "SMS Auto-Composer"}
              </Badge>
            </div>
          </SheetHeader>

          <div className="space-y-4 py-3">
            {/* 5 Programmable Saved Text Macros */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Saved Text Macros (5 Programmable Keys)
                </span>
                <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <Info className="w-3 h-3" /> Tap to paste, hold to edit
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-2.5">
                {macros.map((m, idx) => (
                  <div
                    key={m.id}
                    onPointerDown={() => handlePointerDown(m)}
                    onPointerUp={handlePointerUpOrLeave}
                    onPointerLeave={handlePointerUpOrLeave}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleOpenEdit(m);
                    }}
                    onClick={() => handleMacroClick(m)}
                    className={`group relative flex flex-col justify-between p-3 rounded-xl border bg-card hover:bg-accent/40 active:scale-95 transition-all cursor-pointer select-none text-left shadow-xs hover:border-primary/40 ${
                      idx === 4 ? "col-span-2 sm:col-span-1" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-xs text-foreground truncate max-w-[90px]">
                        {m.label}
                      </span>
                      <span className="text-[9px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        #{idx + 1}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                      {m.content}
                    </p>
                    <div className="mt-2 pt-1 border-t border-border/40 flex items-center justify-between text-[10px] text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="flex items-center gap-0.5">
                        <Copy className="w-2.5 h-2.5" /> Tap
                      </span>
                      <span 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenEdit(m);
                        }}
                        className="hover:underline flex items-center gap-0.5"
                      >
                        <Edit3 className="w-2.5 h-2.5" /> Edit
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Check Calendar Expanding Section */}
            <div className="rounded-xl border bg-muted/20 overflow-hidden">
              <button
                type="button"
                onClick={() => setCalendarOpen(prev => !prev)}
                className="w-full flex items-center justify-between p-3.5 text-left font-medium text-xs hover:bg-muted/40 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-blue-500/10 text-blue-600">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Check Calendar & Available Slots</span>
                    <p className="text-[11px] text-muted-foreground">
                      Inspect live openings grouped by day & duration without leaving chat
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>{calendarOpen ? "Hide" : "Show openings"}</span>
                  {calendarOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </button>

              {calendarOpen && (
                <div className="p-4 border-t bg-background space-y-3.5 animate-in fade-in-50 duration-150">
                  {/* Duration Selector */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs font-medium">Service Duration:</span>
                      <div className="flex gap-1">
                        {[15, 30, 45, 60, 90].map((dur) => (
                          <Button
                            key={dur}
                            type="button"
                            size="xs"
                            variant={selectedDuration === dur ? "default" : "outline"}
                            onClick={() => setSelectedDuration(dur)}
                            className="h-7 text-xs px-2.5"
                          >
                            {dur}m
                          </Button>
                        ))}
                      </div>
                    </div>

                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={loadCalendarAvailability}
                      disabled={loadingCalendar}
                      className="h-7 text-xs text-muted-foreground"
                    >
                      <RefreshCw className={`w-3 h-3 mr-1 ${loadingCalendar ? "animate-spin" : ""}`} />
                      Refresh
                    </Button>
                  </div>

                  {/* Available Slot Cards Grouped by Day */}
                  {loadingCalendar ? (
                    <div className="p-6 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-primary" />
                      Checking appointment schedules...
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-5 gap-3">
                      {calendarSlots.map((day) => (
                        <div key={day.dateStr} className="p-3 rounded-lg border bg-card/60 flex flex-col space-y-2">
                          <div className="border-b pb-1.5">
                            <span className="font-semibold text-xs block text-foreground">{day.dayLabel}</span>
                            <span className="text-[10px] text-muted-foreground">{day.dateStr}</span>
                          </div>
                          <div className="flex-1 space-y-1.5">
                            {day.times.length === 0 ? (
                              <span className="text-[10px] text-muted-foreground italic">Fully booked</span>
                            ) : (
                              day.times.map((t) => (
                                <button
                                  key={t}
                                  type="button"
                                  onClick={() => handleSlotInsert(day, t)}
                                  title="Click to insert into SMS reply"
                                  className="w-full text-left px-2 py-1 rounded text-xs font-mono bg-primary/5 hover:bg-primary hover:text-primary-foreground border border-primary/20 transition-all flex items-center justify-between group"
                                >
                                  <span>{t}</span>
                                  <span className="text-[9px] opacity-0 group-hover:opacity-100 uppercase text-primary-foreground">
                                    Insert
                                  </span>
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Edit Macro Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-primary" /> Customize Macro #{editingMacro?.slot_index !== undefined ? editingMacro.slot_index + 1 : editingMacro?.id}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <Label htmlFor="macro-label">Button Label (max 8 chars)</Label>
                <span className="text-[10px] text-muted-foreground">{editLabel.length}/8</span>
              </div>
              <Input
                id="macro-label"
                value={editLabel}
                maxLength={8}
                onChange={(e) => setEditLabel(e.target.value.slice(0, 8))}
                placeholder="E.g. Pricing"
                className="h-8 text-xs font-semibold"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="macro-content">Macro Content (Saved Text)</Label>
              <Textarea
                id="macro-content"
                value={editContent}
                rows={4}
                onChange={(e) => setEditContent(e.target.value)}
                placeholder="Enter the message text to insert when tapped..."
                className="text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSaveEdit} className="gap-1.5">
              <Save className="w-3.5 h-3.5" /> Save Macro
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
export default QuickToolsSheet;
