import { useState, useEffect } from "react";
import { 
  Calendar as CalendarIcon, 
  List, 
  Download, 
  MoreHorizontal, 
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  Ban,
  Phone,
  Mail,
  MapPin,
  Plus
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

interface BookingItem {
  id: string;
  date: string;
  time: string;
  service: string;
  serviceId: number;
  provider: string;
  providerId: number;
  client: string;
  clientId: number;
  clientEmail: string;
  clientPhone: string;
  duration: string;
  status: string;
  price: string;
  location: string;
  notes: string;
}

const getStatusBadge = (status: string) => {
  const s = (status || "").toLowerCase();
  switch (s) {
    case "confirmed":
      return <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Confirmed</Badge>;
    case "pending":
      return <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
    case "completed":
      return <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Completed</Badge>;
    case "cancelled":
      return <Badge className="bg-red-500/10 text-red-600 border-red-500/20"><XCircle className="w-3 h-3 mr-1" /> Cancelled</Badge>;
    case "noshow":
      return <Badge className="bg-zinc-500/10 text-zinc-600 border-zinc-500/20"><Ban className="w-3 h-3 mr-1" /> No Show</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
};

export default function BookingsAdminPage() {
  const [bookings, setBookings] = useState<BookingItem[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedBooking, setSelectedBooking] = useState<BookingItem | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [bRes, sRes, pRes] = await Promise.all([
        apiClient.get<any>("/api/bookings?page_size=200").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => [])
      ]);

      const rawBookings = Array.isArray(bRes) ? bRes : (bRes?.data ?? bRes?.items ?? []);
      const rawServices = Array.isArray(sRes) ? sRes : (sRes?.data ?? sRes?.items ?? []);
      const rawProviders = Array.isArray(pRes) ? pRes : (pRes?.data ?? pRes?.items ?? []);

      setServices(rawServices);
      setProviders(rawProviders);

      const mapped: BookingItem[] = rawBookings.map((b: any) => {
        const start = new Date(b.start_time);
        const end = new Date(b.end_time);
        const durMinutes = Math.max(15, Math.round((end.getTime() - start.getTime()) / 60000));
        
        const h = start.getHours() % 12 || 12;
        const min = String(start.getMinutes()).padStart(2, "0");
        const timeStr = `${h}:${min} ${start.getHours() < 12 ? "AM" : "PM"}`;

        return {
          id: String(b.id),
          date: start.toISOString().split("T")[0],
          time: timeStr,
          service: b.service?.name || "Service",
          serviceId: b.service_id,
          provider: b.provider?.name || "Unassigned",
          providerId: b.provider_id,
          client: b.client?.name || "Client",
          clientId: b.client_id,
          clientEmail: b.client?.email || "",
          clientPhone: b.client?.phone || "",
          duration: `${durMinutes} min`,
          status: (b.status || "confirmed").toLowerCase(),
          price: b.service?.price ? `$${Number(b.service.price).toFixed(2)}` : "$0.00",
          location: b.location?.name || "Main Branch",
          notes: b.notes || ""
        };
      });

      setBookings(mapped);
    } catch (err: any) {
      toast.error(err.message || "Failed to load bookings.");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (id: string, newStatus: string) => {
    try {
      await apiClient.put(`/api/bookings/${id}`, { status: newStatus.toUpperCase() });
      toast.success(`Booking marked as ${newStatus}`);
      setDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update booking status.");
    }
  };

  const filteredBookings = bookings.filter(b => {
    if (statusFilter !== "all" && b.status !== statusFilter) return false;
    if (searchQuery.trim() !== "") {
      const q = searchQuery.toLowerCase();
      const matchClient = b.client.toLowerCase().includes(q);
      const matchService = b.service.toLowerCase().includes(q);
      const matchProvider = b.provider.toLowerCase().includes(q);
      const matchId = b.id.toLowerCase().includes(q);
      return matchClient || matchService || matchProvider || matchId;
    }
    return true;
  });

  return (
    <div className="flex-1 space-y-4 p-4 md:p-6">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Manage Bookings</h1>
          <p className="text-muted-foreground text-xs mt-1">View, filter, and manage real appointments across all providers.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => window.location.href = '/admin/calendar'}>
            <CalendarIcon className="w-4 h-4 mr-2" /> Calendar View
          </Button>
        </div>
      </div>

      <Card className="border shadow-xs">
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <div className="flex flex-1 flex-wrap items-center gap-2">
              <div className="relative w-72">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input 
                  placeholder="Search client, provider, or ID..." 
                  className="pl-9 h-9 text-xs" 
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px] h-9 text-xs">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="confirmed">Confirmed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
                  <SelectItem value="noshow">No Show</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button variant="outline" size="sm" className="h-9 text-xs px-3" onClick={() => toast.success("Exporting CSV...")}>
              <Download className="mr-1.5 h-4 w-4" />
              Export CSV
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="rounded-xl border bg-card overflow-hidden shadow-xs">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead>Date / Time</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Price</TableHead>
              <TableHead className="w-[60px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground text-sm">
                  Loading bookings...
                </TableCell>
              </TableRow>
            ) : filteredBookings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground text-sm">
                  No bookings found matching your search.
                </TableCell>
              </TableRow>
            ) : (
              filteredBookings.map((b) => (
                <TableRow 
                  key={b.id} 
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => { setSelectedBooking(b); setDialogOpen(true); }}
                >
                  <TableCell>
                    <div className="font-semibold text-sm">{b.date}</div>
                    <div className="text-xs text-muted-foreground">{b.time}</div>
                  </TableCell>
                  <TableCell>
                    <div className="font-semibold text-sm">{b.client}</div>
                    <div className="text-xs text-muted-foreground">ID #{b.id}</div>
                  </TableCell>
                  <TableCell className="font-medium text-sm">{b.service}</TableCell>
                  <TableCell className="text-sm">{b.provider}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{b.duration}</TableCell>
                  <TableCell>{getStatusBadge(b.status)}</TableCell>
                  <TableCell className="text-right font-bold text-sm">{b.price}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => { setSelectedBooking(b); setDialogOpen(true); }}>View Details</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'confirmed')}>Mark Confirmed</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'completed')}>Mark Completed</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'noshow')}>Mark No-show</DropdownMenuItem>
                        <DropdownMenuItem className="text-red-600" onClick={() => handleUpdateStatus(b.id, 'cancelled')}>Cancel Booking</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* ── Booking Details Centered Dialog ─────────────────── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden rounded-xl">
          <DialogHeader className="p-6 pb-4 border-b bg-card">
            <div className="flex items-center justify-between pr-6">
              <div>
                <DialogTitle className="text-xl font-bold flex items-center gap-3">
                  Booking #{selectedBooking?.id}
                  {selectedBooking && getStatusBadge(selectedBooking.status)}
                </DialogTitle>
                <DialogDescription className="mt-1">
                  Scheduled for {selectedBooking?.date} at {selectedBooking?.time}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {selectedBooking && (
            <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
              <Tabs defaultValue="details" className="w-full">
                <TabsList className="grid grid-cols-3 w-full mb-4">
                  <TabsTrigger value="details">Appointment</TabsTrigger>
                  <TabsTrigger value="client">Client Info</TabsTrigger>
                  <TabsTrigger value="payment">Payment & Notes</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="space-y-4 pt-1">
                  <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border bg-card/60">
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Service</span>
                      <span className="font-semibold text-base mt-0.5 block">{selectedBooking.service}</span>
                      <span className="text-xs text-muted-foreground mt-1 block">{selectedBooking.duration}</span>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Provider</span>
                      <span className="font-semibold text-base mt-0.5 block">{selectedBooking.provider}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border bg-card/60">
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Location</span>
                      <span className="font-semibold text-sm mt-0.5 flex items-center gap-1.5">
                        <MapPin className="w-4 h-4 text-primary" /> {selectedBooking.location}
                      </span>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Amount</span>
                      <span className="font-semibold text-sm mt-0.5 text-emerald-600 block">{selectedBooking.price}</span>
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
                    {selectedBooking.clientEmail && (
                      <div className="flex items-center gap-2 text-sm">
                        <Mail className="w-4 h-4 text-muted-foreground" />
                        <a href={`mailto:${selectedBooking.clientEmail}`} className="text-primary hover:underline">{selectedBooking.clientEmail}</a>
                      </div>
                    )}
                    {selectedBooking.clientPhone && (
                      <div className="flex items-center gap-2 text-sm">
                        <Phone className="w-4 h-4 text-muted-foreground" />
                        <a href={`tel:${selectedBooking.clientPhone}`} className="text-primary hover:underline">{selectedBooking.clientPhone}</a>
                      </div>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="payment" className="space-y-4 pt-1">
                  <div className="p-4 rounded-xl border bg-card/60 space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-muted-foreground">Service Fee</span>
                      <span className="font-medium">{selectedBooking.price}</span>
                    </div>
                    <Separator />
                    <div className="flex justify-between items-center text-sm font-bold pt-1">
                      <span>Total Amount</span>
                      <span className="text-primary">{selectedBooking.price}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-xs text-muted-foreground block font-medium">Notes</span>
                    <p className="text-sm bg-muted/30 p-3 rounded-lg border mt-1 min-h-[60px]">
                      {selectedBooking.notes || "No notes provided."}
                    </p>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}

          <DialogFooter className="p-4 border-t bg-muted/20 flex items-center justify-between gap-2">
            <Button variant="outline" size="sm" onClick={() => setDialogOpen(false)}>Close</Button>
            <div className="flex items-center gap-2">
              {selectedBooking?.status !== 'completed' && (
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => handleUpdateStatus(selectedBooking!.id, 'completed')}>
                  Complete
                </Button>
              )}
              {selectedBooking?.status !== 'cancelled' && (
                <Button variant="destructive" size="sm" onClick={() => handleUpdateStatus(selectedBooking!.id, 'cancelled')}>
                  Cancel Booking
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
