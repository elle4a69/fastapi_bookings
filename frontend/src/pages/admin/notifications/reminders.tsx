import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Plus, Clock, Save, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { MobilePageShell, MobileBackButton } from "@/components/ui/mobile-page-shell";

interface ReminderRule {
  id: string;
  name: string;
  hoursTrigger: number;
  direction: "BEFORE" | "AFTER";
  templateId: string;
  isActive: boolean;
}

interface Template {
  id: string;
  name: string;
}

export default function RemindersPage() {
  const [rules, setRules] = useState<ReminderRule[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedRule, setSelectedRule] = useState<ReminderRule | null>(null);
  const [mobileDetailView, setMobileDetailView] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [rulesRes, templatesRes] = await Promise.all([
        apiClient.get<any>("/api/admin/reminder-rules"),
        apiClient.get<any>("/api/admin/notification-templates")
      ]);
      const rList = Array.isArray(rulesRes) ? rulesRes : rulesRes?.data || [];
      const tList = Array.isArray(templatesRes) ? templatesRes : templatesRes?.data || [];

      const normalizedRules: ReminderRule[] = rList.map((r: any) => ({
        id: String(r.id),
        name: r.name,
        hoursTrigger: Number(r.trigger_hours_before ?? r.hoursTrigger ?? 24),
        direction: "BEFORE",
        templateId: String(r.template_id || ""),
        isActive: Boolean(r.active ?? r.isActive ?? true),
      }));

      const normalizedTemplates: Template[] = tList.map((t: any) => ({
        id: String(t.id),
        name: t.code || t.name || `Template ${t.id}`,
      }));

      setRules(normalizedRules);
      setTemplates(normalizedTemplates);
      if (normalizedRules.length > 0 && !selectedRule) {
        setSelectedRule(normalizedRules[0]);
      }
    } catch {
      toast.error("Failed to fetch reminder rules");
    } finally {
      setLoading(false);
    }
  }, [selectedRule]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSave = async () => {
    if (!selectedRule) return;
    setSaving(true);
    try {
      const payload = {
        name: selectedRule.name,
        trigger_hours_before: selectedRule.hoursTrigger,
        template_id: selectedRule.templateId ? Number(selectedRule.templateId) : null,
        active: selectedRule.isActive,
      };

      if (selectedRule.id.startsWith("new_")) {
        await apiClient.post("/api/admin/reminder-rules", payload);
      } else {
        await apiClient.put(`/api/admin/reminder-rules/${selectedRule.id}`, payload);
      }
      toast.success("Reminder rule saved successfully");
      fetchData();
    } catch {
      toast.error("Failed to save reminder rule");
    } finally {
      setSaving(false);
    }
  };

  const handleNewRule = () => {
    const newRule: ReminderRule = {
      id: `new_${Date.now()}`,
      name: "New Reminder Rule",
      hoursTrigger: 24,
      direction: "BEFORE",
      templateId: templates.length > 0 ? templates[0].id : "",
      isActive: true,
    };
    setRules([newRule, ...rules]);
    setSelectedRule(newRule);
    setMobileDetailView(true);
  };

  const handleSelectRule = (rule: ReminderRule) => {
    setSelectedRule(rule);
    setMobileDetailView(true);
  };

  return (
    <MobilePageShell
      title="Reminder Rules"
      description="Configure automated booking reminder schedules and notifications."
      actions={
        <Button 
          onClick={handleNewRule}
          className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-1.5 text-xs sm:text-sm font-medium"
        >
          <Plus className="w-4 h-4 shrink-0" />
          <span>New Rule</span>
        </Button>
      }
    >
      <div className="flex flex-col sm:flex-row flex-1 gap-4 sm:gap-6 min-h-[520px]">
        {/* Master List: Hidden on mobile when viewing detail */}
        <Card className={`w-full sm:w-80 md:w-96 flex flex-col shrink-0 ${mobileDetailView ? "hidden sm:flex" : "flex"}`}>
          <CardHeader className="py-3 px-4 border-b">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold">Scheduled Triggers</CardTitle>
              <Badge variant="secondary" className="text-xs font-mono">
                {rules.length}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[420px] sm:h-[500px]">
              {loading ? (
                <div className="p-6 text-center text-xs text-muted-foreground">Loading rules...</div>
              ) : rules.length === 0 ? (
                <div className="p-6 text-center text-xs text-muted-foreground">No reminder rules defined.</div>
              ) : (
                <div className="flex flex-col p-2 space-y-1">
                  {rules.map((rule) => (
                    <button
                      key={rule.id}
                      type="button"
                      onClick={() => handleSelectRule(rule)}
                      className={`w-full text-left p-3 rounded-lg min-h-[44px] transition-colors flex items-center justify-between gap-2 touch-manipulation ${
                        selectedRule?.id === rule.id
                          ? "bg-primary text-primary-foreground shadow-xs"
                          : "hover:bg-muted/60 text-foreground"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-xs sm:text-sm truncate">{rule.name}</div>
                        <div className="flex items-center gap-1.5 mt-0.5 text-[11px] opacity-80">
                          <Clock className="w-3 h-3 shrink-0" />
                          <span>{rule.hoursTrigger} hours {rule.direction.toLowerCase()}</span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 shrink-0 opacity-60 sm:hidden" />
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Detail Editor: Visible on desktop always, or on mobile when a rule is selected */}
        <Card className={`flex-1 min-w-0 flex flex-col ${!mobileDetailView ? "hidden sm:flex" : "flex"}`}>
          {selectedRule ? (
            <>
              <CardHeader className="py-3 px-4 border-b flex flex-row items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="sm:hidden">
                    <MobileBackButton 
                      label="Rules" 
                      onClick={() => setMobileDetailView(false)}
                      className="px-1.5 -ml-2"
                    />
                  </div>
                  <CardTitle className="text-sm font-bold truncate">
                    {selectedRule.id.startsWith("new_") ? "Create Reminder Rule" : "Edit Rule"}
                  </CardTitle>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Label htmlFor="active-status" className="text-xs text-muted-foreground hidden sm:inline">Active</Label>
                  <Switch
                    id="active-status"
                    checked={selectedRule.isActive}
                    onCheckedChange={(checked) => setSelectedRule({ ...selectedRule, isActive: checked })}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4 p-4 flex-1">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Rule Name</Label>
                  <Input
                    value={selectedRule.name}
                    onChange={(e) => setSelectedRule({ ...selectedRule, name: e.target.value })}
                    placeholder="e.g. 24h Before Reminder"
                    className="h-10 min-h-[44px] text-xs sm:text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">Hours Trigger</Label>
                    <Input
                      type="number"
                      min={1}
                      value={selectedRule.hoursTrigger}
                      onChange={(e) => setSelectedRule({ ...selectedRule, hoursTrigger: parseInt(e.target.value) || 0 })}
                      className="h-10 min-h-[44px] text-xs sm:text-sm"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">Direction</Label>
                    <select
                      className="flex h-10 min-h-[44px] w-full rounded-md border border-input bg-background px-3 py-2 text-xs sm:text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 touch-manipulation"
                      value={selectedRule.direction}
                      onChange={(e) => setSelectedRule({ ...selectedRule, direction: e.target.value as "BEFORE" | "AFTER" })}
                    >
                      <option value="BEFORE">Before Booking</option>
                      <option value="AFTER">After Booking</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Associated Template</Label>
                  <select
                    className="flex h-10 min-h-[44px] w-full rounded-md border border-input bg-background px-3 py-2 text-xs sm:text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 touch-manipulation"
                    value={selectedRule.templateId}
                    onChange={(e) => setSelectedRule({ ...selectedRule, templateId: e.target.value })}
                  >
                    <option value="" disabled>Select a notification template</option>
                    {templates.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {tpl.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col sm:flex-row justify-end gap-2 pt-4 border-t mt-auto">
                  <Button 
                    type="button"
                    variant="outline"
                    onClick={() => setMobileDetailView(false)}
                    className="sm:hidden h-10 min-h-[44px] w-full touch-manipulation text-xs"
                  >
                    Back to Rules
                  </Button>
                  <Button 
                    onClick={handleSave} 
                    disabled={saving}
                    className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-1.5 text-xs sm:text-sm font-medium"
                  >
                    <Save className="w-4 h-4 shrink-0" />
                    <span>{saving ? "Saving..." : "Save Rule"}</span>
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex items-center justify-center h-full p-8 text-xs text-muted-foreground text-center">
              Select a reminder rule from the list to view or edit configuration.
            </div>
          )}
        </Card>
      </div>
    </MobilePageShell>
  );
}
