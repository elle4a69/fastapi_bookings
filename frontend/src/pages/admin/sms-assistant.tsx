import { useState } from "react";
import { MessageSquareTextIcon, Settings, UserSquare2, PlayCircle, Activity, Inbox, Link2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// Component imports
import SmsInboxTab from "./sms/inbox";
import SmsAccountsTab from "./sms/accounts";
import SmsSettingsTab from "./sms/settings";
import SmsSimulatorTab from "./sms/simulator";
import SmsDiagnosticsTab from "./sms/diagnostics";
import SmsChatwootTab from "./sms/chatwoot";

export default function SmsAssistantPage() {
  const [activeTab, setActiveTab] = useState("inbox");

  return (
    <section className="flex min-h-0 w-full flex-1 flex-col gap-4 p-4 md:p-6 text-xs">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-primary">Messaging workspace</p>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            <MessageSquareTextIcon className="size-7 text-primary" />
            SMS Assistant
          </h1>
          <p className="text-sm text-muted-foreground">
            Native SMS management inbox, autoresponder, prompt settings, and diagnostic tools.
          </p>
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col space-y-4">
          <TabsList className="bg-muted/50 border p-1 rounded-lg self-start flex gap-1 h-9">
            <TabsTrigger value="inbox" className="text-xs px-3 h-7">
              <Inbox className="w-3.5 h-3.5 mr-1.5" /> Inbox
            </TabsTrigger>
            <TabsTrigger value="accounts" className="text-xs px-3 h-7">
              <UserSquare2 className="w-3.5 h-3.5 mr-1.5" /> SMS Lines
            </TabsTrigger>
            <TabsTrigger value="chatwoot" className="text-xs px-3 h-7">
              <Link2 className="w-3.5 h-3.5 mr-1.5" /> Chatwoot
            </TabsTrigger>
            <TabsTrigger value="settings" className="text-xs px-3 h-7">
              <Settings className="w-3.5 h-3.5 mr-1.5" /> RAG & Prompts
            </TabsTrigger>
            <TabsTrigger value="simulator" className="text-xs px-3 h-7">
              <PlayCircle className="w-3.5 h-3.5 mr-1.5" /> Simulator
            </TabsTrigger>
            <TabsTrigger value="diagnostics" className="text-xs px-3 h-7">
              <Activity className="w-3.5 h-3.5 mr-1.5" /> Diagnostics
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 min-h-0">
            <TabsContent value="inbox" className="mt-0 h-full">
              <SmsInboxTab />
            </TabsContent>
            <TabsContent value="accounts" className="mt-0">
              <SmsAccountsTab />
            </TabsContent>
            <TabsContent value="chatwoot" className="mt-0">
              <SmsChatwootTab />
            </TabsContent>
            <TabsContent value="settings" className="mt-0">
              <SmsSettingsTab />
            </TabsContent>
            <TabsContent value="simulator" className="mt-0">
              <SmsSimulatorTab />
            </TabsContent>
            <TabsContent value="diagnostics" className="mt-0">
              <SmsDiagnosticsTab />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </section>
  );
}
