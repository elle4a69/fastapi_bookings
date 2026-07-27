import { useState } from "react";
import { 
  Calendar as CalendarIcon, 
  List, 
  Plus, 
  Download, 
  MoreHorizontal, 
  ChevronDown, 
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Clock,
  Ban,
  Phone,
  Mail,
  Edit2,
  MapPin,
  CalendarDays,
  Columns3,
  ListOrdered
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../../components/ui/dropdown-menu";
import { Badge } from "../../components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "../../components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Card, CardContent } from "../../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../../components/ui/select";
import { Separator } from "../../components/ui/separator";

// Mock Data
const mockBookings = [
  {
    id: "B-1001",
    date: "2024-05-15",
    time: "10:00 AM",
    service: "Swedish Massage",
    provider: "Sarah Jenkins",
    client: "Michael Chen",
    clientEmail: "m.chen@example.com",
    clientPhone: "(555) 123-4567",
    duration: "60 min",
    status: "confirmed",
    price: "$120.00",
    location: "Room A",
    notes: "Client requested deep pressure on lower back.",
  },
  {
    id: "B-1002",
    date: "2024-05-15",
    time: "11:30 AM",
    service: "Deep Tissue",
    provider: "David Ross",
    client: "Emma Watson",
    clientEmail: "emma.w@example.com",
    clientPhone: "(555) 987-6543",
    duration: "90 min",
    status: "pending",
    price: "$160.00",
    location: "Room B",
    notes: "First time client.",
  },
  {
    id: "B-1003",
    date: "2024-05-15",
    time: "02:00 PM",
    service: "Acupuncture",
    provider: "Dr. Lin",
    client: "James Smith",
    clientEmail: "jsmith99@example.com",
    clientPhone: "(555) 456-7890",
    duration: "45 min",
    status: "completed",
    price: "$95.00",
    location: "Room C",
    notes: "",
  },
  {
    id: "B-1004",
    date: "2024-05-16",
    time: "09:00 AM",
    service: "Sports Massage",
    provider: "Sarah Jenkins",
    client: "Alex Johnson",
    clientEmail: "alexj@example.com",
    clientPhone: "(555) 222-3333",
    duration: "60 min",
    status: "cancelled",
    price: "$130.00",
    location: "Room A",
    notes: "Cancelled due to illness.",
  },
  {
    id: "B-1005",
    date: "2024-05-16",
    time: "04:30 PM",
    service: "Swedish Massage",
    provider: "David Ross",
    client: "Olivia Brown",
    clientEmail: "olivia.b@example.com",
    clientPhone: "(555) 444-5555",
    duration: "60 min",
    status: "noshow",
    price: "$120.00",
    location: "Room B",
    notes: "Client did not call or show up.",
  }
];

const getStatusBadge = (status: string) => {
  switch (status) {
    case "confirmed":
      return <Badge className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Confirmed</Badge>;
    case "pending":
      return <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
    case "completed":
      return <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Completed</Badge>;
    case "cancelled":
      return <Badge className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20"><XCircle className="w-3 h-3 mr-1" /> Cancelled</Badge>;
    case "noshow":
      return <Badge className="bg-zinc-500/10 text-zinc-500 hover:bg-zinc-500/20 border-zinc-500/20"><Ban className="w-3 h-3 mr-1" /> No Show</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
};

export default function BookingsAdminPage() {
  const [viewMode, setViewMode] = useState<"list" | "calendar">("list");
  const [selectedBooking, setSelectedBooking] = useState<any | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [calViewType, setCalViewType] = useState<"month" | "provider" | "timeline">("month");

  const openBookingDetails = (booking: any) => {
    setSelectedBooking(booking);
    setIsSheetOpen(true);
  };

  return (
    <div className="flex-1 space-y-3 p-3 md:p-6 pt-2">
      <Card className="border shadow-xs">
        <CardContent className="p-3">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <div className="flex flex-1 flex-wrap items-center gap-2">
              {/* Shallow View Switcher */}
              <div className="flex border rounded-lg overflow-hidden bg-muted/40 p-0.5 mr-2">
                <Button 
                  variant={viewMode === "list" ? "default" : "ghost"} 
                  size="sm" 
                  className="rounded-md h-7 px-3 text-xs"
                  onClick={() => setViewMode("list")}
                >
                  <List className="w-3.5 h-3.5 mr-1.5" />
                  List
                </Button>
                <Button 
                  variant={viewMode === "calendar" ? "default" : "ghost"} 
                  size="sm" 
                  className="rounded-md h-7 px-3 text-xs"
                  onClick={() => setViewMode("calendar")}
                >
                  <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                  Calendar
                </Button>
              </div>
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
                <Input placeholder="Search clients or IDs..." className="pl-8 h-8 text-xs" />
              </div>
              <Select defaultValue="all">
                <SelectTrigger className="w-[140px] h-8 text-xs">
                  <SelectValue placeholder="Date Range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="week">This Week</SelectItem>
                  <SelectItem value="month">This Month</SelectItem>
                </SelectContent>
              </Select>
              <Select defaultValue="all">
                <SelectTrigger className="w-[140px] h-8 text-xs">
                  <SelectValue placeholder="Service" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Services</SelectItem>
                  <SelectItem value="massage">Massage</SelectItem>
                  <SelectItem value="acu">Acupuncture</SelectItem>
                </SelectContent>
              </Select>
              <Select defaultValue="all">
                <SelectTrigger className="w-[140px] h-8 text-xs">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Providers</SelectItem>
                  <SelectItem value="p1">Sarah Jenkins</SelectItem>
                  <SelectItem value="p2">David Ross</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" className="h-8 w-8 p-0">
                <Filter className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs px-3">
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export CSV
              </Button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 pt-2 border-t">
            <Badge variant="secondary" className="cursor-pointer bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200">Pending</Badge>
            <Badge variant="secondary" className="cursor-pointer bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-900 dark:text-emerald-200">Confirmed</Badge>
            <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-800 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200">Completed</Badge>
            <Badge variant="secondary" className="cursor-pointer opacity-50">Cancelled</Badge>
            <Badge variant="secondary" className="cursor-pointer opacity-50">No Show</Badge>
          </div>
        </CardContent>
      </Card>

      {viewMode === "list" ? (

          <div className="rounded-md border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date / Time</TableHead>
                  <TableHead>Client</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mockBookings.map((booking) => (
                  <TableRow key={booking.id} className="cursor-pointer hover:bg-muted/50" onClick={() => openBookingDetails(booking)}>
                    <TableCell>
                      <div className="font-medium">{booking.date}</div>
                      <div className="text-xs text-muted-foreground">{booking.time}</div>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{booking.client}</div>
                      <div className="text-xs text-muted-foreground">{booking.id}</div>
                    </TableCell>
                    <TableCell>{booking.service}</TableCell>
                    <TableCell>{booking.provider}</TableCell>
                    <TableCell>{booking.duration}</TableCell>
                    <TableCell>{getStatusBadge(booking.status)}</TableCell>
                    <TableCell className="text-right font-medium">{booking.price}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" className="h-8 w-8 p-0">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openBookingDetails(booking)}>View details</DropdownMenuItem>
                          <DropdownMenuItem>Confirm</DropdownMenuItem>
                          <DropdownMenuItem>Complete</DropdownMenuItem>
                          <DropdownMenuItem>Reschedule</DropdownMenuItem>
                          <DropdownMenuItem className="text-red-600">Cancel Booking</DropdownMenuItem>
                          <DropdownMenuItem className="text-zinc-600">Mark No-show</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
      ) : (
        <div className="flex h-[700px] border rounded-lg bg-card overflow-hidden">
          {/* Calendar Sidebar */}
          <div className="w-64 border-r bg-muted/20 p-4 flex flex-col gap-6">
            <div>
              <h3 className="font-semibold mb-3 flex items-center"><CalendarIcon className="w-4 h-4 mr-2" /> Mini Calendar</h3>
              <div className="bg-background rounded-md border p-3 flex items-center justify-center h-48 text-muted-foreground text-sm">
                [Calendar Picker Widget]
              </div>
            </div>
            
            <div>
              <h3 className="font-semibold mb-3">View Options</h3>
              <div className="space-y-2">
                <Button 
                  variant={calViewType === "month" ? "secondary" : "ghost"} 
                  className="w-full justify-start"
                  onClick={() => setCalViewType("month")}
                >
                  <CalendarDays className="w-4 h-4 mr-2" /> Month
                </Button>
                <Button 
                  variant={calViewType === "provider" ? "secondary" : "ghost"} 
                  className="w-full justify-start"
                  onClick={() => setCalViewType("provider")}
                >
                  <Columns3 className="w-4 h-4 mr-2" /> By Provider
                </Button>
                <Button 
                  variant={calViewType === "timeline" ? "secondary" : "ghost"} 
                  className="w-full justify-start"
                  onClick={() => setCalViewType("timeline")}
                >
                  <ListOrdered className="w-4 h-4 mr-2" /> Timeline
                </Button>
              </div>
            </div>

            <div className="mt-auto">
              <h3 className="font-semibold mb-3">Filters</h3>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-medium">Locations</label>
                  <Select defaultValue="all">
                    <SelectTrigger className="w-full h-8 text-xs">
                      <SelectValue placeholder="All Locations" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Locations</SelectItem>
                      <SelectItem value="main">Main Clinic</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>
          
          {/* Calendar Main Area */}
          <div className="flex-1 p-4 bg-background flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold">
                {calViewType === 'month' ? 'May 2024' : 'Today'}
              </h3>
              <div className="flex space-x-2">
                <Button variant="outline" size="sm">Today</Button>
                <Button variant="outline" size="icon" className="w-8 h-8"><ChevronDown className="w-4 h-4 rotate-90" /></Button>
                <Button variant="outline" size="icon" className="w-8 h-8"><ChevronDown className="w-4 h-4 -rotate-90" /></Button>
              </div>
            </div>
            
            <div className="flex-1 border rounded-md border-dashed flex items-center justify-center text-muted-foreground bg-muted/5">
              <div className="text-center max-w-sm">
                <CalendarIcon className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <h4 className="text-lg font-medium text-foreground mb-2">Interactive Calendar View</h4>
                <p className="text-sm">Click on any scheduled block to view booking details, or click on an empty slot to create a new booking.</p>
                <div className="mt-6 flex justify-center gap-4">
                  <div className="w-32 h-16 bg-blue-100 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded p-2 text-xs text-left cursor-pointer hover:ring-2 ring-blue-400 transition-all" onClick={() => openBookingDetails(mockBookings[0])}>
                    <div className="font-semibold text-blue-900 dark:text-blue-100">10:00 AM</div>
                    <div className="truncate text-blue-800 dark:text-blue-200">Michael Chen</div>
                  </div>
                  <div className="w-32 h-16 bg-muted border border-dashed rounded flex flex-col items-center justify-center text-xs cursor-pointer hover:bg-accent transition-all" onClick={() => { /* Open new booking form */ }}>
                    <Plus className="w-4 h-4 mb-1" />
                    New Booking
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent className="w-[90%] sm:max-w-[55%] overflow-y-auto sm:w-[800px]">
          <SheetHeader className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <SheetTitle className="text-2xl flex items-center gap-3">
                  Booking {selectedBooking?.id}
                  {selectedBooking && getStatusBadge(selectedBooking.status)}
                </SheetTitle>
                <SheetDescription>
                  Created on May 10, 2024 at 09:41 AM
                </SheetDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">Reschedule</Button>
                <Button variant="default" size="sm">Check In</Button>
              </div>
            </div>
          </SheetHeader>

          {selectedBooking && (
            <Tabs defaultValue="booking" className="w-full">
              <TabsList className="grid w-full grid-cols-3 mb-6">
                <TabsTrigger value="booking">Booking Details</TabsTrigger>
                <TabsTrigger value="client">Client Info</TabsTrigger>
                <TabsTrigger value="finance">Financials</TabsTrigger>
              </TabsList>

              <TabsContent value="booking" className="space-y-6">
                <div className="grid grid-cols-2 gap-6">
                  <Card>
                    <CardContent className="pt-6 space-y-4">
                      <div className="flex justify-between items-center">
                        <h4 className="font-semibold flex items-center text-muted-foreground"><Clock className="w-4 h-4 mr-2" /> Date & Time</h4>
                        <Button variant="ghost" size="icon" className="h-6 w-6"><Edit2 className="w-3 h-3" /></Button>
                      </div>
                      <div>
                        <div className="text-lg font-medium">{selectedBooking.date}</div>
                        <div>{selectedBooking.time} ({selectedBooking.duration})</div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="pt-6 space-y-4">
                      <div className="flex justify-between items-center">
                        <h4 className="font-semibold flex items-center text-muted-foreground"><MapPin className="w-4 h-4 mr-2" /> Location</h4>
                        <Button variant="ghost" size="icon" className="h-6 w-6"><Edit2 className="w-3 h-3" /></Button>
                      </div>
                      <div>
                        <div className="text-lg font-medium">Main Clinic</div>
                        <div>{selectedBooking.location}</div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardContent className="pt-6 space-y-6">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-semibold text-muted-foreground mb-1">Service</h4>
                        <div className="text-lg font-medium">{selectedBooking.service}</div>
                      </div>
                      <div className="text-right">
                        <h4 className="font-semibold text-muted-foreground mb-1">Provider</h4>
                        <div className="flex items-center justify-end gap-2">
                          <span>{selectedBooking.provider}</span>
                          <Button variant="ghost" size="icon" className="h-6 w-6"><Edit2 className="w-3 h-3" /></Button>
                        </div>
                      </div>
                    </div>

                    <Separator />
                    
                    <div>
                      <h4 className="font-semibold text-muted-foreground mb-2 flex items-center">
                        Booking Notes
                        <Button variant="ghost" size="icon" className="h-6 w-6 ml-2"><Edit2 className="w-3 h-3" /></Button>
                      </h4>
                      <p className="text-sm bg-muted/50 p-3 rounded-md min-h-[80px]">
                        {selectedBooking.notes || "No notes provided for this booking."}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <div className="flex justify-end gap-3 pt-4 border-t">
                  <Button variant="destructive" className="bg-red-600 hover:bg-red-700">Cancel Booking</Button>
                  <Button variant="outline" className="text-zinc-600">Mark No-show</Button>
                  <Button variant="outline" className="text-emerald-600 border-emerald-200 hover:bg-emerald-50">Complete Session</Button>
                </div>
              </TabsContent>

              <TabsContent value="client" className="space-y-6">
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-4 mb-6">
                      <div className="h-16 w-16 bg-primary/10 text-primary rounded-full flex items-center justify-center text-xl font-bold">
                        {selectedBooking.client.charAt(0)}
                      </div>
                      <div>
                        <h3 className="text-2xl font-bold">{selectedBooking.client}</h3>
                        <div className="flex gap-2 mt-2">
                          <Badge variant="outline">New Client</Badge>
                          <Badge variant="outline">No VIP</Badge>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" className="ml-auto">View Full Profile</Button>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-md">
                        <Mail className="w-5 h-5 text-muted-foreground" />
                        <div>
                          <div className="text-sm font-medium">Email</div>
                          <a href={`mailto:${selectedBooking.clientEmail}`} className="text-sm text-primary hover:underline">{selectedBooking.clientEmail}</a>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-md">
                        <Phone className="w-5 h-5 text-muted-foreground" />
                        <div>
                          <div className="text-sm font-medium">Phone</div>
                          <a href={`tel:${selectedBooking.clientPhone}`} className="text-sm text-primary hover:underline">{selectedBooking.clientPhone}</a>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="finance" className="space-y-6">
                <Card>
                  <CardContent className="pt-6 space-y-4">
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-lg font-semibold">Payment Details</h3>
                      <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">Unpaid</Badge>
                    </div>
                    
                    <div className="space-y-3 text-sm">
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">{selectedBooking.service}</span>
                        <span>{selectedBooking.price}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Taxes (0%)</span>
                        <span>$0.00</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground text-primary cursor-pointer hover:underline flex items-center"><Plus className="w-3 h-3 mr-1"/> Add Discount/Promo</span>
                        <span>-$0.00</span>
                      </div>
                      <Separator />
                      <div className="flex justify-between items-center font-bold text-lg">
                        <span>Total</span>
                        <span>{selectedBooking.price}</span>
                      </div>
                    </div>

                    <div className="pt-6 flex gap-3">
                      <Button className="w-full">Process Payment</Button>
                      <Button variant="outline" className="w-full">Send Invoice</Button>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
