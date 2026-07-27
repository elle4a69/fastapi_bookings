import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Pencil, Trash2, Plus, ExternalLink } from 'lucide-react';

// Mock data
const mockForms = [
  { id: '1', name: 'Standard Booking', slug: 'standard', widgetType: 'full', active: true },
  { id: '2', name: 'Quick Consult', slug: 'quick-consult', widgetType: 'modal', active: false },
];

export default function BookingForms() {
  const [forms, setForms] = useState(mockForms);

  const toggleActive = (id: string) => {
    setForms(forms.map(f => f.id === id ? { ...f, active: !f.active } : f));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Booking Forms</h1>
          <p className="text-muted-foreground">Manage your customer intake configurations.</p>
        </div>
        <Link to="/admin/booking-forms/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" /> New Form
          </Button>
        </Link>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Form Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Widget Type</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Public Link</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {forms.map((form) => (
              <TableRow key={form.id}>
                <TableCell className="font-medium">{form.name}</TableCell>
                <TableCell>{form.slug}</TableCell>
                <TableCell className="capitalize">{form.widgetType}</TableCell>
                <TableCell>
                  <Switch
                    checked={form.active}
                    onCheckedChange={() => toggleActive(form.id)}
                  />
                </TableCell>
                <TableCell>
                  <a
                    href={`/book/${form.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center text-primary hover:underline"
                  >
                    /book/{form.slug}
                    <ExternalLink className="ml-1 h-3 w-3" />
                  </a>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Link to={`/admin/booking-forms/${form.id}`}>
                      <Button variant="ghost" size="icon">
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button variant="ghost" size="icon" className="text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
