import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MobilePageShell, MobileBackButton } from "@/components/ui/mobile-page-shell";
import { Plus, Tag, Mail, MessageSquare } from "lucide-react";
import { toast } from "sonner";

interface Template {
  id: string;
  name: string;
  type: "EMAIL" | "SMS";
  subject: string;
  body: string;
  isActive: boolean;
}

const TEMPLATE_VARIABLES = [
  "client_name",
  "client_phone",
  "client_email",
  "service_name",
  "service_price",
  "service_duration",
  "provider_name",
  "location_name",
  "location_address",
  "booking_date",
  "booking_time",
  "status",
  "notes",
];

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isMobileEditing, setIsMobileEditing] = useState(false);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<any>("/api/admin/notification-templates");
      const list = Array.isArray(res) ? res : res?.data || [];
      const normalized: Template[] = list.map((tmpl: any) => ({
        id: String(tmpl.id),
        name: tmpl.code || tmpl.name || `Template ${tmpl.id}`,
        type: ((tmpl.channel || tmpl.type || "EMAIL").toUpperCase() === "SMS" ? "SMS" : "EMAIL") as "EMAIL" | "SMS",
        subject: tmpl.subject || "",
        body: tmpl.body || "",
        isActive: true,
      }));
      setTemplates(normalized);
      if (normalized.length > 0 && !selectedTemplate) {
        setSelectedTemplate(normalized[0]);
      }
    } catch {
      toast.error("Failed to fetch templates");
    } finally {
      setLoading(false);
    }
  }, [selectedTemplate]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleSave = async () => {
    if (!selectedTemplate) return;
    setSaving(true);
    try {
      const payload = {
        code: selectedTemplate.name.trim().toLowerCase().replace(/\s+/g, "_"),
        channel: selectedTemplate.type.toLowerCase(),
        subject: selectedTemplate.subject || null,
        body: selectedTemplate.body || "",
      };

      if (selectedTemplate.id.startsWith("new_")) {
        await apiClient.post("/api/admin/notification-templates", payload);
      } else {
        await apiClient.put(`/api/admin/notification-templates/${selectedTemplate.id}`, payload);
      }
      toast.success("Template saved successfully");
      fetchTemplates();
    } catch {
      toast.error("Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  const handleNewTemplate = () => {
    const newTemplate: Template = {
      id: `new_${Date.now()}`,
      name: "New Template",
      type: "EMAIL",
      subject: "",
      body: "",
      isActive: true,
    };
    setTemplates([newTemplate, ...templates]);
    setSelectedTemplate(newTemplate);
    setIsMobileEditing(true);
  };

  const insertTag = (tag: string) => {
    if (!selectedTemplate) return;
    setSelectedTemplate({
      ...selectedTemplate,
      body: selectedTemplate.body + ` {{${tag}}} `,
    });
  };

  return (
    <MobilePageShell
      title="Message Templates"
      description="Manage templates for email and SMS notifications."
      actions={
        <Button onClick={handleNewTemplate} className="min-h-[44px] gap-2 w-full sm:w-auto">
          <Plus className="w-4 h-4" /> New Template
        </Button>
      }
    >
      <div className="flex flex-col md:flex-row gap-6 min-h-[500px]">
        {/* Left List (hidden on mobile when editing) */}
        <Card className={`w-full md:w-80 lg:w-96 flex flex-col shrink-0 ${isMobileEditing ? 'hidden md:flex' : 'flex'}`}>
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-base font-semibold">Templates ({templates.length})</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[400px] md:h-[550px]">
              {loading ? (
                <div className="p-4 text-center text-sm text-muted-foreground">Loading templates...</div>
              ) : templates.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">No templates configured yet.</div>
              ) : (
                <div className="flex flex-col p-2 space-y-1">
                  {templates.map((tpl) => (
                    <button
                      key={tpl.id}
                      type="button"
                      onClick={() => {
                        setSelectedTemplate(tpl);
                        setIsMobileEditing(true);
                      }}
                      className={`text-left p-3 rounded-lg transition-colors min-h-[44px] flex items-center justify-between gap-2 ${
                        selectedTemplate?.id === tpl.id
                          ? "bg-primary text-primary-foreground font-medium shadow-xs"
                          : "hover:bg-muted/70 text-foreground"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm truncate">{tpl.name}</div>
                        <div className="text-xs opacity-75 truncate">{tpl.subject || "No subject"}</div>
                      </div>
                      <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${
                        selectedTemplate?.id === tpl.id ? "bg-white/20 text-white" : "bg-muted text-muted-foreground"
                      }`}>
                        {tpl.type === "SMS" ? <MessageSquare className="w-3 h-3" /> : <Mail className="w-3 h-3" />}
                        {tpl.type}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Right Editor (shown full screen on mobile when editing, or hidden on mobile when not editing) */}
        <Card className={`w-full flex-1 flex flex-col ${!isMobileEditing ? 'hidden md:flex' : 'flex'}`}>
          {selectedTemplate ? (
            <>
              <CardHeader className="flex flex-row items-center justify-between border-b py-3 px-4 sm:px-6">
                <div className="flex items-center gap-2">
                  <div className="md:hidden">
                    <MobileBackButton label="Templates" onClick={() => setIsMobileEditing(false)} />
                  </div>
                  <CardTitle className="text-base sm:text-lg">Edit Template</CardTitle>
                </div>
                <div className="flex items-center space-x-2">
                  <Label htmlFor="active-status" className="text-xs sm:text-sm font-medium">Active</Label>
                  <Switch
                    id="active-status"
                    checked={selectedTemplate.isActive}
                    onCheckedChange={(checked) => setSelectedTemplate({ ...selectedTemplate, isActive: checked })}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4 p-4 sm:p-6 flex-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Template Code / Name</Label>
                    <Input
                      className="min-h-[44px]"
                      value={selectedTemplate.name}
                      onChange={(e) => setSelectedTemplate({ ...selectedTemplate, name: e.target.value })}
                      placeholder="e.g. appointment_reminder"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Channel Type</Label>
                    <select
                      className="flex h-11 min-h-[44px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      value={selectedTemplate.type}
                      onChange={(e) => setSelectedTemplate({ ...selectedTemplate, type: e.target.value as "EMAIL" | "SMS" })}
                    >
                      <option value="EMAIL">Email</option>
                      <option value="SMS">SMS</option>
                    </select>
                  </div>
                </div>

                {selectedTemplate.type === "EMAIL" && (
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Subject Line</Label>
                    <Input
                      className="min-h-[44px]"
                      value={selectedTemplate.subject}
                      onChange={(e) => setSelectedTemplate({ ...selectedTemplate, subject: e.target.value })}
                      placeholder="e.g. Reminder: Your appointment on {{booking_date}}"
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Body Content</Label>
                  <Textarea
                    className="min-h-[180px] sm:min-h-[220px] font-mono text-xs sm:text-sm"
                    value={selectedTemplate.body}
                    onChange={(e) => setSelectedTemplate({ ...selectedTemplate, body: e.target.value })}
                    placeholder="Write your template message here with {{variable}} placeholders..."
                  />

                  <div className="pt-2">
                    <Label className="text-xs text-muted-foreground font-medium mb-1.5 block">Insert Variable Tokens</Label>
                    <div className="flex gap-1.5 flex-wrap">
                      {TEMPLATE_VARIABLES.map((tag) => (
                        <Button
                          key={tag}
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-8 min-h-[36px] text-xs gap-1 px-2.5 bg-muted/30 hover:bg-primary/10 hover:text-primary hover:border-primary/40 transition-colors"
                          onClick={() => insertTag(tag)}
                        >
                          <Tag className="w-3 h-3 text-muted-foreground" /> {tag}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row justify-end gap-2 pt-4 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    className="md:hidden min-h-[44px]"
                    onClick={() => setIsMobileEditing(false)}
                  >
                    Back to List
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                    className="min-h-[44px] px-6 font-semibold"
                  >
                    {saving ? "Saving..." : "Save Template"}
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[300px] text-muted-foreground text-sm">
              Select a template to view or edit
            </div>
          )}
        </Card>
      </div>
    </MobilePageShell>
  );
}
