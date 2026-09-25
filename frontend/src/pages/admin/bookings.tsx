import { useState, useEffect } from "react";
import { 
  Calendar as CalendarIcon, 
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
  RefreshCw
} from "lucide-react";
import { toast } from "sonner";
import { apiClient, fetchAllPaginated } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { MobilePageShell } from "@/components/ui/mobile-page-shell";
import { ResponsiveDataTable, type ColumnDef } from "@/components/ui/responsive-data-table";

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
      const rawBookings = await fetchAllPaginated("/api/bookings", 100);

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

  const columns: ColumnDef<BookingItem>[] = [
    {
      id: "datetime",
      header: "Date / Time",
      sortable: true,
      cell: (b) => (
        <div>
          <div className="font-semibold text-sm text-foreground">{b.date}</div>
          <div className="text-xs text-muted-foreground">{b.time}</div>
        </div>
      ),
    },
    {
      id: "client",
      header: "Client",
      sortable: true,
      cell: (b) => (
        <div>
          <div className="font-semibold text-sm text-foreground">{b.client}</div>
          <div className="text-xs text-muted-foreground">#{b.id}</div>
        </div>
      ),
    },
    {
      id: "service",
      header: "Service",
      sortable: true,
      cell: (b) => <span className="font-medium text-sm">{b.service}</span>,
    },
    {
      id: "provider",
      header: "Provider",
      sortable: true,
      cell: (b) => <span className="text-sm text-muted-foreground">{b.provider}</span>,
    },
    {
      id: "duration",
      header: "Duration",
      defaultHidden: true,
      cell: (b) => <span className="text-xs text-muted-foreground">{b.duration}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: (b) => getStatusBadge(b.status),
    },
    {
      id: "price",
      header: "Price",
      sortable: true,
      align: "right",
      cell: (b) => <span className="font-bold text-foreground text-sm">{b.price}</span>,
    },
    {
      id: "actions",
      header: "Actions",
      align: "right",
      hideable: false,
      cell: (b) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" className="h-8 w-8 min-h-0 min-w-0 p-0 touch-manipulation">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => { setSelectedBooking(b); setDialogOpen(true); }}>
              View Details
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'confirmed')}>
              Mark Confirmed
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'completed')}>
              Mark Completed
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'noshow')}>
              Mark No-show
            </DropdownMenuItem>
            <DropdownMenuItem className="text-red-600" onClick={() => handleUpdateStatus(b.id, 'cancelled')}>
              Cancel Booking
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <MobilePageShell
      title="Manage Bookings"
      description="View, filter, and track customer appointments across providers"
      density="compact"
      actions={
        <div className="flex items-center gap-1.5 sm:gap-2 w-full sm:w-auto">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={loadData}
            className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 flex-1 sm:flex-initial touch-manipulation gap-1.5 text-xs sm:text-sm"
          >
            <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => window.location.href = '/admin/calendar'}
            className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 flex-1 sm:flex-initial touch-manipulation gap-1.5 text-xs sm:text-sm"
          >
            <CalendarIcon className="w-3.5 h-3.5 text-primary" />
            <span>Calendar</span>
          </Button>
        </div>
      }
    >
      <div className="space-y-2.5 sm:space-y-3 min-w-0">
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center justify-between">
          <div className="relative flex-1 max-w-full sm:max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input 
              placeholder="Search client, service, ID..." 
              className="pl-8 h-8 sm:h-9 min-h-0 text-xs sm:text-sm" 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[150px] h-8 sm:h-9 min-h-0 text-xs sm:text-sm">
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

            <Button 
              variant="outline" 
              size="sm" 
              className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 shrink-0 touch-manipulation gap-1.5 text-xs sm:text-sm" 
              onClick={() => toast.success("Exporting CSV...")}
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Export</span>
            </Button>
          </div>
        </div>

        <ResponsiveDataTable
          data={filteredBookings}
          columns={columns}
          keyExtractor={(b) => b.id}
          isLoading={loading}
          density="compact"
          onRowClick={(b) => { setSelectedBooking(b); setDialogOpen(true); }}
          defaultSort={{ key: "datetime", direction: "desc" }}
          renderMobileCard={(b) => (
            <div className="p-3.5 rounded-lg border bg-card text-card-foreground shadow-xs space-y-3 touch-manipulation active:bg-accent/40 transition-colors">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-foreground">#{b.id}</span>
                  <span className="text-xs text-muted-foreground">{b.date} • {b.time}</span>
                </div>
                {getStatusBadge(b.status)}
              </div>

              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-bold text-base text-foreground">{b.client}</p>
                  <p className="text-xs font-medium text-primary mt-0.5">{b.service}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Provider: {b.provider}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-foreground text-base">{b.price}</p>
                  <p className="text-xs text-muted-foreground">{b.duration}</p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t text-xs text-muted-foreground" onClick={(e) => e.stopPropagation()}>
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate max-w-[140px]">{b.location}</span>
                </span>

                <div className="flex items-center gap-1">
                  {b.clientPhone && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation"
                      title="Call"
                      asChild
                    >
                      <a href={`tel:${b.clientPhone}`}><Phone className="h-4 w-4" /></a>
                    </Button>
                  )}
                  {b.clientEmail && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation"
                      title="Email"
                      asChild
                    >
                      <a href={`mailto:${b.clientEmail}`}><Mail className="h-4 w-4" /></a>
                    </Button>
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => { setSelectedBooking(b); setDialogOpen(true); }}>
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'confirmed')}>
                        Mark Confirmed
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'completed')}>
                        Mark Completed
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleUpdateStatus(b.id, 'noshow')}>
                        Mark No-show
                      </DropdownMenuItem>
                      <DropdownMenuItem className="text-red-600" onClick={() => handleUpdateStatus(b.id, 'cancelled')}>
                        Cancel Booking
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          )}
        />
      </div>

      {/* Booking Details Centered Dialog / Mobile Sheet */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-full sm:max-w-lg p-0 overflow-hidden rounded-xl">
          <DialogHeader className="p-4 sm:p-6 pb-4 border-b bg-card text-left">
            <div className="flex items-center justify-between pr-6">
              <div>
                <DialogTitle className="text-lg sm:text-xl font-bold flex items-center gap-2">
                  Booking #{selectedBooking?.id}
                  {selectedBooking && getStatusBadge(selectedBooking.status)}
                </DialogTitle>
                <DialogDescription className="mt-1 text-xs">
                  {selectedBooking?.date} at {selectedBooking?.time}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {selectedBooking && (
            <div className="p-4 sm:p-6 space-y-4 max-h-[65vh] overflow-y-auto">
              <Tabs defaultValue="details" className="w-full">
                <TabsList className="grid grid-cols-3 w-full mb-3 h-10">
                  <TabsTrigger value="details" className="text-xs">Appointment</TabsTrigger>
                  <TabsTrigger value="client" className="text-xs">Client Info</TabsTrigger>
                  <TabsTrigger value="payment" className="text-xs">Payment</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="space-y-3 pt-1">
                  <div className="grid grid-cols-2 gap-3 p-3.5 rounded-lg border bg-muted/20">
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Service</span>
                      <span className="font-semibold text-sm mt-0.5 block">{selectedBooking.service}</span>
                      <span className="text-xs text-muted-foreground mt-0.5 block">{selectedBooking.duration}</span>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Provider</span>
                      <span className="font-semibold text-sm mt-0.5 block">{selectedBooking.provider}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 p-3.5 rounded-lg border bg-muted/20">
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Location</span>
                      <span className="font-semibold text-xs mt-0.5 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-primary shrink-0" /> {selectedBooking.location}
                      </span>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground block font-medium">Amount</span>
                      <span className="font-semibold text-sm mt-0.5 text-emerald-600 block">{selectedBooking.price}</span>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="client" className="space-y-3 pt-1">
                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-base shrink-0">
                        {selectedBooking.client[0]}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-sm truncate">{selectedBooking.client}</div>
                        <div className="text-xs text-muted-foreground">ID #{selectedBooking.clientId}</div>
                      </div>
                    </div>
                    <Separator />
                    {selectedBooking.clientEmail && (
                      <div className="flex items-center gap-2 text-xs">
                        <Mail className="w-4 h-4 text-muted-foreground shrink-0" />
                        <a href={`mailto:${selectedBooking.clientEmail}`} className="text-primary hover:underline truncate">{selectedBooking.clientEmail}</a>
                      </div>
                    )}
                    {selectedBooking.clientPhone && (
                      <div className="flex items-center gap-2 text-xs">
                        <Phone className="w-4 h-4 text-muted-foreground shrink-0" />
                        <a href={`tel:${selectedBooking.clientPhone}`} className="text-primary hover:underline">{selectedBooking.clientPhone}</a>
                      </div>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="payment" className="space-y-3 pt-1">
                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-2">
                    <div className="flex justify-between items-center text-xs">
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
                    <p className="text-xs bg-muted/30 p-3 rounded-lg border mt-1 min-h-[50px]">
                      {selectedBooking.notes || "No notes provided."}
                    </p>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}

          <DialogFooter className="p-3.5 border-t bg-muted/20 flex flex-col-reverse sm:flex-row items-center justify-between gap-2">
            <Button 
              variant="outline" 
              onClick={() => setDialogOpen(false)}
              className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation text-xs"
            >
              Close
            </Button>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              {selectedBooking?.status !== 'completed' && (
                <Button 
                  className="bg-emerald-600 hover:bg-emerald-700 text-white h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs" 
                  onClick={() => handleUpdateStatus(selectedBooking!.id, 'completed')}
                >
                  Complete
                </Button>
              )}
              {selectedBooking?.status !== 'cancelled' && (
                <Button 
                  variant="destructive" 
                  className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs" 
                  onClick={() => handleUpdateStatus(selectedBooking!.id, 'cancelled')}
                >
                  Cancel
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MobilePageShell>
  );
}
