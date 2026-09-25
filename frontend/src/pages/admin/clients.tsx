import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, MoreVertical, Eye, ShieldAlert, RefreshCw, Phone, Mail } from 'lucide-react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MobilePageShell, MobileBackButton } from '@/components/ui/mobile-page-shell';
import { ResponsiveDataTable, type ColumnDef } from '@/components/ui/responsive-data-table';

interface Client {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postcode: string | null;
  country: string | null;
  timezone: string | null;
  accepts_marketing: boolean;
  notes: string | null;
  active: boolean;
  management_approval_required: boolean;
  restriction_reason: string | null;
  restricted_at: string | null;
  restriction_cleared_at: string | null;
  terms_accepted_at: string | null;
  privacy_accepted_at: string | null;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<Partial<Client>>({});
  
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<any>('/api/admin/clients');
      const data = Array.isArray(res) ? res : (res.data || res.items || []);
      setClients(data);
    } catch {
      toast.error('Failed to load clients');
      setClients([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectClient = (client: Client) => {
    setSelectedClient(client);
    setFormData(client);
    setIsEditing(false);
  };

  const handleClosePanel = () => {
    setSelectedClient(null);
    setFormData({});
    setIsEditing(false);
  };

  const handleAddClient = () => {
    const newClient: Partial<Client> = {
      name: '',
      email: '',
      phone: '',
      active: true,
      accepts_marketing: false,
      management_approval_required: false
    };
    setSelectedClient(newClient as Client);
    setFormData(newClient);
    setIsEditing(true);
  };

  const handleSave = async () => {
    try {
      if (selectedClient?.id) {
        const updated = await apiClient.put<Client>(`/api/admin/clients/${selectedClient.id}`, formData);
        setClients(clients.map(c => c.id === selectedClient.id ? updated : c));
        setSelectedClient(updated);
        toast.success('Client updated successfully');
      } else {
        const created = await apiClient.post<Client>('/api/admin/clients', formData);
        setClients([...clients, created]);
        setSelectedClient(created);
        toast.success('Client created successfully');
      }
      setIsEditing(false);
    } catch {
      toast.error('Failed to save client');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this client?')) return;
    try {
      await apiClient.delete(`/api/admin/clients/${id}`);
      setClients(clients.filter(c => c.id !== id));
      if (selectedClient?.id === id) {
        handleClosePanel();
      }
      toast.success('Client deleted successfully');
    } catch {
      toast.error('Failed to delete client');
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Are you sure you want to delete ${selectedIds.length} clients?`)) return;
    try {
      await Promise.all(selectedIds.map(id => apiClient.delete(`/api/admin/clients/${id}`)));
      setClients(clients.filter(c => !selectedIds.includes(c.id)));
      setSelectedIds([]);
      if (selectedClient && selectedIds.includes(selectedClient.id)) {
        handleClosePanel();
      }
      toast.success('Clients deleted successfully');
    } catch {
      toast.error('Failed to delete some clients');
    }
  };

  const handleToggleSelect = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(i => i !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const filteredClients = clients.filter(c => {
    const q = searchQuery.toLowerCase();
    return (
      (c.name || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q) ||
      (c.phone || '').toLowerCase().includes(q) ||
      (c.city || '').toLowerCase().includes(q)
    );
  });

  const columns: ColumnDef<Client>[] = [
    {
      id: 'select',
      header: 'Select',
      hideable: false,
      cell: (client) => (
        <div onClick={(e) => e.stopPropagation()}>
          <Checkbox
            checked={selectedIds.includes(client.id)}
            onCheckedChange={() => handleToggleSelect(client.id)}
            className="h-4 w-4"
          />
        </div>
      ),
    },
    {
      id: 'name',
      header: 'Name',
      sortable: true,
      cell: (client) => (
        <div>
          <span className="font-semibold text-foreground text-sm block">{client.name || 'Unnamed Client'}</span>
          <span className="text-xs text-muted-foreground block md:hidden">{client.email}</span>
        </div>
      ),
    },
    {
      id: 'email',
      header: 'Email',
      sortable: true,
      cell: (client) => <span className="text-xs text-muted-foreground">{client.email || '—'}</span>,
    },
    {
      id: 'phone',
      header: 'Phone',
      defaultHidden: true,
      cell: (client) => <span className="text-xs text-muted-foreground">{client.phone || '—'}</span>,
    },
    {
      id: 'status',
      header: 'Status',
      cell: (client) => (
        <Badge variant={client.active ? "default" : "secondary"} className="text-xs">
          {client.active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      hideable: false,
      cell: (client) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="icon" className="h-8 w-8 min-h-0 min-w-0 touch-manipulation">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleSelectClient(client)}>
              <Eye className="h-4 w-4 mr-2" /> View
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => { handleSelectClient(client); setIsEditing(true); }}>
              <Edit className="h-4 w-4 mr-2" /> Edit
            </DropdownMenuItem>
            <DropdownMenuItem 
              onClick={() => { 
                handleSelectClient(client);
                setIsEditing(true);
                setFormData({...client, management_approval_required: true});
              }}
            >
              <ShieldAlert className="h-4 w-4 mr-2" /> Restrict
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleDelete(client.id)} className="text-destructive">
              <Trash2 className="h-4 w-4 mr-2" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <MobilePageShell
      title="Clients"
      description="Manage client accounts, compliance status, and history"
      density="compact"
      actions={
        <div className="flex items-center gap-1.5 sm:gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchClients}
            className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 flex-1 sm:flex-initial touch-manipulation gap-1.5 text-xs sm:text-sm"
          >
            <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          {selectedIds.length > 0 && (
            <Button 
              variant="destructive" 
              size="sm" 
              onClick={handleBulkDelete} 
              className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 touch-manipulation gap-1.5 text-xs sm:text-sm"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete ({selectedIds.length})</span>
            </Button>
          )}
          <Button 
            size="sm" 
            onClick={handleAddClient} 
            className="h-8 sm:h-9 min-h-0 px-2.5 sm:px-3 flex-1 sm:flex-initial touch-manipulation gap-1.5 text-xs sm:text-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Client</span>
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 sm:gap-4 min-w-0">
        {/* Main List / Table Area */}
        <div className={`col-span-1 md:col-span-5 lg:col-span-5 ${selectedClient ? 'hidden md:block' : 'block'}`}>
          <div className="space-y-2.5 sm:space-y-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Search name, email, phone, city..."
                className="pl-8 h-8 sm:h-9 min-h-0 text-xs sm:text-sm"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>

            <ResponsiveDataTable
              data={filteredClients}
              columns={columns}
              keyExtractor={(c) => c.id}
              isLoading={loading}
              density="compact"
              onRowClick={handleSelectClient}
              renderMobileCard={(client) => (
                <div className="p-3.5 rounded-lg border bg-card text-card-foreground shadow-xs space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-base text-foreground truncate">{client.name || 'Unnamed Client'}</span>
                    <Badge variant={client.active ? "default" : "secondary"} className="text-xs">
                      {client.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>

                  <div className="text-xs text-muted-foreground space-y-1">
                    {client.email && (
                      <div className="flex items-center gap-1.5 truncate">
                        <Mail className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{client.email}</span>
                      </div>
                    )}
                    {client.phone && (
                      <div className="flex items-center gap-1.5">
                        <Phone className="h-3.5 w-3.5 shrink-0" />
                        <span>{client.phone}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t text-xs" onClick={e => e.stopPropagation()}>
                    <label className="flex items-center gap-2 cursor-pointer touch-manipulation">
                      <Checkbox
                        checked={selectedIds.includes(client.id)}
                        onCheckedChange={() => handleToggleSelect(client.id)}
                        className="h-4 w-4"
                      />
                      <span className="text-muted-foreground">Select</span>
                    </label>

                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-9 min-h-[40px] text-xs px-2.5 touch-manipulation"
                        onClick={() => handleSelectClient(client)}
                      >
                        View Details
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            />
          </div>
        </div>

        {/* Right Detail Panel */}
        {selectedClient && (
          <div className="col-span-1 md:col-span-7 lg:col-span-7">
            <Card className="shadow-xs border overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 shrink-0 border-b p-4">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="md:hidden">
                    <MobileBackButton label="Clients" onClick={handleClosePanel} />
                  </div>
                  <CardTitle className="text-lg sm:text-xl font-bold truncate">
                    {selectedClient.id ? selectedClient.name : 'New Client'}
                  </CardTitle>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="flex items-center space-x-2">
                    <Switch 
                      checked={isEditing} 
                      onCheckedChange={setIsEditing} 
                      id="edit-mode"
                      className="touch-manipulation"
                    />
                    <Label htmlFor="edit-mode" className="text-xs cursor-pointer hidden sm:inline-block">Edit Mode</Label>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0 max-h-[calc(100vh-280px)] overflow-y-auto">
                <Accordion type="multiple" defaultValue={["profile", "compliance", "history"]} className="w-full">
                  {/* Section 1: Client Profile */}
                  <AccordionItem value="profile" className="px-4">
                    <AccordionTrigger className="text-base font-semibold">Client Profile</AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Name</Label>
                          {isEditing ? (
                            <Input value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} className="h-11 min-h-[44px]" />
                          ) : (
                            <p className="text-sm py-2 font-medium">{formData.name}</p>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Email</Label>
                          {isEditing ? (
                            <Input value={formData.email || ''} onChange={e => setFormData({...formData, email: e.target.value})} type="email" className="h-11 min-h-[44px]" />
                          ) : (
                            <p className="text-sm py-2"><a href={`mailto:${formData.email}`} className="text-primary hover:underline">{formData.email}</a></p>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Phone</Label>
                          {isEditing ? (
                            <Input value={formData.phone || ''} onChange={e => setFormData({...formData, phone: e.target.value})} className="h-11 min-h-[44px]" />
                          ) : (
                            <p className="text-sm py-2"><a href={`tel:${formData.phone}`} className="text-primary hover:underline">{formData.phone}</a></p>
                          )}
                        </div>
                        <div className="space-y-1.5 flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                          <div>
                            <Label className="text-sm font-medium">Active Status</Label>
                            <p className="text-xs text-muted-foreground">Enable or disable client booking privileges</p>
                          </div>
                          <Switch 
                            checked={formData.active || false} 
                            onCheckedChange={v => setFormData({...formData, active: v})} 
                            disabled={!isEditing}
                            className="touch-manipulation"
                          />
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t">
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Address Line 1</Label>
                          {isEditing ? <Input value={formData.address_line1 || ''} onChange={e => setFormData({...formData, address_line1: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.address_line1 || '-'}</p>}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Address Line 2</Label>
                          {isEditing ? <Input value={formData.address_line2 || ''} onChange={e => setFormData({...formData, address_line2: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.address_line2 || '-'}</p>}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">City</Label>
                          {isEditing ? <Input value={formData.city || ''} onChange={e => setFormData({...formData, city: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.city || '-'}</p>}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">State / Province</Label>
                          {isEditing ? <Input value={formData.state || ''} onChange={e => setFormData({...formData, state: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.state || '-'}</p>}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Postcode</Label>
                          {isEditing ? <Input value={formData.postcode || ''} onChange={e => setFormData({...formData, postcode: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.postcode || '-'}</p>}
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Country</Label>
                          {isEditing ? <Input value={formData.country || ''} onChange={e => setFormData({...formData, country: e.target.value})} className="h-11 min-h-[44px]" /> : <p className="text-sm py-1">{formData.country || '-'}</p>}
                        </div>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Notes</Label>
                        {isEditing ? (
                          <Textarea 
                            value={formData.notes || ''} 
                            onChange={e => setFormData({...formData, notes: e.target.value})} 
                            className="min-h-[90px] text-sm"
                          />
                        ) : (
                          <div className="p-3 bg-muted/40 rounded-md min-h-[60px] text-sm whitespace-pre-wrap">
                            {formData.notes || 'No notes recorded.'}
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Section 2: Compliance */}
                  <AccordionItem value="compliance" className="px-4">
                    <AccordionTrigger className="text-base font-semibold text-orange-600 dark:text-orange-400">Compliance & Restrictions</AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="flex items-center justify-between p-3 border border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-950/30 rounded-md">
                        <div>
                          <Label className="font-semibold text-orange-800 dark:text-orange-300 text-sm">Management Approval Required</Label>
                          <p className="text-xs text-orange-700 dark:text-orange-400">Client must be approved manually for each appointment</p>
                        </div>
                        <Switch 
                          checked={formData.management_approval_required || false}
                          onCheckedChange={v => setFormData({...formData, management_approval_required: v})}
                          disabled={!isEditing}
                          className="touch-manipulation"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Restriction Reason</Label>
                        {isEditing ? (
                          <Input value={formData.restriction_reason || ''} onChange={e => setFormData({...formData, restriction_reason: e.target.value})} className="h-11 min-h-[44px]" />
                        ) : (
                          <p className="text-sm">{formData.restriction_reason || 'None'}</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Section 3: Booking History */}
                  <AccordionItem value="history" className="px-4">
                    <AccordionTrigger className="text-base font-semibold">Booking History</AccordionTrigger>
                    <AccordionContent className="pt-2">
                      <Tabs defaultValue="upcoming" className="w-full">
                        <TabsList className="w-full grid grid-cols-3 h-10">
                          <TabsTrigger value="upcoming" className="text-xs">Upcoming</TabsTrigger>
                          <TabsTrigger value="past" className="text-xs">Past</TabsTrigger>
                          <TabsTrigger value="cancelled" className="text-xs">Cancelled</TabsTrigger>
                        </TabsList>
                        <TabsContent value="upcoming" className="p-4 border rounded-md mt-2 min-h-[100px] flex items-center justify-center text-muted-foreground text-xs">
                          <p>No upcoming bookings found.</p>
                        </TabsContent>
                        <TabsContent value="past" className="p-4 border rounded-md mt-2 min-h-[100px] flex items-center justify-center text-muted-foreground text-xs">
                          <p>No past bookings found.</p>
                        </TabsContent>
                        <TabsContent value="cancelled" className="p-4 border rounded-md mt-2 min-h-[100px] flex items-center justify-center text-muted-foreground text-xs">
                          <p>No cancelled bookings found.</p>
                        </TabsContent>
                      </Tabs>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>

              <CardFooter className="flex flex-col sm:flex-row justify-between gap-3 border-t p-4 shrink-0 bg-muted/20">
                <div className="flex flex-wrap gap-2 w-full sm:w-auto">
                  <Button 
                    variant="outline" 
                    onClick={() => setIsEditing(true)} 
                    disabled={isEditing} 
                    className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs"
                  >
                    Edit Client
                  </Button>
                  <Button 
                    variant="outline" 
                    className="h-10 min-h-[44px] flex-1 sm:flex-initial text-orange-600 border-orange-200 hover:bg-orange-50 touch-manipulation text-xs" 
                    onClick={() => {
                      setIsEditing(true);
                      setFormData({...formData, management_approval_required: true, restricted_at: new Date().toISOString()});
                    }}
                  >
                    Restrict
                  </Button>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  {isEditing ? (
                    <>
                      <Button variant="outline" onClick={() => setIsEditing(false)} className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs">Cancel</Button>
                      <Button onClick={handleSave} className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs">Save Changes</Button>
                    </>
                  ) : (
                    <Button variant="destructive" onClick={() => handleDelete(selectedClient.id)} className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation text-xs">Delete</Button>
                  )}
                </div>
              </CardFooter>
            </Card>
          </div>
        )}
      </div>
    </MobilePageShell>
  );
}
