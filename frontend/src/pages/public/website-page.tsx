import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  Calendar,
  Clock,
  MapPin,
  Phone,
  Mail,
  Star,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Heart,
  Award,
  MessageSquare,
  Send,
  X,
  Minus,
  Bot,
  MessageCircle,
  ChevronDown,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export interface WebsiteThemeColors {
  primary: string;
  primaryHover: string;
  accent: string;
  accentText: string;
  textPrimary: string;
  textMuted: string;
  bgSection: string;
  bgCard: string;
  border: string;
}

export const THEMES: Record<string, WebsiteThemeColors> = {
  ocean_slate: {
    primary: "#0284c7",
    primaryHover: "#0369a1",
    accent: "#e0f2fe",
    accentText: "#0369a1",
    textPrimary: "#0f172a",
    textMuted: "#64748b",
    bgSection: "#f8fafc",
    bgCard: "#ffffff",
    border: "#e2e8f0",
  },
  emerald_oasis: {
    primary: "#059669",
    primaryHover: "#047857",
    accent: "#d1fae5",
    accentText: "#065f46",
    textPrimary: "#064e3b",
    textMuted: "#047857",
    bgSection: "#f0fdf4",
    bgCard: "#ffffff",
    border: "#a7f3d0",
  },
  rose_gold: {
    primary: "#be185d",
    primaryHover: "#9d174d",
    accent: "#fce7f3",
    accentText: "#831843",
    textPrimary: "#4c0519",
    textMuted: "#9f1239",
    bgSection: "#fff1f2",
    bgCard: "#ffffff",
    border: "#fbcfe8",
  },
  royal_indigo: {
    primary: "#4338ca",
    primaryHover: "#3730a3",
    accent: "#e0e7ff",
    accentText: "#312e81",
    textPrimary: "#1e1b4b",
    textMuted: "#4338ca",
    bgSection: "#eef2ff",
    bgCard: "#ffffff",
    border: "#c7d2fe",
  },
  monochrome: {
    primary: "#18181b",
    primaryHover: "#27272a",
    accent: "#f4f4f5",
    accentText: "#18181b",
    textPrimary: "#09090b",
    textMuted: "#71717a",
    bgSection: "#fafafa",
    bgCard: "#ffffff",
    border: "#e4e4e7",
  },
};

export interface WebsiteConfigData {
  template_id: string;
  theme_id: string;
  custom_colors?: Record<string, string>;
  sections_data: {
    hero?: {
      headline: string;
      subhead: string;
      cta_text: string;
      cta_link?: string;
      bg_image_url?: string;
      enabled?: boolean;
    };
    about?: {
      badge?: string;
      headline: string;
      story: string;
      image_url?: string;
      enabled?: boolean;
    };
    services?: {
      headline: string;
      subhead: string;
      show_prices?: boolean;
      selected_service_ids?: number[];
      enabled?: boolean;
    };
    booking?: {
      headline: string;
      subhead: string;
      embedded_style?: "card" | "compact" | "split";
      booking_mode?: "fastapi" | "calcom";
      calcom_link?: string;
      calcom_layout?: "month_view" | "week_view" | "column_view";
      enabled?: boolean;
    };
    testimonials?: {
      headline: string;
      subhead: string;
      items: Array<{
        name: string;
        role?: string;
        content: string;
        rating: number;
      }>;
      enabled?: boolean;
    };
    contact?: {
      headline: string;
      subhead: string;
      address?: string;
      phone?: string;
      email?: string;
      hours?: string;
      enabled?: boolean;
    };
    footer?: {
      copyright?: string;
      social_links?: {
        instagram?: string;
        facebook?: string;
        twitter?: string;
      };
      enabled?: boolean;
    };
    chat_widget?: {
      enabled?: boolean;
      invitation_title?: string;
      invitation_message?: string;
      invitation_delay_seconds?: number;
      show_sms_fallback?: boolean;
    };
  };
  is_published?: boolean;
  seo_title?: string;
  seo_description?: string;
}

export interface PublicWebsiteViewProps {
  config: WebsiteConfigData;
  tenantName: string;
  tenantSubdomain: string;
  tenantEmail?: string;
  tenantPhone?: string;
  tenantAddress?: string;
  tenantLogoUrl?: string;
  services?: Array<{
    id: number | string;
    name: string;
    description?: string;
    duration: number;
    price?: number;
    image?: string;
  }>;
  isInteractivePreview?: boolean;
}

export interface WebsiteChatWidgetProps {
  tenantName: string;
  tenantSubdomain?: string;
  tenantPhone?: string;
  tenantLogoUrl?: string;
  config?: {
    enabled?: boolean;
    invitation_title?: string;
    invitation_message?: string;
    invitation_delay_seconds?: number;
    show_sms_fallback?: boolean;
  };
  primaryColor: string;
  isInteractivePreview?: boolean;
}

export function WebsiteChatWidget({
  tenantName,
  tenantSubdomain,
  tenantPhone,
  tenantLogoUrl,
  config,
  primaryColor,
  isInteractivePreview = false,
}: WebsiteChatWidgetProps) {
  const isEnabled = config?.enabled !== false;
  const invitationTitle = config?.invitation_title || "Chat with our Booking Assistant";
  const invitationMessage =
    config?.invitation_message ||
    "Hi there! 👋 Need help choosing a service or booking a slot? Ask us anything or text us.";
  const delaySec =
    typeof config?.invitation_delay_seconds === "number" ? config.invitation_delay_seconds : 3;
  const showSmsFallback = config?.show_sms_fallback !== false;

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isInvitationVisible, setIsInvitationVisible] = useState<boolean>(false);
  const [hasDismissedInvitation, setHasDismissedInvitation] = useState<boolean>(false);
  const [inputText, setInputText] = useState<string>("" );
  const [visitorName, setVisitorName] = useState<string>("");
  const [visitorContact, setVisitorContact] = useState<string>("");
  const [showContactFields, setShowContactFields] = useState<boolean>(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [messages, setMessages] = useState<
    Array<{
      id?: number;
      direction: "inbound" | "outbound";
      author_type: string;
      body: string;
      occurred_at?: string;
    }>
  >([
    {
      id: 0,
      direction: "outbound",
      author_type: "ai",
      body: `Hi there! 👋 Welcome to ${tenantName}. How can I assist you today?`,
      occurred_at: new Date().toISOString(),
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isEnabled || hasDismissedInvitation || isOpen) {
      setIsInvitationVisible(false);
      return;
    }
    const timer = setTimeout(() => {
      if (!isOpen && !hasDismissedInvitation) {
        setIsInvitationVisible(true);
      }
    }, Math.max(0, delaySec * 1000));

    return () => clearTimeout(timer);
  }, [isEnabled, delaySec, isOpen, hasDismissedInvitation]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen, isSending]);

  if (!isEnabled) {
    return null;
  }

  const handleOpenChat = () => {
    setIsOpen(true);
    setIsInvitationVisible(false);
  };

  const handleDismissInvitation = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsInvitationVisible(false);
    setHasDismissedInvitation(true);
  };

  const handleSendMessage = async (customText?: string) => {
    const textToSend = (customText || inputText).trim();
    if (!textToSend || isSending) return;

    if (!isOpen) {
      setIsOpen(true);
      setIsInvitationVisible(false);
    }

    setInputText("");
    const userMsg = {
      direction: "inbound" as const,
      author_type: "customer",
      body: textToSend,
      occurred_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);

    try {
      const res = await fetch("/api/public/website/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tenantSubdomain ? { "X-Tenant": tenantSubdomain } : {}),
        },
        body: JSON.stringify({
          visitor_name: visitorName.trim() || "Visitor",
          visitor_contact: visitorContact.trim() || undefined,
          message: textToSend,
          conversation_id: conversationId || undefined,
        }),
      });

      if (!res.ok) {
        throw new Error("Unable to reach assistant");
      }

      const data = await res.json();
      if (data.ok) {
        setConversationId(data.conversation_id);
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        } else if (data.reply) {
          setMessages((prev) => [
            ...prev,
            {
              direction: "outbound" as const,
              author_type: "ai",
              body: data.reply,
              occurred_at: new Date().toISOString(),
            },
          ]);
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          direction: "outbound" as const,
          author_type: "system",
          body: `Thanks for reaching out! We've noted your message. You can also reach us directly at ${tenantPhone || "our reception"}.`,
          occurred_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const quickChips = [
    "What are your hours?",
    "Pricing details",
    "Book an appointment",
  ];

  return (
    <div
      className={`font-sans select-none ${
        isInteractivePreview
          ? "sticky bottom-4 right-4 z-40 float-right ml-auto mr-4 mb-4"
          : "fixed bottom-6 right-6 z-50"
      }`}
    >
      {/* 1. PROACTIVE INVITATION CALLOUT BUBBLE */}
      {isInvitationVisible && !isOpen && (
        <div className="mb-3 max-w-sm w-[340px] bg-white rounded-2xl shadow-2xl border border-slate-200/80 p-4 animate-in fade-in slide-in-from-bottom-3 duration-300 relative text-slate-800">
          <button
            type="button"
            onClick={handleDismissInvitation}
            className="absolute top-3 right-3 p-1 text-slate-400 hover:text-slate-700 rounded-full hover:bg-slate-100 transition-colors"
            aria-label="Dismiss invitation"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="flex items-start gap-3">
            <div className="relative shrink-0">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-white shadow-sm font-semibold text-sm overflow-hidden"
                style={{ backgroundColor: primaryColor }}
              >
                {tenantLogoUrl ? (
                  <img
                    src={tenantLogoUrl}
                    alt={tenantName}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <Bot className="h-5 w-5" />
                )}
              </div>
              <span className="absolute bottom-0 right-0 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500 border-2 border-white" />
              </span>
            </div>

            <div className="space-y-1 pr-4">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-sm text-slate-900 leading-tight">
                  {invitationTitle}
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                {invitationMessage}
              </p>
            </div>
          </div>

          {/* Quick chips */}
          <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap gap-1.5">
            {quickChips.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSendMessage(chip)}
                className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Action button */}
          <div className="mt-3 flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleOpenChat}
              className="w-full h-8 text-xs font-semibold text-white shadow-sm gap-1.5"
              style={{ backgroundColor: primaryColor }}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Start Chat</span>
            </Button>
          </div>
        </div>
      )}

      {/* 2. INTERACTIVE CHAT POPUP WINDOW */}
      {isOpen && (
        <div className="mb-3 w-[360px] sm:w-[380px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[calc(100vh-6rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200 select-text">
          {/* Header */}
          <div
            className="p-3.5 text-white flex items-center justify-between shadow-sm shrink-0"
            style={{ backgroundColor: primaryColor }}
          >
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center font-bold text-xs overflow-hidden">
                  {tenantLogoUrl ? (
                    <img
                      src={tenantLogoUrl}
                      alt={tenantName}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Bot className="h-4 w-4" />
                  )}
                </div>
                <span className="absolute bottom-0 right-0 flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400 border border-white" />
                </span>
              </div>
              <div>
                <div className="font-bold text-xs leading-tight truncate max-w-[180px]">
                  {tenantName} Assistant
                </div>
                <div className="text-[10px] text-white/80 font-medium flex items-center gap-1">
                  <span>Online</span>
                  <span>•</span>
                  <span>Replies instantly</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                aria-label="Minimize chat"
              >
                <Minus className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                aria-label="Close chat"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Optional Visitor Contact Collapsible Bar */}
          <div className="bg-slate-50 border-b border-slate-100 px-3 py-1.5 flex items-center justify-between text-[11px] text-slate-600">
            <button
              type="button"
              onClick={() => setShowContactFields((prev) => !prev)}
              className="flex items-center gap-1 font-medium hover:text-slate-900 transition-colors"
            >
              <User className="h-3 w-3" />
              <span>
                {visitorName ? `Chatting as ${visitorName}` : "Add your name / phone (optional)"}
              </span>
              <ChevronDown
                className={`h-3 w-3 transition-transform ${showContactFields ? "rotate-180" : ""}`}
              />
            </button>
          </div>

          {showContactFields && (
            <div className="p-3 bg-slate-50/80 border-b border-slate-200/80 space-y-2 text-xs animate-in fade-in duration-150">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[10px] text-slate-500">Your Name</Label>
                  <Input
                    value={visitorName}
                    onChange={(e) => setVisitorName(e.target.value)}
                    placeholder="e.g. Alex"
                    className="h-7 text-xs bg-white"
                  />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-500">Phone or Email</Label>
                  <Input
                    value={visitorContact}
                    onChange={(e) => setVisitorContact(e.target.value)}
                    placeholder="e.g. 555-0199"
                    className="h-7 text-xs bg-white"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Message Thread Body */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3 bg-slate-50/40 text-xs">
            {messages.map((m, idx) => {
              const isUser = m.direction === "inbound";
              return (
                <div
                  key={idx}
                  className={`flex ${isUser ? "justify-end" : "justify-start"} animate-in fade-in duration-200`}
                >
                  <div
                    className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs whitespace-pre-wrap leading-relaxed shadow-sm ${
                      isUser
                        ? "text-white rounded-br-none"
                        : "bg-white text-slate-800 border border-slate-200/70 rounded-bl-none"
                    }`}
                    style={isUser ? { backgroundColor: primaryColor } : undefined}
                  >
                    {m.body}
                  </div>
                </div>
              );
            })}

            {isSending && (
              <div className="flex justify-start animate-in fade-in duration-200">
                <div className="bg-white text-slate-500 border border-slate-200/70 rounded-2xl rounded-bl-none px-3.5 py-2 text-xs flex items-center gap-1.5 shadow-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                  <span className="text-[11px] text-slate-400 ml-1">Assistant is typing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestions row above input */}
          <div className="px-3 py-1.5 bg-white border-t border-slate-100 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            {quickChips.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSendMessage(chip)}
                className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* SMS Fallback Link if enabled */}
          {showSmsFallback && tenantPhone && (
            <div className="px-3 py-1 bg-slate-50 border-t border-slate-100 text-center">
              <a
                href={`sms:${tenantPhone}`}
                className="inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800 underline underline-offset-2 transition-colors"
              >
                <MessageCircle className="h-3 w-3 text-slate-400" />
                <span>Prefer texting? Click here to text {tenantPhone} directly</span>
              </a>
            </div>
          )}

          {/* Input Footer */}
          <div className="p-2.5 bg-white border-t border-slate-200 shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-1.5"
            >
              <Input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Ask a question or request a booking..."
                className="h-9 text-xs flex-1 rounded-xl bg-slate-50 border-slate-200 focus-visible:ring-1"
                disabled={isSending}
              />
              <Button
                type="submit"
                size="sm"
                disabled={!inputText.trim() || isSending}
                className="h-9 w-9 p-0 rounded-xl text-white shadow-sm shrink-0"
                style={{ backgroundColor: primaryColor }}
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>
      )}

      {/* 3. FLOATING LAUNCHER BUTTON */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => {
            if (isOpen) {
              setIsOpen(false);
            } else {
              handleOpenChat();
            }
          }}
          className="relative w-14 h-14 rounded-full text-white shadow-xl flex items-center justify-center transition-transform hover:scale-105 active:scale-95 focus:outline-none focus:ring-4 focus:ring-primary/20"
          style={{ backgroundColor: primaryColor }}
          aria-label={isOpen ? "Close chat" : "Open chat"}
        >
          {isOpen ? (
            <X className="h-6 w-6" />
          ) : (
            <>
              <MessageSquare className="h-6 w-6" />
              <span className="absolute top-1 right-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-white" />
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export function PublicWebsiteView({
  config,
  tenantName,
  tenantSubdomain,
  tenantEmail,
  tenantPhone,
  tenantAddress,
  tenantLogoUrl,
  services = [],
  isInteractivePreview = false,
}: PublicWebsiteViewProps) {
  const theme = THEMES[config.theme_id] || THEMES.ocean_slate;
  const template = config.template_id || "minimalist";
  const sections = config.sections_data || {};

  // Custom colors override
  const primaryColor = config.custom_colors?.primary || theme.primary;
  const accentColor = config.custom_colors?.accent || theme.accent;

  // Inline booking state
  const [selectedServiceId, setSelectedServiceId] = useState<string | number>(
    services.length > 0 ? services[0].id : 1
  );
  const [bookingDate, setBookingDate] = useState<string>(
    new Date(Date.now() + 86400000).toISOString().split("T")[0]
  );
  const [bookingTime, setBookingTime] = useState<string>("10:00");
  const [guestName, setGuestName] = useState<string>("");
  const [guestEmail, setGuestEmail] = useState<string>("");
  const [guestPhone, setGuestPhone] = useState<string>("");
  const [bookingSubmitted, setBookingSubmitted] = useState<boolean>(false);

  // Fallback services if none yet in DB
  const displayServices =
    services && services.length > 0
      ? services
      : [
          {
            id: 1,
            name: "Signature Wellness Session",
            description: "Full body holistic consultation and treatment designed to alleviate stress and restore balance.",
            duration: 60,
            price: 120,
          },
          {
            id: 2,
            name: "Advanced Restorative Therapy",
            description: "Deep tissue technique combined with soothing botanical oils and targeted muscle release.",
            duration: 90,
            price: 165,
          },
          {
            id: 3,
            name: "Express Renewal Treatment",
            description: "Quick 30-minute targeted focus session to refresh your energy and soothe tension.",
            duration: 30,
            price: 75,
          },
        ];

  const handleQuickBook = (e: React.FormEvent) => {
    e.preventDefault();
    if (!guestName || !guestEmail) {
      toast.error("Please enter your name and email to book.");
      return;
    }
    setBookingSubmitted(true);
    toast.success("Appointment request received! We will confirm shortly via SMS/email.");
  };

  const scrollToBooking = (serviceId?: number | string) => {
    if (serviceId) {
      setSelectedServiceId(serviceId);
    }
    const elem = document.getElementById("booking-section");
    if (elem) {
      elem.scrollIntoView({ behavior: "smooth" });
    }
  };

  // Font and aesthetic styling classes per template
  const isWellness = template === "wellness";
  const isClinical = template === "clinical";
  const isLuxury = template === "luxury";

  const fontHeading = isLuxury
    ? "font-serif"
    : isWellness
    ? "font-sans tracking-tight"
    : isClinical
    ? "font-sans font-bold"
    : "font-sans font-semibold";

  const cardRadius = isWellness
    ? "rounded-3xl"
    : isLuxury
    ? "rounded-none border-t-2"
    : isClinical
    ? "rounded-lg"
    : "rounded-2xl";

  const buttonRadius = isWellness
    ? "rounded-full"
    : isLuxury
    ? "rounded-none uppercase tracking-widest text-xs px-8"
    : isClinical
    ? "rounded-md"
    : "rounded-xl";

  return (
    <div
      className="min-h-screen w-full transition-colors duration-200"
      style={{
        backgroundColor: theme.bgSection,
        color: theme.textPrimary,
      }}
    >
      {/* ── 1. Top Navigation Bar ──────────────────────────── */}
      <header
        className={`sticky top-0 z-40 w-full backdrop-blur-md transition-all border-b ${
          isWellness
            ? "bg-white/80 backdrop-blur-lg shadow-sm"
            : isLuxury
            ? "bg-white/95 border-b border-amber-100"
            : isClinical
            ? "bg-white border-b shadow-sm"
            : "bg-white/90"
        }`}
        style={{ borderColor: theme.border }}
      >
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 sm:h-20 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            {tenantLogoUrl ? (
              <img
                src={tenantLogoUrl}
                alt={tenantName}
                className="h-9 sm:h-10 w-auto object-contain rounded shrink-0"
              />
            ) : (
              <div
                className={`h-9 sm:h-10 w-9 sm:w-10 shrink-0 flex items-center justify-center font-bold text-white shadow-sm ${
                  isWellness ? "rounded-full" : isLuxury ? "rounded-none" : "rounded-lg"
                }`}
                style={{ backgroundColor: primaryColor }}
              >
                {tenantName ? tenantName.charAt(0).toUpperCase() : "B"}
              </div>
            )}
            <span
              className={`text-base sm:text-xl font-bold tracking-tight truncate max-w-[150px] sm:max-w-none ${
                isLuxury ? "font-serif tracking-wider" : ""
              }`}
              style={{ color: theme.textPrimary }}
            >
              {tenantName || "Serenity Wellness"}
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium">
            {sections.about?.enabled !== false && (
              <a
                href="#about-section"
                className="hover:opacity-75 transition-opacity"
                style={{ color: theme.textPrimary }}
              >
                About
              </a>
            )}
            {sections.services?.enabled !== false && (
              <a
                href="#services-section"
                className="hover:opacity-75 transition-opacity"
                style={{ color: theme.textPrimary }}
              >
                Services
              </a>
            )}
            {sections.testimonials?.enabled !== false && (
              <a
                href="#testimonials-section"
                className="hover:opacity-75 transition-opacity"
                style={{ color: theme.textPrimary }}
              >
                Reviews
              </a>
            )}
            {sections.contact?.enabled !== false && (
              <a
                href="#contact-section"
                className="hover:opacity-75 transition-opacity"
                style={{ color: theme.textPrimary }}
              >
                Contact & Hours
              </a>
            )}
          </nav>

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <Button
              onClick={() => scrollToBooking()}
              className={`font-semibold text-white shadow-md transition-all hover:opacity-90 min-h-[44px] text-xs sm:text-sm px-3 sm:px-4 ${buttonRadius}`}
              style={{ backgroundColor: primaryColor }}
            >
              <Calendar className="mr-1.5 sm:mr-2 h-4 w-4" />
              <span className="hidden sm:inline">{sections.hero?.cta_text || "Book Online"}</span>
              <span className="sm:hidden">Book</span>
            </Button>
          </div>
        </div>
      </header>

      {/* ── 2. Hero Section ────────────────────────────────── */}
      {sections.hero?.enabled !== false && (
        <section
          id="hero-section"
          className={`relative overflow-hidden py-20 lg:py-32 ${
            isWellness ? "bg-gradient-to-b from-white via-emerald-50/30 to-transparent" : ""
          }`}
        >
          {sections.hero?.bg_image_url && (
            <div className="absolute inset-0 -z-10 opacity-15 overflow-hidden">
              <img
                src={sections.hero.bg_image_url}
                alt="Background"
                className="w-full h-full object-cover filter blur-[1px]"
              />
            </div>
          )}

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
              <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
                {isClinical && (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                    <ShieldCheck className="h-4 w-4 text-blue-600" />
                    Board-Certified Clinical Specialists
                  </div>
                )}
                {isWellness && (
                  <div
                    className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold"
                    style={{ backgroundColor: accentColor, color: theme.accentText }}
                  >
                    <Sparkles className="h-4 w-4" />
                    Holistic Relaxation & Rejuvenation
                  </div>
                )}
                {isLuxury && (
                  <p className="text-xs uppercase tracking-[0.25em] font-medium text-amber-700">
                    Excellence · Artistry · Sanctuary
                  </p>
                )}

                <h1
                  className={`text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight ${fontHeading}`}
                  style={{ color: theme.textPrimary }}
                >
                  {sections.hero?.headline || `Welcome to ${tenantName}`}
                </h1>

                <p
                  className="text-lg sm:text-xl leading-relaxed max-w-2xl mx-auto lg:mx-0"
                  style={{ color: theme.textMuted }}
                >
                  {sections.hero?.subhead ||
                    "Experience personalized care and revitalizing treatments tailored specifically to your goals."}
                </p>

                <div className="pt-4 flex flex-wrap gap-4 justify-center lg:justify-start">
                  <Button
                    size="lg"
                    onClick={() => scrollToBooking()}
                    className={`font-semibold text-white shadow-lg transition-transform hover:scale-105 ${buttonRadius}`}
                    style={{ backgroundColor: primaryColor }}
                  >
                    {sections.hero?.cta_text || "Book Appointment"}
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => {
                      const el = document.getElementById("services-section");
                      el?.scrollIntoView({ behavior: "smooth" });
                    }}
                    className={`font-medium ${buttonRadius}`}
                    style={{ borderColor: theme.border }}
                  >
                    Explore Treatments
                  </Button>
                </div>

                {/* Trust stats */}
                <div className="pt-8 grid grid-cols-3 gap-6 border-t border-slate-200/80 max-w-md mx-auto lg:mx-0">
                  <div>
                    <div className="text-2xl font-bold" style={{ color: primaryColor }}>
                      5.0 ★
                    </div>
                    <div className="text-xs text-slate-500">Over 350+ reviews</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold" style={{ color: primaryColor }}>
                      100%
                    </div>
                    <div className="text-xs text-slate-500">Satisfaction guarantee</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold" style={{ color: primaryColor }}>
                      Verified
                    </div>
                    <div className="text-xs text-slate-500">Top Rated Studio</div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-5 relative">
                <div
                  className={`overflow-hidden shadow-2xl border-4 border-white ${
                    isWellness
                      ? "rounded-3xl rotate-1"
                      : isLuxury
                      ? "rounded-none shadow-amber-900/10"
                      : "rounded-2xl"
                  }`}
                >
                  <img
                    src={
                      sections.hero?.bg_image_url ||
                      "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80"
                    }
                    alt={tenantName}
                    className="w-full h-[400px] object-cover hover:scale-105 transition-transform duration-700"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── 3. About Us Section ────────────────────────────── */}
      {sections.about?.enabled !== false && (
        <section
          id="about-section"
          className="py-20 bg-white border-y"
          style={{ borderColor: theme.border }}
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
              <div className="lg:col-span-5 order-2 lg:order-1">
                <div
                  className={`relative overflow-hidden shadow-xl ${
                    isWellness
                      ? "rounded-3xl"
                      : isLuxury
                      ? "rounded-none border-2 border-amber-200"
                      : "rounded-2xl"
                  }`}
                >
                  <img
                    src={
                      sections.about?.image_url ||
                      "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1000&q=80"
                    }
                    alt="About our practice"
                    className="w-full h-[380px] object-cover"
                  />
                </div>
              </div>

              <div className="lg:col-span-7 order-1 lg:order-2 space-y-6">
                <div
                  className="inline-block px-3 py-1 rounded-full text-xs font-semibold tracking-wider uppercase"
                  style={{ backgroundColor: accentColor, color: theme.accentText }}
                >
                  {sections.about?.badge || "Our Story"}
                </div>

                <h2
                  className={`text-3xl sm:text-4xl font-bold tracking-tight ${fontHeading}`}
                  style={{ color: theme.textPrimary }}
                >
                  {sections.about?.headline || `Dedicated to Exceptional Care at ${tenantName}`}
                </h2>

                <p
                  className="text-base sm:text-lg leading-relaxed text-slate-600"
                  style={{ color: theme.textMuted }}
                >
                  {sections.about?.story ||
                    "Founded with a mission to bring world-class services and mindful relaxation together. Our expert practitioners combine modern techniques with time-honored treatments to deliver an unforgettable experience every visit."}
                </p>

                <div className="grid grid-cols-2 gap-4 pt-4">
                  <div className="flex items-start gap-3">
                    <div
                      className="p-2 rounded-lg text-white"
                      style={{ backgroundColor: primaryColor }}
                    >
                      <Award className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-sm">Certified Practitioners</h4>
                      <p className="text-xs text-slate-500">
                        Rigorous clinical and industry accreditation.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div
                      className="p-2 rounded-lg text-white"
                      style={{ backgroundColor: primaryColor }}
                    >
                      <Heart className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-sm">Personalized Touch</h4>
                      <p className="text-xs text-slate-500">
                        Tailored consultation for your unique goals.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── 4. Featured Services Section ───────────────────── */}
      {sections.services?.enabled !== false && (
        <section id="services-section" className="py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16 space-y-4">
              <h2
                className={`text-3xl sm:text-4xl font-bold tracking-tight ${fontHeading}`}
                style={{ color: theme.textPrimary }}
              >
                {sections.services?.headline || "Signature Services & Treatments"}
              </h2>
              <p className="text-base sm:text-lg" style={{ color: theme.textMuted }}>
                {sections.services?.subhead ||
                  "Explore our highly rated sessions crafted to restore balance and vitality."}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {displayServices.map((svc) => (
                <Card
                  key={svc.id}
                  className={`border overflow-hidden bg-white shadow-sm hover:shadow-lg transition-all duration-300 flex flex-col justify-between ${cardRadius}`}
                  style={{ borderColor: theme.border }}
                >
                  <CardHeader className="p-6">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <Badge variant="outline" className="text-xs font-normal">
                        <Clock className="mr-1 h-3 w-3" />
                        {svc.duration} mins
                      </Badge>
                      {sections.services?.show_prices !== false && svc.price !== undefined && (
                        <span
                          className="text-lg font-bold"
                          style={{ color: primaryColor }}
                        >
                          ${svc.price}
                        </span>
                      )}
                    </div>
                    <CardTitle
                      className={`text-xl font-bold ${fontHeading}`}
                      style={{ color: theme.textPrimary }}
                    >
                      {svc.name}
                    </CardTitle>
                    <CardDescription className="text-sm mt-2 text-slate-600 line-clamp-3">
                      {svc.description || "Personalized treatment tailored to your specific requirements."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-6 pt-0 mt-auto">
                    <Button
                      onClick={() => scrollToBooking(svc.id)}
                      variant="outline"
                      className={`w-full font-medium hover:text-white transition-all ${buttonRadius}`}
                      style={{
                        borderColor: primaryColor,
                        color: primaryColor,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = primaryColor;
                        e.currentTarget.style.color = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = "transparent";
                        e.currentTarget.style.color = primaryColor;
                      }}
                    >
                      Book This Service
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── 5. Booking Section (Natively Embedded) ─────────── */}
      {sections.booking?.enabled !== false && (
        <section
          id="booking-section"
          className="py-20 bg-white border-y relative"
          style={{ borderColor: theme.border }}
        >
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-12 space-y-3">
              <Badge
                className="mb-2"
                style={{ backgroundColor: accentColor, color: theme.accentText }}
              >
                Instant Confirmation
              </Badge>
              <h2
                className={`text-3xl sm:text-4xl font-bold tracking-tight ${fontHeading}`}
                style={{ color: theme.textPrimary }}
              >
                {sections.booking?.headline || "Schedule Your Visit"}
              </h2>
              <p className="text-slate-600 text-sm sm:text-base">
                {sections.booking?.subhead ||
                  "Choose your preferred service, date, and time in just a few clicks."}
              </p>
            </div>

            {/* Embedded Interactive Booking Card or Cal.com Headless Embed */}
            {sections.booking?.booking_mode === "calcom" ? (
              <div
                className={`overflow-hidden border shadow-xl bg-white ${cardRadius}`}
                style={{ borderColor: theme.border }}
              >
                <div className="px-6 py-4 bg-slate-50 border-b flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs font-semibold text-slate-700 tracking-wide uppercase">
                      Live Scheduling Engine
                    </span>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">
                    {sections.booking?.calcom_link || "Cal.com Scheduler"}
                  </span>
                </div>
                <div className="w-full min-h-[680px] bg-white">
                  <iframe
                    src={`https://cal.com/${(sections.booking?.calcom_link || "demo/30min").replace(/^https?:\/\/cal\.com\//, "").trim()}?embed=true&layout=${sections.booking?.calcom_layout || "month_view"}&theme=light`}
                    width="100%"
                    height="700"
                    frameBorder="0"
                    title="Cal.com Booking Scheduler"
                    className="w-full min-h-[700px] border-0"
                  />
                </div>
              </div>
            ) : (
              <div
                className={`p-6 sm:p-10 border shadow-xl bg-white ${cardRadius}`}
                style={{ borderColor: theme.border }}
              >
                {bookingSubmitted ? (
                  <div className="text-center py-12 space-y-4">
                    <div
                      className="w-16 h-16 rounded-full flex items-center justify-center mx-auto text-white"
                      style={{ backgroundColor: primaryColor }}
                    >
                      <CheckCircle2 className="h-8 w-8" />
                    </div>
                    <h3 className="text-2xl font-bold">Booking Request Received!</h3>
                    <p className="text-slate-600 max-w-md mx-auto">
                      Thank you, <strong>{guestName}</strong>. Your session for{" "}
                      <strong>
                        {displayServices.find((s) => String(s.id) === String(selectedServiceId))?.name || "Service"}
                      </strong>{" "}
                      on <strong>{bookingDate}</strong> at <strong>{bookingTime}</strong> has been received.
                    </p>
                    <Button
                      onClick={() => {
                        setBookingSubmitted(false);
                        setGuestName("");
                      }}
                      className={`mt-4 ${buttonRadius}`}
                      style={{ backgroundColor: primaryColor }}
                    >
                      Book Another Appointment
                    </Button>
                  </div>
                ) : (
                  <form onSubmit={handleQuickBook} className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="space-y-2">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          1. Select Service
                        </Label>
                        <select
                          value={selectedServiceId}
                          onChange={(e) => setSelectedServiceId(e.target.value)}
                          className="w-full px-3 py-2 border rounded-md text-sm bg-white focus:ring-2 focus:ring-primary focus:outline-none"
                          style={{ borderColor: theme.border }}
                        >
                          {displayServices.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name} ({s.duration} mins
                              {s.price ? ` - $${s.price}` : ""})
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          2. Date
                        </Label>
                        <Input
                          type="date"
                          value={bookingDate}
                          onChange={(e) => setBookingDate(e.target.value)}
                          className="text-sm"
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          3. Time
                        </Label>
                        <select
                          value={bookingTime}
                          onChange={(e) => setBookingTime(e.target.value)}
                          className="w-full px-3 py-2 border rounded-md text-sm bg-white focus:ring-2 focus:ring-primary focus:outline-none"
                          style={{ borderColor: theme.border }}
                        >
                          {["09:00", "10:00", "11:30", "13:00", "14:30", "16:00", "17:30"].map((t) => (
                            <option key={t} value={t}>
                              {t} (Available)
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="border-t pt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="space-y-1">
                        <Label htmlFor="guestName" className="text-xs font-medium">
                          Your Full Name *
                        </Label>
                        <Input
                          id="guestName"
                          placeholder="Sarah Connor"
                          required
                          value={guestName}
                          onChange={(e) => setGuestName(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="guestEmail" className="text-xs font-medium">
                          Email Address *
                        </Label>
                        <Input
                          id="guestEmail"
                          type="email"
                          placeholder="sarah@example.com"
                          required
                          value={guestEmail}
                          onChange={(e) => setGuestEmail(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="guestPhone" className="text-xs font-medium">
                          Phone Number *
                        </Label>
                        <Input
                          id="guestPhone"
                          type="tel"
                          placeholder="+1 (555) 000-1234"
                          required
                          value={guestPhone}
                          onChange={(e) => setGuestPhone(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t">
                      <div className="text-xs text-slate-500 flex items-center gap-1.5">
                        <ShieldCheck className="h-4 w-4 text-emerald-600" />
                        Free cancellation up to 24 hours prior.
                      </div>
                      <div className="flex items-center gap-3 w-full sm:w-auto">
                        <Button
                          type="submit"
                          size="lg"
                          className={`w-full sm:w-auto font-semibold text-white shadow-md ${buttonRadius}`}
                          style={{ backgroundColor: primaryColor }}
                        >
                          Confirm Booking Request
                        </Button>
                      </div>
                    </div>
                  </form>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── 6. Testimonials Section ────────────────────────── */}
      {sections.testimonials?.enabled !== false && (
        <section id="testimonials-section" className="py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
              <h2
                className={`text-3xl sm:text-4xl font-bold tracking-tight ${fontHeading}`}
                style={{ color: theme.textPrimary }}
              >
                {sections.testimonials?.headline || "What Our Clients Say"}
              </h2>
              <p className="text-base sm:text-lg" style={{ color: theme.textMuted }}>
                {sections.testimonials?.subhead || "Trusted by hundreds of happy clients every month."}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {(
                sections.testimonials?.items || [
                  {
                    name: "Sarah Jenkins",
                    role: "Regular Client",
                    content:
                      "The attention to detail and relaxing ambiance made all the difference. Booking online was effortless!",
                    rating: 5,
                  },
                  {
                    name: "David Miller",
                    role: "Verified Client",
                    content:
                      "Outstanding service from start to finish. Highly recommend their skilled team.",
                    rating: 5,
                  },
                  {
                    name: "Elena Rostova",
                    role: "Monthly Member",
                    content:
                      "A true sanctuary in the middle of a busy week. My favourite place to unwind.",
                    rating: 5,
                  },
                ]
              ).map((t, i) => (
                <div
                  key={i}
                  className={`p-8 bg-white border shadow-sm flex flex-col justify-between ${cardRadius}`}
                  style={{ borderColor: theme.border }}
                >
                  <div className="space-y-4">
                    <div className="flex items-center gap-1 text-amber-400">
                      {Array.from({ length: t.rating || 5 }).map((_, r) => (
                        <Star key={r} className="h-4 w-4 fill-current" />
                      ))}
                    </div>
                    <p className="text-slate-600 text-sm italic leading-relaxed">
                      "{t.content}"
                    </p>
                  </div>
                  <div className="pt-6 border-t mt-6 flex items-center gap-3">
                    <div
                      className="h-9 w-9 rounded-full flex items-center justify-center font-bold text-xs text-white"
                      style={{ backgroundColor: primaryColor }}
                    >
                      {t.name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-sm font-semibold">{t.name}</div>
                      <div className="text-xs text-slate-400">{t.role || "Client"}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── 7. Contact & Opening Hours Section ─────────────── */}
      {sections.contact?.enabled !== false && (
        <section
          id="contact-section"
          className="py-20 bg-white border-y"
          style={{ borderColor: theme.border }}
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
              <div className="space-y-6">
                <h2
                  className={`text-3xl sm:text-4xl font-bold tracking-tight ${fontHeading}`}
                  style={{ color: theme.textPrimary }}
                >
                  {sections.contact?.headline || "Visit or Reach Out"}
                </h2>
                <p className="text-base text-slate-600">
                  {sections.contact?.subhead || "We look forward to welcoming you soon."}
                </p>

                <div className="space-y-4 pt-4">
                  {(sections.contact?.address || tenantAddress) && (
                    <div className="flex items-start gap-3">
                      <div
                        className="p-2 rounded-lg text-white mt-1"
                        style={{ backgroundColor: primaryColor }}
                      >
                        <MapPin className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                          Location Address
                        </div>
                        <div className="text-sm font-medium mt-0.5">
                          {sections.contact?.address || tenantAddress}
                        </div>
                      </div>
                    </div>
                  )}

                  {(sections.contact?.phone || tenantPhone) && (
                    <div className="flex items-start gap-3">
                      <div
                        className="p-2 rounded-lg text-white mt-1"
                        style={{ backgroundColor: primaryColor }}
                      >
                        <Phone className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                          Telephone
                        </div>
                        <a
                          href={`tel:${sections.contact?.phone || tenantPhone}`}
                          className="text-sm font-medium hover:underline mt-0.5 block"
                        >
                          {sections.contact?.phone || tenantPhone}
                        </a>
                      </div>
                    </div>
                  )}

                  {(sections.contact?.email || tenantEmail) && (
                    <div className="flex items-start gap-3">
                      <div
                        className="p-2 rounded-lg text-white mt-1"
                        style={{ backgroundColor: primaryColor }}
                      >
                        <Mail className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                          Email Enquiries
                        </div>
                        <a
                          href={`mailto:${sections.contact?.email || tenantEmail}`}
                          className="text-sm font-medium hover:underline mt-0.5 block"
                        >
                          {sections.contact?.email || tenantEmail}
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div
                className={`p-8 border shadow-sm bg-slate-50/50 ${cardRadius}`}
                style={{ borderColor: theme.border }}
              >
                <div className="flex items-center gap-2 mb-6">
                  <Clock className="h-5 w-5" style={{ color: primaryColor }} />
                  <h3 className="text-xl font-bold">Opening Hours</h3>
                </div>
                <div className="space-y-3 whitespace-pre-line text-sm text-slate-700 leading-relaxed">
                  {sections.contact?.hours ||
                    "Monday - Friday: 9:00 AM - 7:00 PM\nSaturday: 10:00 AM - 6:00 PM\nSunday: Closed"}
                </div>
                <div className="mt-8 pt-6 border-t border-slate-200">
                  <Button
                    onClick={() => scrollToBooking()}
                    className={`w-full font-semibold text-white ${buttonRadius}`}
                    style={{ backgroundColor: primaryColor }}
                  >
                    Reserve Appointment
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── 8. Footer ──────────────────────────────────────── */}
      <footer
        className="py-12 border-t bg-slate-900 text-slate-400 text-sm"
        style={{ borderColor: theme.border }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div>
            <span className="font-bold text-white tracking-wide text-base">
              {tenantName}
            </span>
            <p className="text-xs text-slate-500 mt-1">
              {sections.footer?.copyright || `© ${new Date().getFullYear()} ${tenantName}. All rights reserved.`}
            </p>
          </div>

          <div className="flex items-center gap-6">
            <a
              href="#about-section"
              className="hover:text-white transition-colors text-xs"
            >
              About
            </a>
            <a
              href="#services-section"
              className="hover:text-white transition-colors text-xs"
            >
              Services
            </a>
            <a
              href="#booking-section"
              className="hover:text-white transition-colors text-xs"
            >
              Book
            </a>
            <a
              href="#contact-section"
              className="hover:text-white transition-colors text-xs"
            >
              Hours
            </a>
          </div>

          <div className="flex items-center gap-4">
            <a
              href={sections.footer?.social_links?.instagram || "https://instagram.com"}
              target="_blank"
              rel="noreferrer"
              className="p-2 rounded-full hover:bg-slate-800 hover:text-white transition-colors"
              aria-label="Instagram"
            >
              <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
              </svg>
            </a>
            <a
              href={sections.footer?.social_links?.facebook || "https://facebook.com"}
              target="_blank"
              rel="noreferrer"
              className="p-2 rounded-full hover:bg-slate-800 hover:text-white transition-colors"
              aria-label="Facebook"
            >
              <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
              </svg>
            </a>
            <a
              href={sections.footer?.social_links?.twitter || "https://twitter.com"}
              target="_blank"
              rel="noreferrer"
              className="p-2 rounded-full hover:bg-slate-800 hover:text-white transition-colors"
              aria-label="Twitter"
            >
              <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
            </a>
          </div>
        </div>
      </footer>

      {/* ── FLOATING CHAT WIDGET & PROACTIVE INVITATION BANNER ── */}
      <WebsiteChatWidget
        tenantName={tenantName}
        tenantSubdomain={tenantSubdomain}
        tenantPhone={tenantPhone}
        tenantLogoUrl={tenantLogoUrl}
        config={sections.chat_widget}
        primaryColor={primaryColor}
        isInteractivePreview={isInteractivePreview}
      />
    </div>
  );
}

export default function PublicWebsitePage() {
  const { subdomain } = useParams<{ subdomain?: string }>();
  const [searchParams] = useSearchParams();
  const isPreview = searchParams.get("preview") === "true";

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [siteData, setSiteData] = useState<any>(null);

  useEffect(() => {
    async function loadWebsite() {
      try {
        setLoading(true);
        setError(null);

        const queryStr = isPreview ? "?preview=true" : "";
        const res = await fetch(`/api/public/website${queryStr}`, {
          headers: subdomain ? { "X-Tenant": subdomain } : {},
        });

        if (!res.ok) {
          if (res.status === 404) {
            setError("This website is not published yet. Please check back later!");
          } else {
            setError("Unable to load website configuration.");
          }
          return;
        }

        const json = await res.json();
        if (json.ok && json.data) {
          setSiteData(json.data);
          if (json.data.config?.seo_title) {
            document.title = json.data.config.seo_title;
          }
        } else {
          setError("Invalid website response.");
        }
      } catch (err: any) {
        setError(err.message || "Failed to load website.");
      } finally {
        setLoading(false);
      }
    }

    loadWebsite();
  }, [subdomain, isPreview]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-slate-500 font-medium">Loading website...</p>
        </div>
      </div>
    );
  }

  if (error || !siteData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-sm border border-slate-200 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center mx-auto">
            <Sparkles className="h-6 w-6" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Website Under Construction</h2>
          <p className="text-sm text-slate-600">{error || "This site is not currently published."}</p>
          <div className="pt-2">
            <a
              href="/admin/website"
              className="text-xs text-primary underline underline-offset-4 font-semibold"
            >
              Go to Website Builder
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <PublicWebsiteView
      config={siteData.config}
      tenantName={siteData.tenant_name}
      tenantSubdomain={siteData.tenant_subdomain}
      tenantEmail={siteData.tenant_email}
      tenantPhone={siteData.tenant_phone}
      tenantAddress={siteData.tenant_address}
      tenantLogoUrl={siteData.tenant_logo_url}
      services={siteData.services || []}
    />
  );
}
