import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Calendar,
  Clock,
  MapPin,
  User,
  FileText,
  DollarSign,
  ShieldAlert,
  PlusCircle,
  RefreshCw,
  LogOut,
  CalendarDays,
  CheckCircle2,
  XCircle,
  Camera,
} from "lucide-react";
import { toast } from "sonner";
import { useClientPortal } from "@/context/client-portal-context";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface BookingItem {
  id: number;
  tenant_id: number;
  client_id: number;
  provider_id: number;
  service_id: number;
  location_id?: number | null;
  start_time: string;
  end_time: string;
  status: string;
  notes?: string | null;
  service_name?: string;
  provider_name?: string;
  location_name?: string;
  price?: number;
  duration?: number;
  can_reschedule: boolean;
  can_cancel: boolean;
  has_dispute: boolean;
  dispute_id?: number | null;
  dispute_status?: string | null;
}

interface InvoiceItem {
  id: number;
  tenant_id: number;
  booking_id?: number | null;
  service_name?: string | null;
  subtotal: number;
  discount_total: number;
  tax_total: number;
  total: number;
  amount_paid: number;
  status: string;
  currency: string;
  notes?: string | null;
  created_at: string;
  lines: Array<{
    id: number;
    description: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
}

interface DisputeItem {
  id: number;
  tenant_id: number;
  client_id: number;
  client_name?: string | null;
  booking_id?: number | null;
  booking_service_name?: string | null;
  booking_start_time?: string | null;
  status: string;
  reason: string;
  description: string;
  preferred_resolution: string;
  resolution_notes?: string | null;
  photos?: string[] | null;
  created_at: string;
  resolved_at?: string | null;
}

export default function PortalDashboardPage() {
  const navigate = useNavigate();
  const { client, isAuthenticated, isLoading, logout, clientApi, tenantSlug } =
    useClientPortal();

  const [activeTab, setActiveTab] = useState("upcoming");
  const [bookings, setBookings] = useState<BookingItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [disputes, setDisputes] = useState<DisputeItem[]>([]);
  const [loadingData, setLoadingData] = useState(false);

  // Modals state
  const [rescheduleBooking, setRescheduleBooking] = useState<BookingItem | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduleTime, setRescheduleTime] = useState("10:00");
  const [submittingReschedule, setSubmittingReschedule] = useState(false);

  const [cancelBooking, setCancelBooking] = useState<BookingItem | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [submittingCancel, setSubmittingCancel] = useState(false);

  // Dispute Wizard modal
  const [disputeModalOpen, setDisputeModalOpen] = useState(false);
  const [disputeBookingId, setDisputeBookingId] = useState<string>("none");
  const [disputeReason, setDisputeReason] = useState("quality_concern");
  const [disputeDescription, setDisputeDescription] = useState("");
  const [disputeResolution, setDisputeResolution] = useState("redo_service");
  const [disputePhotoUrl, setDisputePhotoUrl] = useState("");
  const [disputePhotos, setDisputePhotos] = useState<string[]>([]);
  const [submittingDispute, setSubmittingDispute] = useState(false);

  // View Receipt modal
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceItem | null>(null);

  // Load portal data
  const loadData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoadingData(true);
    try {
      const [bks, invs, disps] = await Promise.all([
        clientApi<BookingItem[]>("/api/portal/bookings"),
        clientApi<InvoiceItem[]>("/api/portal/invoices"),
        clientApi<DisputeItem[]>("/api/portal/disputes"),
      ]);
      setBookings(bks);
      setInvoices(invs);
      setDisputes(disps);
    } catch (err: any) {
      console.error("Error loading portal data:", err);
      toast.error("Could not load portal data. Please try again.");
    } finally {
      setLoadingData(false);
    }
  }, [isAuthenticated, clientApi]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate("/portal/login", { replace: true });
    } else if (isAuthenticated) {
      loadData();
    }
  }, [isLoading, isAuthenticated, navigate, loadData]);

  const handleReschedule = async () => {
    if (!rescheduleBooking || !rescheduleDate || !rescheduleTime) {
      toast.error("Please pick a valid date and time slot.");
      return;
    }
    setSubmittingReschedule(true);
    try {
      const combinedDateTime = new Date(`${rescheduleDate}T${rescheduleTime}:00Z`).toISOString();
      await clientApi(`/api/portal/bookings/${rescheduleBooking.id}/reschedule`, {
        method: "POST",
        data: { start_time: combinedDateTime },
      });
      toast.success("Appointment rescheduled successfully!");
      setRescheduleBooking(null);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to reschedule appointment.");
    } finally {
      setSubmittingReschedule(false);
    }
  };

  const handleCancelBooking = async () => {
    if (!cancelBooking) return;
    setSubmittingCancel(true);
    try {
      await clientApi(`/api/portal/bookings/${cancelBooking.id}/cancel`, {
        method: "POST",
        data: { reason: cancelReason },
      });
      toast.success("Appointment cancelled.");
      setCancelBooking(null);
      setCancelReason("");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to cancel appointment.");
    } finally {
      setSubmittingCancel(false);
    }
  };

  const handleAddPhoto = () => {
    if (!disputePhotoUrl.trim()) return;
    setDisputePhotos((prev) => [...prev, disputePhotoUrl.trim()]);
    setDisputePhotoUrl("");
  };

  const handleSubmitDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeDescription.trim()) {
      toast.error("Please provide a description of your issue.");
      return;
    }
    setSubmittingDispute(true);
    try {
      const bId = disputeBookingId && disputeBookingId !== "none" ? parseInt(disputeBookingId, 10) : null;
      await clientApi("/api/portal/disputes", {
        method: "POST",
        data: {
          booking_id: bId,
          reason: disputeReason,
          description: disputeDescription,
          preferred_resolution: disputeResolution,
          photos: disputePhotos,
        },
      });
      toast.success("Dispute lodged successfully. Our management team will review it.");
      setDisputeModalOpen(false);
      setDisputeDescription("");
      setDisputePhotos([]);
      setDisputeBookingId("none");
      loadData();
      setActiveTab("disputes");
    } catch (err: any) {
      toast.error(err.message || "Failed to lodge dispute.");
    } finally {
      setSubmittingDispute(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <RefreshCw className="w-5 h-5 animate-spin text-primary" />
          Loading client portal...
        </div>
      </div>
    );
  }

  const now = new Date();
  const upcomingBookings = bookings.filter((b) => {
    const d = new Date(b.start_time);
    return d >= now && b.status.toLowerCase() !== "cancelled";
  });
  const pastBookings = bookings.filter((b) => {
    const d = new Date(b.start_time);
    return d < now || b.status.toLowerCase() === "cancelled" || b.status.toLowerCase() === "completed";
  });

  return (
    <div className="min-h-screen bg-slate-50/50 dark:bg-slate-950 flex flex-col">
      {/* Client Top Header */}
      <header className="sticky top-0 z-40 border-b bg-card/80 backdrop-blur-md px-3 sm:px-8 py-3 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold shrink-0">
            {client?.name ? client.name.charAt(0).toUpperCase() : "C"}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-sm sm:text-base text-foreground leading-none truncate">
                {client?.name || "Customer Portal"}
              </h2>
              <Badge variant="outline" className="text-[10px] font-mono capitalize shrink-0">
                {tenantSlug}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {client?.phone || client?.email || "Self-Service & Resolution Center"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={loadingData}
            className="h-10 min-h-[44px] text-xs px-3 hidden sm:inline-flex touch-manipulation"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loadingData ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              logout();
              navigate("/portal/login");
            }}
            className="h-10 min-h-[44px] text-xs text-destructive hover:bg-destructive/10 touch-manipulation px-3"
          >
            <LogOut className="w-4 h-4 sm:mr-1.5" />
            <span className="hidden sm:inline">Sign Out</span>
          </Button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-3 sm:p-6 lg:p-8 space-y-6 pb-[calc(2.5rem+env(safe-area-inset-bottom))]">
        {/* Navigation Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b">
            <TabsList className="bg-muted/70 p-1 flex w-full sm:w-auto overflow-x-auto scrollbar-none">
              <TabsTrigger value="upcoming" className="text-xs sm:text-sm flex-1 sm:flex-initial h-10 min-h-[44px] flex items-center justify-center gap-1.5 touch-manipulation">
                <Calendar className="w-4 h-4" />
                <span>Upcoming</span>
                {upcomingBookings.length > 0 && (
                  <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                    {upcomingBookings.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="history" className="text-xs sm:text-sm flex-1 sm:flex-initial h-10 min-h-[44px] flex items-center justify-center gap-1.5 touch-manipulation">
                <FileText className="w-4 h-4" />
                <span>History</span>
              </TabsTrigger>
              <TabsTrigger value="disputes" className="text-xs sm:text-sm flex-1 sm:flex-initial h-10 min-h-[44px] flex items-center justify-center gap-1.5 touch-manipulation">
                <ShieldAlert className="w-4 h-4" />
                <span>Disputes</span>
                {disputes.length > 0 && (
                  <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                    {disputes.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            {activeTab === "disputes" && (
              <Button
                size="sm"
                onClick={() => setDisputeModalOpen(true)}
                className="text-xs font-medium"
              >
                <PlusCircle className="w-4 h-4 mr-1.5" />
                Lodge a Dispute / Request Resolution
              </Button>
            )}
          </div>

          {/* TAB 1: UPCOMING APPOINTMENTS */}
          <TabsContent value="upcoming" className="space-y-4 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-foreground">Upcoming Appointments</h3>
                <p className="text-xs text-muted-foreground">
                  View appointment details or use 1-Tap actions to reschedule or cancel.
                </p>
              </div>
            </div>

            {upcomingBookings.length === 0 ? (
              <Card className="border-dashed p-8 text-center bg-background/50">
                <CalendarDays className="w-10 h-10 mx-auto text-muted-foreground mb-3 opacity-60" />
                <h4 className="text-sm font-medium text-foreground">No upcoming appointments</h4>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  You don't have any scheduled upcoming sessions. You can book a new appointment or review your past history.
                </p>
                <div className="mt-4">
                  <Button size="sm" variant="outline" onClick={() => navigate("/book")}>
                    Book an Appointment
                  </Button>
                </div>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {upcomingBookings.map((b) => {
                  const sDate = new Date(b.start_time);
                  const formattedDate = sDate.toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  });
                  const formattedTime = sDate.toLocaleTimeString(undefined, {
                    hour: "2-digit",
                    minute: "2-digit",
                  });

                  return (
                    <Card key={b.id} className="relative overflow-hidden border bg-card shadow-xs hover:shadow-md transition-shadow">
                      <div className="absolute top-0 left-0 right-0 h-1 bg-primary" />
                      <CardHeader className="pb-3 pt-5">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <CardTitle className="text-base font-semibold text-foreground">
                              {b.service_name}
                            </CardTitle>
                            <CardDescription className="text-xs mt-0.5">
                              Booking #{b.id} • {b.duration} mins
                            </CardDescription>
                          </div>
                          <Badge
                            variant={b.status.toLowerCase() === "confirmed" ? "default" : "secondary"}
                            className="text-[11px] capitalize"
                          >
                            {b.status}
                          </Badge>
                        </div>
                      </CardHeader>

                      <CardContent className="space-y-2.5 text-xs text-muted-foreground pb-4">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-primary" />
                          <span className="font-medium text-foreground">
                            {formattedDate} at {formattedTime}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <User className="w-4 h-4 text-muted-foreground" />
                          <span>Staff: <strong className="text-foreground">{b.provider_name}</strong></span>
                        </div>
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-muted-foreground" />
                          <span>Location: {b.location_name}</span>
                        </div>
                        {b.price !== undefined && (
                          <div className="flex items-center gap-2">
                            <DollarSign className="w-4 h-4 text-muted-foreground" />
                            <span>Fee: ${b.price.toFixed(2)}</span>
                          </div>
                        )}
                        {b.notes && (
                          <p className="text-[11px] bg-muted/40 rounded p-2 text-foreground/80 mt-1 italic">
                            "{b.notes}"
                          </p>
                        )}
                      </CardContent>

                      <CardFooter className="pt-2 border-t flex items-center justify-between gap-2 bg-muted/10">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 text-xs"
                            onClick={() => {
                              const dt = new Date(b.start_time);
                              const yyyy = dt.getFullYear();
                              const mm = String(dt.getMonth() + 1).padStart(2, "0");
                              const dd = String(dt.getDate()).padStart(2, "0");
                              setRescheduleDate(`${yyyy}-${mm}-${dd}`);
                              setRescheduleTime("10:00");
                              setRescheduleBooking(b);
                            }}
                          >
                            <Calendar className="w-3.5 h-3.5 mr-1" />
                            1-Tap Reschedule
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-xs text-destructive hover:bg-destructive/10"
                            onClick={() => setCancelBooking(b)}
                          >
                            Cancel
                          </Button>
                        </div>

                        <button
                          type="button"
                          onClick={() => {
                            setDisputeBookingId(String(b.id));
                            setDisputeModalOpen(true);
                          }}
                          className="text-[11px] text-muted-foreground hover:text-foreground hover:underline"
                        >
                          Dispute Booking
                        </button>
                      </CardFooter>
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>

          {/* TAB 2: PAST HISTORY & RECEIPTS */}
          <TabsContent value="history" className="space-y-6 pt-4">
            <div>
              <h3 className="text-base font-semibold text-foreground">Past Appointments & Receipts</h3>
              <p className="text-xs text-muted-foreground">
                Review completed treatments, invoice receipts, and transaction history.
              </p>
            </div>

            {/* Invoices List */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Billing Invoices & Receipts
              </h4>

              {invoices.length === 0 ? (
                <Card className="p-6 text-center text-xs text-muted-foreground border-dashed">
                  No billing invoices on file.
                </Card>
              ) : (
                <div className="space-y-2">
                  {invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="p-3.5 rounded-lg border bg-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-foreground">
                            Invoice #{inv.id}
                          </span>
                          <Badge
                            variant={inv.status === "paid" ? "default" : "secondary"}
                            className="text-[10px] uppercase font-mono"
                          >
                            {inv.status}
                          </Badge>
                          {inv.booking_id && (
                            <span className="text-muted-foreground">
                              (Booking #{inv.booking_id})
                            </span>
                          )}
                        </div>
                        <div className="text-muted-foreground text-[11px]">
                          Issued {new Date(inv.created_at).toLocaleDateString()} • {inv.lines.length} items
                        </div>
                      </div>

                      <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
                        <div className="text-right">
                          <div className="font-bold text-foreground text-sm">
                            ${inv.total.toFixed(2)} {inv.currency}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            Paid: ${inv.amount_paid.toFixed(2)}
                          </div>
                        </div>

                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 text-xs"
                          onClick={() => setSelectedInvoice(inv)}
                        >
                          <FileText className="w-3.5 h-3.5 mr-1" />
                          View Receipt
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Past Bookings */}
            <div className="space-y-3 pt-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Completed & Past Sessions
              </h4>

              {pastBookings.length === 0 ? (
                <Card className="p-6 text-center text-xs text-muted-foreground border-dashed">
                  No previous sessions recorded.
                </Card>
              ) : (
                <div className="space-y-2">
                  {pastBookings.map((b) => (
                    <div
                      key={b.id}
                      className="p-3 rounded-lg border bg-background flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-medium text-foreground">
                          {b.service_name} • Booking #{b.id}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-0.5">
                          {new Date(b.start_time).toLocaleDateString()} with {b.provider_name}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {b.status}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => {
                            setDisputeBookingId(String(b.id));
                            setDisputeModalOpen(true);
                          }}
                        >
                          Lodge Query
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          {/* TAB 3: DISPUTE & RESOLUTION CENTER */}
          <TabsContent value="disputes" className="space-y-4 pt-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-foreground">Dispute & Quality Resolution Center</h3>
                <p className="text-xs text-muted-foreground">
                  Lodge complaints, report incomplete treatments, billing inquiries, and track resolution statuses.
                </p>
              </div>

              <Button
                size="sm"
                onClick={() => setDisputeModalOpen(true)}
                className="text-xs font-medium"
              >
                <PlusCircle className="w-4 h-4 mr-1.5" />
                Lodge a Dispute
              </Button>
            </div>

            {disputes.length === 0 ? (
              <Card className="border-dashed p-8 text-center bg-background/50">
                <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-500 mb-2 opacity-80" />
                <h4 className="text-sm font-medium text-foreground">No active dispute cases</h4>
                <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                  You have not lodged any service or billing disputes. If you ever experience an issue with service quality, late arrivals, or billing queries, you can easily request a resolution here.
                </p>
                <div className="mt-4">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDisputeModalOpen(true)}
                    className="text-xs"
                  >
                    Lodge a Quality Dispute
                  </Button>
                </div>
              </Card>
            ) : (
              <div className="space-y-3">
                {disputes.map((d) => {
                  const statusColors: Record<string, string> = {
                    submitted: "bg-blue-500/10 text-blue-700 border-blue-200 dark:text-blue-300",
                    under_review: "bg-amber-500/10 text-amber-700 border-amber-200 dark:text-amber-300",
                    resolved: "bg-emerald-500/10 text-emerald-700 border-emerald-200 dark:text-emerald-300",
                    rejected: "bg-rose-500/10 text-rose-700 border-rose-200 dark:text-rose-300",
                  };

                  return (
                    <Card key={d.id} className="border shadow-xs bg-card">
                      <CardHeader className="pb-3 pt-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <CardTitle className="text-sm font-semibold capitalize">
                                Case #{d.id}: {d.reason.replace(/_/g, " ")}
                              </CardTitle>
                              <Badge
                                variant="outline"
                                className={`text-[10px] uppercase tracking-wider font-semibold ${
                                  statusColors[d.status.toLowerCase()] || ""
                                }`}
                              >
                                {d.status.replace(/_/g, " ")}
                              </Badge>
                            </div>
                            <CardDescription className="text-xs">
                              Lodged on {new Date(d.created_at).toLocaleDateString()}
                              {d.booking_service_name && ` • For ${d.booking_service_name}`}
                              {d.booking_id && ` (Booking #${d.booking_id})`}
                            </CardDescription>
                          </div>

                          <Badge variant="secondary" className="text-[10px]">
                            Preferred: {d.preferred_resolution.replace(/_/g, " ")}
                          </Badge>
                        </div>
                      </CardHeader>

                      <CardContent className="space-y-3 text-xs pb-4">
                        <div className="bg-muted/30 p-3 rounded-md text-foreground">
                          <span className="font-semibold text-muted-foreground block text-[11px] mb-1">
                            Client Description:
                          </span>
                          {d.description}
                        </div>

                        {d.photos && d.photos.length > 0 && (
                          <div>
                            <span className="font-semibold text-muted-foreground block text-[11px] mb-1.5 flex items-center gap-1">
                              <Camera className="w-3.5 h-3.5" />
                              Attached Evidence Photos ({d.photos.length}):
                            </span>
                            <div className="flex flex-wrap gap-2">
                              {d.photos.map((url, idx) => (
                                <a
                                  key={idx}
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="relative block w-16 h-16 rounded-md overflow-hidden border border-border group hover:border-primary transition-colors"
                                >
                                  <img
                                    src={url}
                                    alt={`evidence-${idx}`}
                                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                                  />
                                </a>
                              ))}
                            </div>
                          </div>
                        )}

                        {d.resolution_notes && (
                          <div className="bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-md text-emerald-900 dark:text-emerald-200">
                            <span className="font-semibold text-[11px] block mb-1 flex items-center gap-1 text-emerald-800 dark:text-emerald-300">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Management Resolution:
                            </span>
                            {d.resolution_notes}
                            {d.resolved_at && (
                              <span className="block text-[10px] opacity-75 mt-1">
                                Resolved at {new Date(d.resolved_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </main>

      {/* 1-TAP RESCHEDULE MODAL */}
      <Dialog open={!!rescheduleBooking} onOpenChange={(open) => !open && setRescheduleBooking(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold">1-Tap Reschedule Appointment</DialogTitle>
            <DialogDescription className="text-xs">
              Select a new date and time slot for {rescheduleBooking?.service_name}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="rDate" className="text-xs font-medium">
                Select Date
              </Label>
              <Input
                id="rDate"
                type="date"
                value={rescheduleDate}
                onChange={(e) => setRescheduleDate(e.target.value)}
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="rTime" className="text-xs font-medium">
                Select Time Slot
              </Label>
              <Select value={rescheduleTime} onValueChange={setRescheduleTime}>
                <SelectTrigger id="rTime" className="text-xs">
                  <SelectValue placeholder="Select a time slot" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="09:00">09:00 AM</SelectItem>
                  <SelectItem value="10:00">10:00 AM</SelectItem>
                  <SelectItem value="11:00">11:00 AM</SelectItem>
                  <SelectItem value="13:00">01:00 PM</SelectItem>
                  <SelectItem value="14:00">02:00 PM</SelectItem>
                  <SelectItem value="15:30">03:30 PM</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="p-3 bg-muted/40 rounded-lg text-xs text-muted-foreground">
              Provider: <strong>{rescheduleBooking?.provider_name}</strong> • Duration: {rescheduleBooking?.duration} mins
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRescheduleBooking(null)}
              disabled={submittingReschedule}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleReschedule}
              disabled={submittingReschedule}
            >
              {submittingReschedule ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  Updating...
                </>
              ) : (
                "Confirm Reschedule"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CANCEL BOOKING MODAL */}
      <Dialog open={!!cancelBooking} onOpenChange={(open) => !open && setCancelBooking(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold text-destructive">
              Cancel Appointment
            </DialogTitle>
            <DialogDescription className="text-xs">
              Are you sure you wish to cancel Booking #{cancelBooking?.id}?
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <p className="text-muted-foreground">
              Per our policy, cancellations requested in advance incur no penalty. If prepaid, your credit will be preserved.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="cReason" className="text-xs font-medium">
                Reason for Cancellation (Optional)
              </Label>
              <Textarea
                id="cReason"
                placeholder="e.g. Work schedule changed, feeling unwell..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="text-xs resize-none h-20"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCancelBooking(null)}
              disabled={submittingCancel}
            >
              Keep Appointment
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCancelBooking}
              disabled={submittingCancel}
            >
              {submittingCancel ? "Cancelling..." : "Confirm Cancellation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* DISPUTE WIZARD MODAL */}
      <Dialog open={disputeModalOpen} onOpenChange={setDisputeModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <form onSubmit={handleSubmitDispute}>
            <DialogHeader>
              <DialogTitle className="text-base font-semibold flex items-center gap-1.5">
                <ShieldAlert className="w-5 h-5 text-amber-500" />
                Lodge a Dispute or Quality Complaint
              </DialogTitle>
              <DialogDescription className="text-xs">
                Tell us about your experience so our management team can review and provide a remedy.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3.5 py-3 text-xs">
              {/* Select Booking */}
              <div className="space-y-1.5">
                <Label htmlFor="dBooking" className="text-xs font-medium">
                  Associated Appointment
                </Label>
                <Select value={disputeBookingId} onValueChange={setDisputeBookingId}>
                  <SelectTrigger id="dBooking" className="text-xs">
                    <SelectValue placeholder="Select appointment" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">General / No specific booking</SelectItem>
                    {bookings.map((b) => (
                      <SelectItem key={b.id} value={String(b.id)}>
                        Booking #{b.id} - {b.service_name} ({new Date(b.start_time).toLocaleDateString()})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Reason */}
              <div className="space-y-1.5">
                <Label htmlFor="dReason" className="text-xs font-medium">
                  Issue Reason
                </Label>
                <Select value={disputeReason} onValueChange={setDisputeReason}>
                  <SelectTrigger id="dReason" className="text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="incomplete_work">Incomplete Work or Treatment</SelectItem>
                    <SelectItem value="late_arrival">Late Arrival / Delay</SelectItem>
                    <SelectItem value="quality_concern">Quality or Cleanliness Concern</SelectItem>
                    <SelectItem value="billing_dispute">Billing or Pricing Dispute</SelectItem>
                    <SelectItem value="other">Other Concern</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Preferred Resolution */}
              <div className="space-y-1.5">
                <Label htmlFor="dResolution" className="text-xs font-medium">
                  Preferred Remedy / Resolution
                </Label>
                <Select value={disputeResolution} onValueChange={setDisputeResolution}>
                  <SelectTrigger id="dResolution" className="text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="redo_service">Redo Service / Complimentary Session</SelectItem>
                    <SelectItem value="partial_refund">Partial Refund</SelectItem>
                    <SelectItem value="full_refund">Full Refund</SelectItem>
                    <SelectItem value="credit_note">Store Credit / Account Credit</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <Label htmlFor="dDesc" className="text-xs font-medium">
                  Detailed Description *
                </Label>
                <Textarea
                  id="dDesc"
                  placeholder="Please describe specifically what happened..."
                  value={disputeDescription}
                  onChange={(e) => setDisputeDescription(e.target.value)}
                  className="text-xs resize-none h-24"
                  required
                />
              </div>

              {/* Evidence Photos */}
              <div className="space-y-2">
                <Label className="text-xs font-medium flex items-center justify-between">
                  <span>Photo Evidence / Image URLs (Optional)</span>
                  <span className="text-[10px] text-muted-foreground">{disputePhotos.length} attached</span>
                </Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Paste photo URL (e.g. https://...)"
                    value={disputePhotoUrl}
                    onChange={(e) => setDisputePhotoUrl(e.target.value)}
                    className="text-xs flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleAddPhoto}
                    disabled={!disputePhotoUrl.trim()}
                    className="text-xs"
                  >
                    Add
                  </Button>
                </div>

                {disputePhotos.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {disputePhotos.map((url, i) => (
                      <div key={i} className="relative w-12 h-12 rounded border overflow-hidden group">
                        <img src={url} alt="thumbnail" className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() => setDisputePhotos(disputePhotos.filter((_, idx) => idx !== i))}
                          className="absolute inset-0 bg-black/50 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setDisputeModalOpen(false)}
                disabled={submittingDispute}
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={submittingDispute}>
                {submittingDispute ? "Submitting..." : "Submit Dispute"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* INVOICE RECEIPT MODAL */}
      <Dialog open={!!selectedInvoice} onOpenChange={(open) => !open && setSelectedInvoice(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold">Payment Receipt</DialogTitle>
            <DialogDescription className="text-xs">
              Invoice #{selectedInvoice?.id} • {selectedInvoice && new Date(selectedInvoice.created_at).toLocaleDateString()}
            </DialogDescription>
          </DialogHeader>

          {selectedInvoice && (
            <div className="space-y-3 py-2 text-xs">
              <div className="border rounded-md divide-y bg-muted/20">
                {selectedInvoice.lines.map((line) => (
                  <div key={line.id} className="p-2.5 flex items-center justify-between">
                    <div>
                      <div className="font-medium text-foreground">{line.description}</div>
                      <div className="text-[10px] text-muted-foreground">Qty: {line.quantity}</div>
                    </div>
                    <div className="font-semibold text-foreground">
                      ${line.total.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>

              <div className="space-y-1.5 pt-2 text-right">
                <div className="flex justify-between text-muted-foreground">
                  <span>Subtotal:</span>
                  <span>${selectedInvoice.subtotal.toFixed(2)}</span>
                </div>
                {selectedInvoice.tax_total > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>Tax:</span>
                    <span>${selectedInvoice.tax_total.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-between text-sm font-bold text-foreground border-t pt-2">
                  <span>Total:</span>
                  <span>${selectedInvoice.total.toFixed(2)} {selectedInvoice.currency}</span>
                </div>
                <div className="flex justify-between text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                  <span>Amount Paid:</span>
                  <span>${selectedInvoice.amount_paid.toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button size="sm" onClick={() => setSelectedInvoice(null)}>
              Close Receipt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
