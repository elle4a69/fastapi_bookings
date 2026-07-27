import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, MoreVertical, X, Eye, ShieldAlert, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
  
  const [filters, setFilters] = useState({
    name: '',
    email: '',
    phone: ''
  });

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    setLoading(true);
    try {
      // The API endpoint seems to return an array or a paginated response.
      // Adjusting based on typical fastapi_bookings responses.
      const res = await apiClient.get<any>('/api/admin/clients');
      // If it's a list response
      const data = Array.isArray(res) ? res : (res.data || res.items || []);
      setClients(data);
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
      toast.error('Failed to delete some clients');
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedIds.length === filteredClients.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredClients.map(c => c.id));
    }
  };

  const handleToggleSelect = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(i => i !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const filteredClients = clients.filter(c => 
    (c.name || '').toLowerCase().includes(filters.name.toLowerCase()) &&
    (c.email || '').toLowerCase().includes(filters.email.toLowerCase()) &&
    (c.phone || '').toLowerCase().includes(filters.phone.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full overflow-hidden p-4 md:p-6 gap-4 font-sans">
      <div className="flex flex-col md:flex-row justify-between md:items-center gap-4 shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-heading">Clients</h1>
          <p className="text-sm md:text-base text-muted-foreground">Manage your clients and their compliance status.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => toast.info('Export not implemented')} className="min-h-[44px] hidden md:flex"><Search className="w-4 h-4 mr-2" /> Export to CSV</Button>
          <Button variant="destructive" disabled={selectedIds.length === 0} onClick={handleBulkDelete} className="min-h-[44px]">
            <Trash2 className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Delete ({selectedIds.length})</span>
          </Button>
          <Button onClick={handleAddClient} className="min-h-[44px]"><Plus className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Add Client</span></Button>
        </div>
      </div>

      <div className="flex gap-4 flex-1 overflow-hidden relative">
        {/* Main Table Area */}
        <div className={`flex flex-col border rounded-md overflow-hidden bg-background transition-all duration-300 ${selectedClient ? 'hidden md:flex md:w-2/5' : 'flex w-full'}`}>
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 sticky top-0 z-10">
                <tr className="border-b">
                  <th className="p-3 text-left font-medium w-12">
                    <Checkbox 
                      checked={selectedIds.length > 0 && selectedIds.length === filteredClients.length} 
                      onCheckedChange={handleToggleSelectAll} 
                    />
                  </th>
                  <th className="p-3 text-left font-medium">Name
                    <Input 
                      placeholder="Filter..." 
                      className="h-7 mt-1 text-xs" 
                      value={filters.name}
                      onChange={e => setFilters({...filters, name: e.target.value})}
                    />
                  </th>
                  <th className="p-3 text-left font-medium hidden md:table-cell">Email
                    <Input 
                      placeholder="Filter..." 
                      className="h-7 mt-1 text-xs" 
                      value={filters.email}
                      onChange={e => setFilters({...filters, email: e.target.value})}
                    />
                  </th>
                  <th className="p-3 text-left font-medium hidden lg:table-cell">Phone
                    <Input 
                      placeholder="Filter..." 
                      className="h-7 mt-1 text-xs" 
                      value={filters.phone}
                      onChange={e => setFilters({...filters, phone: e.target.value})}
                    />
                  </th>
                  <th className="p-3 text-left font-medium">Status</th>
                  <th className="p-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({length: 5}).map((_, i) => (
                    <tr key={i} className="border-b">
                      <td className="p-3"><Skeleton className="h-4 w-4" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-32" /></td>
                      <td className="p-3 hidden md:table-cell"><Skeleton className="h-4 w-32" /></td>
                      <td className="p-3 hidden lg:table-cell"><Skeleton className="h-4 w-24" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-8 ml-auto" /></td>
                    </tr>
                  ))
                ) : filteredClients.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground">
                      No clients found.
                    </td>
                  </tr>
                ) : (
                  filteredClients.map(client => (
                    <tr 
                      key={client.id} 
                      className={`border-b hover:bg-muted/50 transition-colors ${selectedClient?.id === client.id ? 'bg-muted' : ''}`}
                    >
                      <td className="p-3">
                        <Checkbox 
                          checked={selectedIds.includes(client.id)}
                          onCheckedChange={() => handleToggleSelect(client.id)}
                        />
                      </td>
                      <td className="p-3 cursor-pointer font-medium" onClick={() => handleSelectClient(client)}>
                        {client.name || 'Unnamed Client'}
                      </td>
                      <td className="p-3 hidden md:table-cell text-muted-foreground">{client.email}</td>
                      <td className="p-3 hidden lg:table-cell text-muted-foreground">{client.phone}</td>
                      <td className="p-3">
                        <Badge variant={client.active ? "default" : "secondary"}>
                          {client.active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="p-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
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
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Detail Panel */}
        {selectedClient && (
          <Card className={`flex flex-col overflow-hidden border transition-all duration-300 absolute inset-0 z-50 bg-background md:relative md:z-auto md:w-3/5 h-full rounded-none md:rounded-xl`}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 shrink-0 border-b p-4 sticky top-0 bg-background z-10">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden min-h-[44px] min-w-[44px]" onClick={handleClosePanel}>
                  <ArrowLeft className="h-5 w-5" />
                </Button>
                <CardTitle className="text-xl font-heading">
                  {selectedClient.id ? selectedClient.name : 'New Client'}
                </CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center space-x-2 mr-0 md:mr-4">
                  <Switch 
                    checked={isEditing} 
                    onCheckedChange={setIsEditing} 
                    id="edit-mode"
                  />
                  <Label htmlFor="edit-mode" className="hidden md:inline-block">Edit Mode</Label>
                </div>
                <Button variant="ghost" size="icon" onClick={handleClosePanel} className="hidden md:flex min-h-[44px] min-w-[44px]">
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto p-0">
              <Accordion type="multiple" defaultValue={["profile", "compliance", "history"]} className="w-full">
                {/* Section 1: Client Profile */}
                <AccordionItem value="profile" className="px-4">
                  <AccordionTrigger className="text-lg font-semibold">Client Profile</AccordionTrigger>
                  <AccordionContent className="space-y-4 pt-2">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        {isEditing ? (
                          <Input value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} />
                        ) : (
                          <p className="text-sm py-2 font-medium">{formData.name}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label>Email</Label>
                        {isEditing ? (
                          <Input value={formData.email || ''} onChange={e => setFormData({...formData, email: e.target.value})} type="email" />
                        ) : (
                          <p className="text-sm py-2"><a href={`mailto:${formData.email}`} className="text-primary hover:underline">{formData.email}</a></p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label>Phone</Label>
                        {isEditing ? (
                          <Input value={formData.phone || ''} onChange={e => setFormData({...formData, phone: e.target.value})} />
                        ) : (
                          <p className="text-sm py-2"><a href={`tel:${formData.phone}`} className="text-primary hover:underline">{formData.phone}</a></p>
                        )}
                      </div>
                      <div className="space-y-2 flex items-center gap-2 pt-6">
                        <Switch 
                          checked={formData.active || false} 
                          onCheckedChange={v => setFormData({...formData, active: v})} 
                          disabled={!isEditing}
                        />
                        <Label>Active</Label>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Address Line 1</Label>
                        {isEditing ? <Input value={formData.address_line1 || ''} onChange={e => setFormData({...formData, address_line1: e.target.value})} /> : <p className="text-sm">{formData.address_line1 || '-'}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label>Address Line 2</Label>
                        {isEditing ? <Input value={formData.address_line2 || ''} onChange={e => setFormData({...formData, address_line2: e.target.value})} /> : <p className="text-sm">{formData.address_line2 || '-'}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label>City</Label>
                        {isEditing ? <Input value={formData.city || ''} onChange={e => setFormData({...formData, city: e.target.value})} /> : <p className="text-sm">{formData.city || '-'}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label>State/Province</Label>
                        {isEditing ? <Input value={formData.state || ''} onChange={e => setFormData({...formData, state: e.target.value})} /> : <p className="text-sm">{formData.state || '-'}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label>Postcode</Label>
                        {isEditing ? <Input value={formData.postcode || ''} onChange={e => setFormData({...formData, postcode: e.target.value})} /> : <p className="text-sm">{formData.postcode || '-'}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label>Country</Label>
                        {isEditing ? <Input value={formData.country || ''} onChange={e => setFormData({...formData, country: e.target.value})} /> : <p className="text-sm">{formData.country || '-'}</p>}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Timezone</Label>
                        {isEditing ? (
                          <Select value={formData.timezone || ''} onValueChange={v => setFormData({...formData, timezone: v})}>
                            <SelectTrigger><SelectValue placeholder="Select timezone" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="UTC">UTC</SelectItem>
                              <SelectItem value="America/New_York">America/New_York</SelectItem>
                              <SelectItem value="Europe/London">Europe/London</SelectItem>
                              <SelectItem value="Asia/Tokyo">Asia/Tokyo</SelectItem>
                              <SelectItem value="Australia/Sydney">Australia/Sydney</SelectItem>
                            </SelectContent>
                          </Select>
                        ) : (
                          <p className="text-sm py-2">{formData.timezone || 'Not set'}</p>
                        )}
                      </div>
                      <div className="space-y-2 flex items-center gap-2 pt-6">
                        <Switch 
                          checked={formData.accepts_marketing || false} 
                          onCheckedChange={v => setFormData({...formData, accepts_marketing: v})} 
                          disabled={!isEditing}
                        />
                        <Label>Accepts Marketing</Label>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Notes</Label>
                      {isEditing ? (
                        <Textarea 
                          value={formData.notes || ''} 
                          onChange={e => setFormData({...formData, notes: e.target.value})} 
                          className="min-h-[100px]"
                        />
                      ) : (
                        <div className="p-3 bg-muted rounded-md min-h-[100px] text-sm whitespace-pre-wrap">
                          {formData.notes || 'No notes available.'}
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Section 2: Compliance Status */}
                <AccordionItem value="compliance" className="px-4">
                  <AccordionTrigger className="text-lg font-semibold text-orange-600 dark:text-orange-400">Compliance & Restrictions</AccordionTrigger>
                  <AccordionContent className="space-y-4 pt-2">
                    <div className="flex items-center space-x-2 mb-4 p-3 border border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-950/30 rounded-md">
                      <Switch 
                        checked={formData.management_approval_required || false}
                        onCheckedChange={v => setFormData({...formData, management_approval_required: v})}
                        disabled={!isEditing}
                      />
                      <Label className="font-semibold text-orange-800 dark:text-orange-300">Management Approval Required</Label>
                    </div>

                    <div className="space-y-2">
                      <Label>Restriction Reason</Label>
                      {isEditing ? (
                        <Input value={formData.restriction_reason || ''} onChange={e => setFormData({...formData, restriction_reason: e.target.value})} />
                      ) : (
                        <p className="text-sm">{formData.restriction_reason || 'None'}</p>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Restricted At</Label>
                        {isEditing ? (
                          <Input type="datetime-local" value={formData.restricted_at ? formData.restricted_at.slice(0, 16) : ''} onChange={e => setFormData({...formData, restricted_at: e.target.value ? new Date(e.target.value).toISOString() : null})} />
                        ) : (
                          <p className="text-sm">{formData.restricted_at ? new Date(formData.restricted_at).toLocaleString() : '-'}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label>Restriction Cleared At</Label>
                        {isEditing ? (
                          <Input type="datetime-local" value={formData.restriction_cleared_at ? formData.restriction_cleared_at.slice(0, 16) : ''} onChange={e => setFormData({...formData, restriction_cleared_at: e.target.value ? new Date(e.target.value).toISOString() : null})} />
                        ) : (
                          <p className="text-sm">{formData.restriction_cleared_at ? new Date(formData.restriction_cleared_at).toLocaleString() : '-'}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label>Terms Accepted At</Label>
                        <p className="text-sm py-2 text-muted-foreground">{formData.terms_accepted_at ? new Date(formData.terms_accepted_at).toLocaleString() : 'Not accepted'}</p>
                      </div>
                      <div className="space-y-2">
                        <Label>Privacy Accepted At</Label>
                        <p className="text-sm py-2 text-muted-foreground">{formData.privacy_accepted_at ? new Date(formData.privacy_accepted_at).toLocaleString() : 'Not accepted'}</p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Section 3: Booking History */}
                <AccordionItem value="history" className="px-4">
                  <AccordionTrigger className="text-lg font-semibold">Booking History</AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <Tabs defaultValue="upcoming" className="w-full">
                      <TabsList className="w-full grid grid-cols-3">
                        <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
                        <TabsTrigger value="past">Past</TabsTrigger>
                        <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
                      </TabsList>
                      <TabsContent value="upcoming" className="p-4 border rounded-md mt-2 min-h-[150px] flex items-center justify-center text-muted-foreground">
                        <p>No upcoming bookings found.</p>
                      </TabsContent>
                      <TabsContent value="past" className="p-4 border rounded-md mt-2 min-h-[150px] flex items-center justify-center text-muted-foreground">
                        <p>No past bookings found.</p>
                      </TabsContent>
                      <TabsContent value="cancelled" className="p-4 border rounded-md mt-2 min-h-[150px] flex items-center justify-center text-muted-foreground">
                        <p>No cancelled bookings found.</p>
                      </TabsContent>
                    </Tabs>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>

            <CardFooter className="flex flex-col md:flex-row justify-between gap-4 border-t p-4 shrink-0 bg-muted/20 sticky bottom-0 z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
              <div className="flex flex-wrap gap-2 w-full md:w-auto">
                <Button variant="outline" onClick={() => setIsEditing(true)} disabled={isEditing} className="min-h-[44px] flex-1 md:flex-none">
                  Edit Client
                </Button>
                <Button variant="outline" onClick={() => toast.info('New booking form not implemented yet')} className="min-h-[44px] flex-1 md:flex-none">
                  New Booking
                </Button>
                <Button variant="outline" className="min-h-[44px] flex-1 md:flex-none text-orange-600 border-orange-200 hover:bg-orange-50 dark:hover:bg-orange-950/30" onClick={() => {
                  setIsEditing(true);
                  setFormData({...formData, management_approval_required: true, restricted_at: new Date().toISOString()});
                }}>
                  Restrict Client
                </Button>
              </div>
              <div className="flex gap-2 w-full md:w-auto mt-2 md:mt-0">
                {isEditing ? (
                  <>
                    <Button variant="outline" onClick={() => setIsEditing(false)} className="min-h-[44px] flex-1 md:flex-none">Cancel</Button>
                    <Button onClick={handleSave} className="min-h-[44px] flex-1 md:flex-none">Save Changes</Button>
                  </>
                ) : (
                  <Button variant="destructive" onClick={() => handleDelete(selectedClient.id)} className="min-h-[44px] flex-1 md:flex-none">Delete</Button>
                )}
              </div>
            </CardFooter>
          </Card>
        )}
      </div>
    </div>
  );
}
