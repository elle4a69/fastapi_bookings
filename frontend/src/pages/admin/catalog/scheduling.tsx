import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { WeeklyScheduleEditor } from '@/components/ui/weekly-schedule-editor';

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


export default function SchedulingPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');


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
          weekly_schedule: p.weekly_schedule || {},
        }));

        setProviders(mapped);
        if (mapped.length > 0) {
          setSelectedProvider(mapped[0]);
        }
      } catch (err) {
        console.error('Failed to load providers from backend:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProviders();
  }, []);

  const [specialDaysMap, setSpecialDaysMap] = useState<Record<string, { is_working: boolean; active_slots: string[]; reason?: string | null }>>({});

  useEffect(() => {
    if (!selectedProvider) return;
    const fetchSpecialDays = async () => {
      try {
        const res = await apiClient.get<any>(`/api/admin/providers/${selectedProvider.id}/special-days`);
        const list = Array.isArray(res) ? res : (res?.data || []);
        const map: Record<string, { is_working: boolean; active_slots: string[]; reason?: string | null }> = {};
        list.forEach((item: any) => {
          if (item.date) {
            map[item.date] = {
              is_working: item.is_working,
              active_slots: item.active_slots || [],
              reason: item.reason,
            };
          }
        });
        setSpecialDaysMap(map);
      } catch (err) {
        console.warn('Failed to fetch provider special days', err);
      }
    };
    fetchSpecialDays();
  }, [selectedProvider?.id]);

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
      setSaveStatus('saved');
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 1500);
    }
  };

  const handleScheduleFieldChange = async (
    dayKey: string,
    field: string,
    value: any,
    dateStr: string
  ) => {
    if (!selectedProvider) return;

    const currentSpecial = specialDaysMap[dateStr];
    const currentWeekly = selectedProvider.weekly_schedule?.[dayKey] ?? { is_working: false, recurring: true, active_slots: [] };
    const isCurrentlySpecial = !!currentSpecial;

    const currentEffective = isCurrentlySpecial
      ? { is_working: currentSpecial.is_working, recurring: false, active_slots: currentSpecial.active_slots }
      : currentWeekly;

    const updatedEffective = { ...currentEffective, [field]: value };

    if (field === 'recurring') {
      if (value === false) {
        setSpecialDaysMap(prev => ({
          ...prev,
          [dateStr]: { is_working: currentEffective.is_working, active_slots: currentEffective.active_slots }
        }));
        try {
          setSaveStatus('saving');
          await apiClient.post(`/api/admin/providers/${selectedProvider.id}/special-days`, {
            date: dateStr,
            is_working: currentEffective.is_working,
            active_slots: currentEffective.active_slots,
            reason: 'One-off schedule override',
          });
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus(s => s === 'saved' ? 'idle' : s), 1500);
        } catch (err) {
          console.warn('Failed to save special day', err);
        }
      } else {
        setSpecialDaysMap(prev => {
          const copy = { ...prev };
          delete copy[dateStr];
          return copy;
        });
        try {
          setSaveStatus('saving');
          await apiClient.delete(`/api/admin/providers/${selectedProvider.id}/special-days/${dateStr}`);
        } catch (err) {
          // Ignore
        }

        const updatedWeeklySchedule = {
          ...(selectedProvider.weekly_schedule || {}),
          [dayKey]: {
            is_working: updatedEffective.is_working,
            recurring: true,
            active_slots: updatedEffective.active_slots,
          }
        };
        const updatedProvider = { ...selectedProvider, weekly_schedule: updatedWeeklySchedule };
        setSelectedProvider(updatedProvider);
        setProviders(prev => prev.map(p => p.id === selectedProvider.id ? updatedProvider : p));
        saveSchedule(updatedProvider);
      }
    } else {
      if (isCurrentlySpecial || currentEffective.recurring === false) {
        setSpecialDaysMap(prev => ({
          ...prev,
          [dateStr]: { is_working: updatedEffective.is_working, active_slots: updatedEffective.active_slots }
        }));
        try {
          setSaveStatus('saving');
          await apiClient.post(`/api/admin/providers/${selectedProvider.id}/special-days`, {
            date: dateStr,
            is_working: updatedEffective.is_working,
            active_slots: updatedEffective.active_slots,
            reason: 'One-off schedule override',
          });
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus(s => s === 'saved' ? 'idle' : s), 1500);
        } catch (err) {
          console.warn('Failed to update special day', err);
        }
      } else {
        const updatedWeeklySchedule = {
          ...(selectedProvider.weekly_schedule || {}),
          [dayKey]: {
            ...currentWeekly,
            [field]: value,
          }
        };
        const updatedProvider = { ...selectedProvider, weekly_schedule: updatedWeeklySchedule };
        setSelectedProvider(updatedProvider);
        setProviders(prev => prev.map(p => p.id === selectedProvider.id ? updatedProvider : p));
        saveSchedule(updatedProvider);
      }
    }
  };

  const handleScheduleSlotToggle = async (dayKey: string, slot: string, dateStr: string) => {
    if (!selectedProvider) return;

    const currentSpecial = specialDaysMap[dateStr];
    const currentWeekly = selectedProvider.weekly_schedule?.[dayKey] ?? { is_working: true, recurring: true, active_slots: [] };
    const isCurrentlySpecial = !!currentSpecial;

    const currentSlots: string[] = isCurrentlySpecial
      ? currentSpecial.active_slots
      : (currentWeekly.active_slots || []);

    const newSlots = currentSlots.includes(slot)
      ? currentSlots.filter(s => s !== slot)
      : [...currentSlots, slot];

    if (isCurrentlySpecial || currentWeekly.recurring === false) {
      const isWorking = isCurrentlySpecial ? currentSpecial.is_working : currentWeekly.is_working;
      setSpecialDaysMap(prev => ({
        ...prev,
        [dateStr]: { is_working: isWorking, active_slots: newSlots }
      }));
      try {
        setSaveStatus('saving');
        await apiClient.post(`/api/admin/providers/${selectedProvider.id}/special-days`, {
          date: dateStr,
          is_working: isWorking,
          active_slots: newSlots,
          reason: 'One-off schedule override',
        });
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus(s => s === 'saved' ? 'idle' : s), 1500);
      } catch (err) {
        console.warn('Failed to update special day slot', err);
      }
    } else {
      const updatedWeeklySchedule = {
        ...(selectedProvider.weekly_schedule || {}),
        [dayKey]: {
          ...currentWeekly,
          active_slots: newSlots,
        }
      };
      const updatedProvider = { ...selectedProvider, weekly_schedule: updatedWeeklySchedule };
      setSelectedProvider(updatedProvider);
      setProviders(prev => prev.map(p => p.id === selectedProvider.id ? updatedProvider : p));
      saveSchedule(updatedProvider);
    }
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
      {/* Header: page title + provider selector */}
      <div className="flex flex-col gap-2 mb-2">
        <h1 className="text-xl font-bold tracking-tight text-foreground">Provider Scheduling</h1>
        <select
          value={selectedProvider.id}
          onChange={(e) => handleProviderSelect(e.target.value)}
          className="bg-muted/50 border border-border/50 text-foreground px-3 py-1.5 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-primary transition-all cursor-pointer w-60"
        >
          {providers.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {/* Single unified schedule editor — used on both desktop and mobile */}
      <div className="border border-border/40 rounded-2xl bg-card/80 shadow-xs overflow-hidden">
        <WeeklyScheduleEditor
          schedule={selectedProvider.weekly_schedule}
          specialDays={specialDaysMap}
          saveStatus={saveStatus}
          onFieldChange={(dayKey, field, value, dateStr) =>
            handleScheduleFieldChange(dayKey, field as string, value, dateStr)
          }
          onSlotToggle={(dayKey, slot, dateStr) =>
            handleScheduleSlotToggle(dayKey, slot, dateStr)
          }
        />
      </div>
    </div>
  );
}

