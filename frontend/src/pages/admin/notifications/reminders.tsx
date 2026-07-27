import { useEffect, useState } from "react";
import { apiClient } from "../../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Switch } from "../../../components/ui/switch";
import { ScrollArea } from "../../../components/ui/scroll-area";
import { Plus } from "lucide-react";
import { toast } from "sonner";

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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [rulesData, templatesData] = await Promise.all([
        apiClient.get<ReminderRule[]>("/api/admin/reminder-rules"),
        apiClient.get<Template[]>("/api/admin/notifications/templates")
      ]);
      setRules(rulesData);
      setTemplates(templatesData);
      if (rulesData.length > 0 && !selectedRule) {
        setSelectedRule(rulesData[0]);
      }
    } catch (error) {
      toast.error("Failed to fetch reminder rules");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedRule) return;
    setSaving(true);
    try {
      if (selectedRule.id.startsWith("new_")) {
        await apiClient.post("/api/admin/reminder-rules", selectedRule);
      } else {
        await apiClient.put(`/api/admin/reminder-rules/${selectedRule.id}`, selectedRule);
      }
      toast.success("Reminder rule saved successfully");
      fetchData();
    } catch (error) {
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
      templateId: "",
      isActive: true,
    };
    setRules([newRule, ...rules]);
    setSelectedRule(newRule);
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Reminder Rules</h1>
          <p className="text-muted-foreground">Configure automated reminder triggers.</p>
        </div>
        <Button onClick={handleNewRule}>
          <Plus className="w-4 h-4 mr-2" /> New Rule
        </Button>
      </div>

      <div className="flex flex-1 gap-6 min-h-[500px]">
        {/* Left Sidebar */}
        <Card className="w-1/3 flex flex-col">
          <CardHeader>
            <CardTitle>Rules</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="p-4 text-center">Loading...</div>
              ) : (
                <div className="flex flex-col p-2 space-y-1">
                  {rules.map((rule) => (
                    <button
                      key={rule.id}
                      onClick={() => setSelectedRule(rule)}
                      className={`text-left p-3 rounded-md transition-colors ${
                        selectedRule?.id === rule.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted"
                      }`}
                    >
                      <div className="font-medium">{rule.name}</div>
                      <div className="text-xs opacity-80">
                        {rule.hoursTrigger} hours {rule.direction.toLowerCase()}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Right Editor */}
        <Card className="w-2/3">
          {selectedRule ? (
            <>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Edit Rule</CardTitle>
                <div className="flex items-center space-x-2">
                  <Label htmlFor="active-status">Active</Label>
                  <Switch
                    id="active-status"
                    checked={selectedRule.isActive}
                    onCheckedChange={(checked) => setSelectedRule({ ...selectedRule, isActive: checked })}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Rule Name</Label>
                  <Input
                    value={selectedRule.name}
                    onChange={(e) => setSelectedRule({ ...selectedRule, name: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Hours Trigger</Label>
                    <Input
                      type="number"
                      min={1}
                      value={selectedRule.hoursTrigger}
                      onChange={(e) => setSelectedRule({ ...selectedRule, hoursTrigger: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Direction</Label>
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      value={selectedRule.direction}
                      onChange={(e) => setSelectedRule({ ...selectedRule, direction: e.target.value as "BEFORE" | "AFTER" })}
                    >
                      <option value="BEFORE">Before Booking</option>
                      <option value="AFTER">After Booking</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Message Template</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    value={selectedRule.templateId}
                    onChange={(e) => setSelectedRule({ ...selectedRule, templateId: e.target.value })}
                  >
                    <option value="" disabled>Select a template</option>
                    {templates.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {tpl.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-end pt-4">
                  <Button onClick={handleSave} disabled={saving}>
                    {saving ? "Saving..." : "Save Rule"}
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Select a rule to edit
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
