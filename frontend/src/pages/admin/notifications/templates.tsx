import { useEffect, useState } from "react";
import { apiClient } from "../../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Textarea } from "../../../components/ui/textarea";
import { Label } from "../../../components/ui/label";
import { Switch } from "../../../components/ui/switch";
import { ScrollArea } from "../../../components/ui/scroll-area";
import { Plus, Tag } from "lucide-react";
import { toast } from "sonner";

interface Template {
  id: string;
  name: string;
  type: "EMAIL" | "SMS";
  subject: string;
  body: string;
  isActive: boolean;
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const data = await apiClient.get<Template[]>("/api/admin/notifications/templates");
      setTemplates(data);
      if (data.length > 0 && !selectedTemplate) {
        setSelectedTemplate(data[0]);
      }
    } catch (error) {
      toast.error("Failed to fetch templates");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedTemplate) return;
    setSaving(true);
    try {
      if (selectedTemplate.id.startsWith("new_")) {
        await apiClient.post("/api/admin/notifications/templates", selectedTemplate);
      } else {
        await apiClient.put(`/api/admin/notifications/templates/${selectedTemplate.id}`, selectedTemplate);
      }
      toast.success("Template saved successfully");
      fetchTemplates();
    } catch (error) {
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
  };

  const insertTag = (tag: string) => {
    if (!selectedTemplate) return;
    setSelectedTemplate({
      ...selectedTemplate,
      body: selectedTemplate.body + ` {{${tag}}} `,
    });
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Message Templates</h1>
          <p className="text-muted-foreground">Manage templates for email and SMS notifications.</p>
        </div>
        <Button onClick={handleNewTemplate}>
          <Plus className="w-4 h-4 mr-2" /> New Template
        </Button>
      </div>

      <div className="flex flex-1 gap-6 min-h-[500px]">
        {/* Left Sidebar */}
        <Card className="w-1/3 flex flex-col">
          <CardHeader>
            <CardTitle>Templates</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="p-4 text-center">Loading...</div>
              ) : (
                <div className="flex flex-col p-2 space-y-1">
                  {templates.map((tpl) => (
                    <button
                      key={tpl.id}
                      onClick={() => setSelectedTemplate(tpl)}
                      className={`text-left p-3 rounded-md transition-colors ${
                        selectedTemplate?.id === tpl.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted"
                      }`}
                    >
                      <div className="font-medium">{tpl.name}</div>
                      <div className="text-xs opacity-80">{tpl.type}</div>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Right Editor */}
        <Card className="w-2/3">
          {selectedTemplate ? (
            <>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Edit Template</CardTitle>
                <div className="flex items-center space-x-2">
                  <Label htmlFor="active-status">Active</Label>
                  <Switch
                    id="active-status"
                    checked={selectedTemplate.isActive}
                    onCheckedChange={(checked) => setSelectedTemplate({ ...selectedTemplate, isActive: checked })}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Template Name</Label>
                    <Input
                      value={selectedTemplate.name}
                      onChange={(e) => setSelectedTemplate({ ...selectedTemplate, name: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Type</Label>
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
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
                    <Label>Subject</Label>
                    <Input
                      value={selectedTemplate.subject}
                      onChange={(e) => setSelectedTemplate({ ...selectedTemplate, subject: e.target.value })}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label>Body Content</Label>
                  <Textarea
                    className="min-h-[200px]"
                    value={selectedTemplate.body}
                    onChange={(e) => setSelectedTemplate({ ...selectedTemplate, body: e.target.value })}
                  />
                  <div className="flex gap-2 mt-2 flex-wrap">
                    <Button variant="outline" size="sm" onClick={() => insertTag("client_name")}>
                      <Tag className="w-3 h-3 mr-1" /> client_name
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => insertTag("booking_time")}>
                      <Tag className="w-3 h-3 mr-1" /> booking_time
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => insertTag("service_name")}>
                      <Tag className="w-3 h-3 mr-1" /> service_name
                    </Button>
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <Button onClick={handleSave} disabled={saving}>
                    {saving ? "Saving..." : "Save Template"}
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Select a template to edit
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
