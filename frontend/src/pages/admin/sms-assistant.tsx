import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { 
  ChevronLeft,
  ChevronRight,
  MessagesSquare,
  UserCheck,
  DoorOpen,
  Smartphone,
  Bot,
  Settings, 
  UserSquare2, 
  PlayCircle, 
  Activity, 
  Inbox, 
  Link2,
  BellRing,
  Sliders,
  Sparkles,
  Terminal,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
// Component imports
import AssistantMessagesPage from "./sms/assistant-messages-page";
import SmsInboxTab from "./sms/inbox";
import SmsArrivalsTab from "./sms/arrivals-tab";
import SmsTriageTab from "./sms/triage-tab";
import AssistantBootcampPage from "./sms/assistant-bootcamp-page";
import BootcampSettingsTab from "./sms/bootcamp-settings-tab";
import SmsAgentConsoleTab from "./sms/agent-console-tab";
import SmsAccountsTab from "./sms/accounts";
import SmsSettingsTab from "./sms/settings";
import SmsSimulatorTab from "./sms/simulator";
import SmsDiagnosticsTab from "./sms/diagnostics";
import SmsChatwootTab from "./sms/chatwoot";

const TABS_CONFIG = [
  { id: "messages", label: "Messages", icon: MessagesSquare, color: "text-indigo-500" },
  { id: "inbox", label: "Inbox", icon: Inbox, color: "text-foreground" },
  { id: "arrivals", label: "Arrivals", icon: BellRing, color: "text-amber-500" },
  { id: "triage", label: "Draft Triage", icon: Sparkles, color: "text-indigo-500" },
  { id: "bootcamp", label: "Bootcamp", icon: Bot, color: "text-purple-500" },
  { id: "bootcamp-settings", label: "Camp Settings", icon: Sliders, color: "text-indigo-500" },
  { id: "console", label: "Console", icon: Terminal, color: "text-emerald-500" },
  { id: "accounts", label: "SMS Lines", icon: UserSquare2, color: "text-foreground" },
  { id: "chatwoot", label: "Chatwoot", icon: Link2, color: "text-foreground" },
  { id: "settings", label: "RAG & Prompts", icon: Settings, color: "text-foreground" },
  { id: "simulator", label: "Simulator", icon: PlayCircle, color: "text-foreground" },
  { id: "diagnostics", label: "Diagnostics", icon: Activity, color: "text-foreground" },
];

const BOTTOM_TABS = [
  { id: "messages", label: "Messages", icon: MessagesSquare },
  { id: "inbox", label: "Console", icon: UserCheck },
  { id: "arrivals", label: "Arrivals", icon: DoorOpen },
  { id: "triage", label: "Triage", icon: Sparkles },
  { id: "simulator", label: "SMS Sim", icon: Smartphone },
  { id: "bootcamp", label: "Camp", icon: Bot },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function SmsAssistantPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState(tabFromUrl || "messages");
  const tabsScrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    const el = tabsScrollRef.current;
    if (!el) return;
    const { scrollLeft, scrollWidth, clientWidth } = el;
    setCanScrollLeft(scrollLeft > 2);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 2);
  }, []);

  const scrollTabs = useCallback((direction: "left" | "right") => {
    if (tabsScrollRef.current) {
      const offset = direction === "left" ? -200 : 200;
      tabsScrollRef.current.scrollBy({ left: offset, behavior: "smooth" });
    }
  }, []);

  const handleTabChange = useCallback((tabId: string) => {
    setActiveTab(tabId);
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set("tab", tabId);
      return p;
    }, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    if (tabFromUrl && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    }
  }, [tabFromUrl, activeTab]);

  useEffect(() => {
    const handleNav = (e: any) => {
      if (e.detail && typeof e.detail === "string") {
        handleTabChange(e.detail);
      }
    };
    window.addEventListener("sms-navigate-tab", handleNav);
    return () => window.removeEventListener("sms-navigate-tab", handleNav);
  }, [handleTabChange]);

  useEffect(() => {
    checkScroll();
    const el = tabsScrollRef.current;
    if (!el) return;

    const resizeObserver = new ResizeObserver(() => {
      checkScroll();
    });
    resizeObserver.observe(el);

    window.addEventListener("resize", checkScroll);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", checkScroll);
    };
  }, [checkScroll]);

  // Smoothly center the active tab in view if it changes
  useEffect(() => {
    if (!tabsScrollRef.current) return;
    const activeEl = tabsScrollRef.current.querySelector<HTMLElement>(`[data-tab-id="${activeTab}"]`);
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [activeTab]);

  return (
    <section className="flex min-h-0 w-full flex-1 flex-col gap-0 p-0 text-xs bg-background">
      <div className="flex-1 flex flex-col min-h-0">
        <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0 space-y-0">
          {/* Horizontal Slider Tabs bar with Left/Right Controls and Fade Masks */}
          <div className="border-b border-border/80 bg-card/60 backdrop-blur-xs shrink-0">
            <div className="relative flex items-center p-1 max-w-full">
              {/* Left Scroll Button */}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => scrollTabs("left")}
                disabled={!canScrollLeft}
                aria-label="Scroll tabs left"
                className={`h-7 w-7 shrink-0 rounded-md p-0 transition-opacity z-20 ${
                  canScrollLeft 
                    ? "opacity-100 hover:bg-muted text-foreground cursor-pointer" 
                    : "opacity-20 cursor-not-allowed pointer-events-none"
                }`}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>

              {/* Left Fade Mask */}
              {canScrollLeft && (
                <div 
                  aria-hidden="true" 
                  className="pointer-events-none absolute left-8 top-1 bottom-1 w-6 bg-gradient-to-r from-card to-transparent z-10" 
                />
              )}

              {/* Scrollable Tabs List Container */}
              <div
                ref={tabsScrollRef}
                onScroll={checkScroll}
                className="flex-1 overflow-x-auto no-scrollbar scroll-smooth flex-nowrap shrink-0"
              >
                <TabsList className="bg-transparent border-0 p-0 flex flex-nowrap gap-1 h-8 w-max">
                  {TABS_CONFIG.map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <TabsTrigger
                        key={tab.id}
                        value={tab.id}
                        data-tab-id={tab.id}
                        className="text-xs px-3 h-7 gap-1.5 whitespace-nowrap shrink-0 flex-nowrap"
                      >
                        <Icon className={`w-3.5 h-3.5 ${tab.color}`} /> {tab.label}
                      </TabsTrigger>
                    );
                  })}
                </TabsList>
              </div>

              {/* Right Fade Mask */}
              {canScrollRight && (
                <div 
                  aria-hidden="true" 
                  className="pointer-events-none absolute right-8 top-1 bottom-1 w-6 bg-gradient-to-l from-card to-transparent z-10" 
                />
              )}

              {/* Right Scroll Button */}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => scrollTabs("right")}
                disabled={!canScrollRight}
                aria-label="Scroll tabs right"
                className={`h-7 w-7 shrink-0 rounded-md p-0 transition-opacity z-20 ${
                  canScrollRight 
                    ? "opacity-100 hover:bg-muted text-foreground cursor-pointer" 
                    : "opacity-20 cursor-not-allowed pointer-events-none"
                }`}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <TabsContent value="messages" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <AssistantMessagesPage onNavigate={setActiveTab} />
          </TabsContent>
          <TabsContent value="inbox" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <SmsInboxTab onNavigate={setActiveTab} />
          </TabsContent>
          <TabsContent value="arrivals" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsArrivalsTab />
            </div>
          </TabsContent>
          <TabsContent value="triage" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsTriageTab />
            </div>
          </TabsContent>
          <TabsContent value="bootcamp" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <AssistantBootcampPage onNavigate={handleTabChange} />
          </TabsContent>
          <TabsContent value="bootcamp-settings" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <BootcampSettingsTab onBackToBootcamp={() => handleTabChange("bootcamp")} />
            </div>
          </TabsContent>
          <TabsContent value="console" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsAgentConsoleTab />
            </div>
          </TabsContent>
          <TabsContent value="accounts" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsAccountsTab />
            </div>
          </TabsContent>
          <TabsContent value="chatwoot" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsChatwootTab />
            </div>
          </TabsContent>
          <TabsContent value="settings" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsSettingsTab />
            </div>
          </TabsContent>
          <TabsContent value="simulator" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsSimulatorTab onNavigate={setActiveTab} />
            </div>
          </TabsContent>
          <TabsContent value="diagnostics" className="mt-0 flex-1 min-h-0 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
              <SmsDiagnosticsTab />
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Mobile Bottom Navigation Menu */}
      <nav data-testid="mobile-bottom-nav" className="flex h-16 w-full shrink-0 border-t border-slate-800 bg-slate-900 text-white shadow-lg sm:hidden z-40 select-none">
        <div className="flex w-full items-center justify-around px-1 overflow-x-auto no-scrollbar">
          {BOTTOM_TABS.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`flex flex-col items-center justify-center flex-1 min-w-[54px] py-1 transition-colors cursor-pointer bg-transparent border-none ${
                  active ? 'text-indigo-400 font-bold' : 'text-slate-400'
                }`}
              >
                <tab.icon className="w-4.5 h-4.5 mb-0.5" />
                <span className="text-[9.5px] tracking-tight">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </section>
  );
}
