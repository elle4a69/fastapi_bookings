import { useState, useEffect, useMemo, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { CalendarOff, Clock, Trash2, Plus, Loader2, User, RefreshCw } from 'lucide-react';
import { useTenantModules } from '@/context/tenant-modules-context';

interface Location {
  id: string | number;
  name: string;
}

interface Provider {
  id: string | number;
  name: string;
}

interface SpecialDayRecord {
  id: number;
  provider_id: number | null;
  location_id: number | null;
  date: string; // YYYY-MM-DD
  is_working: boolean;
  start_time?: string | null;
  end_time?: string | null;
  reason?: string | null;
  created_at?: string;
}

interface BlockedTime {
  id: string | number;
  provider_id: string | number | null;
  location_id: string | number | null;
  start_time: string; // ISO datetime
  end_time: string;   // ISO datetime
  reason: string;
  active?: boolean;
  is_active?: boolean;
  provider_name?: string;
  location_name?: string;
}

interface ReservedTime {
  id: string | number;
  provider_name: string;
  service_name: string;
  client_name: string;
  start_time: string;
  end_time: string;
  status: string;
  expires_at: string;
  note: string;
}

interface UnifiedException {
  uniqueKey: string;
  id: string | number;
  sourceType: 'special_day' | 'blocked_time';
  providerId: string | number | null;
  providerName: string;
  locationId: string | number | null;
  locationName: string;
  dateStr: string;
  dateDisplay: string;
  timeDisplay: string;
  isDayOff: boolean;
  isWorking: boolean;
  reason: string;
  isActive?: boolean;
}

function parseDateSafe(dateStr: string): Date | null {
  if (!dateStr) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, d] = dateStr.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? null : d;
}

function formatDateSafe(dateStr: string): string {
  const d = parseDateSafe(dateStr);
  if (!d) return dateStr || '-';
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(d);
}

function formatTimeSafe(isoOrTime: string): string {
  if (!isoOrTime) return '';
  if (/^\d{1,2}:\d{2}$/.test(isoOrTime)) {
    const [h, m] = isoOrTime.split(':').map(Number);
    const period = h >= 12 ? 'PM' : 'AM';
    const hour = h > 12 ? h - 12 : h === 0 ? 12 : h;
    return `${hour}:${String(m).padStart(2, '0')} ${period}`;
  }
  try {
    const d = new Date(isoOrTime);
    if (!isNaN(d.getTime())) {
      return new Intl.DateTimeFormat('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      }).format(d);
    }
  } catch {}
  return isoOrTime;
}

function getProviderName(providerId: string | number | null | undefined, providersList: Provider[]): string {
  if (!providerId) return 'All Staff';
  const norm = String(providerId).replace(/^prov-/, '');
  const p = providersList.find((prov) => String(prov.id).replace(/^prov-/, '') === norm);
  return p ? p.name : `Staff #${norm}`;
}

function getLocationName(locationId: string | number | null | undefined, locationsList: Location[]): string {
  if (!locationId) return 'All Locations';
  const norm = String(locationId).replace(/^loc-/, '');
  const l = locationsList.find((loc) => String(loc.id).replace(/^loc-/, '') === norm);
  return l ? l.name : `Location #${norm}`;
}

export default function ExceptionsPage() {
  const { multipleProvidersEnabled, locationsEnabled } = useTenantModules();
  const [specialDays, setSpecialDays] = useState<SpecialDayRecord[]>([]);
  const [blockedTimes, setBlockedTimes] = useState<BlockedTime[]>([]);
  const [reservedTimes, setReservedTimes] = useState<ReservedTime[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Filters
  const [filterProvider, setFilterProvider] = useState<string>('all');
  const [filterType, setFilterType] = useState<'all' | 'day_off' | 'blocked_time'>('all');

  // New Exception Dialog Form State
  const [exceptionType, setExceptionType] = useState<'day_off' | 'blocked_time'>('day_off');
  const [newBlockProvider, setNewBlockProvider] = useState<string>('');
  const [newBlockLocation, setNewBlockLocation] = useState<string>('none');
  const [newBlockDate, setNewBlockDate] = useState<string>('');
  const [newBlockStart, setNewBlockStart] = useState<string>('09:00');
  const [newBlockEnd, setNewBlockEnd] = useState<string>('17:00');
  const [newBlockReason, setNewBlockReason] = useState<string>('');

  const fetchData = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setIsLoading(true);
      else setIsRefreshing(true);

      const [specialDaysRes, blockedData, reservedData, providersRes, locationsRes] = await Promise.all([
        apiClient.get<any>('/api/admin/schedule/special-days').catch(() => []),
        apiClient.get<BlockedTime[]>('/api/admin/schedule/blocked-times').catch(() => []),
        apiClient.get<ReservedTime[]>('/api/admin/schedule/reserved-times').catch(() => []),
        apiClient.get<any>('/api/admin/providers').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/locations').catch(() => ({ data: [] })),
      ]);

      const specialDaysList: SpecialDayRecord[] = Array.isArray(specialDaysRes)
        ? specialDaysRes
        : (Array.isArray(specialDaysRes?.data) ? specialDaysRes.data : []);

      const providersList = Array.isArray(providersRes) ? providersRes : (providersRes?.data || []);
      const locationsList = Array.isArray(locationsRes) ? locationsRes : (locationsRes?.data || []);

      setSpecialDays(specialDaysList);
      setBlockedTimes(Array.isArray(blockedData) ? blockedData : []);
      setReservedTimes(Array.isArray(reservedData) ? reservedData : []);
      setProviders(providersList);
      setLocations(locationsList);

      if (providersList.length > 0 && !newBlockProvider) {
        setNewBlockProvider(String(providersList[0].id));
      }
    } catch (error) {
      toast.error('Failed to load schedule exceptions');
      console.error(error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [newBlockProvider]);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Synchronize across pages and windows
  useEffect(() => {
    const handleSync = () => {
      fetchData(true);
    };

    window.addEventListener('schedule-exceptions-updated', handleSync);
    window.addEventListener('focus', handleSync);

    return () => {
      window.removeEventListener('schedule-exceptions-updated', handleSync);
      window.removeEventListener('focus', handleSync);
    };
  }, [fetchData]);

  // Consolidated Single-Source-of-Truth Exceptions List
  const unifiedExceptions: UnifiedException[] = useMemo(() => {
    const list: UnifiedException[] = [];

    // 1. Map Special Days (Time-off & overrides created on Schedule Workdays page)
    specialDays.forEach((sd) => {
      const isDayOff = !sd.is_working;
      let cleanReason = sd.reason || '';
      if (cleanReason.startsWith('SLOTS:')) {
        cleanReason = 'Custom working hours';
      } else if (!cleanReason) {
        cleanReason = isDayOff ? 'Scheduled Day Off' : 'Custom Hours Override';
      }

      let timeDisplay = 'All Day (Time Off)';
      if (sd.is_working) {
        if (sd.start_time && sd.end_time) {
          timeDisplay = `${formatTimeSafe(sd.start_time)} - ${formatTimeSafe(sd.end_time)}`;
        } else {
          timeDisplay = 'Custom Hours';
        }
      }

      list.push({
        uniqueKey: `sd-${sd.id}`,
        id: sd.id,
        sourceType: 'special_day',
        providerId: sd.provider_id,
        providerName: getProviderName(sd.provider_id, providers),
        locationId: sd.location_id,
        locationName: getLocationName(sd.location_id, locations),
        dateStr: sd.date,
        dateDisplay: formatDateSafe(sd.date),
        timeDisplay,
        isDayOff,
        isWorking: sd.is_working,
        reason: cleanReason,
      });
    });

    // 2. Map Blocked Times
    blockedTimes.forEach((bt) => {
      const rawDateStr = bt.start_time ? bt.start_time.split('T')[0] : '';
      const timeDisplay = `${formatTimeSafe(bt.start_time)} - ${formatTimeSafe(bt.end_time)}`;

      list.push({
        uniqueKey: `bt-${bt.id}`,
        id: bt.id,
        sourceType: 'blocked_time',
        providerId: bt.provider_id,
        providerName: bt.provider_name || getProviderName(bt.provider_id, providers),
        locationId: bt.location_id,
        locationName: bt.location_name || getLocationName(bt.location_id, locations),
        dateStr: rawDateStr,
        dateDisplay: formatDateSafe(rawDateStr),
        timeDisplay,
        isDayOff: false,
        isWorking: false,
        reason: bt.reason || 'Blocked Time',
        isActive: bt.active ?? bt.is_active ?? true,
      });
    });

    // Sort chronologically ascending
    return list.sort((a, b) => a.dateStr.localeCompare(b.dateStr));
  }, [specialDays, blockedTimes, providers, locations]);

  // Filtered List
  const filteredExceptions = useMemo(() => {
    return unifiedExceptions.filter((item) => {
      if (filterProvider !== 'all') {
        const normFilter = String(filterProvider).replace(/^prov-/, '');
        const normItem = String(item.providerId || '').replace(/^prov-/, '');
        if (normFilter !== normItem) return false;
      }
      if (filterType === 'day_off') {
        if (!item.isDayOff) return false;
      } else if (filterType === 'blocked_time') {
        if (item.sourceType !== 'blocked_time') return false;
      }
      return true;
    });
  }, [unifiedExceptions, filterProvider, filterType]);

  // Add Exception Handler
  const handleAddException = async () => {
    const effectiveProvider = (multipleProvidersEnabled ? newBlockProvider : (newBlockProvider || providers[0]?.id)) || '';
    const effectiveLocation = locationsEnabled ? (newBlockLocation === 'none' ? null : newBlockLocation) : null;

    if (!effectiveProvider || !newBlockDate) {
      toast.error('Please specify a staff member and date');
      return;
    }

    try {
      setIsSubmitting(true);

      if (exceptionType === 'day_off') {
        // Create Full Day Off override (ProviderSpecialDay where is_working = false)
        await apiClient.post(`/api/admin/providers/${effectiveProvider}/special-days`, {
          date: newBlockDate,
          is_working: false,
          active_slots: [],
          reason: newBlockReason || 'Scheduled Day Off',
        });
        toast.success('Day off exception created');
      } else {
        // Create Blocked Time Window
        if (!newBlockStart || !newBlockEnd) {
          toast.error('Please specify start and end times');
          return;
        }
        const startDateTime = new Date(`${newBlockDate}T${newBlockStart}`).toISOString();
        const endDateTime = new Date(`${newBlockDate}T${newBlockEnd}`).toISOString();

        await apiClient.post<BlockedTime>('/api/admin/schedule/blocked-times', {
          provider_id: effectiveProvider,
          location_id: effectiveLocation,
          start_time: startDateTime,
          end_time: endDateTime,
          reason: newBlockReason || 'Staff block',
          is_active: true,
        });
        toast.success('Blocked time added successfully');
      }

      window.dispatchEvent(new CustomEvent('schedule-exceptions-updated'));
      setIsDialogOpen(false);
      setNewBlockReason('');
      setNewBlockDate('');
      fetchData(true);
    } catch (error) {
      toast.error('Failed to create exception');
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Delete Exception Handler (Unified delete that removes the underlying record)
  const handleDeleteException = async (item: UnifiedException) => {
    try {
      if (item.sourceType === 'special_day') {
        // Delete underlying ProviderSpecialDay
        await apiClient.delete(`/api/admin/schedule/special-days/${item.id}`);
        setSpecialDays((prev) => prev.filter((sd) => sd.id !== item.id));
        window.dispatchEvent(new CustomEvent('schedule-exceptions-updated'));
        toast.success('Time-off exception deleted. Normal schedule restored.');
      } else {
        // Delete underlying BlockedTime
        await apiClient.delete(`/api/admin/schedule/blocked-times/${item.id}`);
        setBlockedTimes((prev) => prev.filter((bt) => bt.id !== item.id));
        window.dispatchEvent(new CustomEvent('schedule-exceptions-updated'));
        toast.success('Blocked time removed.');
      }
    } catch (error) {
      toast.error('Failed to remove exception');
      console.error(error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight font-heading">Schedule Exceptions</h1>
          <p className="text-muted-foreground text-sm">
            Consolidated, real-time list of all time-off entries and blocked times synchronized with the Schedule
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchData(true)}
            disabled={isRefreshing}
            className="h-9 gap-1.5"
            title="Refresh exceptions"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>

          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-9 gap-1.5">
                <Plus className="h-4 w-4" />
                Add Exception
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[480px]">
              <DialogHeader>
                <DialogTitle>Add Schedule Exception</DialogTitle>
                <DialogDescription>
                  Create a time-off exception or blocked time window. This directly synchronizes with practitioner schedules.
                </DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 py-4">
                {/* Exception Mode Selector */}
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label className="text-right font-medium">Type</Label>
                  <div className="col-span-3 flex items-center gap-2 bg-muted/50 p-1 rounded-lg border text-xs">
                    <button
                      type="button"
                      onClick={() => setExceptionType('day_off')}
                      className={`flex-1 py-1.5 rounded-md font-medium transition-all ${
                        exceptionType === 'day_off'
                          ? 'bg-background shadow-xs text-foreground font-semibold'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Full Day Off
                    </button>
                    <button
                      type="button"
                      onClick={() => setExceptionType('blocked_time')}
                      className={`flex-1 py-1.5 rounded-md font-medium transition-all ${
                        exceptionType === 'blocked_time'
                          ? 'bg-background shadow-xs text-foreground font-semibold'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Time Window Block
                    </button>
                  </div>
                </div>

                {/* Staff Member Selector */}
                {multipleProvidersEnabled && (
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="provider" className="text-right font-medium">Staff</Label>
                    <Select value={newBlockProvider} onValueChange={setNewBlockProvider}>
                      <SelectTrigger id="provider" aria-label="Select staff member" className="col-span-3">
                        <SelectValue placeholder="Select staff member" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* Location (for blocked time only) */}
                {locationsEnabled && exceptionType === 'blocked_time' && (
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="location" className="text-right font-medium">Location</Label>
                    <Select value={newBlockLocation} onValueChange={setNewBlockLocation}>
                      <SelectTrigger id="location" aria-label="Select location" className="col-span-3">
                        <SelectValue placeholder="All locations (Optional)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">All locations</SelectItem>
                        {locations.map((l) => (
                          <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* Date */}
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="date" className="text-right font-medium">Date</Label>
                  <Input 
                    id="date" 
                    type="date" 
                    className="col-span-3"
                    value={newBlockDate}
                    onChange={(e) => setNewBlockDate(e.target.value)}
                  />
                </div>

                {/* Times (for blocked time only) */}
                {exceptionType === 'blocked_time' && (
                  <>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="start" className="text-right font-medium">Start Time</Label>
                      <Input 
                        id="start" 
                        type="time" 
                        className="col-span-3"
                        value={newBlockStart}
                        onChange={(e) => setNewBlockStart(e.target.value)}
                      />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="end" className="text-right font-medium">End Time</Label>
                      <Input 
                        id="end" 
                        type="time" 
                        className="col-span-3"
                        value={newBlockEnd}
                        onChange={(e) => setNewBlockEnd(e.target.value)}
                      />
                    </div>
                  </>
                )}

                {/* Reason */}
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="reason" className="text-right font-medium">Reason</Label>
                  <Input 
                    id="reason" 
                    placeholder={exceptionType === 'day_off' ? 'e.g. Annual leave, Personal day' : 'e.g. Doctor appointment, Meeting'} 
                    className="col-span-3"
                    value={newBlockReason}
                    onChange={(e) => setNewBlockReason(e.target.value)}
                  />
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleAddException} disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Exception
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Tabs defaultValue="consolidated" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="consolidated" className="flex items-center gap-2">
            <CalendarOff className="h-4 w-4" />
            Time-Off & Exceptions ({unifiedExceptions.length})
          </TabsTrigger>
          <TabsTrigger value="reserved" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Reserved Holds ({reservedTimes.length})
          </TabsTrigger>
        </TabsList>

        {/* CONSOLIDATED EXCEPTIONS TAB */}
        <TabsContent value="consolidated">
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 gap-4">
              <div>
                <CardTitle className="text-lg">All Schedule Exceptions & Time Off</CardTitle>
                <CardDescription>
                  Unified records from the Schedule page and blocked time entries. Deleting an entry immediately restores normal working hours.
                </CardDescription>
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-2">
                {multipleProvidersEnabled && (
                  <Select value={filterProvider} onValueChange={setFilterProvider}>
                    <SelectTrigger className="w-[160px] h-8 text-xs" aria-label="Filter staff">
                      <SelectValue placeholder="All Staff" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Staff</SelectItem>
                      {providers.map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                <Select value={filterType} onValueChange={(val: any) => setFilterType(val)}>
                  <SelectTrigger className="w-[140px] h-8 text-xs" aria-label="Filter type">
                    <SelectValue placeholder="All Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="day_off">Day Off Only</SelectItem>
                    <SelectItem value="blocked_time">Time Blocks</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>

            <CardContent>
              {filteredExceptions.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground space-y-2">
                  <CalendarOff className="h-8 w-8 mx-auto text-muted-foreground/50" />
                  <p className="font-medium text-base">No exceptions found</p>
                  <p className="text-xs">
                    Days off toggled on the Schedule page or added here will appear in this unified list.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      {multipleProvidersEnabled && <TableHead>Staff</TableHead>}
                      <TableHead>Type</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Hours / Scope</TableHead>
                      {locationsEnabled && <TableHead>Location</TableHead>}
                      <TableHead>Reason</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredExceptions.map((item) => (
                      <TableRow key={item.uniqueKey}>
                        {multipleProvidersEnabled && (
                          <TableCell className="font-medium">
                            <span className="flex items-center gap-1.5">
                              <User className="h-3.5 w-3.5 text-muted-foreground" />
                              {item.providerName}
                            </span>
                          </TableCell>
                        )}
                        <TableCell>
                          {item.isDayOff ? (
                            <Badge variant="destructive" className="bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700 font-semibold">
                              Full Day Off
                            </Badge>
                          ) : item.sourceType === 'special_day' ? (
                            <Badge variant="secondary" className="bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-700">
                              Special Hours
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-300 dark:border-purple-700">
                              Time Block
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{item.dateDisplay}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{item.timeDisplay}</TableCell>
                        {locationsEnabled && (
                          <TableCell className="text-muted-foreground text-xs">{item.locationName}</TableCell>
                        )}
                        <TableCell className="max-w-[220px] truncate" title={item.reason}>
                          {item.reason}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            onClick={() => handleDeleteException(item)}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            title="Delete exception and restore normal schedule"
                            aria-label="Delete exception"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* RESERVED HOLDS TAB */}
        <TabsContent value="reserved">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Reserved Booking Holds</CardTitle>
              <CardDescription>Temporary holds placed during customer booking workflows</CardDescription>
            </CardHeader>
            <CardContent>
              {reservedTimes.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  No active reserved holds found.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      {multipleProvidersEnabled && <TableHead>Staff</TableHead>}
                      <TableHead>Service</TableHead>
                      <TableHead>Client</TableHead>
                      <TableHead>Start</TableHead>
                      <TableHead>End</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Note</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reservedTimes.map((res) => (
                      <TableRow key={res.id}>
                        {multipleProvidersEnabled && (
                          <TableCell className="font-medium">{res.provider_name}</TableCell>
                        )}
                        <TableCell>{res.service_name}</TableCell>
                        <TableCell>{res.client_name}</TableCell>
                        <TableCell>{formatDateSafe(res.start_time)} {formatTimeSafe(res.start_time)}</TableCell>
                        <TableCell>{formatDateSafe(res.end_time)} {formatTimeSafe(res.end_time)}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="bg-amber-500/10 text-amber-800 dark:text-amber-300 border border-amber-500/20 font-semibold">
                            {res.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-red-400">{formatTimeSafe(res.expires_at)}</TableCell>
                        <TableCell className="max-w-[200px] truncate" title={res.note}>
                          {res.note || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
