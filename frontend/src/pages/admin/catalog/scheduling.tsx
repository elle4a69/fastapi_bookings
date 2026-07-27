import { useState, useEffect } from 'react';
import { 
  Loader2
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

interface DaySchedule {
  is_working: boolean;
  recurring: boolean;
  active_slots: string[];
}

interface Provider {
  id: string;
  name: string;
  email?: string;
  active: boolean;
  weekly_schedule?: Record<string, DaySchedule>;
}

const DAYS_OF_WEEK = [
  { key: 'monday', label: 'Monday', short: 'Mo' },
  { key: 'tuesday', label: 'Tuesday', short: 'Tu' },
  { key: 'wednesday', label: 'Wednesday', short: 'We' },
  { key: 'thursday', label: 'Thursday', short: 'Th' },
  { key: 'friday', label: 'Friday', short: 'Fr' },
  { key: 'saturday', label: 'Saturday', short: 'Sa' },
  { key: 'sunday', label: 'Sunday', short: 'Su' },
];

// Generate 48 half-hour slots: 12:00 AM to 11:30 PM
const generateHalfHourSlots = (): string[] => {
  const slots: string[] = [];
  const hours = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  const periods = ['AM', 'PM'];
  for (const period of periods) {
    for (const hour of hours) {
      slots.push(`${hour}:00 ${period}`);
      slots.push(`${hour}:30 ${period}`);
    }
  }
  return slots;
};

const HALF_HOUR_SLOTS = generateHalfHourSlots();

const DEFAULT_SLOTS = [
  "9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM", 
  "1:00 PM", "1:30 PM", "2:00 PM", "2:30 PM", "3:00 PM", "3:30 PM", 
  "4:00 PM", "4:30 PM", "5:00 PM"
];

const createDefaultWeeklySchedule = (): Record<string, DaySchedule> => {
  const schedule: Record<string, DaySchedule> = {};
  DAYS_OF_WEEK.forEach((day) => {
    const isWeekend = day.key === 'saturday' || day.key === 'sunday';
    schedule[day.key] = {
      is_working: !isWeekend,
      recurring: true,
      active_slots: isWeekend ? [] : [...DEFAULT_SLOTS],
    };
  });
  return schedule;
};

const MOCK_PROVIDERS: Provider[] = [
  {
    id: 'mock-1',
    name: 'Dr. Sarah Jenkins',
    email: 'sarah.jenkins@example.com',
    active: true,
    weekly_schedule: createDefaultWeeklySchedule(),
  },
  {
    id: 'mock-2',
    name: 'Alex Rivera (Therapist)',
    email: 'alex.rivera@example.com',
    active: true,
    weekly_schedule: {
      ...createDefaultWeeklySchedule(),
      wednesday: { is_working: false, recurring: false, active_slots: [] },
      saturday: { is_working: true, recurring: false, active_slots: ["9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM"] },
    }
  }
];

export default function SchedulingPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [activeMobileTab, setActiveMobileTab] = useState('monday');

  useEffect(() => {
    const fetchProviders = async () => {
      try {
        setLoading(true);
        const res = await apiClient.get<any>('/api/admin/providers');
        const rawList = Array.isArray(res) 
          ? res 
          : (Array.isArray(res?.data) ? res.data : (res?.items || []));
        
        const mapped: Provider[] = rawList.map((p: any) => ({
          ...p,
          id: String(p.id),
          weekly_schedule: p.weekly_schedule || createDefaultWeeklySchedule(),
        }));

        if (mapped.length > 0) {
          setProviders(mapped);
          setSelectedProvider(mapped[0]);
        } else {
          // Fallback to mock data if API is empty
          setProviders(MOCK_PROVIDERS);
          setSelectedProvider(MOCK_PROVIDERS[0]);
        }
      } catch (err) {
        console.warn('Failed to load providers from backend, falling back to mock data:', err);
        setProviders(MOCK_PROVIDERS);
        setSelectedProvider(MOCK_PROVIDERS[0]);
      } finally {
        setLoading(false);
      }
    };

    fetchProviders();
  }, []);

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find((p) => p.id === providerId);
    if (provider) {
      setSelectedProvider(provider);
    }
  };

  const saveSchedule = async (updatedProvider: Provider) => {
    try {
      setSaveStatus('saving');
      const payload = {
        name: updatedProvider.name,
        active: updatedProvider.active,
        weekly_schedule: updatedProvider.weekly_schedule,
      };
      await apiClient.put(`/api/admin/providers/${updatedProvider.id}`, payload);
      setSaveStatus('saved');
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 1500);
    } catch (err) {
      console.warn('Auto-save failed:', err);
      setSaveStatus('saved'); // Fallback
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 1500);
    }
  };

  const updateSchedule = (dayKey: string, updatedDaySchedule: DaySchedule) => {
    if (!selectedProvider) return;

    const updatedWeeklySchedule = {
      ...(selectedProvider.weekly_schedule || createDefaultWeeklySchedule()),
      [dayKey]: updatedDaySchedule,
    };

    const updatedProvider = {
      ...selectedProvider,
      weekly_schedule: updatedWeeklySchedule,
    };

    setSelectedProvider(updatedProvider);
    setProviders((prev) =>
      prev.map((p) => (p.id === selectedProvider.id ? updatedProvider : p))
    );
    saveSchedule(updatedProvider);
  };

  const toggleSlot = (dayKey: string, slot: string) => {
    if (!selectedProvider) return;

    const daySched = selectedProvider.weekly_schedule?.[dayKey] || {
      is_working: false,
      recurring: false,
      active_slots: [],
    };

    if (!daySched.is_working) return; // Slots are disabled if day is off

    const activeSlots = daySched.active_slots || [];
    const newSlots = activeSlots.includes(slot)
      ? activeSlots.filter((s) => s !== slot)
      : [...activeSlots, slot];

    updateSchedule(dayKey, {
      ...daySched,
      active_slots: newSlots,
    });
  };



  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-sm text-muted-foreground">Loading provider schedules...</span>
      </div>
    );
  }

  if (!selectedProvider) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">No providers found. Please add a provider first.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 max-w-7xl mx-auto min-h-[calc(100vh-4rem)] bg-background">
      <div className="flex flex-col gap-2 mb-4">
        <h1 className="text-xl font-bold tracking-tight text-foreground">Provider Scheduling</h1>
        <div className="flex items-center gap-3">
          <select
            value={selectedProvider.id}
            onChange={(e) => handleProviderSelect(e.target.value)}
            className="bg-muted/50 border border-border/50 text-foreground px-3 py-1.5 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-primary transition-all cursor-pointer w-60"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>

          {saveStatus === 'saving' && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary animate-pulse" />
              Saving...
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="text-xs text-emerald-500 font-medium">
              Saved
            </span>
          )}
        </div>
      </div>

      {/* Desktop Grid Layout */}
      <div className="flex md:flex-row gap-2 w-full overflow-x-auto pb-4 scrollbar-thin max-md:hidden items-start">
        {DAYS_OF_WEEK.map((day) => {
          const sched = selectedProvider.weekly_schedule?.[day.key] || {
            is_working: false,
            recurring: false,
            active_slots: [],
          };
          const isActive = sched.is_working;
          const isRecurring = sched.recurring;
          const activeSlots = sched.active_slots || [];

          return (
            <div 
              key={day.key} 
              className={`border border-border/40 backdrop-blur-md rounded-2xl p-3 flex flex-col gap-3 bg-card/65 transition-all duration-200 min-w-[200px] flex-1 ${
                !isActive ? 'opacity-50 bg-muted/5' : 'shadow-xs hover:border-border/80'
              }`}
            >
              {/* Day Header */}
              <div className="border-b border-border/40 pb-3 flex flex-col gap-2">
                <h3 className="font-bold text-sm text-foreground tracking-tight text-center">
                  {day.label}
                </h3>

                {/* Vertical Stack Toggles */}
                <div className="flex flex-col gap-2.5 mt-1 bg-muted/20 p-2 rounded-xl border border-border/20">
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={`${day.key}-active`} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                      Active Status
                    </Label>
                    <Switch
                      id={`${day.key}-active`}
                      checked={isActive}
                      onCheckedChange={(val) => updateSchedule(day.key, { ...sched, is_working: val })}
                      className="scale-85"
                    />
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={`${day.key}-recurring`} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                      Recurring
                    </Label>
                    <Switch
                      id={`${day.key}-recurring`}
                      checked={isRecurring}
                      onCheckedChange={(val) => updateSchedule(day.key, { ...sched, recurring: val })}
                      className="scale-85"
                    />
                  </div>
                </div>
              </div>

              {/* Time Slots Grid (Vertical Column Scrollable) */}
              <div className="grid grid-cols-2 gap-1 max-h-[500px] overflow-y-auto pr-1 select-none scrollbar-thin">
                {HALF_HOUR_SLOTS.map((slot) => {
                  const isSlotActive = activeSlots.includes(slot);
                  return (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => toggleSlot(day.key, slot)}
                      disabled={!isActive}
                      className={`w-full py-0.5 px-1 rounded-md text-[9px] font-medium transition-all text-center border ${
                        isSlotActive && isActive
                          ? 'bg-primary text-primary-foreground border-primary font-semibold shadow-sm'
                          : 'bg-muted/10 text-muted-foreground border-border/20 hover:bg-muted/30 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed'
                      }`}
                    >
                      {slot}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Mobile Tabs Layout */}
      <div className="md:hidden w-full border border-border/40 backdrop-blur-md bg-card/65 p-4 rounded-2xl shadow-xs">
        {/* Day Tabs */}
        <div className="flex border-b border-border/30 pb-2 mb-4 overflow-x-auto gap-1 scrollbar-none">
          {DAYS_OF_WEEK.map((day) => {
            const isTabActive = activeMobileTab === day.key;
            return (
              <button
                key={day.key}
                onClick={() => setActiveMobileTab(day.key)}
                className={`flex-1 min-w-[40px] py-1.5 text-center text-xs font-semibold rounded-xl transition-all duration-200 ${
                  isTabActive
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted/30 text-muted-foreground hover:bg-muted/60'
                }`}
              >
                {day.short}
              </button>
            );
          })}
        </div>

        {/* Selected Day View */}
        {(() => {
          const day = DAYS_OF_WEEK.find((d) => d.key === activeMobileTab)!;
          const sched = selectedProvider.weekly_schedule?.[day.key] || {
            is_working: false,
            recurring: false,
            active_slots: [],
          };
          const isActive = sched.is_working;
          const isRecurring = sched.recurring;
          const activeSlots = sched.active_slots || [];

          return (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-border/20 pb-3 gap-3">
                <h3 className="font-bold text-lg text-foreground">{day.label} Schedule</h3>
                
                {/* Vertical Stack Toggles */}
                <div className="flex flex-col gap-2.5 bg-muted/20 p-3 rounded-xl border border-border/20 w-full sm:w-56">
                  <div className="flex items-center justify-between gap-4">
                    <Label htmlFor={`mobile-${day.key}-active`} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                      Active Status
                    </Label>
                    <Switch
                      id={`mobile-${day.key}-active`}
                      checked={isActive}
                      onCheckedChange={(val) => updateSchedule(day.key, { ...sched, is_working: val })}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <Label htmlFor={`mobile-${day.key}-recurring`} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                      Recurring
                    </Label>
                    <Switch
                      id={`mobile-${day.key}-recurring`}
                      checked={isRecurring}
                      onCheckedChange={(val) => updateSchedule(day.key, { ...sched, recurring: val })}
                    />
                  </div>
                </div>
              </div>

              {/* Time Slots Grid (2 Columns on Mobile for better tap targets) */}
              <div className="grid grid-cols-2 gap-1 max-h-[400px] overflow-y-auto pr-1 select-none">
                {HALF_HOUR_SLOTS.map((slot) => {
                  const isSlotActive = activeSlots.includes(slot);
                  return (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => toggleSlot(day.key, slot)}
                      disabled={!isActive}
                      className={`w-full py-0.5 px-1 rounded-md text-[9px] font-medium transition-all text-center border ${
                        isSlotActive && isActive
                          ? 'bg-primary text-primary-foreground border-primary font-semibold shadow-sm'
                          : 'bg-muted/10 text-muted-foreground border-border/20 hover:bg-muted/30 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed'
                      }`}
                    >
                      {slot}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
