import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { CalendarOff, Clock, Trash2, Plus, Loader2 } from 'lucide-react';

interface Location {
  id: string;
  name: string;
}

interface Provider {
  id: string;
  name: string;
}

interface BlockedTime {
  id: string;
  provider_id: string;
  location_id: string | null;
  start_time: string; // ISO datetime
  end_time: string;   // ISO datetime
  reason: string;
  is_active: boolean;
  provider_name?: string;
  location_name?: string;
}

interface ReservedTime {
  id: string;
  provider_name: string;
  service_name: string;
  client_name: string;
  start_time: string;
  end_time: string;
  status: string;
  expires_at: string;
  note: string;
}

export default function ExceptionsPage() {
  const [blockedTimes, setBlockedTimes] = useState<BlockedTime[]>([]);
  const [reservedTimes, setReservedTimes] = useState<ReservedTime[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New Blocked Time Form State
  const [newBlockProvider, setNewBlockProvider] = useState<string>('');
  const [newBlockLocation, setNewBlockLocation] = useState<string>('none');
  const [newBlockDate, setNewBlockDate] = useState<string>('');
  const [newBlockStart, setNewBlockStart] = useState<string>('');
  const [newBlockEnd, setNewBlockEnd] = useState<string>('');
  const [newBlockReason, setNewBlockReason] = useState<string>('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [blockedData, reservedData, providersData, locationsData] = await Promise.all([
        apiClient.get<BlockedTime[]>('/api/admin/schedule/blocked-times').catch(() => []),
        apiClient.get<ReservedTime[]>('/api/admin/schedule/reserved-times').catch(() => []),
        apiClient.get<Provider[]>('/api/admin/providers').catch(() => []),
        apiClient.get<Location[]>('/api/admin/locations').catch(() => []),
      ]);

      setBlockedTimes(blockedData);
      setReservedTimes(reservedData);
      setProviders(providersData);
      setLocations(locationsData);
    } catch (error) {
      toast.error('Failed to load schedule exceptions');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddBlockedTime = async () => {
    if (!newBlockProvider || !newBlockDate || !newBlockStart || !newBlockEnd) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      setIsSubmitting(true);
      
      const startDateTime = new Date(`${newBlockDate}T${newBlockStart}`).toISOString();
      const endDateTime = new Date(`${newBlockDate}T${newBlockEnd}`).toISOString();

      const newBlock = await apiClient.post<BlockedTime>('/api/admin/schedule/blocked-times', {
        provider_id: newBlockProvider,
        location_id: newBlockLocation === 'none' ? null : newBlockLocation,
        start_time: startDateTime,
        end_time: endDateTime,
        reason: newBlockReason,
        is_active: true
      });

      setBlockedTimes([...blockedTimes, newBlock]);
      toast.success('Blocked time added successfully');
      setIsDialogOpen(false);
      
      // Reset form
      setNewBlockProvider('');
      setNewBlockLocation('none');
      setNewBlockDate('');
      setNewBlockStart('');
      setNewBlockEnd('');
      setNewBlockReason('');
      
    } catch (error) {
      toast.error('Failed to add blocked time');
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteBlockedTime = async (id: string) => {
    try {
      await apiClient.delete(`/api/admin/schedule/blocked-times/${id}`);
      setBlockedTimes(blockedTimes.filter(b => b.id !== id));
      toast.success('Blocked time removed');
    } catch (error) {
      toast.error('Failed to remove blocked time');
      console.error(error);
    }
  };

  const toggleBlockedTimeActive = async (id: string, currentStatus: boolean) => {
    try {
      await apiClient.put(`/api/admin/schedule/blocked-times/${id}`, {
        is_active: !currentStatus
      });
      setBlockedTimes(blockedTimes.map(b => 
        b.id === id ? { ...b, is_active: !currentStatus } : b
      ));
      toast.success('Status updated');
    } catch (error) {
      toast.error('Failed to update status');
      console.error(error);
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return new Intl.DateTimeFormat('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit'
      }).format(date);
    } catch {
      return isoString;
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
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Schedule Exceptions</h1>
          <p className="text-muted-foreground">Manage blocked times and view reserved holds</p>
        </div>
      </div>

      <Tabs defaultValue="blocked" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="blocked" className="flex items-center gap-2">
            <CalendarOff className="h-4 w-4" />
            Blocked Times
          </TabsTrigger>
          <TabsTrigger value="reserved" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Reserved Times
          </TabsTrigger>
        </TabsList>

        {/* BLOCKED TIMES TAB */}
        <TabsContent value="blocked">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Blocked Times</CardTitle>
                <CardDescription>Staff exceptions, meetings, or time off</CardDescription>
              </div>
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Blocked Time
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Blocked Time</DialogTitle>
                    <DialogDescription>
                      Create a schedule exception to prevent bookings during this time.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="provider" className="text-right">Staff</Label>
                      <Select value={newBlockProvider} onValueChange={setNewBlockProvider}>
                        <SelectTrigger className="col-span-3">
                          <SelectValue placeholder="Select staff member" />
                        </SelectTrigger>
                        <SelectContent>
                          {providers.map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="location" className="text-right">Location</Label>
                      <Select value={newBlockLocation} onValueChange={setNewBlockLocation}>
                        <SelectTrigger className="col-span-3">
                          <SelectValue placeholder="All locations (Optional)" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">All locations</SelectItem>
                          {locations.map(l => (
                            <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="date" className="text-right">Date</Label>
                      <Input 
                        id="date" 
                        type="date" 
                        className="col-span-3"
                        value={newBlockDate}
                        onChange={(e) => setNewBlockDate(e.target.value)}
                      />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="start" className="text-right">Start Time</Label>
                      <Input 
                        id="start" 
                        type="time" 
                        className="col-span-3"
                        value={newBlockStart}
                        onChange={(e) => setNewBlockStart(e.target.value)}
                      />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="end" className="text-right">End Time</Label>
                      <Input 
                        id="end" 
                        type="time" 
                        className="col-span-3"
                        value={newBlockEnd}
                        onChange={(e) => setNewBlockEnd(e.target.value)}
                      />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                      <Label htmlFor="reason" className="text-right">Reason</Label>
                      <Input 
                        id="reason" 
                        placeholder="e.g. Doctor appointment" 
                        className="col-span-3"
                        value={newBlockReason}
                        onChange={(e) => setNewBlockReason(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleAddBlockedTime} disabled={isSubmitting}>
                      {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Save
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {blockedTimes.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No blocked times found.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>Location</TableHead>
                      <TableHead>Start</TableHead>
                      <TableHead>End</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Active</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blockedTimes.map((block) => {
                      const provider = providers.find(p => p.id === block.provider_id);
                      const location = locations.find(l => l.id === block.location_id);
                      
                      return (
                        <TableRow key={block.id}>
                          <TableCell className="font-medium">{block.provider_name || provider?.name || 'Unknown'}</TableCell>
                          <TableCell>{block.location_name || location?.name || 'All Locations'}</TableCell>
                          <TableCell>{formatDate(block.start_time)}</TableCell>
                          <TableCell>{formatDate(block.end_time)}</TableCell>
                          <TableCell>{block.reason || '-'}</TableCell>
                          <TableCell>
                            <Switch 
                              checked={block.is_active} 
                              onCheckedChange={() => toggleBlockedTimeActive(block.id, block.is_active)} 
                            />
                          </TableCell>
                          <TableCell className="text-right">
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              onClick={() => handleDeleteBlockedTime(block.id)}
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* RESERVED TIMES TAB */}
        <TabsContent value="reserved">
          <Card>
            <CardHeader>
              <CardTitle>Reserved Times</CardTitle>
              <CardDescription>Temporary holds placed during the booking process</CardDescription>
            </CardHeader>
            <CardContent>
              {reservedTimes.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No active reserved times found.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
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
                        <TableCell className="font-medium">{res.provider_name}</TableCell>
                        <TableCell>{res.service_name}</TableCell>
                        <TableCell>{res.client_name}</TableCell>
                        <TableCell>{formatDate(res.start_time)}</TableCell>
                        <TableCell>{formatDate(res.end_time)}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-500">
                            {res.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-red-400">{formatDate(res.expires_at)}</TableCell>
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
