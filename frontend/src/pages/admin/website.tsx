import { useState, useEffect, useRef } from "react";
import {
  Globe,
  Eye,
  Send,
  Save,
  Monitor,
  Tablet,
  Smartphone,
  Sparkles,
  Mic,
  MicOff,
  Plus,
  Trash2,
  Check,
  Wand2,
  Image as ImageIcon,
  RefreshCw,
  CheckCircle2,
  MessageSquare,
  Calendar,
  Link2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import {
  PublicWebsiteView,
  THEMES,
} from "@/pages/public/website-page";
import type { WebsiteConfigData } from "@/pages/public/website-page";

const TEMPLATES = [
  {
    id: "minimalist",
    name: "Modern Minimalist",
    badge: "Clean & Contemporary",
    description: "Sleek lines, airy whitespace, and high contrast typography. Ideal for modern studios and consultants.",
    image: "https://images.unsplash.com/photo-1497366216548-37526070297c?w=400&auto=format&fit=crop&q=80",
  },
  {
    id: "wellness",
    name: "Wellness & Sanctuary",
    badge: "Calming & Organic",
    description: "Gentle curves, soothing pastel gradients, and tranquil zen ambiance. Perfect for spas, massage, and holistic therapies.",
    image: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=400&auto=format&fit=crop&q=80",
  },
  {
    id: "clinical",
    name: "Clinical & Medical",
    badge: "Authoritative & Trust",
    description: "Structured layout with verified credentials, trust badges, and clear clinical focus. Built for clinics and doctors.",
    image: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=400&auto=format&fit=crop&q=80",
  },
  {
    id: "luxury",
    name: "Luxury & Boutique",
    badge: "Refined & Editorial",
    description: "Serif accents, warm gold tones, and couture salon aesthetic. Tailored for high-end beauty salons and lash ateliers.",
    image: "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=400&auto=format&fit=crop&q=80",
  },
];

const CURATED_THEMES = [
  { id: "ocean_slate", name: "Ocean Slate", primary: "#0284c7", bg: "#f8fafc" },
  { id: "emerald_oasis", name: "Emerald Oasis", primary: "#059669", bg: "#f0fdf4" },
  { id: "rose_gold", name: "Rose Gold", primary: "#be185d", bg: "#fff1f2" },
  { id: "royal_indigo", name: "Royal Indigo", primary: "#4338ca", bg: "#eef2ff" },
  { id: "monochrome", name: "Monochrome", primary: "#18181b", bg: "#fafafa" },
];

const CURATED_MEDIA_PHOTOS = [
  {
    name: "Spa Sanctuary & Candles",
    url: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80",
  },
  {
    name: "Clean Modern Studio",
    url: "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1200&q=80",
  },
  {
    name: "Medical Clinic Suite",
    url: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
  },
  {
    name: "Luxury Salon Atelier",
    url: "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1200&q=80",
  },
  {
    name: "Aromatherapy Treatment",
    url: "https://images.unsplash.com/photo-1512290900673-7002fffe935a?auto=format&fit=crop&w=1200&q=80",
  },
  {
    name: "Gentle Facial Care",
    url: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&q=80",
  },
];

export default function WebsiteBuilderPage() {
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [publishing, setPublishing] = useState<boolean>(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);

  // Active Website State
  const [config, setConfig] = useState<WebsiteConfigData>({
    template_id: "minimalist",
    theme_id: "ocean_slate",
    custom_colors: {},
    sections_data: {
      hero: {
        headline: "Elevate Your Wellness & Care",
        subhead: "Experience personalized treatments tailored specifically to your goals.",
        cta_text: "Book Appointment",
        cta_link: "#booking",
        bg_image_url: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1600&q=80",
        enabled: true,
      },
      about: {
        badge: "Our Story",
        headline: "Dedicated to Exceptional Quality",
        story: "Founded with a mission to bring world-class services and mindful care together.",
        image_url: "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1000&q=80",
        enabled: true,
      },
      services: {
        headline: "Signature Services & Treatments",
        subhead: "Explore our top rated sessions crafted to restore balance and vitality.",
        show_prices: true,
        enabled: true,
      },
      booking: {
        headline: "Schedule Your Visit",
        subhead: "Choose your preferred service, date, and time in just a few clicks.",
        embedded_style: "card",
        enabled: true,
      },
      testimonials: {
        headline: "What Our Clients Say",
        subhead: "Trusted by hundreds of happy clients every month.",
        items: [
          {
            name: "Sarah Jenkins",
            role: "Regular Client",
            content: "The attention to detail and relaxing ambiance made all the difference. Booking online was effortless!",
            rating: 5,
          },
          {
            name: "David Miller",
            role: "Verified Client",
            content: "Outstanding service from start to finish. Highly recommend their skilled team.",
            rating: 5,
          },
        ],
        enabled: true,
      },
      contact: {
        headline: "Visit or Reach Out",
        subhead: "We look forward to welcoming you soon.",
        address: "123 Harmony Boulevard, Suite 400",
        phone: "+1 (555) 234-5678",
        email: "hello@example.com",
        hours: "Mon - Sat: 9:00 AM - 7:00 PM\nSunday: Closed",
        enabled: true,
      },
      footer: {
        copyright: `© ${new Date().getFullYear()} All rights reserved.`,
        enabled: true,
      },
      chat_widget: {
        enabled: true,
        invitation_title: "Need help booking?",
        invitation_message: "Hi there! 👋 Have questions about our services or need to book? Chat with us!",
        invitation_delay_seconds: 3,
        show_sms_fallback: true,
      },
    },
    is_published: false,
    seo_title: "My Business | Book Online",
    seo_description: "Book your appointment online effortlessly.",
  });

  const [tenantInfo, setTenantInfo] = useState<{
    name: string;
    subdomain: string;
    email?: string;
    phone?: string;
    address?: string;
    logo_url?: string;
  }>({
    name: "SimplyBook Studio",
    subdomain: "simplydemo",
  });

  const [catalogServices, setCatalogServices] = useState<any[]>([]);

  // Preview Mode: desktop, tablet, mobile
  const [deviceMode, setDeviceMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [mobileView, setMobileView] = useState<"editor" | "preview">("editor");

  // Media Picker Dialog State
  const [mediaPickerOpen, setMediaPickerOpen] = useState<boolean>(false);
  const [mediaTargetField, setMediaTargetField] = useState<"hero" | "about">("hero");
  const [customMediaUrl, setCustomMediaUrl] = useState<string>("");

  // AI Generator Dialog State
  const [aiModalOpen, setAiModalOpen] = useState<boolean>(false);
  const [aiPrompt, setAiPrompt] = useState<string>("");
  const [aiAction, setAiAction] = useState<"generate_full" | "rewrite_section" | "suggest_theme">("generate_full");
  const [aiSectionKey, setAiSectionKey] = useState<string>("hero");
  const [aiGenerating, setAiGenerating] = useState<boolean>(false);
  const [isVoiceListening, setIsVoiceListening] = useState<boolean>(false);
  const speechRecognitionRef = useRef<any>(null);

  // Guided Onboarding Wizard State
  const [wizardOpen, setWizardOpen] = useState<boolean>(false);
  const [wizardStep, setWizardStep] = useState<number>(1);
  const [wizardBizName, setWizardBizName] = useState<string>("");
  const [wizardIndustry, setWizardIndustry] = useState<string>("Wellness & Spa");
  const [wizardTemplate, setWizardTemplate] = useState<string>("wellness");
  const [wizardTheme, setWizardTheme] = useState<string>("emerald_oasis");

  // Cal.com Integration State
  const [calcomStatus, setCalcomStatus] = useState<any>(null);
  const [calcomEventTypes, setCalcomEventTypes] = useState<any[]>([]);

  // Load Initial Draft & Tenant Info
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        // Load draft website config
        const websiteRes: any = await apiClient.get("/api/admin/website");
        if (websiteRes?.ok && websiteRes?.data) {
          setConfig(websiteRes.data);
        }

        // Load business profile for tenant info
        try {
          const profileRes: any = await apiClient.get("/api/admin/business-profile");
          if (profileRes?.ok && profileRes?.data) {
            setTenantInfo({
              name: profileRes.data.name || "My Business",
              subdomain: profileRes.data.subdomain || "simplydemo",
              email: profileRes.data.email,
              phone: profileRes.data.phone,
              address: profileRes.data.address,
              logo_url: profileRes.data.logo_url,
            });
            setWizardBizName(profileRes.data.name || "");
          }
        } catch {
          // ignore fallback
        }

        // Load services
        try {
          const sRes: any = await apiClient.get("/api/admin/services");
          if (sRes?.ok && sRes?.data) {
            setCatalogServices(sRes.data);
          }
        } catch {
          // ignore fallback
        }

        // Load Cal.com integration status & event types
        try {
          const calStatus: any = await apiClient.get("/api/admin/integrations/calcom/status");
          if (calStatus?.ok && calStatus?.data) {
            setCalcomStatus(calStatus.data);
          }
        } catch {
          // ignore fallback
        }

        try {
          const calEvents: any = await apiClient.get("/api/admin/integrations/calcom/event-types");
          if (calEvents?.ok && calEvents?.data) {
            setCalcomEventTypes(calEvents.data);
          }
        } catch {
          // ignore fallback
        }
      } catch (err: any) {
        toast.error("Failed to load website configuration: " + err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Track edits
  const updateSection = (sectionName: string, updates: Record<string, any>) => {
    setConfig((prev) => {
      const currentSection = (prev.sections_data as any)?.[sectionName] || {};
      return {
        ...prev,
        sections_data: {
          ...prev.sections_data,
          [sectionName]: {
            ...currentSection,
            ...updates,
          },
        },
      };
    });
    setHasUnsavedChanges(true);
  };

  // Save Draft
  const handleSaveDraft = async () => {
    try {
      setSaving(true);
      const res: any = await apiClient.put("/api/admin/website", {
        template_id: config.template_id,
        theme_id: config.theme_id,
        custom_colors: config.custom_colors,
        sections_data: config.sections_data,
        seo_title: config.seo_title,
        seo_description: config.seo_description,
      });
      if (res?.ok) {
        setConfig(res.data);
        setHasUnsavedChanges(false);
        toast.success("Draft saved successfully!");
      }
    } catch (err: any) {
      toast.error("Failed to save draft: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  // 1-Click Publish / Unpublish
  const handlePublishToggle = async (publish: boolean) => {
    try {
      setPublishing(true);
      const res: any = await apiClient.post("/api/admin/website/publish", {
        is_published: publish,
      });
      if (res?.ok) {
        setConfig((prev) => ({
          ...prev,
          is_published: res.data.is_published,
          published_at: res.data.published_at,
        }));
        setHasUnsavedChanges(false);
        if (publish) {
          toast.success("Website is now LIVE! Visitors can view it at /site");
        } else {
          toast.info("Website has been unpublished.");
        }
      }
    } catch (err: any) {
      toast.error("Publishing error: " + err.message);
    } finally {
      setPublishing(false);
    }
  };

  // Voice Dictation handler
  const toggleVoiceListening = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      toast.error("Voice recognition is not supported in this browser. Please use Google Chrome or Edge.");
      return;
    }

    if (isVoiceListening) {
      speechRecognitionRef.current?.stop();
      setIsVoiceListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        setIsVoiceListening(true);
        toast.info("Listening... Speak your prompt clearly.");
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setAiPrompt((prev) => (prev ? `${prev} ${transcript}` : transcript));
          toast.success("Voice captured: " + transcript);
        }
        setIsVoiceListening(false);
      };

      recognition.onerror = (event: any) => {
        setIsVoiceListening(false);
        toast.error("Voice recognition error: " + event.error);
      };

      recognition.onend = () => {
        setIsVoiceListening(false);
      };

      speechRecognitionRef.current = recognition;
      recognition.start();
    } catch (e: any) {
      setIsVoiceListening(false);
      toast.error("Could not start microphone: " + e.message);
    }
  };

  // AI Generation trigger
  const handleRunAi = async () => {
    if (!aiPrompt.trim()) {
      toast.error("Please enter a prompt or speak your requirements.");
      return;
    }

    try {
      setAiGenerating(true);
      const res: any = await apiClient.post("/api/admin/website/ai-generate", {
        prompt: aiPrompt,
        action: aiAction,
        section_key: aiSectionKey,
      });

      if (res?.ok) {
        if (aiAction === "generate_full" && res.generated_sections) {
          setConfig((prev) => ({
            ...prev,
            template_id: res.suggested_template || prev.template_id,
            theme_id: res.suggested_theme || prev.theme_id,
            sections_data: res.generated_sections,
          }));
          toast.success("Full website copy and layout generated!");
        } else if (aiAction === "rewrite_section" && res.rewritten_text) {
          updateSection(aiSectionKey, {
            headline: res.rewritten_text,
            story: res.rewritten_text,
          });
          toast.success(`Rewrote ${aiSectionKey} successfully!`);
        } else if (aiAction === "suggest_theme") {
          setConfig((prev) => ({
            ...prev,
            template_id: res.suggested_template || prev.template_id,
            theme_id: res.suggested_theme || prev.theme_id,
          }));
          toast.success(`Theme updated to ${res.suggested_theme} with ${res.suggested_template} template!`);
        }
        setHasUnsavedChanges(true);
        setAiModalOpen(false);
      }
    } catch (err: any) {
      toast.error("AI Generation error: " + err.message);
    } finally {
      setAiGenerating(false);
    }
  };

  // Guided Wizard Completion
  const handleFinishWizard = async () => {
    try {
      setSaving(true);
      // Run AI generate for the selected industry
      const res: any = await apiClient.post("/api/admin/website/ai-generate", {
        prompt: `${wizardBizName || tenantInfo.name} - ${wizardIndustry}`,
        action: "generate_full",
      });

      const newSections = res?.ok && res.generated_sections ? res.generated_sections : config.sections_data;

      setConfig((prev) => ({
        ...prev,
        template_id: wizardTemplate,
        theme_id: wizardTheme,
        sections_data: newSections,
        seo_title: `${wizardBizName || tenantInfo.name} | Book Online`,
      }));

      setHasUnsavedChanges(true);
      setWizardOpen(false);
      toast.success("Guided setup complete! You can now refine details and publish.");
    } catch {
      toast.error("Could not complete wizard.");
    } finally {
      setSaving(false);
    }
  };

  // Open Media Picker for hero or about
  const openMediaPicker = (field: "hero" | "about") => {
    setMediaTargetField(field);
    setCustomMediaUrl("");
    setMediaPickerOpen(true);
  };

  const handleSelectMedia = (url: string) => {
    if (mediaTargetField === "hero") {
      updateSection("hero", { bg_image_url: url });
    } else {
      updateSection("about", { image_url: url });
    }
    setMediaPickerOpen(false);
    toast.success("Image selected!");
  };

  if (loading) {
    return (
      <div className="flex h-96 w-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-slate-500">Loading website builder...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden bg-slate-50">
      {/* ── HEADER BAR ────────────────────────────────────── */}
      <header className="min-h-16 py-2.5 px-3 sm:px-6 border-b bg-white flex flex-wrap items-center justify-between gap-2.5 z-10 shrink-0">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-primary shrink-0" />
            <h1 className="text-base sm:text-lg font-bold tracking-tight">Website Builder</h1>
          </div>

          {/* Status Badge */}
          {config.is_published ? (
            <Badge className="bg-emerald-500 text-white font-medium flex items-center gap-1.5 px-2.5 py-0.5">
              <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
              Published Live
            </Badge>
          ) : hasUnsavedChanges ? (
            <Badge variant="outline" className="text-amber-600 border-amber-300 bg-amber-50">
              ● Draft (Unsaved Changes)
            </Badge>
          ) : (
            <Badge variant="secondary" className="text-slate-600">
              Draft
            </Badge>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => setWizardOpen(true)}
            className="text-xs flex items-center gap-1.5 border-indigo-200 text-indigo-700 bg-indigo-50/50 hover:bg-indigo-100 min-h-[36px]"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            <span className="hidden sm:inline">Guided</span> Wizard
          </Button>

          {/* Mobile Editor/Preview toggle */}
          <div className="flex lg:hidden items-center bg-slate-100 p-0.5 rounded-lg border">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMobileView("editor")}
              className={`h-7 px-2.5 text-xs ${mobileView === "editor" ? "bg-white shadow-xs font-semibold text-primary" : "text-slate-500"}`}
            >
              Editor
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMobileView("preview")}
              className={`h-7 px-2.5 text-xs ${mobileView === "preview" ? "bg-white shadow-xs font-semibold text-primary" : "text-slate-500"}`}
            >
              Preview
            </Button>
          </div>
        </div>

        {/* Device Switcher & Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Device Switcher */}
          <div className="hidden sm:flex items-center bg-slate-100 p-1 rounded-lg border">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeviceMode("desktop")}
              className={`h-8 px-2.5 ${deviceMode === "desktop" ? "bg-white shadow-xs font-semibold text-primary" : "text-slate-500"}`}
              title="Desktop view"
            >
              <Monitor className="h-4 w-4 mr-1" />
              Desktop
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeviceMode("tablet")}
              className={`h-8 px-2.5 ${deviceMode === "tablet" ? "bg-white shadow-xs font-semibold text-primary" : "text-slate-500"}`}
              title="Tablet view"
            >
              <Tablet className="h-4 w-4 mr-1" />
              Tablet
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeviceMode("mobile")}
              className={`h-8 px-2.5 ${deviceMode === "mobile" ? "bg-white shadow-xs font-semibold text-primary" : "text-slate-500"}`}
              title="Mobile phone view"
            >
              <Smartphone className="h-4 w-4 mr-1" />
              Mobile
            </Button>
          </div>

          {/* AI Copilot Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAiModalOpen(true)}
            className="border-violet-300 text-violet-700 bg-violet-50 hover:bg-violet-100 flex items-center gap-1.5 min-h-[36px]"
          >
            <Wand2 className="h-4 w-4 text-violet-600" />
            <span className="hidden sm:inline">AI</span> Assistant
          </Button>

          {/* View Live Site */}
          <Button
            variant="outline"
            size="sm"
            asChild
            className="flex items-center gap-1.5 min-h-[36px]"
          >
            <a href={`/site${config.is_published ? "" : "?preview=true"}`} target="_blank" rel="noreferrer">
              <Eye className="h-4 w-4" />
              <span className="hidden sm:inline">View</span> Site
            </a>
          </Button>

          {/* Save Draft */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveDraft}
            disabled={saving}
            className="flex items-center gap-1.5 min-h-[36px]"
          >
            <Save className="h-4 w-4" />
            {saving ? "Saving..." : <><span className="hidden sm:inline">Save</span> Draft</>}
          </Button>

          {/* Publish Toggle Button */}
          {config.is_published ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handlePublishToggle(false)}
              disabled={publishing}
              className="flex items-center gap-1.5 min-h-[36px]"
            >
              Unpublish
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => handlePublishToggle(true)}
              disabled={publishing}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold flex items-center gap-1.5 shadow-sm min-h-[36px]"
            >
              <Send className="h-4 w-4" />
              {publishing ? "Publishing..." : <><span className="hidden sm:inline">Publish</span> Website</>}
            </Button>
          )}
        </div>
      </header>

      {/* ── TWO-COLUMN WORKSPACE ───────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT PANEL: EDITORS & TABS */}
        <div className={`w-full lg:w-[480px] xl:w-[540px] border-r bg-white flex flex-col shrink-0 overflow-y-auto ${mobileView === "preview" ? "hidden lg:flex" : "flex"}`}>
          <Tabs defaultValue="templates" className="flex flex-col h-full">
            <div className="px-6 pt-4 border-b bg-slate-50/50">
              <TabsList className="grid grid-cols-4 w-full">
                <TabsTrigger value="templates" className="text-xs">
                  Templates
                </TabsTrigger>
                <TabsTrigger value="themes" className="text-xs">
                  Themes
                </TabsTrigger>
                <TabsTrigger value="sections" className="text-xs">
                  Sections
                </TabsTrigger>
                <TabsTrigger value="seo" className="text-xs">
                  SEO & Meta
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="p-6 space-y-6 flex-1 overflow-y-auto">
              {/* TAB 1: TEMPLATES */}
              <TabsContent value="templates" className="space-y-4 m-0">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Choose Website Template</h3>
                  <p className="text-xs text-slate-500">
                    Select a layout structure designed for your industry.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  {TEMPLATES.map((tpl) => {
                    const isSelected = config.template_id === tpl.id;
                    return (
                      <div
                        key={tpl.id}
                        onClick={() => {
                          setConfig((prev) => ({ ...prev, template_id: tpl.id }));
                          setHasUnsavedChanges(true);
                          toast.success(`Activated ${tpl.name} template!`);
                        }}
                        className={`group relative flex gap-4 p-4 rounded-xl border-2 transition-all cursor-pointer ${
                          isSelected
                            ? "border-primary bg-primary/5 shadow-sm"
                            : "border-slate-200 hover:border-slate-300 bg-white"
                        }`}
                      >
                        <div className="w-24 h-24 rounded-lg overflow-hidden shrink-0 border bg-slate-100">
                          <img
                            src={tpl.image}
                            alt={tpl.name}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        </div>

                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between">
                            <h4 className="text-sm font-bold text-slate-900">{tpl.name}</h4>
                            {isSelected && (
                              <Badge className="bg-primary text-white text-[10px] h-5 px-1.5">
                                Active
                              </Badge>
                            )}
                          </div>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            {tpl.badge}
                          </Badge>
                          <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                            {tpl.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </TabsContent>

              {/* TAB 2: COLOR THEMES */}
              <TabsContent value="themes" className="space-y-6 m-0">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Color Themes & Palettes</h3>
                  <p className="text-xs text-slate-500">
                    Curated color sets that harmonize typography, buttons, and section cards.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {CURATED_THEMES.map((th) => {
                    const isSelected = config.theme_id === th.id;
                    return (
                      <div
                        key={th.id}
                        onClick={() => {
                          setConfig((prev) => ({ ...prev, theme_id: th.id }));
                          setHasUnsavedChanges(true);
                          toast.success(`Selected ${th.name} theme!`);
                        }}
                        className={`flex items-center justify-between p-3.5 rounded-xl border-2 cursor-pointer transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 shadow-xs"
                            : "border-slate-200 hover:border-slate-300 bg-white"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex items-center -space-x-1">
                            <div
                              className="w-6 h-6 rounded-full border border-white shadow-xs"
                              style={{ backgroundColor: th.primary }}
                            />
                            <div
                              className="w-6 h-6 rounded-full border border-white shadow-xs"
                              style={{ backgroundColor: th.bg }}
                            />
                          </div>
                          <span className="text-sm font-semibold text-slate-800">{th.name}</span>
                        </div>

                        {isSelected && (
                          <div className="h-6 w-6 rounded-full bg-primary text-white flex items-center justify-center">
                            <Check className="h-4 w-4" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Custom Color Overrides */}
                <div className="pt-4 border-t space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                        Custom Color Overrides
                      </h4>
                      <p className="text-xs text-slate-400">Specify custom hex colors if desired.</p>
                    </div>
                    {config.custom_colors?.primary && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setConfig((prev) => ({ ...prev, custom_colors: {} }));
                          setHasUnsavedChanges(true);
                        }}
                        className="text-xs text-slate-500 h-7"
                      >
                        Reset
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Primary Brand Color</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={config.custom_colors?.primary || THEMES[config.theme_id]?.primary || "#0284c7"}
                          onChange={(e) => {
                            setConfig((prev) => ({
                              ...prev,
                              custom_colors: { ...prev.custom_colors, primary: e.target.value },
                            }));
                            setHasUnsavedChanges(true);
                          }}
                          className="h-8 w-8 rounded cursor-pointer border p-0.5"
                        />
                        <Input
                          value={config.custom_colors?.primary || ""}
                          placeholder="#0284c7"
                          onChange={(e) => {
                            setConfig((prev) => ({
                              ...prev,
                              custom_colors: { ...prev.custom_colors, primary: e.target.value },
                            }));
                            setHasUnsavedChanges(true);
                          }}
                          className="text-xs h-8"
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs">Accent Color</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={config.custom_colors?.accent || THEMES[config.theme_id]?.accent || "#e0f2fe"}
                          onChange={(e) => {
                            setConfig((prev) => ({
                              ...prev,
                              custom_colors: { ...prev.custom_colors, accent: e.target.value },
                            }));
                            setHasUnsavedChanges(true);
                          }}
                          className="h-8 w-8 rounded cursor-pointer border p-0.5"
                        />
                        <Input
                          value={config.custom_colors?.accent || ""}
                          placeholder="#e0f2fe"
                          onChange={(e) => {
                            setConfig((prev) => ({
                              ...prev,
                              custom_colors: { ...prev.custom_colors, accent: e.target.value },
                            }));
                            setHasUnsavedChanges(true);
                          }}
                          className="text-xs h-8"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>

              {/* TAB 3: SECTIONS EDITOR */}
              <TabsContent value="sections" className="space-y-4 m-0">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Website Content Sections</h3>
                  <p className="text-xs text-slate-500">
                    Customize headlines, stories, testimonials, and opening hours.
                  </p>
                </div>

                <Accordion type="single" collapsible defaultValue="hero" className="w-full">
                  {/* HERO ACCORDION */}
                  <AccordionItem value="hero">
                    <AccordionTrigger className="text-sm font-semibold">
                      Hero Section
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Headline</Label>
                        <Input
                          value={config.sections_data?.hero?.headline || ""}
                          onChange={(e) => updateSection("hero", { headline: e.target.value })}
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Subheading</Label>
                        <Textarea
                          rows={2}
                          value={config.sections_data?.hero?.subhead || ""}
                          onChange={(e) => updateSection("hero", { subhead: e.target.value })}
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">CTA Button Text</Label>
                          <Input
                            value={config.sections_data?.hero?.cta_text || ""}
                            onChange={(e) => updateSection("hero", { cta_text: e.target.value })}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">CTA Link Target</Label>
                          <Input
                            value={config.sections_data?.hero?.cta_link || "#booking"}
                            onChange={(e) => updateSection("hero", { cta_link: e.target.value })}
                          />
                        </div>
                      </div>

                      <div className="space-y-1 pt-1">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs">Background Image</Label>
                          <Button
                            variant="link"
                            size="sm"
                            onClick={() => openMediaPicker("hero")}
                            className="text-xs h-6 p-0 text-primary flex items-center gap-1"
                          >
                            <ImageIcon className="h-3.5 w-3.5" />
                            Select from Media
                          </Button>
                        </div>
                        <Input
                          value={config.sections_data?.hero?.bg_image_url || ""}
                          onChange={(e) => updateSection("hero", { bg_image_url: e.target.value })}
                          placeholder="https://..."
                          className="text-xs"
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* ABOUT US ACCORDION */}
                  <AccordionItem value="about">
                    <AccordionTrigger className="text-sm font-semibold">
                      About Us Section
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-1 space-y-1">
                          <Label className="text-xs">Badge Pill</Label>
                          <Input
                            value={config.sections_data?.about?.badge || ""}
                            onChange={(e) => updateSection("about", { badge: e.target.value })}
                          />
                        </div>
                        <div className="col-span-2 space-y-1">
                          <Label className="text-xs">Section Headline</Label>
                          <Input
                            value={config.sections_data?.about?.headline || ""}
                            onChange={(e) => updateSection("about", { headline: e.target.value })}
                          />
                        </div>
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Our Story / Mission</Label>
                        <Textarea
                          rows={4}
                          value={config.sections_data?.about?.story || ""}
                          onChange={(e) => updateSection("about", { story: e.target.value })}
                        />
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs">Featured Photo</Label>
                          <Button
                            variant="link"
                            size="sm"
                            onClick={() => openMediaPicker("about")}
                            className="text-xs h-6 p-0 text-primary flex items-center gap-1"
                          >
                            <ImageIcon className="h-3.5 w-3.5" />
                            Select from Media
                          </Button>
                        </div>
                        <Input
                          value={config.sections_data?.about?.image_url || ""}
                          onChange={(e) => updateSection("about", { image_url: e.target.value })}
                          placeholder="https://..."
                          className="text-xs"
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* SERVICES ACCORDION */}
                  <AccordionItem value="services">
                    <AccordionTrigger className="text-sm font-semibold">
                      Featured Services Section
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Headline</Label>
                        <Input
                          value={config.sections_data?.services?.headline || ""}
                          onChange={(e) => updateSection("services", { headline: e.target.value })}
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Subheading</Label>
                        <Input
                          value={config.sections_data?.services?.subhead || ""}
                          onChange={(e) => updateSection("services", { subhead: e.target.value })}
                        />
                      </div>

                      <div className="flex items-center justify-between p-3 rounded-lg border bg-slate-50">
                        <div>
                          <Label className="text-xs font-semibold">Display Prices</Label>
                          <p className="text-[11px] text-slate-500">
                            Show service prices directly on cards
                          </p>
                        </div>
                        <Switch
                          checked={config.sections_data?.services?.show_prices !== false}
                          onCheckedChange={(checked) =>
                            updateSection("services", { show_prices: checked })
                          }
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* BOOKING SECTION & CAL.COM SCHEDULING ACCORDION */}
                  <AccordionItem value="booking">
                    <AccordionTrigger className="text-sm font-semibold">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-primary" />
                        <span>Booking Engine & Scheduler</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Headline</Label>
                        <Input
                          value={config.sections_data?.booking?.headline || ""}
                          onChange={(e) =>
                            updateSection("booking", { headline: e.target.value })
                          }
                          placeholder="Schedule Your Visit"
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Subhead Description</Label>
                        <Input
                          value={config.sections_data?.booking?.subhead || ""}
                          onChange={(e) =>
                            updateSection("booking", { subhead: e.target.value })
                          }
                          placeholder="Choose your preferred service, date, and time..."
                        />
                      </div>

                      <div className="space-y-2 pt-2 border-t">
                        <Label className="text-xs font-semibold">Booking Mode Engine</Label>
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              updateSection("booking", { booking_mode: "fastapi" })
                            }
                            className={`p-3 text-left rounded-lg border transition-all ${
                              (config.sections_data?.booking?.booking_mode || "fastapi") === "fastapi"
                                ? "border-primary bg-primary/5 ring-1 ring-primary"
                                : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                          >
                            <p className="text-xs font-bold text-slate-800">Native FastAPI Engine</p>
                            <p className="text-[10px] text-slate-500 mt-0.5">
                              Direct slots, provider assignment, and checkout flow.
                            </p>
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              updateSection("booking", { booking_mode: "calcom" })
                            }
                            className={`p-3 text-left rounded-lg border transition-all ${
                              config.sections_data?.booking?.booking_mode === "calcom"
                                ? "border-primary bg-primary/5 ring-1 ring-primary"
                                : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <p className="text-xs font-bold text-slate-800">Cal.com Scheduler</p>
                              {calcomStatus?.connected ? (
                                <Badge className="text-[9px] bg-emerald-600 px-1 py-0">Connected</Badge>
                              ) : null}
                            </div>
                            <p className="text-[10px] text-slate-500 mt-0.5">
                              Sleek embedded scheduler, Google/Outlook sync & holds.
                            </p>
                          </button>
                        </div>
                      </div>

                      {config.sections_data?.booking?.booking_mode === "calcom" && (
                        <div className="space-y-3 p-3 rounded-lg border border-primary/20 bg-primary/[0.02]">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs font-semibold flex items-center gap-1.5">
                              <Link2 className="h-3.5 w-3.5 text-primary" />
                              <span>Cal.com Event Link or Slug</span>
                            </Label>
                            {calcomStatus?.connected && (
                              <span className="text-[10px] text-emerald-600 font-medium">
                                API key active
                              </span>
                            )}
                          </div>

                          <Input
                            value={config.sections_data?.booking?.calcom_link || ""}
                            onChange={(e) =>
                              updateSection("booking", { calcom_link: e.target.value })
                            }
                            placeholder="e.g. john/30min or my-spa/consultation"
                          />
                          <p className="text-[11px] text-slate-500">
                            Enter your Cal.com username/event slug or full booking link.
                          </p>

                          {calcomEventTypes && calcomEventTypes.length > 0 && (
                            <div className="space-y-1 pt-1">
                              <Label className="text-[11px] text-slate-600">
                                Or select from your connected Cal.com event types:
                              </Label>
                              <select
                                className="w-full text-xs border rounded-md p-2 bg-white"
                                onChange={(e) => {
                                  if (e.target.value) {
                                    updateSection("booking", { calcom_link: e.target.value });
                                  }
                                }}
                                defaultValue=""
                              >
                                <option value="">-- Choose an Event Type --</option>
                                {calcomEventTypes.map((et: any) => (
                                  <option key={et.id || et.slug} value={et.slug || et.scheduling_url}>
                                    {et.title} ({et.length || 30} mins)
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}

                          <div className="space-y-1 pt-1">
                            <Label className="text-xs">Scheduler Layout</Label>
                            <select
                              className="w-full text-xs border rounded-md p-2 bg-white"
                              value={config.sections_data?.booking?.calcom_layout || "month_view"}
                              onChange={(e) =>
                                updateSection("booking", { calcom_layout: e.target.value })
                              }
                            >
                              <option value="month_view">Month View (Recommended)</option>
                              <option value="week_view">Week View</option>
                              <option value="column_view">Column View</option>
                            </select>
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between p-3 rounded-lg border bg-slate-50">
                        <div>
                          <Label className="text-xs font-semibold">Enable Booking Section</Label>
                          <p className="text-[11px] text-slate-500">
                            Show or hide the interactive booking section on your public site
                          </p>
                        </div>
                        <Switch
                          checked={config.sections_data?.booking?.enabled !== false}
                          onCheckedChange={(checked) =>
                            updateSection("booking", { enabled: checked })
                          }
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* TESTIMONIALS ACCORDION */}
                  <AccordionItem value="testimonials">
                    <AccordionTrigger className="text-sm font-semibold">
                      Client Reviews & Testimonials
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Headline</Label>
                        <Input
                          value={config.sections_data?.testimonials?.headline || ""}
                          onChange={(e) =>
                            updateSection("testimonials", { headline: e.target.value })
                          }
                        />
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs font-semibold text-slate-700">
                            Review Cards
                          </Label>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const currentItems =
                                config.sections_data?.testimonials?.items || [];
                              updateSection("testimonials", {
                                items: [
                                  ...currentItems,
                                  {
                                    name: "New Client",
                                    role: "Verified Customer",
                                    content: "Exceptional experience! Loved every minute.",
                                    rating: 5,
                                  },
                                ],
                              });
                            }}
                            className="text-xs h-7 flex items-center gap-1"
                          >
                            <Plus className="h-3 w-3" />
                            Add Review
                          </Button>
                        </div>

                        {(config.sections_data?.testimonials?.items || []).map((t, idx) => (
                          <div
                            key={idx}
                            className="p-3 border rounded-lg bg-slate-50 space-y-2 relative"
                          >
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                const currentItems = [
                                  ...(config.sections_data?.testimonials?.items || []),
                                ];
                                currentItems.splice(idx, 1);
                                updateSection("testimonials", { items: currentItems });
                              }}
                              className="absolute top-2 right-2 h-6 w-6 p-0 text-slate-400 hover:text-red-500"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>

                            <div className="grid grid-cols-2 gap-2">
                              <Input
                                value={t.name}
                                placeholder="Client Name"
                                onChange={(e) => {
                                  const currentItems = [
                                    ...(config.sections_data?.testimonials?.items || []),
                                  ];
                                  currentItems[idx].name = e.target.value;
                                  updateSection("testimonials", { items: currentItems });
                                }}
                                className="text-xs h-7"
                              />
                              <Input
                                value={t.role || ""}
                                placeholder="Role (e.g. Regular Client)"
                                onChange={(e) => {
                                  const currentItems = [
                                    ...(config.sections_data?.testimonials?.items || []),
                                  ];
                                  currentItems[idx].role = e.target.value;
                                  updateSection("testimonials", { items: currentItems });
                                }}
                                className="text-xs h-7"
                              />
                            </div>

                            <Textarea
                              rows={2}
                              value={t.content}
                              onChange={(e) => {
                                const currentItems = [
                                  ...(config.sections_data?.testimonials?.items || []),
                                ];
                                currentItems[idx].content = e.target.value;
                                updateSection("testimonials", { items: currentItems });
                              }}
                              className="text-xs"
                            />
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* CONTACT & HOURS ACCORDION */}
                  <AccordionItem value="contact">
                    <AccordionTrigger className="text-sm font-semibold">
                      Contact & Opening Hours
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Address</Label>
                        <Input
                          value={config.sections_data?.contact?.address || ""}
                          onChange={(e) => updateSection("contact", { address: e.target.value })}
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Phone</Label>
                          <Input
                            value={config.sections_data?.contact?.phone || ""}
                            onChange={(e) => updateSection("contact", { phone: e.target.value })}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Email</Label>
                          <Input
                            value={config.sections_data?.contact?.email || ""}
                            onChange={(e) => updateSection("contact", { email: e.target.value })}
                          />
                        </div>
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Operating Hours Schedule</Label>
                        <Textarea
                          rows={3}
                          value={config.sections_data?.contact?.hours || ""}
                          onChange={(e) => updateSection("contact", { hours: e.target.value })}
                          className="text-xs font-mono"
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* CHAT WIDGET & PROACTIVE INVITATION ACCORDION */}
                  <AccordionItem value="chat_widget">
                    <AccordionTrigger className="text-sm font-semibold">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-primary" />
                        <span>Chat Widget & Invitation</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="flex items-center justify-between p-3 rounded-lg border bg-slate-50">
                        <div className="space-y-0.5">
                          <Label className="text-xs font-semibold">Enable Live Chat Widget</Label>
                          <p className="text-[11px] text-muted-foreground">
                            Display floating assistant launcher & proactive invitation bubble
                          </p>
                        </div>
                        <Switch
                          checked={config.sections_data?.chat_widget?.enabled !== false}
                          onCheckedChange={(checked) =>
                            updateSection("chat_widget", { enabled: checked })
                          }
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Invitation Callout Header</Label>
                        <Input
                          value={
                            config.sections_data?.chat_widget?.invitation_title ??
                            "Need help booking?"
                          }
                          onChange={(e) =>
                            updateSection("chat_widget", { invitation_title: e.target.value })
                          }
                          placeholder="Need help booking?"
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Proactive Invitation Message</Label>
                        <Textarea
                          rows={2}
                          value={
                            config.sections_data?.chat_widget?.invitation_message ??
                            "Hi there! 👋 Have questions about our services or need to book? Chat with us!"
                          }
                          onChange={(e) =>
                            updateSection("chat_widget", { invitation_message: e.target.value })
                          }
                          placeholder="Hi there! 👋 Have questions about our services or need to book? Chat with us!"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Invitation Delay (seconds)</Label>
                          <Input
                            type="number"
                            min={0}
                            max={60}
                            value={config.sections_data?.chat_widget?.invitation_delay_seconds ?? 3}
                            onChange={(e) =>
                              updateSection("chat_widget", {
                                invitation_delay_seconds: parseInt(e.target.value) || 0,
                              })
                            }
                          />
                        </div>

                        <div className="space-y-1">
                          <Label className="text-xs font-semibold">SMS Texting Fallback</Label>
                          <div className="pt-2 flex items-center justify-between">
                            <span className="text-[11px] text-muted-foreground">Direct SMS link</span>
                            <Switch
                              checked={config.sections_data?.chat_widget?.show_sms_fallback !== false}
                              onCheckedChange={(checked) =>
                                updateSection("chat_widget", { show_sms_fallback: checked })
                              }
                            />
                          </div>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </TabsContent>

              {/* TAB 4: SEO & META */}
              <TabsContent value="seo" className="space-y-4 m-0">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">SEO & Metadata</h3>
                  <p className="text-xs text-slate-500">
                    Control how your website appears on Google and social media shares.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs">Page Title (Meta Title)</Label>
                  <Input
                    value={config.seo_title || ""}
                    onChange={(e) => {
                      setConfig((prev) => ({ ...prev, seo_title: e.target.value }));
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="Studio Name | Book Online"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs">Meta Description</Label>
                  <Textarea
                    rows={3}
                    value={config.seo_description || ""}
                    onChange={(e) => {
                      setConfig((prev) => ({ ...prev, seo_description: e.target.value }));
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="Book your massage, facial or styling appointment online..."
                  />
                </div>

                {/* Google Preview Snippet */}
                <div className="p-4 rounded-xl border bg-slate-50 space-y-1 text-xs">
                  <div className="text-slate-400">Search Engine Result Preview</div>
                  <div className="text-blue-700 font-semibold text-sm truncate">
                    {config.seo_title || `${tenantInfo.name} | Book Online`}
                  </div>
                  <div className="text-emerald-700 text-[11px]">
                    https://{tenantInfo.subdomain}.example.com/site
                  </div>
                  <div className="text-slate-600 line-clamp-2 text-[11px]">
                    {config.seo_description ||
                      "Book your appointment online effortlessly with our top-rated specialists."}
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>

        {/* RIGHT PANEL: INTERACTIVE LIVE PREVIEW */}
        <div className={`flex-1 bg-slate-200/70 p-2 sm:p-4 lg:p-8 flex items-center justify-center overflow-auto ${mobileView === "editor" ? "hidden lg:flex" : "flex"}`}>
          <div
            className={`transition-all duration-300 bg-white shadow-2xl overflow-y-auto ${
              deviceMode === "desktop"
                ? "w-full h-full rounded-xl border"
                : deviceMode === "tablet"
                ? "w-[768px] h-[92%] rounded-2xl border-8 border-slate-800 shadow-2xl"
                : "w-[375px] h-[92%] rounded-[36px] border-[10px] border-slate-900 shadow-2xl"
            }`}
          >
            <PublicWebsiteView
              config={config}
              tenantName={tenantInfo.name}
              tenantSubdomain={tenantInfo.subdomain}
              tenantEmail={tenantInfo.email}
              tenantPhone={tenantInfo.phone}
              tenantAddress={tenantInfo.address}
              tenantLogoUrl={tenantInfo.logo_url}
              services={catalogServices}
              isInteractivePreview={true}
            />
          </div>
        </div>
      </div>

      {/* ── MODAL: MEDIA PICKER ────────────────────────────── */}
      <Dialog open={mediaPickerOpen} onOpenChange={setMediaPickerOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Select Image from Media Library</DialogTitle>
            <DialogDescription>
              Choose from your uploaded photos, curated library, or enter an image URL.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="flex gap-2">
              <Input
                placeholder="Or paste direct image URL (https://...)"
                value={customMediaUrl}
                onChange={(e) => setCustomMediaUrl(e.target.value)}
                className="text-xs"
              />
              <Button
                size="sm"
                onClick={() => {
                  if (customMediaUrl.trim()) {
                    handleSelectMedia(customMediaUrl.trim());
                  }
                }}
              >
                Use URL
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-3 max-h-[360px] overflow-y-auto p-1">
              {CURATED_MEDIA_PHOTOS.map((photo, i) => (
                <div
                  key={i}
                  onClick={() => handleSelectMedia(photo.url)}
                  className="group relative rounded-lg overflow-hidden border cursor-pointer hover:ring-2 hover:ring-primary transition-all aspect-video bg-slate-100"
                >
                  <img
                    src={photo.url}
                    alt={photo.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                    <span className="text-white text-[11px] font-medium truncate">
                      {photo.name}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── MODAL: AI ASSISTANT & VOICE DICTATION ──────────── */}
      <Dialog open={aiModalOpen} onOpenChange={setAiModalOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-violet-100 text-violet-700">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <DialogTitle>AI Website Copilot</DialogTitle>
                <DialogDescription>
                  Generate complete site copy, rewrite specific sections, or dictate via microphone.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Quick Prompt Suggestions */}
            <div className="space-y-1.5">
              <Label className="text-xs text-slate-500">Quick Prompt Suggestions</Label>
              <div className="flex flex-wrap gap-1.5">
                {[
                  "Serene massage and wellness spa offering aromatherapy",
                  "Modern dermatology and medical aesthetics clinic",
                  "High-end boutique hair salon and styling studio",
                  "Bespoke personal training and fitness studio",
                ].map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setAiPrompt(s)}
                    className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-full text-left transition-colors"
                  >
                    "{s}"
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt Textarea + Voice Dictation Button */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold">Your Business Description or Request</Label>
                <Button
                  type="button"
                  variant={isVoiceListening ? "destructive" : "outline"}
                  size="sm"
                  onClick={toggleVoiceListening}
                  className="h-7 text-xs flex items-center gap-1.5"
                >
                  {isVoiceListening ? (
                    <>
                      <MicOff className="h-3.5 w-3.5 animate-pulse" />
                      Listening... (Click to stop)
                    </>
                  ) : (
                    <>
                      <Mic className="h-3.5 w-3.5 text-red-500" />
                      Voice Dictate
                    </>
                  )}
                </Button>
              </div>

              <Textarea
                rows={3}
                placeholder="Describe your services, clientele, and the desired atmosphere..."
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
              />
            </div>

            {/* Action selector */}
            <div className="grid grid-cols-3 gap-3">
              <div
                onClick={() => setAiAction("generate_full")}
                className={`p-3 rounded-lg border text-center cursor-pointer transition-all ${
                  aiAction === "generate_full"
                    ? "border-violet-600 bg-violet-50 text-violet-900 font-semibold"
                    : "border-slate-200 hover:border-slate-300 text-slate-700"
                }`}
              >
                <div className="text-xs">Full Website</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Copy & Layout</div>
              </div>

              <div
                onClick={() => setAiAction("rewrite_section")}
                className={`p-3 rounded-lg border text-center cursor-pointer transition-all ${
                  aiAction === "rewrite_section"
                    ? "border-violet-600 bg-violet-50 text-violet-900 font-semibold"
                    : "border-slate-200 hover:border-slate-300 text-slate-700"
                }`}
              >
                <div className="text-xs">Rewrite Section</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Focus on one area</div>
              </div>

              <div
                onClick={() => setAiAction("suggest_theme")}
                className={`p-3 rounded-lg border text-center cursor-pointer transition-all ${
                  aiAction === "suggest_theme"
                    ? "border-violet-600 bg-violet-50 text-violet-900 font-semibold"
                    : "border-slate-200 hover:border-slate-300 text-slate-700"
                }`}
              >
                <div className="text-xs">Suggest Theme</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Palette & Vibe</div>
              </div>
            </div>

            {aiAction === "rewrite_section" && (
              <div className="space-y-1">
                <Label className="text-xs">Select Section to Polish</Label>
                <select
                  value={aiSectionKey}
                  onChange={(e) => setAiSectionKey(e.target.value)}
                  className="w-full text-xs px-3 py-2 border rounded-md"
                >
                  <option value="hero">Hero Section</option>
                  <option value="about">About Us Story</option>
                  <option value="services">Services Description</option>
                  <option value="booking">Booking Prompt</option>
                </select>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setAiModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleRunAi}
              disabled={aiGenerating}
              className="bg-violet-600 hover:bg-violet-700 text-white font-semibold flex items-center gap-2"
            >
              <Sparkles className="h-4 w-4" />
              {aiGenerating ? "Generating Content..." : "Generate with AI"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── MODAL: STEP-BY-STEP GUIDED ONBOARDING WIZARD ─── */}
      <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle>Website Setup Wizard</DialogTitle>
                <DialogDescription>
                  Step {wizardStep} of 3: Build your customized booking website in 60 seconds.
                </DialogDescription>
              </div>
              <Badge variant="outline" className="text-xs font-semibold">
                Step {wizardStep} / 3
              </Badge>
            </div>
          </DialogHeader>

          <div className="py-4">
            {/* STEP 1: BUSINESS BASICS */}
            {wizardStep === 1 && (
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Business or Brand Name</Label>
                  <Input
                    value={wizardBizName}
                    placeholder="e.g. Blossom Sanctuary Spa"
                    onChange={(e) => setWizardBizName(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Business Industry & Category</Label>
                  <select
                    value={wizardIndustry}
                    onChange={(e) => setWizardIndustry(e.target.value)}
                    className="w-full text-sm px-3 py-2 border rounded-md bg-white"
                  >
                    <option value="Wellness & Spa">Wellness & Spa (Massage, Holistic, Zen)</option>
                    <option value="Beauty & Salon">Beauty & Salon (Hair, Lash, Nail, Brow)</option>
                    <option value="Medical & Clinical">Medical & Clinical (Dental, Physio, Health)</option>
                    <option value="Fitness & Studio">Fitness & Studio (Gym, Pilates, Trainer)</option>
                    <option value="Professional Services">Professional & Consulting</option>
                  </select>
                </div>
              </div>
            )}

            {/* STEP 2: CHOOSE TEMPLATE */}
            {wizardStep === 2 && (
              <div className="space-y-4">
                <Label>Choose Your Preferred Website Style</Label>
                <div className="grid grid-cols-2 gap-3">
                  {TEMPLATES.map((tpl) => (
                    <div
                      key={tpl.id}
                      onClick={() => setWizardTemplate(tpl.id)}
                      className={`p-3 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                        wizardTemplate === tpl.id
                          ? "border-primary bg-primary/5"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="font-semibold text-sm">{tpl.name}</div>
                        <p className="text-[11px] text-slate-500 leading-tight">
                          {tpl.description}
                        </p>
                      </div>
                      {wizardTemplate === tpl.id && (
                        <Badge className="bg-primary text-white text-[10px] self-start mt-2">
                          Selected
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* STEP 3: COLOR THEME & POLISH */}
            {wizardStep === 3 && (
              <div className="space-y-4">
                <Label>Select Color Theme Palette</Label>
                <div className="grid grid-cols-2 gap-3">
                  {CURATED_THEMES.map((th) => (
                    <div
                      key={th.id}
                      onClick={() => setWizardTheme(th.id)}
                      className={`p-3 rounded-xl border-2 cursor-pointer flex items-center justify-between ${
                        wizardTheme === th.id
                          ? "border-primary bg-primary/5"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded-full border"
                          style={{ backgroundColor: th.primary }}
                        />
                        <span className="text-xs font-semibold">{th.name}</span>
                      </div>
                      {wizardTheme === th.id && <Check className="h-4 w-4 text-primary" />}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="flex justify-between">
            {wizardStep > 1 ? (
              <Button variant="outline" onClick={() => setWizardStep((s) => s - 1)}>
                Back
              </Button>
            ) : (
              <div />
            )}

            {wizardStep < 3 ? (
              <Button onClick={() => setWizardStep((s) => s + 1)}>
                Next Step
              </Button>
            ) : (
              <Button
                onClick={handleFinishWizard}
                className="bg-primary text-white font-semibold flex items-center gap-1.5"
              >
                <CheckCircle2 className="h-4 w-4" />
                Finish & Apply Setup
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
