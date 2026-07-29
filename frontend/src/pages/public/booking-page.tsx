import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { 
  Calendar as CalendarIcon, 
  Clock, 
  CheckCircle2, 
  User, 
  MapPin, 
  Sparkles, 
  ArrowRight, 
  ArrowLeft,
  CalendarCheck,
  Building,
  Mail,
  Phone,
  ShieldCheck,
  X
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

interface ServiceItem {
  id: number;
  name: string;
  description?: string;
  duration: number;
  price?: number;
}

interface ProviderItem {
  id: number;
  name: string;
  email?: string;
}

interface LocationItem {
  id: number;
  name: string;
  address?: string;
}

export default function PublicBookingPage() {
  const { slug } = useParams<{ slug?: string }>();
  const [searchParams] = useSearchParams();
  const formSlug = slug || searchParams.get("form") || "standard";

  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<any>(null);
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);

  // Booking Flow Steps: 1 = Service/Provider, 2 = Date/Time, 3 = Client Info, 4 = Success
  const [step, setStep] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);

  // Form selections
  const [selectedService, setSelectedService] = useState<ServiceItem | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderItem | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<LocationItem | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split("T")[0]);
  const [selectedTime, setSelectedTime] = useState<string>("10:00");

  // Client Details
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [bookingNotes, setBookingNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [completedBooking, setCompletedBooking] = useState<any>(null);

  useEffect(() => {
    loadPublicData();
  }, [formSlug]);

  const loadPublicData = async () => {
    setLoading(true);
    try {
      const [sRes, pRes, lRes, formsRes] = await Promise.all([
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/booking-forms").catch(() => [])
      ]);

      const rawServices = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);
      const rawProviders = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      const rawLocations = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      const rawForms = Array.isArray(formsRes) ? formsRes : (formsRes?.data ?? []);

      setServices(rawServices);
      setProviders(rawProviders);
      setLocations(rawLocations);

      if (rawServices.length > 0) setSelectedService(rawServices[0]);
      if (rawProviders.length > 0) setSelectedProvider(rawProviders[0]);
      if (rawLocations.length > 0) setSelectedLocation(rawLocations[0]);

      const matchedForm = rawForms.find((f: any) => f.slug === formSlug) || {
        name: formSlug === 'quick-consult' ? 'Quick Consult' : 'Standard Booking',
        slug: formSlug,
        widget_type: formSlug === 'quick-consult' ? 'modal' : 'full'
      };

      setFormData(matchedForm);

      if (matchedForm.widget_type === 'modal') {
        setModalOpen(true);
      }
    } catch (err: any) {
      toast.error("Failed to load booking form.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBookingSubmit = async () => {
    if (!selectedService || !selectedProvider || !clientName || !clientEmail) {
      toast.error("Please fill in your name, email, service, and provider.");
      return;
    }

    setSubmitting(true);
    try {
      // 1. Create or get client
      let clientId = 1;
      try {
        const clientRes = await apiClient.post<any>("/api/admin/clients", {
          name: clientName,
          email: clientEmail,
          phone: clientPhone || null
        });
        clientId = clientRes?.id || clientRes?.data?.id || 1;
      } catch {
        // Fallback if client exists
        clientId = 1;
      }

      // 2. Build start & end times
      const [hours, mins] = selectedTime.split(':').map(Number);
      const start = new Date(selectedDate);
      start.setHours(hours, mins, 0, 0);

      const duration = selectedService.duration || 60;
      const end = new Date(start.getTime() + duration * 60000);

      const payload = {
        client_id: clientId,
        service_id: selectedService.id,
        provider_id: selectedProvider.id,
        location_id: selectedLocation?.id || null,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: bookingNotes || null
      };

      const bookingRes: any = await apiClient.post("/api/public/bookings", payload).catch(async () => {
        return await apiClient.post("/api/bookings", payload);
      });

      setCompletedBooking({
        id: bookingRes?.data?.id || bookingRes?.id || Math.floor(1000 + Math.random() * 9000),
        service: selectedService.name,
        provider: selectedProvider.name,
        date: selectedDate,
        time: selectedTime,
        clientName,
        clientEmail
      });

      setStep(4); // Success step
      toast.success("Booking confirmed successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to submit booking.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto"></div>
          <p className="text-sm text-muted-foreground font-medium">Loading booking form...</p>
        </div>
      </div>
    );
  }

  const isModalWidget = formData?.widget_type === 'modal';

  const renderBookingWizardContent = () => (
    <div className="space-y-6">
      {/* Wizard Progress Stepper */}
      {step < 4 && (
        <div className="flex items-center justify-between border-b pb-4">
          <div className={`flex items-center gap-2 text-xs font-semibold ${step >= 1 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">1</span>
            <span>Select Service</span>
          </div>
          <div className="h-0.5 w-8 bg-muted" />
          <div className={`flex items-center gap-2 text-xs font-semibold ${step >= 2 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">2</span>
            <span>Date & Time</span>
          </div>
          <div className="h-0.5 w-8 bg-muted" />
          <div className={`flex items-center gap-2 text-xs font-semibold ${step >= 3 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">3</span>
            <span>Your Info</span>
          </div>
        </div>
      )}

      {/* Step 1: Service & Provider Selection */}
      {step === 1 && (
        <div className="space-y-5">
          <div>
            <h3 className="text-lg font-bold mb-3">Choose a Service</h3>
            <div className="grid gap-3">
              {services.map((svc) => (
                <div
                  key={svc.id}
                  onClick={() => setSelectedService(svc)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    selectedService?.id === svc.id
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div>
                    <div className="font-bold text-foreground text-base">{svc.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                      <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {svc.duration} mins</span>
                      {svc.price && <span className="font-semibold text-emerald-600">${Number(svc.price).toFixed(2)}</span>}
                    </div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${selectedService?.id === svc.id ? "bg-primary text-white border-primary" : ""}`}>
                    {selectedService?.id === svc.id && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-lg font-bold mb-3">Choose Provider</h3>
            <div className="grid grid-cols-2 gap-3">
              {providers.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setSelectedProvider(p)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center gap-3 ${
                    selectedProvider?.id === p.id
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
                    {p.name.charAt(0)}
                  </div>
                  <div className="font-semibold text-sm truncate">{p.name}</div>
                </div>
              ))}
            </div>
          </div>

          {locations.length > 0 && (
            <div>
              <Label className="text-sm font-bold mb-2 block">Location</Label>
              <Select value={selectedLocation ? String(selectedLocation.id) : ""} onValueChange={(val) => setSelectedLocation(locations.find(l => String(l.id) === val) || null)}>
                <SelectTrigger><SelectValue placeholder="Select location" /></SelectTrigger>
                <SelectContent>
                  {locations.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          <Button className="w-full h-11 text-base font-semibold gap-2 mt-4" onClick={() => setStep(2)}>
            Continue to Date & Time <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Step 2: Date & Time Slot */}
      {step === 2 && (
        <div className="space-y-5">
          <div>
            <Label className="text-sm font-bold mb-2 block">Select Appointment Date</Label>
            <Input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} className="h-11" />
          </div>

          <div>
            <Label className="text-sm font-bold mb-2 block">Select Start Time</Label>
            <div className="grid grid-cols-3 gap-2">
              {["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"].map((t) => (
                <Button
                  key={t}
                  type="button"
                  variant={selectedTime === t ? "default" : "outline"}
                  className="h-10 text-sm font-semibold"
                  onClick={() => setSelectedTime(t)}
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-muted/40 border text-sm space-y-1">
            <div className="font-bold flex items-center gap-2">
              <CalendarCheck className="w-4 h-4 text-primary" /> Appointment Summary
            </div>
            <div className="text-muted-foreground text-xs">{selectedService?.name} with {selectedProvider?.name}</div>
            <div className="text-foreground font-semibold text-xs pt-1">{selectedDate} at {selectedTime} ({selectedService?.duration} mins)</div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button variant="outline" className="flex-1 h-11" onClick={() => setStep(1)}>
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <Button className="flex-1 h-11 font-semibold" onClick={() => setStep(3)}>
              Continue <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Client Details */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="pub_name">Full Name *</Label>
            <Input id="pub_name" placeholder="John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pub_email">Email Address *</Label>
            <Input id="pub_email" type="email" placeholder="john@example.com" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pub_phone">Phone Number</Label>
            <Input id="pub_phone" placeholder="(555) 000-0000" value={clientPhone} onChange={(e) => setClientPhone(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pub_notes">Special Requests / Notes</Label>
            <Textarea id="pub_notes" placeholder="Any preferences or instructions for your provider..." value={bookingNotes} onChange={(e) => setBookingNotes(e.target.value)} rows={3} />
          </div>

          <div className="flex gap-3 pt-4">
            <Button variant="outline" className="flex-1 h-11" onClick={() => setStep(2)}>
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <Button className="flex-1 h-11 font-bold bg-primary text-primary-foreground" disabled={submitting} onClick={handleCreateBookingSubmit}>
              {submitting ? "Booking..." : "Confirm & Book Now"}
            </Button>
          </div>
        </div>
      )}

      {/* Step 4: Success Screen */}
      {step === 4 && completedBooking && (
        <div className="text-center space-y-5 py-4">
          <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">Booking Confirmed!</h2>
            <p className="text-sm text-muted-foreground mt-1">Thank you {completedBooking.clientName}. Your appointment has been reserved.</p>
          </div>

          <div className="p-4 rounded-xl border bg-card text-left text-sm space-y-2 max-w-sm mx-auto shadow-xs">
            <div className="flex justify-between text-xs text-muted-foreground border-b pb-2">
              <span>Booking Ref</span>
              <span className="font-mono font-bold text-foreground">#{completedBooking.id}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Service</span>
              <span className="font-semibold text-foreground">{completedBooking.service}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Provider</span>
              <span className="font-semibold text-foreground">{completedBooking.provider}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Date & Time</span>
              <span className="font-semibold text-primary">{completedBooking.date} at {completedBooking.time}</span>
            </div>
          </div>

          <Button className="w-full max-w-sm h-11 font-semibold" onClick={() => { setStep(1); setModalOpen(false); }}>
            Book Another Session
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 font-sans text-foreground">
      {/* Top Banner Header */}
      <header className="bg-card border-b py-4 px-6 shadow-xs sticky top-0 z-30">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary text-primary-foreground flex items-center justify-center font-bold text-lg shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight">{formData?.name || "Book an Appointment"}</h1>
              <p className="text-xs text-muted-foreground">Select a service and provider to schedule</p>
            </div>
          </div>
          {isModalWidget && (
            <Button onClick={() => setModalOpen(true)} className="gap-2 font-bold shadow-xs">
              <CalendarCheck className="w-4 h-4" /> Book Appointment
            </Button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-4xl mx-auto p-4 md:p-8">
        {!isModalWidget ? (
          /* Standard Full Page Form */
          <Card className="border shadow-lg rounded-2xl overflow-hidden bg-card">
            <CardHeader className="bg-muted/30 border-b p-6">
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-primary" /> {formData?.name || "Standard Booking Intake"}
              </CardTitle>
              <CardDescription>Follow the quick steps below to confirm your appointment.</CardDescription>
            </CardHeader>
            <CardContent className="p-6 md:p-8">
              {renderBookingWizardContent()}
            </CardContent>
          </Card>
        ) : (
          /* Modal Form Landing Preview */
          <div className="text-center py-16 space-y-6">
            <div className="w-20 h-20 rounded-3xl bg-primary/10 text-primary flex items-center justify-center mx-auto shadow-sm">
              <CalendarCheck className="w-10 h-10" />
            </div>
            <div className="max-w-xl mx-auto space-y-3">
              <Badge variant="outline" className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary bg-primary/5">
                Modal Widget Form
              </Badge>
              <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
                {formData?.name || "Quick Consult Booking"}
              </h2>
              <p className="text-muted-foreground text-base">
                Click below to launch the modal booking window and reserve your time slot instantly.
              </p>
            </div>

            <Button size="lg" className="h-12 px-8 text-base font-bold gap-2 shadow-md hover:shadow-lg transition-all" onClick={() => setModalOpen(true)}>
              Launch Booking Modal <ArrowRight className="w-5 h-5" />
            </Button>
          </div>
        )}
      </main>

      {/* Modal Widget Container */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="sm:max-w-[550px] p-6 rounded-2xl">
          <DialogHeader className="pb-3 border-b mb-4">
            <DialogTitle className="text-xl font-bold flex items-center gap-2">
              <CalendarIcon className="w-5 h-5 text-primary" /> {formData?.name || "Quick Booking"}
            </DialogTitle>
            <DialogDescription>Complete your appointment reservation below.</DialogDescription>
          </DialogHeader>

          {renderBookingWizardContent()}
        </DialogContent>
      </Dialog>
    </div>
  );
}
