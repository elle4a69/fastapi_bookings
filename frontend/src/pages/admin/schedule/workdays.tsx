import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { User, Save, Loader2, ChevronLeft, ChevronRight, Calendar, ArrowLeft } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

const DAYS_OF_WEEK = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

interface DaySchedule {
  dayName: string;
  date: Date;
  isDayOff: boolean;
  isRecurring: boolean;
  selectedSlots: string[];
}

interface Provider {
  id: string;
  user_id: string;
  name: string;
  weekly_schedule?: any[];
}

const TIME_SLOTS: string[] = [];
for (let h = 7; h <= 19; h++) {
  TIME_SLOTS.push(`${String(h).padStart(2, '0')}:00`);
  TIME_SLOTS.push(`${String(h).padStart(2, '0')}:30`);
}

function formatSlot(slot: string) {
  const [h, m] = slot.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const hour = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
}

const getStartOfWeek = (date: Date) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day;
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
};

export default function WorkdaysPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [maxDaysAhead, setMaxDaysAhead] = useState(14);
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(getStartOfWeek(new Date()));
  const [mobileSelectedDay, setMobileSelectedDay] = useState<string>(DAYS_OF_WEEK[new Date().getDay()]);

  const generateInitialSchedules = (weekStart: Date): DaySchedule[] => {
    return DAYS_OF_WEEK.map((day, i) => {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      return {
        dayName: day,
        date: d,
        isDayOff: i === 0, // Sunday off by default
        isRecurring: true,
        selectedSlots: i > 0 && i < 6
          ? ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30']
          : [],
      };
    });
  };

  const [schedules, setSchedules] = useState<DaySchedule[]>(generateInitialSchedules(currentWeekStart));
  
  // Fixed Start Times state
  const [fixedStartTimesSchedules, setFixedStartTimesSchedules] = useState<DaySchedule[]>(generateInitialSchedules(currentWeekStart));

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    // When week changes, regenerate dates
    setSchedules(prev => prev.map((s, i) => {
      const d = new Date(currentWeekStart);
      d.setDate(d.getDate() + i);
      return { ...s, date: d };
    }));
    
    setFixedStartTimesSchedules(prev => prev.map((s, i) => {
      const d = new Date(currentWeekStart);
      d.setDate(d.getDate() + i);
      return { ...s, date: d };
    }));
  }, [currentWeekStart]);

  const fetchInitialData = async () => {
    try {
      setIsLoading(true);
      const providersData = await apiClient.get<Provider[]>('/api/admin/providers');
      setProviders(providersData);
      if (providersData.length > 0) {
        handleSelectProvider(providersData[0]);
      }
    } catch (error) {
      toast.error('Failed to load initial data');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectProvider = (provider: Provider) => {
    setSelectedProvider(provider);
    
    // In a real app we'd map provider.weekly_schedule to the new state here
    // For now we just reset to defaults
    setSchedules(generateInitialSchedules(currentWeekStart));
    setFixedStartTimesSchedules(generateInitialSchedules(currentWeekStart));
  };

  const handleSave = async () => {
    if (!selectedProvider) return;

    try {
      setIsSaving(true);
      
      // Map back to API format (simplistic mapping for compatibility)
      const apiSchedule = schedules.map(day => {
        let start_time = '09:00';
        let end_time = '17:00';
        if (day.selectedSlots.length > 0) {
           const sorted = [...day.selectedSlots].sort();
           start_time = sorted[0];
           const lastSlot = sorted[sorted.length - 1];
           const [h, m] = lastSlot.split(':').map(Number);
           const d = new Date();
           d.setHours(h, m + 30);
           end_time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        }
        
        const oldDayOfWeek = day.date.getDay() === 0 ? 6 : day.date.getDay() - 1;
        
        return {
          day_of_week: oldDayOfWeek,
          is_working: !day.isDayOff && day.selectedSlots.length > 0,
          start_time,
          end_time,
          location_id: null
        };
      });

      await apiClient.put(`/api/admin/providers/${selectedProvider.id}`, {
        weekly_schedule: apiSchedule,
      });
      
      toast.success('Schedule saved');
    } catch (error) {
      toast.error('Failed to save schedule');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  const navigateWeek = (dir: 1 | -1) => {
    const nextWeek = new Date(currentWeekStart);
    nextWeek.setDate(nextWeek.getDate() + dir * 7);
    setCurrentWeekStart(nextWeek);
  };

  const toggleSlot = (dayIndex: number, slot: string, isFixed: boolean = false) => {
    const setState = isFixed ? setFixedStartTimesSchedules : setSchedules;
    
    setState(prev => {
      const next = [...prev];
      const day = { ...next[dayIndex] };
      if (day.selectedSlots.includes(slot)) {
        day.selectedSlots = day.selectedSlots.filter(s => s !== slot);
      } else {
        day.selectedSlots = [...day.selectedSlots, slot].sort();
      }
      next[dayIndex] = day;
      return next;
    });
  };

  const updateDay = (dayIndex: number, updates: Partial<DaySchedule>, isFixed: boolean = false) => {
    const setState = isFixed ? setFixedStartTimesSchedules : setSchedules;
    setState(prev => {
      const next = [...prev];
      next[dayIndex] = { ...next[dayIndex], ...updates };
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  
  const formattedWeekStart = currentWeekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] md:gap-6 p-4 md:p-6 font-sans">
      <Card className={`md:w-[35%] flex flex-col h-full rounded-xl transition-all duration-300 border-border/50 shadow-sm bg-card/50 backdrop-blur-sm ${selectedProvider ? 'hidden md:flex' : 'flex w-full'}`}>
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
                  onClick={() => handleSelectProvider(provider)}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all duration-200 hover:scale-[1.01] hover:shadow-md border min-h-[60px] ${
                    selectedProvider?.id === provider.id ? 'bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-primary font-medium' : 'text-muted-foreground bg-card hover:bg-accent/30 border-transparent hover:border-border/60'
                  }`}
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    {provider.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="truncate">
                    <div className={selectedProvider?.id === provider.id ? 'text-foreground' : ''}>
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

      <Card className={`md:w-[65%] flex flex-col h-full border-0 md:border md:border-border/50 shadow-none md:shadow-sm bg-card/50 backdrop-blur-sm transition-all duration-300 absolute inset-0 z-50 md:relative md:z-auto bg-background md:bg-transparent rounded-none md:rounded-xl ${selectedProvider ? 'flex w-full' : 'hidden md:flex'}`}>
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 md:p-6 pb-4 gap-4 border-b sticky top-0 bg-background/95 z-10 shrink-0">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => setSelectedProvider(null)}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <CardTitle className="text-xl flex items-center gap-2 font-heading">
                <Calendar className="h-5 w-5" />
                Weekly Schedule {selectedProvider ? `- ${selectedProvider.name}` : ''}
              </CardTitle>
              <CardDescription className="hidden md:block">Configure working days and specific hours</CardDescription>
            </div>
          </div>
          <Button onClick={handleSave} disabled={isSaving || !selectedProvider} className="min-h-[44px] w-full sm:w-auto">
            {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Schedule
          </Button>
        </CardHeader>
        
        <CardContent className="flex-1 overflow-auto p-0">
          {selectedProvider ? (
            <div className="p-6 space-y-8">
              
              <div className="flex flex-col gap-2 p-4 bg-muted/30 rounded-lg border">
                <Label htmlFor="maxDaysAhead" className="font-semibold text-base">Time in Advance</Label>
                <div className="flex items-center gap-4">
                  <Input 
                    id="maxDaysAhead"
                    type="number" 
                    value={maxDaysAhead} 
                    onChange={(e) => setMaxDaysAhead(parseInt(e.target.value) || 0)}
                    className="w-32"
                  />
                  <span className="text-sm text-muted-foreground">Maximum Days Ahead: Determines how far in advance clients can book</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold font-heading">Week of {formattedWeekStart}</h3>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="icon" onClick={() => navigateWeek(-1)} className="min-h-[44px] min-w-[44px]">
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => navigateWeek(1)} className="min-h-[44px] min-w-[44px]">
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* Mobile days navigation */}
              <div className="flex sm:hidden overflow-x-auto pb-2 gap-2 snap-x hide-scrollbar">
                {DAYS_OF_WEEK.map((day) => (
                  <Button
                    key={day}
                    variant={mobileSelectedDay === day ? "default" : "outline"}
                    className="snap-center whitespace-nowrap rounded-full min-h-[44px]"
                    size="sm"
                    onClick={() => setMobileSelectedDay(day)}
                  >
                    {day.substring(0, 3)}
                  </Button>
                ))}
              </div>

              <div className="space-y-6">
                {schedules.map((day, idx) => (
                  <div 
                    key={day.dayName}
                    className={`flex flex-col gap-4 p-4 rounded-lg border transition-colors ${day.isDayOff ? 'bg-muted/10 border-dashed' : 'bg-card'} ${
                      mobileSelectedDay !== day.dayName ? 'hidden sm:flex' : 'flex'
                    }`}
                  >
                    <div className="flex items-center justify-between border-b pb-3">
                      <div>
                        <h4 className="font-semibold">{day.dayName} <span className="text-muted-foreground font-normal text-sm">({day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})</span></h4>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2">
                          <Switch
                            id={`dayoff-${day.dayName}`}
                            checked={day.isDayOff}
                            onCheckedChange={(c) => updateDay(idx, { isDayOff: c })}
                          />
                          <Label htmlFor={`dayoff-${day.dayName}`} className="text-sm font-medium cursor-pointer">Day Off</Label>
                        </div>
                        
                        {!day.isDayOff && (
                          <div className="flex items-center gap-2">
                            <Switch
                              id={`recurring-${day.dayName}`}
                              checked={day.isRecurring}
                              onCheckedChange={(c) => updateDay(idx, { isRecurring: c })}
                            />
                            <Label htmlFor={`recurring-${day.dayName}`} className="text-sm font-medium cursor-pointer">Recurring</Label>
                          </div>
                        )}
                      </div>
                    </div>

                    {!day.isDayOff ? (
                      <div className="space-y-3">
                        {!day.isRecurring && (
                          <p className="text-xs text-muted-foreground italic">
                            This overrides only {day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, not future {day.dayName}s
                          </p>
                        )}
                        <div className="flex flex-wrap gap-2">
                          {TIME_SLOTS.map((slot) => {
                            const isSelected = day.selectedSlots.includes(slot);
                            return (
                              <Button
                                key={slot}
                                variant={isSelected ? "default" : "outline"}
                                size="sm"
                                className={`h-10 md:h-8 px-3 md:px-2 text-sm md:text-xs min-h-[44px] md:min-h-0 ${isSelected ? '' : 'text-muted-foreground'}`}
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
                        Day off — no bookings available
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              <div className="pt-6 mt-8 border-t">
                <h3 className="text-lg font-semibold mb-2">Fixed Start Times</h3>
                <p className="text-sm text-muted-foreground mb-6">Services with fixed start times will only be available at these slots</p>
                
                <div className="space-y-6">
                  {fixedStartTimesSchedules.map((day, idx) => (
                    <div 
                      key={`fixed-${day.dayName}`}
                      className={`flex flex-col gap-4 p-4 rounded-lg border transition-colors ${day.isDayOff ? 'bg-muted/10 border-dashed' : 'bg-card'} ${
                        mobileSelectedDay !== day.dayName ? 'hidden sm:flex' : 'flex'
                      }`}
                    >
                      <div className="flex items-center justify-between border-b pb-3">
                        <h4 className="font-semibold">{day.dayName} <span className="text-muted-foreground font-normal text-sm">({day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})</span></h4>
                        
                        <div className="flex items-center gap-2">
                          <Switch
                            id={`fixed-dayoff-${day.dayName}`}
                            checked={day.isDayOff}
                            onCheckedChange={(c) => updateDay(idx, { isDayOff: c }, true)}
                          />
                          <Label htmlFor={`fixed-dayoff-${day.dayName}`} className="text-sm font-medium cursor-pointer">Day Off</Label>
                        </div>
                      </div>

                      {!day.isDayOff ? (
                        <div className="flex flex-wrap gap-2">
                          {TIME_SLOTS.map((slot) => {
                            const isSelected = day.selectedSlots.includes(slot);
                            return (
                              <Button
                                key={slot}
                                variant={isSelected ? "default" : "outline"}
                                size="sm"
                                className={`h-10 md:h-8 px-3 md:px-2 text-sm md:text-xs min-h-[44px] md:min-h-0 ${isSelected ? '' : 'text-muted-foreground'}`}
                                onClick={() => toggleSlot(idx, slot, true)}
                              >
                                {formatSlot(slot)}
                              </Button>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="py-4 text-center text-muted-foreground text-sm italic">
                          No fixed start times on this day off
                        </div>
                      )}
                    </div>
                  ))}
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
