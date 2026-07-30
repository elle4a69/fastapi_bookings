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
  RotateCcw,
  AlertCircle,
  Lock,
  Building
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
  provider_ids?: number[];
  category_ids?: number[];
}

interface ProviderItem {
  id: number;
  name: string;
  email?: string;
  service_ids?: number[];
}

interface LocationItem {
  id: number;
  name: string;
  address?: string;
  provider_ids?: number[];
  service_ids?: number[];
}

export default function PublicBookingPage() {
  const { slug } = useParams<{ slug?: string }>();
  const [searchParams] = useSearchParams();

  // Extract path slug
  const currentPath = window.location.pathname;
  const pathSlug = currentPath.startsWith("/book/") 
    ? currentPath.replace(/^\/book\//, "").replace(/\/$/, "")
    : "";
  const formSlug = pathSlug || slug || searchParams.get("form") || "standard";

  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<any>(null);
  const [allServices, setAllServices] = useState<ServiceItem[]>([]);
  const [allProviders, setAllProviders] = useState<ProviderItem[]>([]);
  const [allLocations, setAllLocations] = useState<LocationItem[]>([]);

  // Stepper state: 1 = Selections, 2 = Date & Time, 3 = Client Info, 4 = Confirmation
  const [step, setStep] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);

  // Active selections
  const [selectedLocation, setSelectedLocation] = useState<LocationItem | null>(null);
  const [selectedService, setSelectedService] = useState<ServiceItem | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderItem | null>(null);

  // Lock status (from form predefined_values or URL params)
  const [isLocationLocked, setIsLocationLocked] = useState(false);
  const [isProviderLocked, setIsProviderLocked] = useState(false);
  const [isServiceLocked, setIsServiceLocked] = useState(false);

  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split("T")[0]);
  const [selectedTime, setSelectedTime] = useState<string>("10:00");

  // Client info
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [bookingNotes, setBookingNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [completedBooking, setCompletedBooking] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [formSlug]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sRes, pRes, lRes, formsRes] = await Promise.all([
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/booking-forms").catch(() => [])
      ]);

      const servicesArr = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);
      const providersArr = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      const locationsArr = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      const formsArr = Array.isArray(formsRes) ? formsRes : (formsRes?.data ?? []);

      setAllServices(servicesArr);
      setAllProviders(providersArr);
      setAllLocations(locationsArr);

      const normalizeSlug = (str: string) => str.toLowerCase().replace(/[^a-z0-9]/g, "");
      const matched = formsArr.find((f: any) => 
        f.slug === formSlug || 
        normalizeSlug(f.slug) === normalizeSlug(formSlug)
      ) || {
        name: formSlug === 'quick-consult' ? 'Quick Consult' : 'Standard Booking',
        slug: formSlug,
        widget_type: formSlug === 'quick-consult' ? 'modal' : 'full'
      };

      setFormData(matched);

      // Extract predefined values from backend setup or URL parameters
      const pv = matched.predefined_values || {};
      const paramLocId = searchParams.get("location_id") || pv.location_id;
      const paramProvId = searchParams.get("provider_id") || pv.provider_id;
      const paramSvcId = searchParams.get("service_id") || pv.service_id;

      let locLocked = false;
      let provLocked = false;
      let svcLocked = false;

      let activeLoc: LocationItem | null = locationsArr.length > 0 ? locationsArr[0] : null;
      let activeProv: ProviderItem | null = providersArr.length > 0 ? providersArr[0] : null;
      let activeSvc: ServiceItem | null = servicesArr.length > 0 ? servicesArr[0] : null;

      if (paramLocId) {
        const found = locationsArr.find((l: LocationItem) => String(l.id) === String(paramLocId));
        if (found) {
          activeLoc = found;
          locLocked = true;
          setIsLocationLocked(true);
        }
      }

      if (paramProvId) {
        const found = providersArr.find((p: ProviderItem) => String(p.id) === String(paramProvId));
        if (found) {
          activeProv = found;
          provLocked = true;
          setIsProviderLocked(true);
        }
      }

      if (paramSvcId) {
        const found = servicesArr.find((s: ServiceItem) => String(s.id) === String(paramSvcId));
        if (found) {
          activeSvc = found;
          svcLocked = true;
          setIsServiceLocked(true);
        }
      }

      setSelectedLocation(activeLoc);
      setSelectedProvider(activeProv);
      setSelectedService(activeSvc);

      // Auto-advance to Step 2 (Date & Time) if Location, Provider, and Service are pre-selected
      if ((locLocked || locationsArr.length <= 1) && (provLocked || providersArr.length <= 1) && activeSvc) {
        setStep(2);
      }

      if (matched.widget_type === 'modal') {
        setModalOpen(true);
      }
    } catch {
      toast.error("Failed to initialize booking form.");
    } finally {
      setLoading(false);
    }
  };

  // ── Relational Calculation Filters ──────────────────────────────────

  const availableLocations = allLocations.filter(loc => {
    if (selectedService && loc.service_ids && loc.service_ids.length > 0) {
      if (!loc.service_ids.includes(selectedService.id)) return false;
    }
    if (selectedProvider && loc.provider_ids && loc.provider_ids.length > 0) {
      if (!loc.provider_ids.includes(selectedProvider.id)) return false;
    }
    return true;
  });

  const availableServices = allServices.filter(svc => {
    if (selectedLocation && selectedLocation.service_ids && selectedLocation.service_ids.length > 0) {
      if (!selectedLocation.service_ids.includes(svc.id)) return false;
    }
    if (selectedProvider) {
      if (svc.provider_ids && svc.provider_ids.length > 0 && !svc.provider_ids.includes(selectedProvider.id)) {
        return false;
      }
      if (selectedProvider.service_ids && selectedProvider.service_ids.length > 0 && !selectedProvider.service_ids.includes(svc.id)) {
        return false;
      }
    }
    return true;
  });

  const availableProviders = allProviders.filter(prov => {
    if (selectedLocation && selectedLocation.provider_ids && selectedLocation.provider_ids.length > 0) {
      if (!selectedLocation.provider_ids.includes(prov.id)) return false;
    }
    if (selectedService) {
      if (selectedService.provider_ids && selectedService.provider_ids.length > 0 && !selectedService.provider_ids.includes(prov.id)) {
        return false;
      }
      if (prov.service_ids && prov.service_ids.length > 0 && !prov.service_ids.includes(selectedService.id)) {
        return false;
      }
    }
    return true;
  });

  const handleSelectService = (svc: ServiceItem) => {
    setSelectedService(svc);

    if (!isProviderLocked) {
      const validProvidersForSvc = allProviders.filter(prov => {
        if (selectedLocation && selectedLocation.provider_ids && selectedLocation.provider_ids.length > 0) {
          if (!selectedLocation.provider_ids.includes(prov.id)) return false;
        }
        if (svc.provider_ids && svc.provider_ids.length > 0 && !svc.provider_ids.includes(prov.id)) return false;
        if (prov.service_ids && prov.service_ids.length > 0 && !prov.service_ids.includes(svc.id)) return false;
        return true;
      });

      if (selectedProvider && !validProvidersForSvc.some(p => p.id === selectedProvider.id)) {
        setSelectedProvider(validProvidersForSvc.length > 0 ? validProvidersForSvc[0] : null);
      }
    }
  };

  const handleSelectProvider = (prov: ProviderItem) => {
    setSelectedProvider(prov);

    if (!isServiceLocked) {
      const validServicesForProv = allServices.filter(svc => {
        if (selectedLocation && selectedLocation.service_ids && selectedLocation.service_ids.length > 0) {
          if (!selectedLocation.service_ids.includes(svc.id)) return false;
        }
        if (svc.provider_ids && svc.provider_ids.length > 0 && !svc.provider_ids.includes(prov.id)) return false;
        if (prov.service_ids && prov.service_ids.length > 0 && !prov.service_ids.includes(svc.id)) return false;
        return true;
      });

      if (selectedService && !validServicesForProv.some(s => s.id === selectedService.id)) {
        setSelectedService(validServicesForProv.length > 0 ? validServicesForProv[0] : null);
      }
    }
  };

  const handleCreateBookingSubmit = async () => {
    if (!selectedService || !selectedProvider || !clientName || !clientEmail) {
      toast.error("Please fill in your name, email, service, and provider.");
      return;
    }

    setSubmitting(true);
    try {
      let clientId = 1;
      try {
        const clientRes = await apiClient.post<any>("/api/admin/clients", {
          name: clientName,
          email: clientEmail,
          phone: clientPhone || null
        });
        clientId = clientRes?.id || clientRes?.data?.id || 1;
      } catch {
        clientId = 1;
      }

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
        location: selectedLocation?.name || "Main Branch",
        date: selectedDate,
        time: selectedTime,
        clientName,
        clientEmail
      });

      setStep(4);
      toast.success("Booking submitted!");
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
          <p className="text-sm text-muted-foreground font-medium">Loading form...</p>
        </div>
      </div>
    );
  }

  const isModalWidget = formData?.widget_type === 'modal';

  const renderBookingWizardContent = () => (
    <div className="space-y-6">
      {/* Locked Presets Banner */}
      {(isLocationLocked || isProviderLocked || isServiceLocked) && (
        <div className="p-3.5 rounded-xl border bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-200 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold block">Pre-configured Booking Session</span>
              <span className="text-[11px] opacity-90">
                {isProviderLocked && `Provider: ${selectedProvider?.name}`}
                {isLocationLocked && ` • Location: ${selectedLocation?.name}`}
                {isServiceLocked && ` • Service: ${selectedService?.name}`}
              </span>
            </div>
          </div>
          <Badge className="bg-amber-600 text-white font-bold text-[10px]">Pre-selected</Badge>
        </div>
      )}

      {/* Wizard Stepper */}
      {step < 4 && (
        <div className="flex items-center justify-between border-b pb-4">
          <div className={`flex items-center gap-2 text-xs font-bold ${step >= 1 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">1</span>
            <span>{isServiceLocked ? "Service Confirmed" : "Select Service"}</span>
          </div>
          <div className="h-0.5 w-8 bg-muted" />
          <div className={`flex items-center gap-2 text-xs font-bold ${step >= 2 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">2</span>
            <span>Date & Time</span>
          </div>
          <div className="h-0.5 w-8 bg-muted" />
          <div className={`flex items-center gap-2 text-xs font-bold ${step >= 3 ? "text-primary" : "text-muted-foreground"}`}>
            <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">3</span>
            <span>Client Details</span>
          </div>
        </div>
      )}

      {/* Step 1: Relational Service Selection Only (Location and Provider selections are COMPLETELY OMITTED when pre-selected) */}
      {step === 1 && (
        <div className="space-y-6">
          {/* Location Selector (ONLY if NOT pre-selected/locked) */}
          {!isLocationLocked && allLocations.length > 1 && (
            <div className="space-y-2">
              <Label className="text-xs font-bold text-foreground">Location</Label>
              <Select
                value={selectedLocation ? String(selectedLocation.id) : ""}
                onValueChange={(val) => {
                  const found = allLocations.find(l => String(l.id) === val);
                  if (found) setSelectedLocation(found);
                }}
              >
                <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="Select location" /></SelectTrigger>
                <SelectContent>
                  {allLocations.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Services List (ONLY if NOT pre-selected/locked) */}
          {!isServiceLocked && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Available Services ({availableServices.length})
                </h3>
                {isProviderLocked && (
                  <span className="text-xs text-primary font-semibold">
                    Offered by {selectedProvider?.name}
                  </span>
                )}
              </div>

              <div className="grid gap-3 max-h-[280px] overflow-y-auto pr-1">
                {availableServices.map((svc) => {
                  const isSelected = selectedService?.id === svc.id;
                  return (
                    <div
                      key={svc.id}
                      onClick={() => handleSelectService(svc)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                        isSelected
                          ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                          : "hover:border-primary/50 bg-card"
                      }`}
                    >
                      <div>
                        <div className="font-bold text-foreground text-sm">{svc.name}</div>
                        <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {svc.duration} mins</span>
                          {svc.price && <span className="font-semibold text-emerald-600">${Number(svc.price).toFixed(2)}</span>}
                        </div>
                      </div>
                      <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                        {isSelected && <CheckCircle2 className="w-4 h-4" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Provider Selection (ONLY if NOT pre-selected/locked) */}
          {!isProviderLocked && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Select Service Provider ({availableProviders.length})
                </h3>
              </div>

              <div className="grid grid-cols-2 gap-3 max-h-[200px] overflow-y-auto pr-1">
                {availableProviders.map((p) => {
                  const isSelected = selectedProvider?.id === p.id;
                  return (
                    <div
                      key={p.id}
                      onClick={() => handleSelectProvider(p)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center gap-3 ${
                        isSelected
                          ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                          : "hover:border-primary/50 bg-card"
                      }`}
                    >
                      <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {p.name.charAt(0)}
                      </div>
                      <div className="font-semibold text-xs truncate">{p.name}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <Button
            className="w-full h-11 text-sm font-bold gap-2 mt-4"
            disabled={!selectedService || !selectedProvider}
            onClick={() => setStep(2)}
          >
            Continue to Date & Time <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Step 2: Date & Time */}
      {step === 2 && (
        <div className="space-y-5">
          <div>
            <Label className="text-sm font-bold mb-2 block">Appointment Date</Label>
            <Input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} className="h-10" />
          </div>

          <div>
            <Label className="text-sm font-bold mb-2 block">Available Start Time</Label>
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

          <div className="p-4 rounded-xl bg-muted/40 border text-xs space-y-1.5">
            <div className="font-bold flex items-center gap-2 text-foreground">
              <CalendarCheck className="w-4 h-4 text-primary" /> Reservation Details
            </div>
            <div className="text-muted-foreground">{selectedService?.name} with {selectedProvider?.name}</div>
            <div className="text-foreground font-semibold pt-1">{selectedDate} at {selectedTime} ({selectedService?.duration} mins)</div>
          </div>

          <div className="flex gap-3 pt-2">
            {!isLocationLocked && !isProviderLocked && (
              <Button variant="outline" className="flex-1 h-11" onClick={() => setStep(1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold" onClick={() => setStep(3)}>
              Continue <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Client Info */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="pub_name" className="text-xs font-semibold">Full Name *</Label>
            <Input id="pub_name" placeholder="John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pub_email" className="text-xs font-semibold">Email Address *</Label>
            <Input id="pub_email" type="email" placeholder="john@example.com" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pub_phone" className="text-xs font-semibold">Phone Number</Label>
            <Input id="pub_phone" placeholder="(555) 000-0000" value={clientPhone} onChange={(e) => setClientPhone(e.target.value)} className="h-10" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pub_notes" className="text-xs font-semibold">Special Requests / Notes</Label>
            <Textarea id="pub_notes" placeholder="Notes for your provider..." value={bookingNotes} onChange={(e) => setBookingNotes(e.target.value)} rows={3} />
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
            <p className="text-xs text-muted-foreground mt-1">Thank you {completedBooking.clientName}. Your appointment has been registered.</p>
          </div>

          <div className="p-4 rounded-xl border bg-card text-left text-xs space-y-2 max-w-sm mx-auto shadow-xs">
            <div className="flex justify-between text-muted-foreground border-b pb-2">
              <span>Booking Ref</span>
              <span className="font-mono font-bold text-foreground">#{completedBooking.id}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Service</span>
              <span className="font-semibold text-foreground">{completedBooking.service}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Provider</span>
              <span className="font-semibold text-foreground">{completedBooking.provider}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Date & Time</span>
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
              <p className="text-xs text-muted-foreground">Pre-configured Booking Intake Engine</p>
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
              <CardDescription>Select your desired service and appointment time.</CardDescription>
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
