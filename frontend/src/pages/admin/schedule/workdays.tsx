import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { User, Loader2, ChevronLeft, ChevronRight, Calendar, ArrowLeft, Clock, Sparkles } from 'lucide-react';
import { AutoSaveStatus, type SaveState } from '@/components/ui/auto-save-status';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTenantModules } from '@/context/tenant-modules-context';

const DAYS_OF_WEEK = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

interface DaySchedule {
  dayName: string;
  date: Date;
  dateStr: string;
  isDayOff: boolean;
  isRecurring: boolean;
  selectedSlots: string[];
  isOverride: boolean;
}

interface Provider {
  id: string;
  user_id: string;
  name: string;
  weekly_schedule?: Record<string, { is_working: boolean; recurring: boolean; active_slots: string[] }> | null;
}

interface DateOverride {
  dateStr: string;
  isDayOff: boolean;
  isRecurring: boolean;
  selectedSlots: string[];
}

interface SpecialDayBackendRecord {
  id?: number;
  date: string;
  is_working: boolean;
  start_time?: string | null;
  end_time?: string | null;
  active_slots?: string[];
  reason?: string | null;
}

const TIME_SLOTS: string[] = [];
for (let h = 0; h < 24; h++) {
  TIME_SLOTS.push(`${String(h).padStart(2, '0')}:00`);
  TIME_SLOTS.push(`${String(h).padStart(2, '0')}:30`);
}

function formatSlot(slot: string) {
  const [h, m] = slot.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const hour = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
}

const convertSlot = (slot: string): string => {
  const match = slot.match(/^(\d+):(\d+)\s*(AM|PM)$/i);
  if (!match) return slot;
  let h = parseInt(match[1]);
  const m = match[2];
  const period = match[3].toUpperCase();
  if (period === 'PM' && h !== 12) h += 12;
  if (period === 'AM' && h === 12) h = 0;
  return `${String(h).padStart(2, '0')}:${m}`;
};

const convertTo12h = (slot: string): string => {
  const [hStr, mStr] = slot.split(':');
  let h = parseInt(hStr);
  const m = mStr;
  const period = h >= 12 ? 'PM' : 'AM';
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return `${h}:${m} ${period}`;
};

const toISODate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const getStartOfWeek = (date: Date) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day;
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
};

const DEFAULT_ACTIVE_SLOTS = [
  '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
  '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
  '15:00', '15:30', '16:00', '16:30'
];

export default function WorkdaysPage() {
  const { multipleProvidersEnabled } = useTenantModules();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [maxDaysAhead, setMaxDaysAhead] = useState(14);
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(getStartOfWeek(new Date()));
  const [selectedDayName, setSelectedDayName] = useState<string>(DAYS_OF_WEEK[new Date().getDay()]);
  const [viewMode, setViewMode] = useState<'single' | 'all'>('all');

  // Baseline recurring weekly schedule for the selected provider
  const [weeklyScheduleTemplate, setWeeklyScheduleTemplate] = useState<
    Record<string, { is_working: boolean; active_slots: string[] }>
  >({});

  // Special-day overrides loaded from backend for this provider (keyed by YYYY-MM-DD)
  const [specialDaysMap, setSpecialDaysMap] = useState<Record<string, SpecialDayBackendRecord>>({});

  // Fixed Start Times local state
  const [fixedStartTimesTemplate, setFixedStartTimesTemplate] = useState<
    Record<string, { is_working: boolean; active_slots: string[] }>
  >({});
  const [fixedStartTimesOverrides, setFixedStartTimesOverrides] = useState<Record<string, DateOverride>>({});

  // Auto-save debounce refs
  const weeklyDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const specialDayDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const advanceDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (weeklyDebounceRef.current) clearTimeout(weeklyDebounceRef.current);
      if (specialDayDebounceRef.current) clearTimeout(specialDayDebounceRef.current);
      if (advanceDebounceRef.current) clearTimeout(advanceDebounceRef.current);
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
    };
  }, []);

  // Fetch initial providers list
  const fetchProviders = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await apiClient.get<any>('/api/admin/providers');
      const providersList = Array.isArray(res)
        ? res
        : (Array.isArray(res?.data) ? res.data : (res?.items || []));
      setProviders(providersList);
      if (providersList.length > 0) {
        setSelectedProvider(providersList[0]);
      }
    } catch (error) {
      toast.error('Failed to load initial data');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  // Load business profile advance booking window
  useEffect(() => {
    apiClient.get<any>('/api/admin/business-profile')
      .then((res) => {
        const data = res?.data || res;
        if (data?.max_advance_days !== undefined && data?.max_advance_days !== null) {
          setMaxDaysAhead(data.max_advance_days);
        }
      })
      .catch((err) => {
        console.warn('Failed to load advance booking window:', err);
      });
  }, []);

  // Fetch provider special days from backend
  const fetchSpecialDays = useCallback(async (providerId: string) => {
    try {
      const res = await apiClient.get<any>(`/api/admin/providers/${providerId}/special-days`);
      const list: SpecialDayBackendRecord[] = Array.isArray(res)
        ? res
        : (Array.isArray(res?.data) ? res.data : []);
      
      const map: Record<string, SpecialDayBackendRecord> = {};
      list.forEach((item) => {
        if (item.date) {
          map[item.date] = {
            id: item.id,
            date: item.date,
            is_working: item.is_working,
            active_slots: item.active_slots || [],
            reason: item.reason,
          };
        }
      });
      setSpecialDaysMap(map);
    } catch (err) {
      console.warn('Failed to fetch provider special days:', err);
    }
  }, []);

  // When selected provider changes: load recurring weekly template and fetch special days
  useEffect(() => {
    if (!selectedProvider) return;

    // 1. Build weekly template from provider's weekly_schedule
    const sched = selectedProvider.weekly_schedule;
    const initialTemplate: Record<string, { is_working: boolean; active_slots: string[] }> = {};
    const initialFixedTemplate: Record<string, { is_working: boolean; active_slots: string[] }> = {};

    DAYS_OF_WEEK.forEach((dayName, idx) => {
      const key = dayName.toLowerCase();
      const dayData = sched && typeof sched === 'object' && !Array.isArray(sched) ? sched[key] : undefined;
      const isWorking = dayData ? dayData.is_working : (idx > 0 && idx < 6);
      const slots = dayData && dayData.active_slots
        ? dayData.active_slots.map(convertSlot)
        : (idx > 0 && idx < 6 ? [...DEFAULT_ACTIVE_SLOTS] : []);

      initialTemplate[key] = {
        is_working: isWorking,
        active_slots: slots,
      };
      initialFixedTemplate[key] = {
        is_working: isWorking,
        active_slots: [...slots],
      };
    });

    setWeeklyScheduleTemplate(initialTemplate);
    setFixedStartTimesTemplate(initialFixedTemplate);
    setFixedStartTimesOverrides({});

    fetchSpecialDays(selectedProvider.id);
  }, [selectedProvider?.id, fetchSpecialDays]);

  // Synchronize in real time with changes from the Exceptions page or other windows
  useEffect(() => {
    if (!selectedProvider?.id) return;
    const handleSync = () => {
      fetchSpecialDays(selectedProvider.id);
    };
    window.addEventListener('schedule-exceptions-updated', handleSync);
    window.addEventListener('focus', handleSync);
    return () => {
      window.removeEventListener('schedule-exceptions-updated', handleSync);
      window.removeEventListener('focus', handleSync);
    };
  }, [selectedProvider?.id, fetchSpecialDays]);

  // ─────────────────────────────────────────────────────────────────────────
  // Auto-Save Mechanics
  // ─────────────────────────────────────────────────────────────────────────
  const saveWeeklySchedule = useCallback(
    async (template: Record<string, { is_working: boolean; active_slots: string[] }>) => {
      if (!selectedProvider) return;
      setSaveState('saving');
      try {
        const weekly_schedule: Record<string, { is_working: boolean; recurring: boolean; active_slots: string[] }> = {};
        DAYS_OF_WEEK.forEach((dayName) => {
          const key = dayName.toLowerCase();
          const base = template[key] ?? { is_working: false, active_slots: [] };
          weekly_schedule[key] = {
            is_working: base.is_working && base.active_slots.length > 0,
            recurring: true,
            active_slots: base.active_slots.map(convertTo12h),
          };
        });

        await apiClient.put(`/api/admin/providers/${selectedProvider.id}`, { weekly_schedule });
        
        setSelectedProvider((prev) => prev ? { ...prev, weekly_schedule } : null);
        setProviders((prev) => prev.map((p) => (p.id === selectedProvider.id ? { ...p, weekly_schedule } : p)));

        setSaveState('saved');
        if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
        savedTimerRef.current = setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        console.error('Failed to auto-save weekly schedule:', err);
        setSaveState('failed');
      }
    },
    [selectedProvider]
  );

  const debouncedSaveWeeklySchedule = useCallback(
    (template: Record<string, { is_working: boolean; active_slots: string[] }>) => {
      setSaveState('saving');
      if (weeklyDebounceRef.current) clearTimeout(weeklyDebounceRef.current);
      weeklyDebounceRef.current = setTimeout(() => {
        saveWeeklySchedule(template);
      }, 500);
    },
    [saveWeeklySchedule]
  );

  const saveSpecialDay = useCallback(
    async (dateStr: string, isWorking: boolean, activeSlots: string[], reason?: string) => {
      if (!selectedProvider) return;
      setSaveState('saving');
      try {
        await apiClient.post(`/api/admin/providers/${selectedProvider.id}/special-days`, {
          date: dateStr,
          is_working: isWorking,
          active_slots: activeSlots.map(convertTo12h),
          reason: reason || (isWorking ? 'One-off schedule override' : 'Day off override'),
        });
        window.dispatchEvent(new CustomEvent('schedule-exceptions-updated'));
        setSaveState('saved');
        if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
        savedTimerRef.current = setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        console.error('Failed to auto-save special day:', err);
        setSaveState('failed');
      }
    },
    [selectedProvider]
  );

  const debouncedSaveSpecialDay = useCallback(
    (dateStr: string, isWorking: boolean, activeSlots: string[], reason?: string) => {
      setSaveState('saving');
      if (specialDayDebounceRef.current) clearTimeout(specialDayDebounceRef.current);
      specialDayDebounceRef.current = setTimeout(() => {
        saveSpecialDay(dateStr, isWorking, activeSlots, reason);
      }, 500);
    },
    [saveSpecialDay]
  );

  const deleteSpecialDay = useCallback(
    async (dateStr: string) => {
      if (!selectedProvider) return;
      setSaveState('saving');
      try {
        await apiClient.delete(`/api/admin/providers/${selectedProvider.id}/special-days/${dateStr}`);
        window.dispatchEvent(new CustomEvent('schedule-exceptions-updated'));
        setSaveState('saved');
        if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
        savedTimerRef.current = setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        console.error('Failed to delete special day:', err);
        setSaveState('failed');
      }
    },
    [selectedProvider]
  );

  const handleMaxDaysAheadChange = (val: number) => {
    setMaxDaysAhead(val);
    setSaveState('saving');
    if (advanceDebounceRef.current) clearTimeout(advanceDebounceRef.current);
    advanceDebounceRef.current = setTimeout(async () => {
      try {
        await apiClient.put('/api/admin/business-profile', { max_advance_days: val });
        setSaveState('saved');
        if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
        savedTimerRef.current = setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        console.error('Failed to update advance days:', err);
        setSaveState('failed');
      }
    }, 500);
  };

  const handleRetry = () => {
    saveWeeklySchedule(weeklyScheduleTemplate);
  };

  // Compute effective 7-day schedule for the active week start
  const schedules: DaySchedule[] = useMemo(() => {
    return DAYS_OF_WEEK.map((dayName, i) => {
      const d = new Date(currentWeekStart);
      d.setDate(d.getDate() + i);
      const dateStr = toISODate(d);
      const dayKey = dayName.toLowerCase();

      // Check special-day override for this date
      const specialRecord = specialDaysMap[dateStr];
      if (specialRecord) {
        return {
          dayName,
          date: d,
          dateStr,
          isDayOff: !specialRecord.is_working,
          isRecurring: false,
          selectedSlots: specialRecord.active_slots ? specialRecord.active_slots.map(convertSlot) : [],
          isOverride: true,
        };
      }

      // Baseline recurring weekly template
      const base = weeklyScheduleTemplate[dayKey] ?? {
        is_working: i > 0 && i < 6,
        active_slots: i > 0 && i < 6 ? [...DEFAULT_ACTIVE_SLOTS] : [],
      };

      return {
        dayName,
        date: d,
        dateStr,
        isDayOff: !base.is_working,
        isRecurring: true,
        selectedSlots: base.active_slots,
        isOverride: false,
      };
    });
  }, [currentWeekStart, weeklyScheduleTemplate, specialDaysMap]);

  // Compute Fixed Start Times schedules
  const fixedStartTimesSchedules: DaySchedule[] = useMemo(() => {
    return DAYS_OF_WEEK.map((dayName, i) => {
      const d = new Date(currentWeekStart);
      d.setDate(d.getDate() + i);
      const dateStr = toISODate(d);
      const dayKey = dayName.toLowerCase();

      const localOverride = fixedStartTimesOverrides[dateStr];
      if (localOverride) {
        return {
          dayName,
          date: d,
          dateStr,
          isDayOff: localOverride.isDayOff,
          isRecurring: false,
          selectedSlots: localOverride.selectedSlots,
          isOverride: true,
        };
      }

      const base = fixedStartTimesTemplate[dayKey] ?? {
        is_working: i > 0 && i < 6,
        active_slots: i > 0 && i < 6 ? ['09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00'] : [],
      };

      return {
        dayName,
        date: d,
        dateStr,
        isDayOff: !base.is_working,
        isRecurring: true,
        selectedSlots: base.active_slots,
        isOverride: false,
      };
    });
  }, [currentWeekStart, fixedStartTimesTemplate, fixedStartTimesOverrides]);

  const toggleSlot = (dayIndex: number, slot: string, isFixed: boolean = false) => {
    const activeList = isFixed ? fixedStartTimesSchedules : schedules;
    const day = activeList[dayIndex];
    if (!day) return;

    const newSlots = day.selectedSlots.includes(slot)
      ? day.selectedSlots.filter((s) => s !== slot)
      : [...day.selectedSlots, slot].sort();

    if (isFixed) {
      if (day.isRecurring) {
        setFixedStartTimesTemplate((prev) => ({
          ...prev,
          [day.dayName.toLowerCase()]: {
            is_working: !day.isDayOff,
            active_slots: newSlots,
          },
        }));
      } else {
        setFixedStartTimesOverrides((prev) => ({
          ...prev,
          [day.dateStr]: {
            dateStr: day.dateStr,
            isDayOff: day.isDayOff,
            isRecurring: false,
            selectedSlots: newSlots,
          },
        }));
      }
      return;
    }

    if (day.isRecurring) {
      const nextTemplate = {
        ...weeklyScheduleTemplate,
        [day.dayName.toLowerCase()]: {
          is_working: !day.isDayOff && newSlots.length > 0,
          active_slots: newSlots,
        },
      };
      setWeeklyScheduleTemplate(nextTemplate);
      debouncedSaveWeeklySchedule(nextTemplate);
    } else {
      const nextSpecial = {
        ...specialDaysMap,
        [day.dateStr]: {
          date: day.dateStr,
          is_working: !day.isDayOff && newSlots.length > 0,
          active_slots: newSlots.map(convertTo12h),
          reason: 'One-off schedule override',
        },
      };
      setSpecialDaysMap(nextSpecial);
      debouncedSaveSpecialDay(day.dateStr, !day.isDayOff && newSlots.length > 0, newSlots, 'One-off schedule override');
    }
  };

  const updateDay = (dayIndex: number, updates: Partial<DaySchedule>, isFixed: boolean = false) => {
    const activeList = isFixed ? fixedStartTimesSchedules : schedules;
    const day = activeList[dayIndex];
    if (!day) return;

    const dayKey = day.dayName.toLowerCase();

    // ─────────────────────────────────────────────────────────────────────────
    // 1. RECURRING TOGGLE CHANGED
    // ─────────────────────────────────────────────────────────────────────────
    if (updates.isRecurring !== undefined) {
      const nextRecurring = updates.isRecurring;

      if (!nextRecurring) {
        // Turning Recurring OFF for this specific calendar date:
        // Snapshot into specialDaysMap and save
        if (isFixed) {
          setFixedStartTimesOverrides((prev) => ({
            ...prev,
            [day.dateStr]: {
              dateStr: day.dateStr,
              isDayOff: day.isDayOff,
              isRecurring: false,
              selectedSlots: [...day.selectedSlots],
            },
          }));
        } else {
          const nextSpecial = {
            ...specialDaysMap,
            [day.dateStr]: {
              date: day.dateStr,
              is_working: !day.isDayOff,
              active_slots: day.selectedSlots.map(convertTo12h),
              reason: day.isDayOff ? 'Day Off override' : 'One-off schedule override',
            },
          };
          setSpecialDaysMap(nextSpecial);
          saveSpecialDay(day.dateStr, !day.isDayOff, day.selectedSlots, day.isDayOff ? 'Day Off override' : 'One-off schedule override');
        }
      } else {
        // Turning Recurring BACK ON for this specific calendar date:
        // Discard date-specific override and revert back to recurring weekly template
        if (isFixed) {
          setFixedStartTimesOverrides((prev) => {
            const next = { ...prev };
            delete next[day.dateStr];
            return next;
          });
        } else {
          const nextSpecial = { ...specialDaysMap };
          delete nextSpecial[day.dateStr];
          setSpecialDaysMap(nextSpecial);
          deleteSpecialDay(day.dateStr);
        }
      }
      return;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 2. DAY OFF / SLOTS CHANGED
    // ─────────────────────────────────────────────────────────────────────────
    const nextIsDayOff = updates.isDayOff !== undefined ? updates.isDayOff : day.isDayOff;
    const nextSlots = updates.selectedSlots !== undefined ? updates.selectedSlots : day.selectedSlots;

    if (isFixed) {
      if (day.isRecurring) {
        setFixedStartTimesTemplate((prev) => ({
          ...prev,
          [dayKey]: {
            is_working: !nextIsDayOff,
            active_slots: nextSlots,
          },
        }));
      } else {
        setFixedStartTimesOverrides((prev) => ({
          ...prev,
          [day.dateStr]: {
            dateStr: day.dateStr,
            isDayOff: nextIsDayOff,
            isRecurring: false,
            selectedSlots: nextSlots,
          },
        }));
      }
      return;
    }

    if (day.isRecurring) {
      // Modify recurring weekly template
      const nextTemplate = {
        ...weeklyScheduleTemplate,
        [dayKey]: {
          is_working: !nextIsDayOff,
          active_slots: nextSlots,
        },
      };
      setWeeklyScheduleTemplate(nextTemplate);
      debouncedSaveWeeklySchedule(nextTemplate);
    } else {
      // Modify date-specific override
      const nextSpecial = {
        ...specialDaysMap,
        [day.dateStr]: {
          date: day.dateStr,
          is_working: !nextIsDayOff,
          active_slots: nextSlots.map(convertTo12h),
          reason: nextIsDayOff ? 'Day Off override' : 'One-off schedule override',
        },
      };
      setSpecialDaysMap(nextSpecial);
      debouncedSaveSpecialDay(day.dateStr, !nextIsDayOff, nextSlots, nextIsDayOff ? 'Day Off override' : 'One-off schedule override');
    }
  };

  const navigateWeek = (dir: 1 | -1) => {
    const nextWeek = new Date(currentWeekStart);
    nextWeek.setDate(nextWeek.getDate() + dir * 7);
    setCurrentWeekStart(nextWeek);
  };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const formattedWeekStart = currentWeekStart.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] md:gap-6 p-1 sm:p-4 md:p-6 font-sans">
      {multipleProvidersEnabled && (
        <Card
          className={`md:w-[35%] flex flex-col h-full rounded-xl transition-all duration-300 border-border/50 shadow-sm bg-card/50 backdrop-blur-sm ${
            selectedProvider ? 'hidden md:flex' : 'flex w-full'
          }`}
        >
          <CardHeader className="p-4 md:p-6 pb-4">
            <CardTitle className="text-xl flex items-center gap-2 font-heading">
              <User className="h-5 w-5" />
              Staff
            </CardTitle>
            <CardDescription>Select a provider to manage their schedule</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-full">
              <div className="flex flex-col gap-2 p-4 pt-0">
                {providers.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => setSelectedProvider(provider)}
                    className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all duration-200 hover:scale-[1.01] hover:shadow-md border min-h-[60px] ${
                      selectedProvider?.id === provider.id
                        ? 'bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-primary font-medium'
                        : 'text-muted-foreground bg-card hover:bg-accent/30 border-transparent hover:border-border/60'
                    }`}
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      {provider.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="truncate">
                      <div className={selectedProvider?.id === provider.id ? 'text-foreground font-semibold' : ''}>
                        {provider.name}
                      </div>
                    </div>
                  </button>
                ))}
                {providers.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    No staff members found
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      <Card
        className={`${
          multipleProvidersEnabled ? 'md:w-[65%]' : 'w-full'
        } flex flex-col h-full border border-border/50 shadow-sm bg-card/50 backdrop-blur-sm transition-all duration-300 ${
          multipleProvidersEnabled ? (selectedProvider ? 'flex w-full' : 'hidden md:flex') : 'flex w-full'
        } rounded-xl`}
      >
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 sm:p-4 md:p-6 pb-3 sm:pb-4 gap-3 sm:gap-4 border-b sticky top-0 bg-background/95 z-10 shrink-0">
          <div className="flex items-center gap-3">
            {multipleProvidersEnabled && (
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden shrink-0 min-h-[44px] min-w-[44px]"
                onClick={() => setSelectedProvider(null)}
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>
            )}
            <div>
              <CardTitle className="text-xl flex items-center gap-2 font-heading">
                <Calendar className="h-5 w-5 text-primary" />
                {multipleProvidersEnabled && selectedProvider
                  ? `Weekly Schedule - ${selectedProvider.name}`
                  : 'Weekly Schedule'}
              </CardTitle>
              <CardDescription className="hidden md:block">
                Manage recurring weekly hours and date-specific schedule overrides
              </CardDescription>
            </div>
          </div>
          <AutoSaveStatus state={saveState} onRetry={handleRetry} />
        </CardHeader>

        <CardContent className="flex-1 overflow-auto p-0">
          {selectedProvider ? (
            <div className="p-2 sm:p-4 md:p-6 space-y-4 sm:space-y-6 md:space-y-8">
              {/* Advance Booking Window Setting */}
              <div className="flex flex-col gap-1.5 sm:gap-2 p-2.5 sm:p-4 bg-muted/30 rounded-lg border">
                <Label htmlFor="maxDaysAhead" className="font-semibold text-base">
                  Time in Advance
                </Label>
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                  <div className="flex items-center gap-2">
                    <Input
                      id="maxDaysAhead"
                      type="number"
                      value={maxDaysAhead}
                      onChange={(e) => handleMaxDaysAheadChange(parseInt(e.target.value) || 0)}
                      className="w-24 sm:w-32 h-9 text-base"
                    />
                    <span className="text-sm text-muted-foreground whitespace-nowrap">days ahead</span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    Maximum Days Ahead: Determines how far in advance clients can book
                  </span>
                </div>
              </div>

              {/* Week Navigation Header */}
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-3">
                  <h3 className="text-base sm:text-lg font-semibold font-heading">
                    Week of {formattedWeekStart}
                  </h3>
                  {/* View Mode Toggle for Desktop */}
                  <div className="hidden sm:flex items-center gap-1 bg-muted/40 p-0.5 rounded-lg border text-xs">
                    <button
                      type="button"
                      onClick={() => setViewMode('all')}
                      className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                        viewMode === 'all'
                          ? 'bg-background text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      All 7 Days
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode('single')}
                      className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                        viewMode === 'single'
                          ? 'bg-background text-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Selected Day
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 sm:gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => navigateWeek(-1)}
                    className="h-8 w-8 sm:h-9 sm:w-9"
                    title="Previous week"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => navigateWeek(1)}
                    className="h-8 w-8 sm:h-9 sm:w-9"
                    title="Next week"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* 7-Day Selector Bar: Always visible on mobile, responsive on desktop */}
              <div className="grid grid-cols-7 gap-1 w-full pb-1">
                {DAYS_OF_WEEK.map((dayName) => {
                  const isSelected = selectedDayName === dayName;
                  const daySched = schedules.find((s) => s.dayName === dayName);
                  const dateNum = daySched ? daySched.date.getDate() : '';
                  const hasOverride = daySched?.isOverride;
                  const isOff = daySched?.isDayOff;

                  return (
                    <Button
                      key={dayName}
                      type="button"
                      variant={isSelected ? 'default' : 'outline'}
                      size="sm"
                      className={`h-12 w-full min-w-0 p-0 flex flex-col items-center justify-center rounded-lg transition-all relative ${
                        isSelected
                          ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                          : isOff
                          ? 'text-muted-foreground/60 bg-muted/20 border-dashed hover:text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-accent/40'
                      }`}
                      onClick={() => {
                        setSelectedDayName(dayName);
                      }}
                    >
                      <div className="flex items-center gap-0.5 leading-none">
                        <span className="text-[11px] font-semibold uppercase">{dayName.slice(0, 3)}</span>
                      </div>
                      {dateNum && <span className="text-xs leading-none font-bold mt-1">{dateNum}</span>}

                      {/* Override Indicator Dot */}
                      {hasOverride && (
                        <span
                          className={`absolute top-1 right-1 w-2 h-2 rounded-full ${
                            isSelected ? 'bg-amber-300 ring-1 ring-background' : 'bg-amber-500'
                          }`}
                          title="Date-specific override active"
                        />
                      )}
                    </Button>
                  );
                })}
              </div>

              {/* Main Working Day Cards */}
              <div className="space-y-4 sm:space-y-6">
                {schedules.map((day, idx) => {
                  const isCardVisible = viewMode === 'all' ? true : selectedDayName === day.dayName;
                  // On mobile screens (<640px), always respect selectedDayName
                  const mobileVisible = selectedDayName === day.dayName;

                  return (
                    <div
                      key={day.dayName}
                      className={`flex flex-col gap-3 sm:gap-4 p-2.5 sm:p-4 rounded-lg border transition-colors ${
                        day.isDayOff ? 'bg-muted/10 border-dashed' : 'bg-card'
                      } ${mobileVisible ? 'flex' : isCardVisible ? 'hidden sm:flex' : 'hidden'}`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b pb-2.5 sm:pb-3 gap-2 sm:gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-base">
                            {day.dayName}{' '}
                            <span className="text-muted-foreground font-normal text-sm">
                              ({day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })})
                            </span>
                          </h4>
                          {day.isOverride ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-600 border border-amber-500/30">
                              <Sparkles className="w-3 h-3" />
                              Date Override
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground border">
                              Recurring
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-4 sm:gap-6 pt-0.5 sm:pt-0">
                          {/* Day Off Switch */}
                          <div className="flex items-center gap-2">
                            <Switch
                              id={`dayoff-${day.dayName}`}
                              checked={day.isDayOff}
                              onCheckedChange={(c) => updateDay(idx, { isDayOff: c })}
                            />
                            <Label htmlFor={`dayoff-${day.dayName}`} className="text-sm font-medium cursor-pointer">
                              Day Off
                            </Label>
                          </div>

                          {/* Recurring Switch — ALWAYS AVAILABLE so Day Off can also be one-off vs recurring */}
                          <div className="flex items-center gap-2">
                            <Switch
                              id={`recurring-${day.dayName}`}
                              checked={day.isRecurring}
                              onCheckedChange={(c) => updateDay(idx, { isRecurring: c })}
                            />
                            <Label htmlFor={`recurring-${day.dayName}`} className="text-sm font-medium cursor-pointer">
                              Recurring
                            </Label>
                          </div>
                        </div>
                      </div>

                      {/* Explanation note when recurring is turned OFF */}
                      {!day.isRecurring && (
                        <div className="text-xs text-amber-700 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-md flex items-center justify-between">
                          <span>
                            <strong>One-off date exception:</strong> Changes apply only to{' '}
                            {day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, without altering future {day.dayName}s.
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs text-amber-800 hover:text-amber-950 hover:bg-amber-500/20 underline"
                            onClick={() => updateDay(idx, { isRecurring: true })}
                          >
                            Revert to weekly template
                          </Button>
                        </div>
                      )}

                      {!day.isDayOff ? (
                        <div className="space-y-2.5 sm:space-y-3">
                          <div className="flex items-center justify-between gap-2 pt-0.5">
                            <span className="text-sm text-muted-foreground font-medium flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5" />
                              Slots ({day.selectedSlots.length} active)
                            </span>
                            <div className="flex items-center gap-1">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                onClick={() =>
                                  updateDay(idx, {
                                    selectedSlots: [
                                      '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
                                      '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
                                      '15:00', '15:30', '16:00', '16:30'
                                    ]
                                  })
                                }
                              >
                                9-5
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => updateDay(idx, { selectedSlots: [...TIME_SLOTS] })}
                              >
                                All
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => updateDay(idx, { selectedSlots: [] })}
                              >
                                Clear
                              </Button>
                            </div>
                          </div>
                          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-1 sm:gap-1.5">
                            {TIME_SLOTS.map((slot) => {
                              const isSelected = day.selectedSlots.includes(slot);
                              return (
                                <Button
                                  key={slot}
                                  type="button"
                                  variant={isSelected ? 'default' : 'outline'}
                                  size="sm"
                                  className={`h-8 w-full p-0 text-xs font-semibold justify-center transition-all ${
                                    isSelected ? 'shadow-xs' : 'text-muted-foreground hover:text-foreground'
                                  }`}
                                  onClick={() => toggleSlot(idx, slot)}
                                >
                                  {formatSlot(slot)}
                                </Button>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="py-4 text-center text-muted-foreground text-sm italic">
                          Day off — no bookings available on this date
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Fixed Start Times Section */}
              <div className="pt-4 sm:pt-6 mt-6 sm:mt-8 border-t">
                <h3 className="text-base sm:text-lg font-semibold mb-1 sm:mb-2">Fixed Start Times</h3>
                <p className="text-sm text-muted-foreground mb-4 sm:mb-6">
                  Services with fixed start times will only be available at these slots
                </p>

                <div className="space-y-4 sm:space-y-6">
                  {fixedStartTimesSchedules.map((day, idx) => {
                    const isCardVisible = viewMode === 'all' ? true : selectedDayName === day.dayName;
                    const mobileVisible = selectedDayName === day.dayName;

                    return (
                      <div
                        key={`fixed-${day.dayName}`}
                        className={`flex flex-col gap-3 sm:gap-4 p-2.5 sm:p-4 rounded-lg border transition-colors ${
                          day.isDayOff ? 'bg-muted/10 border-dashed' : 'bg-card'
                        } ${mobileVisible ? 'flex' : isCardVisible ? 'hidden sm:flex' : 'hidden'}`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b pb-2.5 sm:pb-3 gap-2 sm:gap-4">
                          <div>
                            <h4 className="font-semibold text-base">
                              {day.dayName}{' '}
                              <span className="text-muted-foreground font-normal text-sm">
                                ({day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})
                              </span>
                            </h4>
                          </div>

                          <div className="flex items-center gap-2 pt-0.5 sm:pt-0">
                            <Switch
                              id={`fixed-dayoff-${day.dayName}`}
                              checked={day.isDayOff}
                              onCheckedChange={(c) => updateDay(idx, { isDayOff: c }, true)}
                            />
                            <Label htmlFor={`fixed-dayoff-${day.dayName}`} className="text-sm font-medium cursor-pointer">
                              Day Off
                            </Label>
                          </div>
                        </div>

                        {!day.isDayOff ? (
                          <div className="space-y-2.5 sm:space-y-3">
                            <div className="flex items-center justify-between gap-2 pt-0.5">
                              <span className="text-sm text-muted-foreground font-medium">
                                Fixed Slots ({day.selectedSlots.length} active)
                              </span>
                              <div className="flex items-center gap-1">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() =>
                                    updateDay(
                                      idx,
                                      {
                                        selectedSlots: [
                                          '09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00'
                                        ]
                                      },
                                      true
                                    )
                                  }
                                >
                                  Hourly
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => updateDay(idx, { selectedSlots: [...TIME_SLOTS] }, true)}
                                >
                                  All
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => updateDay(idx, { selectedSlots: [] }, true)}
                                >
                                  Clear
                                </Button>
                              </div>
                            </div>
                            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-1 sm:gap-1.5">
                              {TIME_SLOTS.map((slot) => {
                                const isSelected = day.selectedSlots.includes(slot);
                                return (
                                  <Button
                                    key={slot}
                                    type="button"
                                    variant={isSelected ? 'default' : 'outline'}
                                    size="sm"
                                    className={`h-8 w-full p-0 text-xs font-semibold justify-center transition-all ${
                                      isSelected ? 'shadow-xs' : 'text-muted-foreground hover:text-foreground'
                                    }`}
                                    onClick={() => toggleSlot(idx, slot, true)}
                                  >
                                    {formatSlot(slot)}
                                  </Button>
                                );
                              })}
                            </div>
                          </div>
                        ) : (
                          <div className="py-4 text-center text-muted-foreground text-sm italic">
                            No fixed start times on this day off
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              Select a provider from the sidebar to view their schedule
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
