import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Save, ArrowLeft, GripVertical } from 'lucide-react';
import { Link } from 'react-router-dom';

const DEFAULT_MODULES = [
  { id: 'service', label: 'Service Selection', enabled: true },
  { id: 'provider', label: 'Provider Selection', enabled: true },
  { id: 'location', label: 'Location Selection', enabled: false },
  { id: 'datetime', label: 'Date/Time', enabled: true },
  { id: 'intake', label: 'Intake Fields', enabled: true },
  { id: 'client', label: 'Client Details', enabled: true },
  { id: 'checkout', label: 'Checkout', enabled: true },
  { id: 'outcome', label: 'Outcome', enabled: true },
];

export default function BookingFormEditor() {
  const [modules, setModules] = useState(DEFAULT_MODULES);
  const [themeJson, setThemeJson] = useState('{\n  "primaryColor": "#000000",\n  "borderRadius": "8px"\n}');

  const toggleModule = (id: string) => {
    setModules(modules.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4 bg-background">
        <div className="flex items-center gap-4">
          <Link to="/admin/booking-forms">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-xl font-bold">Edit Booking Form</h1>
        </div>
        <Button>
          <Save className="mr-2 h-4 w-4" /> Save Changes
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - Modules */}
        <div className="w-64 border-r bg-muted/30 p-4 overflow-y-auto">
          <h2 className="font-semibold mb-4 text-sm uppercase text-muted-foreground tracking-wider">
            Enabled Modules
          </h2>
          <div className="space-y-2">
            {modules.map((module) => (
              <div
                key={module.id}
                className="flex items-center justify-between p-3 bg-background border rounded-md shadow-sm"
              >
                <div className="flex items-center gap-2">
                  <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab active:cursor-grabbing" />
                  <span className="text-sm font-medium">{module.label}</span>
                </div>
                <Switch
                  checked={module.enabled}
                  onCheckedChange={() => toggleModule(module.id)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Center Panel - Preview */}
        <div className="flex-1 bg-muted/10 p-6 overflow-y-auto">
          <div className="max-w-2xl mx-auto">
            <div className="mb-4 text-center">
              <h2 className="text-lg font-medium">Live Preview</h2>
              <p className="text-sm text-muted-foreground">This is how clients will see the widget</p>
            </div>
            
            {/* Mock Widget Preview */}
            <div className="bg-card border rounded-xl shadow-lg p-6 min-h-[500px]">
              <div className="space-y-6">
                {modules.filter(m => m.enabled).map(module => (
                  <div key={`preview-${module.id}`} className="border-b pb-4 last:border-0 opacity-80">
                    <h3 className="font-medium text-lg mb-2">{module.label}</h3>
                    <div className="h-16 bg-muted rounded-md border border-dashed flex items-center justify-center text-sm text-muted-foreground">
                      [ {module.label} Component ]
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel - Properties */}
        <div className="w-80 border-l bg-background p-4 overflow-y-auto">
          <h2 className="font-semibold mb-6 text-sm uppercase text-muted-foreground tracking-wider">
            Global Settings
          </h2>
          
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Form Name</Label>
              <Input defaultValue="Standard Booking" />
            </div>

            <div className="space-y-2">
              <Label>URL Slug</Label>
              <div className="flex">
                <span className="inline-flex items-center px-3 rounded-l-md border border-r-0 bg-muted text-muted-foreground text-sm">
                  /book/
                </span>
                <Input className="rounded-l-none" defaultValue="standard" />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Widget Type</Label>
              <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
                <option value="full">Full Page</option>
                <option value="modal">Modal Popup</option>
                <option value="inline">Inline Embed</option>
              </select>
            </div>
            
            <div className="flex items-center justify-between">
              <Label>ADA Compliance Mode</Label>
              <Switch defaultChecked />
            </div>

            <div className="space-y-2">
              <Label>Appearance Theme (JSON)</Label>
              <Textarea
                className="font-mono text-xs h-40"
                value={themeJson}
                onChange={(e) => setThemeJson(e.target.value)}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
