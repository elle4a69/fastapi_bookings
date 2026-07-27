import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { Search, Plus, Save, Trash2, MapPin, Users, Box, ArrowLeft, Check, X, ChevronDown, ChevronRight } from 'lucide-react';

interface Resource {
  id?: string;
  name: string;
  type: string;
  location_id: string;
  capacity?: number;
  active: boolean;
}

interface ServiceResourceRequirement {
  id?: string;
  service_id: number;
  resource_type: string;
  quantity: number;
}

interface Service {
  id: number;
  name: string;
}

interface Location {
  id: string;
  name: string;
}

interface ResourceGroup {
  type: string;
  originalType?: string;
  location_id: string;
  required_mode: 'one' | 'shared';
  qty: number;
  active: boolean;
  resources: Resource[];
  connected_services: { service_id: number; quantity: number }[];
}

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [requirements, setRequirements] = useState<ServiceResourceRequirement[]>([]);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [serviceSearchQuery, setServiceSearchQuery] = useState('');
  const [selectedGroupType, setSelectedGroupType] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<ResourceGroup | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setIsLoading(true);
    try {
      const [resData, srvData, locData, reqData] = await Promise.all([
        apiClient.get<any>('/api/admin/resources').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/services').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/locations').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/resources/requirements').catch(() => ({ data: [] })),
      ]);

      const loadedResources = Array.isArray(resData) ? resData : (resData?.data ?? []);
      const loadedServices = Array.isArray(srvData) ? srvData : (srvData?.data ?? []);
      const loadedLocations = Array.isArray(locData) ? locData : (locData?.data ?? []);
      const loadedRequirements = Array.isArray(reqData) ? reqData : (reqData?.data ?? []);

      setResources(loadedResources);
      setServices(loadedServices);
      setLocations(loadedLocations);
      setRequirements(loadedRequirements);
    } catch (error) {
      toast.error('Failed to load initial data');
    } finally {
      setIsLoading(false);
    }
  };

  // Group resources by type
  const resourceGroups = resources.reduce<Record<string, Resource[]>>((acc, res) => {
    if (!acc[res.type]) {
      acc[res.type] = [];
    }
    acc[res.type].push(res);
    return acc;
  }, {});

  const listGroups = Object.keys(resourceGroups).map(type => {
    const groupResources = resourceGroups[type];
    const firstRes = groupResources[0];
    const isShared = groupResources.some(r => (r.capacity || 1) > 1);
    
    const groupReqs = requirements.filter(req => req.resource_type === type);
    const connectedServices = groupReqs.map(req => ({
      service_id: req.service_id,
      quantity: req.quantity
    }));

    return {
      type,
      location_id: firstRes?.location_id || (locations[0]?.id ? String(locations[0].id) : ''),
      required_mode: (isShared ? 'shared' : 'one') as 'one' | 'shared',
      qty: groupResources.length,
      active: groupResources.some(r => r.active),
      resources: groupResources,
      connected_services: connectedServices
    };
  });

  const filteredGroups = listGroups.filter(g => 
    g.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
    g.resources.some(r => r.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleSelectGroup = (group: typeof listGroups[0]) => {
    setIsCreating(false);
    setSelectedGroupType(group.type);
    setSelectedGroup({
      ...group,
      originalType: group.type
    });
  };

  const handleCreateNew = () => {
    setIsCreating(true);
    setSelectedGroupType(null);
    setSelectedGroup({
      type: '',
      location_id: locations[0]?.id ? String(locations[0].id) : '',
      required_mode: 'one',
      qty: 1,
      active: true,
      resources: [],
      connected_services: []
    });
  };

  const handleSaveGroup = async () => {
    if (!selectedGroup) return;
    if (!selectedGroup.type.trim()) {
      toast.error('Resource type/group name is required');
      return;
    }
    if (!selectedGroup.location_id) {
      toast.error('Location is required');
      return;
    }

    setIsLoading(true);
    try {
      const type = selectedGroup.type.trim();
      const originalType = selectedGroup.originalType;
      
      // 1. Sync physical resources
      const targetQty = Number(selectedGroup.qty) || 1;
      const capacity = selectedGroup.required_mode === 'shared' ? 9999 : 1;

      // Fetch all resources currently matching either new type or original type
      const currentMatching = resources.filter(r => r.type === type || (originalType && r.type === originalType));
      
      // Delete any resources with the original type if the type changed
      if (originalType && originalType !== type) {
        const toDelete = resources.filter(r => r.type === originalType);
        for (const r of toDelete) {
          if (r.id) await apiClient.delete(`/api/admin/resources/${r.id}`);
        }
      }

      // Re-create or adjust resources for the target quantity
      const existingRemaining = originalType && originalType !== type ? [] : currentMatching;
      const remainingCount = existingRemaining.length;

      // Update existing ones
      for (let i = 0; i < Math.min(remainingCount, targetQty); i++) {
        const res = existingRemaining[i];
        if (res.id) {
          await apiClient.put(`/api/admin/resources/${res.id}`, {
            name: `${type} ${i + 1}`,
            type: type,
            location_id: parseInt(selectedGroup.location_id),
            capacity: capacity,
            active: selectedGroup.active
          });
        }
      }

      // Delete excess ones
      if (remainingCount > targetQty) {
        for (let i = targetQty; i < remainingCount; i++) {
          const res = existingRemaining[i];
          if (res.id) {
            await apiClient.delete(`/api/admin/resources/${res.id}`);
          }
        }
      }

      // Add new ones
      if (targetQty > remainingCount) {
        for (let i = remainingCount; i < targetQty; i++) {
          await apiClient.post('/api/admin/resources', {
            name: `${type} ${i + 1}`,
            type: type,
            location_id: parseInt(selectedGroup.location_id),
            capacity: capacity,
            active: selectedGroup.active
          });
        }
      }

      // 2. Sync Connected Services requirements
      // Delete any old requirements matching this type / original type
      const oldReqs = requirements.filter(req => req.resource_type === type || (originalType && req.resource_type === originalType));
      for (const req of oldReqs) {
        if (req.id) await apiClient.delete(`/api/admin/resources/requirements/${req.id}`);
      }

      // Create new requirements for checked services
      for (const conn of selectedGroup.connected_services) {
        await apiClient.post('/api/admin/resources/requirements', {
          service_id: conn.service_id,
          resource_type: type,
          quantity: conn.quantity
        });
      }

      toast.success('Resource group saved successfully');
      await fetchInitialData();
      setSelectedGroup(null);
      setSelectedGroupType(null);
    } catch (error) {
      toast.error('Failed to save resource group');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteGroup = async () => {
    if (!selectedGroup) return;
    const type = selectedGroup.type;
    if (!confirm(`Are you sure you want to delete all resources and requirements in the group "${type}"?`)) return;

    setIsLoading(true);
    try {
      // Delete resources of this type
      const groupResources = resources.filter(r => r.type === type);
      for (const r of groupResources) {
        if (r.id) await apiClient.delete(`/api/admin/resources/${r.id}`);
      }

      // Delete requirements of this type
      const groupReqs = requirements.filter(req => req.resource_type === type);
      for (const req of groupReqs) {
        if (req.id) await apiClient.delete(`/api/admin/resources/requirements/${req.id}`);
      }

      toast.success('Resource group deleted successfully');
      await fetchInitialData();
      setSelectedGroup(null);
      setSelectedGroupType(null);
    } catch (error) {
      toast.error('Failed to delete resource group');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleGroupExpand = (type: string) => {
    setExpandedGroups(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  const handleServiceCheck = (serviceId: number, checked: boolean) => {
    if (!selectedGroup) return;
    const current = [...selectedGroup.connected_services];
    if (checked) {
      if (!current.some(c => c.service_id === serviceId)) {
        current.push({ service_id: serviceId, quantity: 1 });
      }
    } else {
      const idx = current.findIndex(c => c.service_id === serviceId);
      if (idx !== -1) current.splice(idx, 1);
    }
    setSelectedGroup({
      ...selectedGroup,
      connected_services: current
    });
  };

  const handleServiceQtyChange = (serviceId: number, qty: number) => {
    if (!selectedGroup) return;
    const current = selectedGroup.connected_services.map(c => 
      c.service_id === serviceId ? { ...c, quantity: Math.max(1, qty) } : c
    );
    setSelectedGroup({
      ...selectedGroup,
      connected_services: current
    });
  };

  const getLocationName = (locationId: string) => {
    return locations.find((l) => String(l.id) === String(locationId))?.name || 'Unknown Location';
  };

  const filteredServices = services.filter(s => 
    s.name.toLowerCase().includes(serviceSearchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] md:gap-0 p-0 font-sans bg-background">
      {/* Left Sidebar - Groups Master List */}
      <div className={`md:w-[35%] border-r flex flex-col bg-muted/10 h-full transition-all duration-300 ${selectedGroup ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4 bg-card">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Resources</h2>
              <span className="text-xs text-muted-foreground">
                {resources.length} total in {listGroups.length} groups
              </span>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" onClick={handleCreateNew} className="h-9 w-9 text-primary hover:bg-primary/10">
                <Plus className="w-5 h-5" />
              </Button>
              {selectedGroupType && (
                <Button variant="ghost" size="icon" onClick={handleDeleteGroup} className="h-9 w-9 text-destructive hover:bg-destructive/10">
                  <Trash2 className="w-5 h-5" />
                </Button>
              )}
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search resources..."
              className="pl-10 bg-background min-h-[40px] text-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <ScrollArea className="flex-1 p-4 bg-muted/5">
          <div className="flex flex-col gap-3">
            {filteredGroups.length === 0 ? (
              <div className="text-center p-8 text-muted-foreground text-sm">
                No resources found.
              </div>
            ) : (
              filteredGroups.map((group) => {
                const isExpanded = !!expandedGroups[group.type];
                return (
                  <div key={group.type} className="flex flex-col gap-1 border rounded-lg overflow-hidden bg-card hover:shadow-sm transition-all">
                    <div
                      onClick={() => handleSelectGroup(group)}
                      className={`flex items-center justify-between p-3.5 cursor-pointer select-none transition-colors
                        ${selectedGroupType === group.type 
                          ? 'bg-primary/5 border-l-2 border-primary' 
                          : 'bg-card hover:bg-accent/40'}
                      `}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleGroupExpand(group.type);
                          }}
                          className="h-6 w-6 flex items-center justify-center rounded hover:bg-accent shrink-0"
                        >
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                        <div className="flex flex-col min-w-0">
                          <span className="font-semibold text-sm truncate">{group.type}</span>
                          <span className="text-[11px] text-muted-foreground">
                            {getLocationName(group.location_id)}
                          </span>
                        </div>
                      </div>
                      <Badge variant="secondary" className="text-xs h-5">
                        {group.qty} {group.qty === 1 ? 'asset' : 'assets'}
                      </Badge>
                    </div>

                    {isExpanded && (
                      <div className="bg-muted/15 border-t divide-y divide-border/30 pl-11 pr-4 py-1">
                        {group.resources.map((res, index) => (
                          <div key={res.id || index} className="py-2.5 flex items-center justify-between text-xs text-muted-foreground">
                            <span>{res.name}</span>
                            <div className="flex items-center gap-2">
                              {!res.active && <Badge variant="outline" className="text-[9px] px-1 py-0 h-4">Inactive</Badge>}
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4 bg-background">
                                Cap: {res.capacity || 1}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Right Detail Pane */}
      <div className={`md:w-[65%] h-full transition-all duration-300 ${selectedGroup ? 'flex w-full absolute inset-0 z-50 md:relative md:z-auto bg-background' : 'hidden md:flex'}`}>
        {selectedGroup ? (
          <div className="flex flex-col w-full h-full bg-card">
            {/* Toolbar Header */}
            <div className="p-4 border-b flex justify-between items-center bg-card sticky top-0 z-10 min-h-[65px]">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedGroup(null); setSelectedGroupType(null); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <h2 className="text-xl font-semibold">
                  {selectedGroupType ? selectedGroupType : 'New Resource Group'}
                </h2>
              </div>
              <div className="flex space-x-2">
                {selectedGroupType && (
                  <Button variant="outline" size="sm" onClick={handleDeleteGroup} className="min-h-[40px] text-destructive hover:bg-destructive/10 hover:text-destructive rounded-md">
                    <Trash2 className="h-4 w-4 mr-2" /> Delete Group
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => { setSelectedGroup(null); setSelectedGroupType(null); }} className="min-h-[40px] rounded-md">
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSaveGroup} disabled={isLoading} className="min-h-[40px] rounded-full px-6 bg-primary text-primary-foreground hover:bg-primary/90">
                  <Save className="h-4 w-4 mr-2" /> Save & Close
                </Button>
              </div>
            </div>

            {/* Accordion Panels */}
            <ScrollArea className="flex-1 p-6">
              <div className="max-w-3xl mx-auto">
                <Accordion type="single" collapsible defaultValue="details" className="space-y-4">
                  
                  {/* Accordion 1 - Details Form */}
                  <AccordionItem value="details" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline font-semibold text-base py-4">
                      Name of resource group
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-5">
                      <div className="grid gap-2">
                        <Label htmlFor="type-name" className="text-sm font-medium">Name of resource type <span className="text-destructive">*</span></Label>
                        <Input
                          id="type-name"
                          value={selectedGroup.type}
                          onChange={(e) => setSelectedGroup({ ...selectedGroup, type: e.target.value })}
                          placeholder="e.g. Suite, Massage Room"
                          className="min-h-[40px]"
                        />
                      </div>

                      <div className="space-y-3">
                        <Label className="text-sm font-medium">Resources required per booking</Label>
                        <div className="grid gap-3">
                          <label 
                            onClick={() => setSelectedGroup({ ...selectedGroup, required_mode: 'one' })}
                            className={`flex items-start p-3 border rounded-lg cursor-pointer transition-all hover:bg-accent/40
                              ${selectedGroup.required_mode === 'one' ? 'border-primary bg-primary/5' : 'border-border'}
                            `}
                          >
                            <input 
                              type="radio" 
                              name="required_mode" 
                              checked={selectedGroup.required_mode === 'one'}
                              onChange={() => {}}
                              className="mt-1 mr-3 h-4 w-4 accent-primary" 
                            />
                            <div className="flex flex-col gap-0.5">
                              <span className="text-sm font-semibold">One per booking</span>
                              <span className="text-xs text-muted-foreground">Each booking reserves its own resource from this group</span>
                            </div>
                          </label>

                          <label 
                            onClick={() => setSelectedGroup({ ...selectedGroup, required_mode: 'shared' })}
                            className={`flex items-start p-3 border rounded-lg cursor-pointer transition-all hover:bg-accent/40
                              ${selectedGroup.required_mode === 'shared' ? 'border-primary bg-primary/5' : 'border-border'}
                            `}
                          >
                            <input 
                              type="radio" 
                              name="required_mode" 
                              checked={selectedGroup.required_mode === 'shared'}
                              onChange={() => {}}
                              className="mt-1 mr-3 h-4 w-4 accent-primary" 
                            />
                            <div className="flex flex-col gap-0.5">
                              <span className="text-sm font-semibold">Shared</span>
                              <span className="text-xs text-muted-foreground">One resource is shared across all concurrent bookings for the same service and provider</span>
                            </div>
                          </label>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 pt-2">
                        <div className="grid gap-2">
                          <Label htmlFor="qty" className="text-sm font-medium">Qty of resources</Label>
                          <Input
                            id="qty"
                            type="number"
                            value={selectedGroup.qty || ''}
                            onChange={(e) => setSelectedGroup({ ...selectedGroup, qty: Math.max(1, Number(e.target.value)) })}
                            placeholder="e.g. 3"
                            className="min-h-[40px]"
                          />
                        </div>

                        <div className="grid gap-2">
                          <Label className="text-sm font-medium">Branch / Location <span className="text-destructive">*</span></Label>
                          <Select
                            value={selectedGroup.location_id}
                            onValueChange={(val) => setSelectedGroup({ ...selectedGroup, location_id: val })}
                          >
                            <SelectTrigger className="min-h-[40px]">
                              <SelectValue placeholder="Select location" />
                            </SelectTrigger>
                            <SelectContent>
                              {locations.map((loc) => (
                                <SelectItem key={loc.id} value={String(loc.id)}>{loc.name}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="flex flex-col justify-center gap-2 pt-2 border-t border-border/30">
                        <Label className="flex items-center gap-3 cursor-pointer py-1">
                          <Switch
                            checked={selectedGroup.active}
                            onCheckedChange={(checked) => setSelectedGroup({ ...selectedGroup, active: checked })}
                          />
                          <span className="text-sm font-medium">Active (Available for booking)</span>
                        </Label>
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 2 - Connected Services */}
                  <AccordionItem value="services" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline font-semibold text-base py-4">
                      Connected services
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-4">
                      <div className="relative">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Search services..."
                          className="pl-10 bg-background min-h-[40px] text-sm"
                          value={serviceSearchQuery}
                          onChange={(e) => setServiceSearchQuery(e.target.value)}
                        />
                      </div>

                      <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                        {filteredServices.map(service => {
                          const connected = selectedGroup.connected_services.find(c => c.service_id === service.id);
                          const isChecked = !!connected;
                          return (
                            <div key={service.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                              <div className="flex items-center space-x-3 flex-1 min-w-0">
                                <Checkbox 
                                  id={`service-${service.id}`} 
                                  checked={isChecked}
                                  onCheckedChange={(checked) => handleServiceCheck(service.id, checked as boolean)}
                                />
                                <Label htmlFor={`service-${service.id}`} className="font-medium text-sm truncate cursor-pointer">
                                  {service.name}
                                </Label>
                              </div>
                              
                              {isChecked && (
                                <div className="flex items-center gap-3 shrink-0 pl-4">
                                  <span className="text-xs text-muted-foreground">Resources needed for service</span>
                                  <Input
                                    type="number"
                                    value={connected.quantity || 1}
                                    onChange={(e) => handleServiceQtyChange(service.id, Number(e.target.value))}
                                    className="w-16 h-8 text-center text-xs font-semibold"
                                  />
                                </div>
                              )}
                            </div>
                          );
                        })}
                        {filteredServices.length === 0 && (
                          <div className="p-6 text-center text-sm text-muted-foreground">
                            No services found.
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                </Accordion>
              </div>
            </ScrollArea>
          </div>
        ) : (
          <div className="h-full w-full flex items-center justify-center border-0 md:border-l bg-card/10">
            <div className="text-center flex flex-col items-center max-w-sm px-6">
              <Box className="w-12 h-12 text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-semibold text-foreground">No Resource Selected</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Select a resource group from the list on the left to view and configure its assets, or create a new group.
              </p>
              <Button onClick={handleCreateNew} variant="outline" className="mt-6 gap-2 border-primary text-primary hover:bg-primary/5 min-h-[40px]">
                <Plus className="w-4 h-4" />
                Create Resource Group
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
