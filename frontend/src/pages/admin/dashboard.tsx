import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarCheck,
  Clock,
  DollarSign,
  Users,
  MessageSquare,
  Plus,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  SlidersHorizontal,
  ChevronRight,
  TrendingUp,
  Receipt,
  Scissors,
  RefreshCw,
  Globe,
  BellRing
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MobilePageShell } from '@/components/ui/mobile-page-shell';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { apiClient } from '@/lib/api';

interface BookingRecord {
  id: number | string;
  client_name?: string;
  service_name?: string;
  provider_name?: string;
  start_time: string;
  end_time?: string;
  status: string;
  total_price?: number;
  client_phone?: string;
}

interface ClientRecord {
  id: number | string;
  name: string;
  email?: string;
  phone?: string;
  created_at?: string;
}

interface InvoiceRecord {
  id: number | string;
  invoice_number?: string;
  total: number;
  balance?: number;
  status: string;
  client_name?: string;
}

interface ServiceRecord {
  id: number | string;
  name: string;
  duration: number;
  price: number;
  is_active?: boolean;
}

// Configurable Widget Definition
export interface DashboardWidgetConfig {
  id: string;
  title: string;
  description: string;
  enabled: boolean;
}

const DEFAULT_WIDGETS: DashboardWidgetConfig[] = [
  { id: 'metrics_overview', title: 'Core Metrics Banner', description: 'Key performance indicators: bookings, revenue, clients, active inquiries', enabled: true },
  { id: 'today_agenda', title: "Today's Agenda & Appointments", description: 'Scheduled client appointments with 1-tap links directly into calendar', enabled: true },
  { id: 'quick_actions', title: 'Quick Operations & Shortcuts', description: '1-tap shortcuts to book, invoice, message, or manage services', enabled: true },
  { id: 'revenue_summary', title: 'Financial & Billing Snapshot', description: 'Real-time invoice collections, paid totals, and overdue balances', enabled: true },
  { id: 'arrivals_lobby', title: 'Live Lobby & Client Arrivals', description: 'Clients checked-in or waiting in reception with chime alert link', enabled: true },
  { id: 'recent_clients', title: 'Recent Client Registrations', description: 'New clients added with direct phone and profile shortcuts', enabled: true },
  { id: 'popular_services', title: 'Service Catalog Highlights', description: 'Top active services and standard treatment durations', enabled: true },
];

const STORAGE_KEY = 'fastapi_bookings_dashboard_widgets_v1';

export default function DashboardPage() {
  const navigate = useNavigate();

  // Data states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [bookings, setBookings] = useState<BookingRecord[]>([]);
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [invoices, setInvoices] = useState<InvoiceRecord[]>([]);
  const [services, setServices] = useState<ServiceRecord[]>([]);
  const [arrivalsCount, setArrivalsCount] = useState<number>(0);
  const [arrivalsList, setArrivalsList] = useState<any[]>([]);

  // Widget Preferences
  const [widgets, setWidgets] = useState<DashboardWidgetConfig[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // Merge with defaults in case new widgets were introduced
          return DEFAULT_WIDGETS.map((def) => {
            const found = parsed.find((p: any) => p.id === def.id);
            return found ? { ...def, enabled: found.enabled } : def;
          });
        }
      }
    } catch {
      // ignore JSON error
    }
    return DEFAULT_WIDGETS;
  });

  const [customizeOpen, setCustomizeOpen] = useState(false);

  // Fetch live operational data
  const loadDashboardData = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);

    try {
      const [bkgRes, cliRes, invRes, srvRes, arrRes] = await Promise.allSettled([
        apiClient.get<any>('/api/admin/bookings'),
        apiClient.get<any>('/api/admin/clients'),
        apiClient.get<any>('/api/admin/invoices'),
        apiClient.get<any>('/api/admin/services'),
        apiClient.get<any>('/api/admin/sms/arrivals'),
      ]);

      if (bkgRes.status === 'fulfilled') {
        const raw = bkgRes.value;
        const list = Array.isArray(raw) ? raw : raw?.data || raw?.items || [];
        setBookings(list);
      }

      if (cliRes.status === 'fulfilled') {
        const raw = cliRes.value;
        const list = Array.isArray(raw) ? raw : raw?.data || raw?.items || [];
        setClients(list);
      }

      if (invRes.status === 'fulfilled') {
        const raw = invRes.value;
        const list = Array.isArray(raw) ? raw : raw?.data || raw?.items || [];
        setInvoices(list);
      }

      if (srvRes.status === 'fulfilled') {
        const raw = srvRes.value;
        const list = Array.isArray(raw) ? raw : raw?.data || raw?.items || [];
        setServices(list);
      }

      if (arrRes.status === 'fulfilled') {
        const raw = arrRes.value;
        const list = Array.isArray(raw) ? raw : raw?.data || [];
        const active = list.filter((a: any) => a.status === 'waiting' || a.status === 'arrived');
        setArrivalsCount(active.length);
        setArrivalsList(list.slice(0, 4));
      }
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const toggleWidget = (id: string) => {
    setWidgets((prev) => {
      const updated = prev.map((w) => (w.id === id ? { ...w, enabled: !w.enabled } : w));
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  };

  const isWidgetEnabled = (id: string) => {
    const found = widgets.find((w) => w.id === id);
    return found ? found.enabled : true;
  };

  // Calculations
  const todayStr = useMemo(() => new Date().toISOString().split('T')[0], []);

  const todayBookings = useMemo(() => {
    return bookings.filter((b) => {
      if (!b.start_time) return false;
      return b.start_time.startsWith(todayStr);
    });
  }, [bookings, todayStr]);

  const upcomingBookings = useMemo(() => {
    const now = new Date();
    return bookings
      .filter((b) => {
        if (!b.start_time) return false;
        return new Date(b.start_time) >= now && b.status !== 'cancelled';
      })
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
      .slice(0, 5);
  }, [bookings]);

  const financialStats = useMemo(() => {
    let totalInvoiced = 0;
    let totalOutstanding = 0;
    let paidCount = 0;

    invoices.forEach((inv) => {
      const total = Number(inv.total || 0);
      const bal = Number(inv.balance ?? (inv.status === 'Paid' ? 0 : total));
      totalInvoiced += total;
      totalOutstanding += Math.max(0, bal);
      if (inv.status === 'Paid') paidCount++;
    });

    return { totalInvoiced, totalOutstanding, paidCount };
  }, [invoices]);

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <MobilePageShell
      title="Dashboard"
      description="Real-time operational summary, appointments, and shortcuts."
      actions={
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadDashboardData(true)}
            disabled={refreshing || loading}
            className="h-10 min-h-[44px] gap-2 touch-manipulation flex-1 sm:flex-initial"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>

          {/* Customize Cards Modal */}
          <Dialog open={customizeOpen} onOpenChange={setCustomizeOpen}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-10 min-h-[44px] gap-2 border-primary/30 text-primary hover:bg-primary/5 touch-manipulation flex-1 sm:flex-initial"
              >
                <SlidersHorizontal className="w-4 h-4" />
                <span>Customize Cards</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[480px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <SlidersHorizontal className="w-5 h-5 text-primary" />
                  Customize Dashboard Cards
                </DialogTitle>
                <DialogDescription>
                  Choose which operational cards and widgets appear on your dashboard. Preferences are saved automatically.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 py-3 max-h-[60vh] overflow-y-auto pr-1">
                {widgets.map((widget) => (
                  <div
                    key={widget.id}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card/60 hover:bg-muted/40 transition-colors"
                  >
                    <div className="space-y-0.5 pr-3">
                      <Label htmlFor={`toggle-${widget.id}`} className="text-sm font-semibold cursor-pointer">
                        {widget.title}
                      </Label>
                      <p className="text-xs text-muted-foreground">{widget.description}</p>
                    </div>
                    <Switch
                      id={`toggle-${widget.id}`}
                      checked={widget.enabled}
                      onCheckedChange={() => toggleWidget(widget.id)}
                    />
                  </div>
                ))}
              </div>

              <DialogFooter>
                <Button
                  onClick={() => setCustomizeOpen(false)}
                  className="w-full sm:w-auto min-h-[44px]"
                >
                  Done
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* New Booking Primary Action */}
          <Button
            size="sm"
            onClick={() => navigate('/admin/calendar')}
            className="h-10 min-h-[44px] gap-2 bg-primary text-primary-foreground font-semibold shadow-sm touch-manipulation w-full sm:w-auto"
          >
            <Plus className="w-4 h-4" />
            <span>New Booking</span>
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* ============================================================ */}
        {/* 1. CORE METRICS OVERVIEW BANNER                              */}
        {/* ============================================================ */}
        {isWidgetEnabled('metrics_overview') && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            {/* Today's Bookings Card */}
            <Card
              onClick={() => navigate('/admin/calendar')}
              className="cursor-pointer hover:border-primary/50 transition-all shadow-xs group touch-manipulation"
            >
              <CardContent className="p-4 sm:p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Today's Bookings</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                      {todayBookings.length}
                    </span>
                    <span className="text-xs text-muted-foreground">scheduled</span>
                  </div>
                  <div className="flex items-center gap-1 mt-2 text-xs text-primary font-medium group-hover:underline">
                    <span>View Calendar</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-primary/10 text-primary group-hover:scale-105 transition-transform">
                  <CalendarCheck className="w-6 h-6" />
                </div>
              </CardContent>
            </Card>

            {/* Invoiced & Revenue Card */}
            <Card
              onClick={() => navigate('/admin/finance/invoices')}
              className="cursor-pointer hover:border-emerald-500/50 transition-all shadow-xs group touch-manipulation"
            >
              <CardContent className="p-4 sm:p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Billing</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                      ${financialStats.totalInvoiced.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mt-2 text-xs text-emerald-600 dark:text-emerald-400 font-medium group-hover:underline">
                    <span>${financialStats.totalOutstanding.toFixed(0)} unpaid balance</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-600 group-hover:scale-105 transition-transform">
                  <DollarSign className="w-6 h-6" />
                </div>
              </CardContent>
            </Card>

            {/* Total Clients Card */}
            <Card
              onClick={() => navigate('/admin/clients')}
              className="cursor-pointer hover:border-blue-500/50 transition-all shadow-xs group touch-manipulation"
            >
              <CardContent className="p-4 sm:p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Client Base</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                      {clients.length}
                    </span>
                    <span className="text-xs text-muted-foreground">registered</span>
                  </div>
                  <div className="flex items-center gap-1 mt-2 text-xs text-blue-600 dark:text-blue-400 font-medium group-hover:underline">
                    <span>Manage Directory</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-blue-500/10 text-blue-600 group-hover:scale-105 transition-transform">
                  <Users className="w-6 h-6" />
                </div>
              </CardContent>
            </Card>

            {/* SMS & Arrivals Waiting Card */}
            <Card
              onClick={() => navigate('/admin/sms-assistant?tab=arrivals')}
              className="cursor-pointer hover:border-amber-500/50 transition-all shadow-xs group touch-manipulation"
            >
              <CardContent className="p-4 sm:p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">SMS & Reception</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                      {arrivalsCount > 0 ? `${arrivalsCount} Waiting` : 'Active'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mt-2 text-xs text-amber-600 dark:text-amber-400 font-medium group-hover:underline">
                    <span>Open SMS Assistant</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-amber-500/10 text-amber-600 group-hover:scale-105 transition-transform">
                  <MessageSquare className="w-6 h-6" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* ============================================================ */}
        {/* 2. MAIN SPLIT: TODAY'S AGENDA + QUICK SHORTCUTS              */}
        {/* ============================================================ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (2/3 on desktop): Today & Upcoming Agenda */}
          {isWidgetEnabled('today_agenda') && (
            <Card className="lg:col-span-2 border shadow-xs flex flex-col">
              <CardHeader className="p-4 sm:p-5 border-b flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                    <Clock className="w-5 h-5 text-primary" />
                    Today & Upcoming Appointments
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground mt-0.5">
                    Click any appointment to inspect details or jump to the calendar.
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/calendar')}
                  className="text-xs text-primary gap-1 font-semibold h-8"
                >
                  <span>Full Calendar</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </CardHeader>

              <CardContent className="p-0 flex-1">
                {upcomingBookings.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground space-y-3">
                    <CalendarCheck className="w-10 h-10 mx-auto text-muted-foreground/50" />
                    <div>
                      <p className="text-sm font-semibold">No upcoming appointments scheduled</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Ready for new bookings.</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate('/admin/calendar')}
                      className="min-h-[40px] text-xs gap-1.5"
                    >
                      <Plus className="w-3.5 h-3.5" /> Book Client Now
                    </Button>
                  </div>
                ) : (
                  <div className="divide-y">
                    {upcomingBookings.map((bkg) => (
                      <div
                        key={bkg.id}
                        onClick={() => navigate('/admin/calendar')}
                        className="p-4 sm:p-5 flex items-center justify-between hover:bg-muted/40 transition-colors cursor-pointer group touch-manipulation"
                      >
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex flex-col items-center justify-center font-bold shrink-0">
                            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                              {formatDate(bkg.start_time).split(' ')[0]}
                            </span>
                            <span className="text-sm">
                              {formatDate(bkg.start_time).split(' ')[1] || 'Today'}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm text-foreground truncate">
                                {bkg.client_name || 'Walk-in Client'}
                              </span>
                              <Badge
                                variant={bkg.status === 'confirmed' ? 'default' : 'secondary'}
                                className="text-[10px] uppercase font-semibold px-1.5 py-0"
                              >
                                {bkg.status}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                              {bkg.service_name || 'Standard Service'} {bkg.provider_name ? `• with ${bkg.provider_name}` : ''}
                            </p>
                          </div>
                        </div>

                        <div className="text-right shrink-0 pl-2">
                          <div className="font-semibold text-sm text-foreground">
                            {formatTime(bkg.start_time)}
                          </div>
                          {bkg.total_price ? (
                            <span className="text-xs text-muted-foreground">${bkg.total_price}</span>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Right Column (1/3 on desktop): Quick Operations & Module Shortcuts */}
          {isWidgetEnabled('quick_actions') && (
            <Card className="border shadow-xs flex flex-col">
              <CardHeader className="p-4 sm:p-5 border-b">
                <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-amber-500" />
                  Quick Actions
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Direct shortcuts to active operations.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-4 sm:p-5 space-y-2.5 flex-1">
                <button
                  type="button"
                  onClick={() => navigate('/admin/calendar')}
                  className="w-full p-3 rounded-lg border bg-card hover:bg-primary/5 hover:border-primary/40 text-left transition-all flex items-center justify-between group min-h-[48px] touch-manipulation"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <CalendarCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors">
                        Open Calendar
                      </div>
                      <div className="text-[11px] text-muted-foreground">Schedule or reschedule slots</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/admin/sms-assistant?tab=arrivals')}
                  className="w-full p-3 rounded-lg border bg-card hover:bg-amber-500/5 hover:border-amber-500/40 text-left transition-all flex items-center justify-between group min-h-[48px] touch-manipulation"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600">
                      <MessageSquare className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground group-hover:text-amber-600 transition-colors">
                        SMS Assistant & Arrivals
                      </div>
                      <div className="text-[11px] text-muted-foreground">Inbound chats & lobby chime</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-amber-600 transition-colors" />
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/admin/finance/invoices')}
                  className="w-full p-3 rounded-lg border bg-card hover:bg-emerald-500/5 hover:border-emerald-500/40 text-left transition-all flex items-center justify-between group min-h-[48px] touch-manipulation"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600">
                      <Receipt className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground group-hover:text-emerald-600 transition-colors">
                        Invoices & Payments
                      </div>
                      <div className="text-[11px] text-muted-foreground">Process billing & receipts</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-emerald-600 transition-colors" />
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/admin/catalog/services')}
                  className="w-full p-3 rounded-lg border bg-card hover:bg-indigo-500/5 hover:border-indigo-500/40 text-left transition-all flex items-center justify-between group min-h-[48px] touch-manipulation"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600">
                      <Scissors className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground group-hover:text-indigo-600 transition-colors">
                        Services Catalog
                      </div>
                      <div className="text-[11px] text-muted-foreground">Configure treatments & pricing</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-indigo-600 transition-colors" />
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/admin/website')}
                  className="w-full p-3 rounded-lg border bg-card hover:bg-teal-500/5 hover:border-teal-500/40 text-left transition-all flex items-center justify-between group min-h-[48px] touch-manipulation"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-teal-500/10 text-teal-600">
                      <Globe className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground group-hover:text-teal-600 transition-colors">
                        Website Builder
                      </div>
                      <div className="text-[11px] text-muted-foreground">Edit live booking website</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-teal-600 transition-colors" />
                </button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* ============================================================ */}
        {/* 3. SECOND ROW: BILLING SNAPSHOT + CLIENTS & SERVICES         */}
        {/* ============================================================ */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {/* Live Lobby & Arrivals Card */}
          {isWidgetEnabled('arrivals_lobby') && (
            <Card className="border shadow-xs">
              <CardHeader className="p-4 sm:p-5 border-b flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <BellRing className="w-5 h-5 text-amber-500" />
                    Lobby & Arrivals
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Clients checked in at reception
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/sms-assistant?tab=arrivals')}
                  className="text-xs text-primary h-8"
                >
                  Arrivals ({arrivalsCount})
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {arrivalsList.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted-foreground">
                    No clients currently waiting in the lobby.
                  </div>
                ) : (
                  <div className="divide-y">
                    {arrivalsList.map((arr: any) => (
                      <div
                        key={arr.id}
                        onClick={() => navigate('/admin/sms-assistant?tab=arrivals')}
                        className="p-3.5 sm:p-4 flex items-center justify-between hover:bg-muted/30 transition-colors cursor-pointer"
                      >
                        <div className="min-w-0">
                          <p className="font-semibold text-xs text-foreground truncate">
                            {arr.client_name || arr.customer_phone || 'Client Arrival'}
                          </p>
                          <p className="text-[11px] text-muted-foreground truncate">
                            {arr.location_name || 'Location 1 - Main Center'} • {arr.status || 'waiting'}
                          </p>
                        </div>
                        <Badge
                          variant="outline"
                          className="text-[10px] capitalize shrink-0 bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30"
                        >
                          {arr.status || 'waiting'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
          {/* Revenue & Collections Card */}
          {isWidgetEnabled('revenue_summary') && (
            <Card className="border shadow-xs">
              <CardHeader className="p-4 sm:p-5 border-b flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                    Financial Collections
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Invoicing balance summary
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/finance/invoices')}
                  className="text-xs text-primary h-8"
                >
                  Invoices
                </Button>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-muted/40 border">
                    <span className="text-[11px] font-medium text-muted-foreground uppercase">Paid Invoices</span>
                    <p className="text-xl font-bold text-foreground mt-0.5">{financialStats.paidCount}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/40 border">
                    <span className="text-[11px] font-medium text-muted-foreground uppercase">Outstanding</span>
                    <p className="text-xl font-bold text-destructive mt-0.5">
                      ${financialStats.totalOutstanding.toFixed(0)}
                    </p>
                  </div>
                </div>

                <div className="p-3.5 rounded-lg border bg-emerald-500/5 border-emerald-500/20 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                    <div className="text-xs">
                      <span className="font-semibold text-foreground">Billing Status Healthy</span>
                      <p className="text-muted-foreground text-[11px]">Direct integration with Stripe & cash flow</p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate('/admin/finance/payments')}
                    className="text-xs h-8 min-h-[36px]"
                  >
                    View
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Recent Clients Snapshot */}
          {isWidgetEnabled('recent_clients') && (
            <Card className="border shadow-xs">
              <CardHeader className="p-4 sm:p-5 border-b flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <Users className="w-5 h-5 text-blue-600" />
                    Recent Clients
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Latest registrations
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/clients')}
                  className="text-xs text-primary h-8"
                >
                  All ({clients.length})
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {clients.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted-foreground">
                    No clients registered yet.
                  </div>
                ) : (
                  <div className="divide-y">
                    {clients.slice(0, 4).map((client) => (
                      <div
                        key={client.id}
                        onClick={() => navigate('/admin/clients')}
                        className="p-3.5 sm:p-4 flex items-center justify-between hover:bg-muted/30 transition-colors cursor-pointer"
                      >
                        <div className="min-w-0">
                          <p className="font-semibold text-xs text-foreground truncate">{client.name}</p>
                          <p className="text-[11px] text-muted-foreground truncate">{client.phone || client.email || 'No contact info'}</p>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Services Catalog Highlights */}
          {isWidgetEnabled('popular_services') && (
            <Card className="border shadow-xs">
              <CardHeader className="p-4 sm:p-5 border-b flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <Scissors className="w-5 h-5 text-indigo-600" />
                    Active Services
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Catalog items & durations
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/catalog/services')}
                  className="text-xs text-primary h-8"
                >
                  Catalog
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {services.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted-foreground">
                    No services configured.
                  </div>
                ) : (
                  <div className="divide-y">
                    {services.slice(0, 4).map((srv) => (
                      <div
                        key={srv.id}
                        onClick={() => navigate('/admin/catalog/services')}
                        className="p-3.5 sm:p-4 flex items-center justify-between hover:bg-muted/30 transition-colors cursor-pointer"
                      >
                        <div className="min-w-0">
                          <p className="font-semibold text-xs text-foreground truncate">{srv.name}</p>
                          <p className="text-[11px] text-muted-foreground">{srv.duration} mins</p>
                        </div>
                        <Badge variant="outline" className="font-mono text-xs shrink-0">
                          ${srv.price}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </MobilePageShell>
  );
}
