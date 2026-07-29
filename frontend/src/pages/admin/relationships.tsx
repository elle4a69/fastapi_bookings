import { useState, useEffect } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

interface BaseItem {
  id: number | string;
  name: string;
}

type TabConfig = {
  id: string;
  label: string;
  leftType: string;
  leftUrl: string;
  rightType: string;
  rightUrl: string;
};

const TABS: TabConfig[] = [
  { id: 'service-provider', label: 'Service ↔ Provider', leftType: 'services', leftUrl: '/api/admin/services', rightType: 'providers', rightUrl: '/api/admin/providers' },
  { id: 'service-location', label: 'Service ↔ Location', leftType: 'services', leftUrl: '/api/admin/services', rightType: 'locations', rightUrl: '/api/admin/locations' },
  { id: 'provider-location', label: 'Provider ↔ Location', leftType: 'providers', leftUrl: '/api/admin/providers', rightType: 'locations', rightUrl: '/api/admin/locations' },
  { id: 'service-category', label: 'Service ↔ Category', leftType: 'services', leftUrl: '/api/admin/services', rightType: 'categories', rightUrl: '/api/admin/categories' },
  { id: 'service-addon', label: 'Service ↔ Add-on', leftType: 'services', leftUrl: '/api/admin/services', rightType: 'add-ons', rightUrl: '/api/admin/add-ons' },
  { id: 'service-product', label: 'Service ↔ Product', leftType: 'services', leftUrl: '/api/admin/services', rightType: 'products', rightUrl: '/api/admin/products' },
];

export default function RelationshipsPage() {
  const [activeTab, setActiveTab] = useState<string>(TABS[0].id);
  const [leftItems, setLeftItems] = useState<BaseItem[]>([]);
  const [rightItems, setRightItems] = useState<BaseItem[]>([]);
  const [selectedLeftId, setSelectedLeftId] = useState<number | string | null>(null);
  
  const [assignedRightIds, setAssignedRightIds] = useState<Set<number | string>>(new Set());
  const [leftLoading, setLeftLoading] = useState(false);
  const [rightLoading, setRightLoading] = useState(false);
  const [mappingsLoading, setMappingsLoading] = useState(false);
  
  const [leftSearch, setLeftSearch] = useState('');
  const [rightSearch, setRightSearch] = useState('');
  
  const [updatingIds, setUpdatingIds] = useState<Set<number | string>>(new Set());

  const currentTab = TABS.find(t => t.id === activeTab)!;

  useEffect(() => {
    loadLists();
    setSelectedLeftId(null);
    setAssignedRightIds(new Set());
    setLeftSearch('');
    setRightSearch('');
  }, [activeTab]);

  useEffect(() => {
    if (selectedLeftId) {
      loadMappings();
    } else {
      setAssignedRightIds(new Set());
    }
  }, [selectedLeftId, activeTab]);

  const loadLists = async () => {
    setLeftLoading(true);
    setRightLoading(true);
    try {
      const [leftRes, rightRes] = await Promise.all([
        apiClient.get<any>(currentTab.leftUrl),
        apiClient.get<any>(currentTab.rightUrl)
      ]);
      
      const leftData = Array.isArray(leftRes) ? leftRes : leftRes.data || leftRes.items || [];
      const rightData = Array.isArray(rightRes) ? rightRes : rightRes.data || rightRes.items || [];
      
      setLeftItems(leftData);
      setRightItems(rightData);
    } catch (error) {
      toast.error('Failed to load items.');
    } finally {
      setLeftLoading(false);
      setRightLoading(false);
    }
  };

  const loadMappings = async () => {
    if (!selectedLeftId) return;
    setMappingsLoading(true);
    try {
      const url = `/api/admin/relationships/${currentTab.leftType}/${selectedLeftId}/${currentTab.rightType}`;
      const res = await apiClient.get<any>(url);
      const data = Array.isArray(res) ? res : res.data || [];
      const ids = new Set<number | string>(data.map((item: any) => item.id));
      setAssignedRightIds(ids);
    } catch (error) {
      toast.error('Failed to load mappings.');
    } finally {
      setMappingsLoading(false);
    }
  };

  const toggleMapping = async (rightId: number | string, isAssigned: boolean) => {
    if (!selectedLeftId) return;
    
    setUpdatingIds(prev => new Set(prev).add(rightId));
    try {
      const url = `/api/admin/relationships/${currentTab.leftType}/${selectedLeftId}/${currentTab.rightType}/${rightId}`;
      if (isAssigned) {
        // unlink
        await apiClient.delete(url);
        setAssignedRightIds(prev => {
          const next = new Set(prev);
          next.delete(rightId);
          return next;
        });
        toast.success('Unlinked successfully.');
      } else {
        // link
        await apiClient.post(url);
        setAssignedRightIds(prev => new Set(prev).add(rightId));
        toast.success('Linked successfully.');
      }
    } catch (error) {
      toast.error('Failed to update mapping.');
    } finally {
      setUpdatingIds(prev => {
        const next = new Set(prev);
        next.delete(rightId);
        return next;
      });
    }
  };

  const filteredLeft = leftItems.filter(item => (item.name || '').toLowerCase().includes(leftSearch.toLowerCase()));
  const filteredRight = rightItems.filter(item => (item.name || '').toLowerCase().includes(rightSearch.toLowerCase()));

  return (
    <div className="container mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Bulk Relationship Matrix Editor</h1>
        <p className="text-muted-foreground mt-2">
          Manage many-to-many relationships across all catalog and provider records efficiently.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full flex flex-col">
        <div className="flex flex-wrap gap-2 pb-2 border-b mb-6">
          {TABS.map(tab => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium rounded-lg border transition-all duration-150 ${
                  isActive 
                    ? 'bg-primary text-primary-foreground border-primary shadow-sm font-semibold' 
                    : 'bg-card text-muted-foreground border-border/60 hover:text-foreground hover:bg-muted/30'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        
        <TabsContent value={activeTab} className="mt-0 outline-none">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[700px]">
            {/* Left Column */}
            <Card className="md:col-span-4 lg:col-span-4 flex flex-col h-full overflow-hidden">
              <CardHeader className="pb-3 shrink-0">
                <CardTitle className="text-lg">Select {currentTab.leftType.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}</CardTitle>
                <div className="relative mt-2">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="search"
                    placeholder="Search..."
                    className="pl-8"
                    value={leftSearch}
                    onChange={(e) => setLeftSearch(e.target.value)}
                  />
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-hidden p-0">
                <ScrollArea className="h-full">
                  <div className="p-4 pt-0 space-y-2">
                    {leftLoading ? (
                      Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-12 w-full rounded-md" />
                      ))
                    ) : filteredLeft.length === 0 ? (
                      <p className="text-center text-muted-foreground text-sm py-4">No items found.</p>
                    ) : (
                      filteredLeft.map(item => {
                        const isSelected = selectedLeftId === item.id;
                        return (
                          <button
                            key={item.id}
                            onClick={() => setSelectedLeftId(item.id)}
                            className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all duration-200 hover:scale-[1.01] hover:shadow-sm ${
                              isSelected 
                                ? 'ring-1 ring-primary/20 border-primary bg-primary/5 text-primary font-semibold' 
                                : 'border-border bg-card text-foreground'
                            }`}
                          >
                            <Avatar className="h-8 w-8 shrink-0 border bg-muted/40 flex items-center justify-center">
                              <AvatarFallback className={`text-xs font-bold bg-transparent ${isSelected ? 'text-primary' : 'text-foreground/80'}`}>
                                {item.name ? item.name[0].toUpperCase() : 'S'}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{item.name || `Unnamed (ID: ${item.id})`}</p>
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Right Column */}
            <Card className="md:col-span-8 lg:col-span-8 flex flex-col h-full overflow-hidden">
              <CardHeader className="pb-3 shrink-0">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    Target {currentTab.rightType.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </CardTitle>
                  {mappingsLoading && (
                    <Badge variant="outline" className="animate-pulse">Loading mappings...</Badge>
                  )}
                </div>
                <div className="relative mt-2">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="search"
                    placeholder="Search targets..."
                    className="pl-8"
                    value={rightSearch}
                    onChange={(e) => setRightSearch(e.target.value)}
                    disabled={!selectedLeftId}
                  />
                </div>
                {!selectedLeftId && (
                  <CardDescription className="mt-2 text-yellow-600 dark:text-yellow-500">
                    Please select a source item from the left column first.
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="flex-1 overflow-hidden p-0 bg-muted/20">
                <ScrollArea className="h-full">
                  <div className="p-4 space-y-3">
                    {rightLoading ? (
                      Array.from({ length: 8 }).map((_, i) => (
                        <div key={i} className="flex items-center space-x-3 p-2">
                          <Skeleton className="h-5 w-5 rounded" />
                          <Skeleton className="h-5 w-48" />
                        </div>
                      ))
                    ) : !selectedLeftId ? (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-50 pt-20">
                        <Search className="h-12 w-12 mb-4" />
                        <p>Select an item to view mappings</p>
                      </div>
                    ) : filteredRight.length === 0 ? (
                      <p className="text-center text-muted-foreground text-sm py-4">No targets found.</p>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {filteredRight.map(item => {
                          const isAssigned = assignedRightIds.has(item.id);
                          const isUpdating = updatingIds.has(item.id);

                          return (
                            <div 
                              key={item.id} 
                              className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-colors bg-card ${
                                isAssigned ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border'
                              } ${isUpdating ? 'opacity-70 pointer-events-none' : 'hover:border-primary/20'}`}
                            >
                              <Avatar className="h-8 w-8 shrink-0 border bg-muted/40 flex items-center justify-center">
                                <AvatarFallback className="text-xs font-bold bg-transparent text-foreground/80">
                                  {item.name ? item.name[0].toUpperCase() : 'T'}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{item.name || `Unnamed (ID: ${item.id})`}</p>
                              </div>
                              <div className="shrink-0 flex items-center justify-center w-8">
                                {isUpdating ? (
                                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                                ) : (
                                  <Switch
                                    id={`target-${item.id}`}
                                    checked={isAssigned}
                                    onCheckedChange={() => toggleMapping(item.id, isAssigned)}
                                  />
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
