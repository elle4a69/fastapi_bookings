import { useState, useEffect } from 'react';
import { Search, Loader2, ArrowLeft, RefreshCw, Building, User, Sparkles, Layers, Tag, PlusCircle, Package } from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';

import { apiClient } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface EntityItem {
  id: number | string;
  name: string;
}

const normId = (id: any): number => {
  if (id === null || id === undefined) return 0;
  const str = String(id).replace(/^(prov|loc|svc|cat|add_on|addon|prod|product)-/i, '');
  return parseInt(str, 10) || 0;
};

export default function RelationshipsTreePage() {
  const [locations, setLocations] = useState<EntityItem[]>([]);
  const [allProviders, setAllProviders] = useState<EntityItem[]>([]);
  const [allServices, setAllServices] = useState<EntityItem[]>([]);
  const [allCategories, setAllCategories] = useState<EntityItem[]>([]);
  const [allAddons, setAllAddons] = useState<EntityItem[]>([]);
  const [allProducts, setAllProducts] = useState<EntityItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Relationship ID sets
  const [locProvidersMap, setLocProvidersMap] = useState<Record<number, Set<number>>>({});
  const [provServicesMap, setProvServicesMap] = useState<Record<number, Set<number>>>({});
  const [svcCategoriesMap, setSvcCategoriesMap] = useState<Record<number, Set<number>>>({});
  const [svcAddonsMap, setSvcAddonsMap] = useState<Record<number, Set<number>>>({});
  const [svcProductsMap, setSvcProductsMap] = useState<Record<number, Set<number>>>({});

  const [updatingKeys, setUpdatingKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadAllCatalogs();
  }, []);

  const loadAllCatalogs = async () => {
    setLoading(true);
    try {
      const [lRes, pRes, sRes, cRes, aRes, prRes] = await Promise.all([
        apiClient.get<any>('/api/admin/locations'),
        apiClient.get<any>('/api/admin/providers'),
        apiClient.get<any>('/api/admin/services'),
        apiClient.get<any>('/api/admin/categories'),
        apiClient.get<any>('/api/admin/add-ons'),
        apiClient.get<any>('/api/admin/products'),
      ]);

      const locs = Array.isArray(lRes) ? lRes : (lRes?.data || []);
      const provs = Array.isArray(pRes) ? pRes : (pRes?.data || []);
      const svcs = Array.isArray(sRes) ? sRes : (sRes?.data || []);
      const cats = Array.isArray(cRes) ? cRes : (cRes?.data || []);
      const addons = Array.isArray(aRes) ? aRes : (aRes?.data || []);
      const prods = Array.isArray(prRes) ? prRes : (prRes?.data || []);

      setLocations(locs);
      setAllProviders(provs);
      setAllServices(svcs);
      setAllCategories(cats);
      setAllAddons(addons);
      setAllProducts(prods);

      const locProvSets: Record<number, Set<number>> = {};
      await Promise.all(
        locs.map(async (loc: any) => {
          try {
            const rels = await apiClient.get<any>(`/api/admin/relationships/locations/${normId(loc.id)}/providers`);
            const list = Array.isArray(rels) ? rels : (rels?.data || []);
            locProvSets[normId(loc.id)] = new Set(list.map((item: any) => normId(item.id)));
          } catch {
            locProvSets[normId(loc.id)] = new Set();
          }
        })
      );
      setLocProvidersMap(locProvSets);
    } catch {
      toast.error('Failed to load catalog tree.');
    } finally {
      setLoading(false);
    }
  };

  const ensureProviderServicesLoaded = async (provId: number | string) => {
    const numProvId = normId(provId);
    if (provServicesMap[numProvId]) return;

    try {
      const rels = await apiClient.get<any>(`/api/admin/relationships/providers/${numProvId}/services`);
      const list = Array.isArray(rels) ? rels : (rels?.data || []);
      const idSet = new Set<number>(list.map((item: any) => normId(item.id)));
      setProvServicesMap(prev => ({ ...prev, [numProvId]: idSet }));
    } catch {
      setProvServicesMap(prev => ({ ...prev, [numProvId]: new Set() }));
    }
  };

  const ensureServiceRelationsLoaded = async (svcId: number | string) => {
    const numSvcId = normId(svcId);
    if (svcCategoriesMap[numSvcId] && svcAddonsMap[numSvcId] && svcProductsMap[numSvcId]) return;

    try {
      const [cRels, aRels, pRels] = await Promise.all([
        apiClient.get<any>(`/api/admin/relationships/services/${numSvcId}/categories`).catch(() => []),
        apiClient.get<any>(`/api/admin/relationships/services/${numSvcId}/add-ons`).catch(() => []),
        apiClient.get<any>(`/api/admin/relationships/services/${numSvcId}/products`).catch(() => []),
      ]);

      const cList = Array.isArray(cRels) ? cRels : (cRels?.data || []);
      const aList = Array.isArray(aRels) ? aRels : (aRels?.data || []);
      const pList = Array.isArray(pRels) ? pRels : (pRels?.data || []);

      setSvcCategoriesMap(prev => ({ ...prev, [numSvcId]: new Set(cList.map((item: any) => normId(item.id))) }));
      setSvcAddonsMap(prev => ({ ...prev, [numSvcId]: new Set(aList.map((item: any) => normId(item.id))) }));
      setSvcProductsMap(prev => ({ ...prev, [numSvcId]: new Set(pList.map((item: any) => normId(item.id))) }));
    } catch {
      setSvcCategoriesMap(prev => ({ ...prev, [numSvcId]: new Set() }));
      setSvcAddonsMap(prev => ({ ...prev, [numSvcId]: new Set() }));
      setSvcProductsMap(prev => ({ ...prev, [numSvcId]: new Set() }));
    }
  };

  // Toggle Relationship Handlers
  const toggleLocationProvider = async (locId: number | string, provId: number | string, isLinked: boolean) => {
    const numLoc = normId(locId);
    const numProv = normId(provId);
    const key = `loc-${numLoc}-prov-${numProv}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      const url = `/api/admin/relationships/locations/${numLoc}/providers/${numProv}`;
      if (isLinked) {
        await apiClient.delete(url);
        setLocProvidersMap(prev => {
          const set = new Set(prev[numLoc] || []);
          set.delete(numProv);
          return { ...prev, [numLoc]: set };
        });
        toast.success('Provider unlinked from location');
      } else {
        await apiClient.post(url);
        setLocProvidersMap(prev => {
          const set = new Set(prev[numLoc] || []);
          set.add(numProv);
          return { ...prev, [numLoc]: set };
        });
        toast.success('Provider linked to location');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update provider link');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleProviderService = async (provId: number | string, svcId: number | string, isLinked: boolean) => {
    const numProv = normId(provId);
    const numSvc = normId(svcId);
    const key = `prov-${numProv}-svc-${numSvc}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      const url = `/api/admin/relationships/providers/${numProv}/services/${numSvc}`;
      if (isLinked) {
        await apiClient.delete(url);
        setProvServicesMap(prev => {
          const set = new Set(prev[numProv] || []);
          set.delete(numSvc);
          return { ...prev, [numProv]: set };
        });
        toast.success('Service unlinked from provider');
      } else {
        await apiClient.post(url);
        setProvServicesMap(prev => {
          const set = new Set(prev[numProv] || []);
          set.add(numSvc);
          return { ...prev, [numProv]: set };
        });
        toast.success('Service linked to provider');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update service link');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleServiceCategory = async (svcId: number | string, catId: number | string, isLinked: boolean) => {
    const numSvc = normId(svcId);
    const numCat = normId(catId);
    const key = `svc-${numSvc}-cat-${numCat}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      const url = `/api/admin/relationships/services/${numSvc}/categories/${numCat}`;
      if (isLinked) {
        await apiClient.delete(url);
        setSvcCategoriesMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.delete(numCat);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Category unlinked from service');
      } else {
        await apiClient.post(url);
        setSvcCategoriesMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.add(numCat);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Category linked to service');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update category link');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleServiceAddon = async (svcId: number | string, addonId: number | string, isLinked: boolean) => {
    const numSvc = normId(svcId);
    const numAdd = normId(addonId);
    const key = `svc-${numSvc}-addon-${numAdd}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      const url = `/api/admin/relationships/services/${numSvc}/add-ons/${numAdd}`;
      if (isLinked) {
        await apiClient.delete(url);
        setSvcAddonsMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.delete(numAdd);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Add-on unlinked from service');
      } else {
        await apiClient.post(url);
        setSvcAddonsMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.add(numAdd);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Add-on linked to service');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update add-on link');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleServiceProduct = async (svcId: number | string, prodId: number | string, isLinked: boolean) => {
    const numSvc = normId(svcId);
    const numProd = normId(prodId);
    const key = `svc-${numSvc}-prod-${numProd}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      const url = `/api/admin/relationships/services/${numSvc}/products/${numProd}`;
      if (isLinked) {
        await apiClient.delete(url);
        setSvcProductsMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.delete(numProd);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Product unlinked from service');
      } else {
        await apiClient.post(url);
        setSvcProductsMap(prev => {
          const set = new Set(prev[numSvc] || []);
          set.add(numProd);
          return { ...prev, [numSvc]: set };
        });
        toast.success('Product linked to service');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update product link');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const filteredLocations = locations.filter(loc =>
    (loc.name || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="text-sm text-muted-foreground font-medium">Loading relationship tree hierarchy...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] max-w-3xl mx-auto p-4 sm:p-6 gap-5 bg-background font-sans">
      {/* ── Header ────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b pb-4 shrink-0">
        <div>
          <div className="flex items-center gap-2.5">
            <Link to="/admin/relationships">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Nested Hierarchy Tree</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 ml-10">
            Mobile-optimized: Locations ➔ Providers ➔ Services ➔ [Categories | Add-ons | Products]
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link to="/admin/relationships-matrix">
            <Button variant="outline" size="sm" className="h-8 text-xs font-semibold gap-1.5">
              <Layers className="w-3.5 h-3.5 text-primary" /> 5-Column Matrix
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={loadAllCatalogs} className="h-8 text-xs gap-1">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {/* ── Search Filter ──────────────────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search locations..."
          className="pl-9 h-9 text-xs rounded-xl bg-card border-border/60"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* ── Centered Column of Accordions ─────────────────────────── */}
      <Card className="border border-border/60 bg-card/90 shadow-xs overflow-hidden rounded-2xl">
        <CardHeader className="p-3.5 pb-2.5 border-b bg-muted/20">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
              <Building className="w-4 h-4 text-primary" /> Locations Hierarchy
            </CardTitle>
            <Badge variant="secondary" className="font-bold text-[10px] h-5 px-1.5">
              {filteredLocations.length} Locations
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-3 space-y-3">
          {filteredLocations.length === 0 ? (
            <p className="text-center text-muted-foreground text-xs py-8">No locations found.</p>
          ) : (
            <Accordion type="multiple" className="space-y-3">
              {filteredLocations.map((loc) => {
                const numLoc = normId(loc.id);
                const assignedProvSet = locProvidersMap[numLoc] || new Set();

                return (
                  <AccordionItem
                    key={loc.id}
                    value={`loc-${loc.id}`}
                    className="border border-border/60 rounded-xl bg-card overflow-hidden shadow-2xs"
                  >
                    {/* Level 1 Accordion Trigger (Location) */}
                    <AccordionTrigger className="hover:no-underline px-3.5 py-3 bg-muted/10 hover:bg-muted/20">
                      <div className="flex items-center justify-between w-full pr-3 text-left">
                        <div className="flex items-center gap-2 min-w-0 pr-2">
                          <Building className="w-4 h-4 text-primary shrink-0" />
                          <span className="font-bold text-xs text-foreground truncate">{loc.name}</span>
                        </div>
                        <Badge variant="outline" className="text-[10px] font-semibold bg-background shrink-0">
                          {assignedProvSet.size} Providers
                        </Badge>
                      </div>
                    </AccordionTrigger>

                    <AccordionContent className="p-3 pt-2.5 border-t bg-muted/5 space-y-3">
                      <div>
                        <h4 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-primary" /> Service Providers at {loc.name}
                        </h4>

                        {/* Level 2: Providers List (Nested Accordion) */}
                        <Accordion type="multiple" className="space-y-2">
                          {allProviders.map((prov) => {
                            const numProv = normId(prov.id);
                            const isProvLinked = assignedProvSet.has(numProv);
                            const provKey = `loc-${numLoc}-prov-${numProv}`;
                            const isUpdatingProv = updatingKeys.has(provKey);

                            const assignedSvcSet = provServicesMap[numProv] || new Set();

                            return (
                              <AccordionItem
                                key={prov.id}
                                value={`prov-${prov.id}`}
                                className={`border rounded-lg transition-colors bg-card ${
                                  isProvLinked ? 'border-primary/40 bg-primary/5' : 'border-border/40 opacity-80'
                                }`}
                              >
                                <div className="flex items-center justify-between px-3 py-2">
                                  <AccordionTrigger
                                    onClick={() => ensureProviderServicesLoaded(prov.id)}
                                    className="hover:no-underline py-1 flex-1 min-w-0 pr-2"
                                  >
                                    <div className="flex items-center gap-2 min-w-0">
                                      <User className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                                      <span className="text-xs font-semibold truncate text-foreground">{prov.name}</span>
                                      {isProvLinked && (
                                        <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 text-[9px] px-1.5 py-0 h-4 font-bold shrink-0">
                                          Assigned
                                        </Badge>
                                      )}
                                    </div>
                                  </AccordionTrigger>

                                  <div className="shrink-0 flex items-center gap-2 pl-2">
                                    {isUpdatingProv ? (
                                      <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                                    ) : (
                                      <Switch
                                        id={provKey}
                                        checked={isProvLinked}
                                        onCheckedChange={() => toggleLocationProvider(loc.id, prov.id, isProvLinked)}
                                        className="scale-75 cursor-pointer"
                                      />
                                    )}
                                  </div>
                                </div>

                                {/* Level 3: Services (Nested Accordion under Provider) */}
                                <AccordionContent className="p-3 pt-1 border-t bg-muted/10 space-y-3">
                                  <div className="flex items-center justify-between mb-1">
                                    <h5 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                                      <Sparkles className="w-3 h-3 text-primary" /> Services by {prov.name}
                                    </h5>
                                    <Badge variant="secondary" className="text-[9px] h-4 px-1">
                                      {assignedSvcSet.size} Linked
                                    </Badge>
                                  </div>

                                  <Accordion type="multiple" className="space-y-1.5">
                                    {allServices.map((svc) => {
                                      const numSvc = normId(svc.id);
                                      const isSvcLinked = assignedSvcSet.has(numSvc);
                                      const svcKey = `prov-${numProv}-svc-${numSvc}`;
                                      const isUpdatingSvc = updatingKeys.has(svcKey);

                                      const catSet = svcCategoriesMap[numSvc] || new Set();
                                      const addonSet = svcAddonsMap[numSvc] || new Set();
                                      const productSet = svcProductsMap[numSvc] || new Set();

                                      return (
                                        <AccordionItem
                                          key={svc.id}
                                          value={`svc-${svc.id}`}
                                          className={`border rounded-md bg-background ${
                                            isSvcLinked ? 'border-primary/30 bg-primary/5' : 'border-border/30'
                                          }`}
                                        >
                                          <div className="flex items-center justify-between px-2.5 py-1.5">
                                            <AccordionTrigger
                                              onClick={() => ensureServiceRelationsLoaded(svc.id)}
                                              className="hover:no-underline py-0.5 flex-1 min-w-0 pr-2"
                                            >
                                              <div className="flex items-center gap-1.5 min-w-0">
                                                <Sparkles className="w-3 h-3 text-muted-foreground shrink-0" />
                                                <span className="text-xs font-medium truncate text-foreground">{svc.name}</span>
                                              </div>
                                            </AccordionTrigger>

                                            <div className="shrink-0 flex items-center gap-2">
                                              {isUpdatingSvc ? (
                                                <Loader2 className="w-3 h-3 text-primary animate-spin" />
                                              ) : (
                                                <Switch
                                                  id={svcKey}
                                                  checked={isSvcLinked}
                                                  onCheckedChange={() => toggleProviderService(prov.id, svc.id, isSvcLinked)}
                                                  className="scale-75 cursor-pointer"
                                                />
                                              )}
                                            </div>
                                          </div>

                                          {/* Level 4: 3 TABS under each Service (Categories | Add-ons | Products) */}
                                          <AccordionContent className="p-2.5 pt-1.5 border-t bg-muted/20">
                                            <Tabs defaultValue="categories" className="w-full">
                                              <TabsList className="w-full h-7 grid grid-cols-3 bg-muted/50 p-0.5 rounded-lg mb-2">
                                                <TabsTrigger value="categories" className="text-[10px] font-bold py-0.5 h-6 gap-1">
                                                  <Tag className="w-3 h-3" /> Categories ({catSet.size})
                                                </TabsTrigger>
                                                <TabsTrigger value="addons" className="text-[10px] font-bold py-0.5 h-6 gap-1">
                                                  <PlusCircle className="w-3 h-3" /> Add-ons ({addonSet.size})
                                                </TabsTrigger>
                                                <TabsTrigger value="products" className="text-[10px] font-bold py-0.5 h-6 gap-1">
                                                  <Package className="w-3 h-3" /> Products ({productSet.size})
                                                </TabsTrigger>
                                              </TabsList>

                                              {/* Tab 1: Categories */}
                                              <TabsContent value="categories" className="mt-0">
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-48 overflow-y-auto pr-1">
                                                  {allCategories.map((cat) => {
                                                    const numCat = normId(cat.id);
                                                    const isCatLinked = catSet.has(numCat);
                                                    const catKey = `svc-${numSvc}-cat-${numCat}`;
                                                    const isUpdatingCat = updatingKeys.has(catKey);

                                                    return (
                                                      <div
                                                        key={cat.id}
                                                        className="flex items-center justify-between p-1 px-2 rounded border bg-card border-border/40 text-[11px]"
                                                      >
                                                        <span className="truncate font-medium pr-1 text-foreground">{cat.name}</span>
                                                        {isUpdatingCat ? (
                                                          <Loader2 className="w-3 h-3 text-primary animate-spin" />
                                                        ) : (
                                                          <Switch
                                                            id={catKey}
                                                            checked={isCatLinked}
                                                            onCheckedChange={() => toggleServiceCategory(svc.id, cat.id, isCatLinked)}
                                                            className="scale-75 cursor-pointer"
                                                          />
                                                        )}
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              </TabsContent>

                                              {/* Tab 2: Service Add-ons */}
                                              <TabsContent value="addons" className="mt-0">
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-48 overflow-y-auto pr-1">
                                                  {allAddons.map((addon) => {
                                                    const numAdd = normId(addon.id);
                                                    const isAddonLinked = addonSet.has(numAdd);
                                                    const addKey = `svc-${numSvc}-addon-${numAdd}`;
                                                    const isUpdatingAdd = updatingKeys.has(addKey);

                                                    return (
                                                      <div
                                                        key={addon.id}
                                                        className="flex items-center justify-between p-1 px-2 rounded border bg-card border-border/40 text-[11px]"
                                                      >
                                                        <span className="truncate font-medium pr-1 text-foreground">{addon.name}</span>
                                                        {isUpdatingAdd ? (
                                                          <Loader2 className="w-3 h-3 text-primary animate-spin" />
                                                        ) : (
                                                          <Switch
                                                            id={addKey}
                                                            checked={isAddonLinked}
                                                            onCheckedChange={() => toggleServiceAddon(svc.id, addon.id, isAddonLinked)}
                                                            className="scale-75 cursor-pointer"
                                                          />
                                                        )}
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              </TabsContent>

                                              {/* Tab 3: Products */}
                                              <TabsContent value="products" className="mt-0">
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-48 overflow-y-auto pr-1">
                                                  {allProducts.map((prod) => {
                                                    const numProd = normId(prod.id);
                                                    const isProdLinked = productSet.has(numProd);
                                                    const prodKey = `svc-${numSvc}-prod-${numProd}`;
                                                    const isUpdatingProd = updatingKeys.has(prodKey);

                                                    return (
                                                      <div
                                                        key={prod.id}
                                                        className="flex items-center justify-between p-1 px-2 rounded border bg-card border-border/40 text-[11px]"
                                                      >
                                                        <span className="truncate font-medium pr-1 text-foreground">{prod.name}</span>
                                                        {isUpdatingProd ? (
                                                          <Loader2 className="w-3 h-3 text-primary animate-spin" />
                                                        ) : (
                                                          <Switch
                                                            id={prodKey}
                                                            checked={isProdLinked}
                                                            onCheckedChange={() => toggleServiceProduct(svc.id, prod.id, isProdLinked)}
                                                            className="scale-75 cursor-pointer"
                                                          />
                                                        )}
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              </TabsContent>
                                            </Tabs>
                                          </AccordionContent>
                                        </AccordionItem>
                                      );
                                    })}
                                  </Accordion>
                                </AccordionContent>
                              </AccordionItem>
                            );
                          })}
                        </Accordion>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
