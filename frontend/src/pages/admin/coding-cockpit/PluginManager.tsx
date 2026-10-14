import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, Loader2, PlugZap, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { codexApi } from './workbench/api/codexApi'
import { Badge } from './workbench/components/ui/badge'
import type { PluginApp, PluginDetailResponse, PluginSummary } from './workbench/types/workbench'

const isCodexSecurity = (plugin: Pick<PluginSummary, 'id' | 'name'>) =>
  plugin.name === 'codex-security' || plugin.id.startsWith('codex-security@')

export const PluginManager: React.FC = () => {
  const [plugins, setPlugins] = useState<PluginSummary[]>([])
  const [featured, setFeatured] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PluginDetailResponse | null>(null)
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null)
  const [authorizationApps, setAuthorizationApps] = useState<Record<string, PluginApp[]>>({})

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    try {
      const catalog = await codexApi.listPlugins()
      setPlugins(catalog.plugins)
      setFeatured(new Set(catalog.featuredPluginIds))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load the Codex plugin catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const filteredPlugins = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return plugins
      .filter(plugin => {
        if (!normalized) return true
        const searchable = [
          plugin.name,
          plugin.interface?.displayName,
          plugin.interface?.shortDescription,
          plugin.interface?.developerName,
          ...(plugin.keywords || []),
        ].filter(Boolean).join(' ').toLowerCase()
        return searchable.includes(normalized)
      })
      .sort((left, right) => {
        if (isCodexSecurity(left)) return -1
        if (isCodexSecurity(right)) return 1
        if (left.installed !== right.installed) return left.installed ? -1 : 1
        if (featured.has(left.id) !== featured.has(right.id)) return featured.has(left.id) ? -1 : 1
        return (left.interface?.displayName || left.name).localeCompare(right.interface?.displayName || right.name)
      })
  }, [featured, plugins, query])

  const loadDetail = async (plugin: PluginSummary) => {
    setDetailLoadingId(plugin.id)
    try {
      setDetail(await codexApi.readPlugin(plugin.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load plugin details')
    } finally {
      setDetailLoadingId(null)
    }
  }

  const install = async (plugin: PluginSummary) => {
    setInstallingId(plugin.id)
    try {
      const result = await codexApi.installPlugin(plugin.id)
      setAuthorizationApps(previous => ({ ...previous, [plugin.id]: result.appsNeedingAuth }))
      setPlugins(previous => previous.map(item => item.id === plugin.id ? { ...item, installed: true, enabled: true } : item))
      toast.success(result.alreadyInstalled ? 'Plugin is already installed' : `${plugin.interface?.displayName || plugin.name} installed`)
      if (detail?.summary.id === plugin.id) {
        setDetail(previous => previous ? { ...previous, summary: { ...previous.summary, installed: true, enabled: true } } : previous)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Plugin installation failed')
    } finally {
      setInstallingId(null)
    }
  }

  const selectedAuthApps = detail ? authorizationApps[detail.summary.id] || [] : []
  const displayedApps = detail ? (selectedAuthApps.length > 0 ? selectedAuthApps : detail.apps) : []

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">Codex App Server preview:</span> plugin list, detail, and install methods are currently marked under development by OpenAI. This screen uses the authenticated local app-server and never accepts marketplace filesystem paths from the browser.
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search plugins, capabilities, or developers" className="pl-9" />
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{plugins.filter(plugin => plugin.installed).length} installed</Badge>
          <Button variant="outline" size="sm" onClick={() => void loadCatalog()} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      {detail && (
        <section className="rounded-xl border border-primary/30 bg-card p-4 shadow-sm">
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex gap-3 min-w-0">
              {detail.summary.interface?.logoUrl || detail.summary.interface?.composerIconUrl ? (
                <img src={detail.summary.interface.logoUrl || detail.summary.interface.composerIconUrl || ''} alt="" className="w-12 h-12 rounded-lg object-contain bg-muted" />
              ) : (
                <div className="w-12 h-12 rounded-lg bg-primary/10 text-primary flex items-center justify-center"><PlugZap className="w-6 h-6" /></div>
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold text-base text-foreground">{detail.summary.interface?.displayName || detail.summary.name}</h3>
                  {detail.summary.installed && <Badge variant="success">Installed</Badge>}
                  {isCodexSecurity(detail.summary) && <Badge variant="outline">OpenAI Security</Badge>}
                </div>
                <p className="text-xs text-muted-foreground mt-1 max-w-3xl">{detail.description || detail.summary.interface?.longDescription || detail.summary.interface?.shortDescription}</p>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {detail.summary.interface?.capabilities.map(capability => <Badge key={capability} variant="secondary">{capability}</Badge>)}
                  <Badge variant="outline">{detail.skills.length} skills</Badge>
                  {detail.mcpServers.length > 0 && <Badge variant="outline">{detail.mcpServers.length} MCP server</Badge>}
                </div>
              </div>
            </div>
            <div className="flex md:flex-col gap-2 shrink-0">
              <Button disabled={detail.summary.installed || installingId === detail.summary.id} onClick={() => void install(detail.summary)}>
                {installingId === detail.summary.id ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : detail.summary.installed ? <CheckCircle2 className="w-4 h-4 mr-1" /> : <PlugZap className="w-4 h-4 mr-1" />}
                {detail.summary.installed ? 'Installed' : 'Install plugin'}
              </Button>
              {detail.shareUrl && <a href={detail.shareUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center gap-1 text-xs text-primary hover:underline">Open listing <ExternalLink className="w-3 h-3" /></a>}
            </div>
          </div>

          {displayedApps.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
              <div className="flex items-center gap-2 font-semibold text-sm text-foreground"><ShieldCheck className="w-4 h-4 text-amber-500" /> {selectedAuthApps.length > 0 ? 'Finish app authorization' : 'Connected apps and authorization'}</div>
              <p className="text-xs text-muted-foreground mt-1">{selectedAuthApps.length > 0 ? 'The plugin is installed. Connect only the apps you intend to use; each provider opens its own authorization flow.' : 'These app connections are available to this plugin. Open a provider to connect it or review its current authorization.'}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                {displayedApps.map(app => app.installUrl ? (
                  <a key={app.id} href={app.installUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-background px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted">
                    Connect {app.name} <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                ) : <Badge key={app.id} variant="warning">{app.name} requires workspace setup</Badge>)}
              </div>
            </div>
          )}

          {detail.skills.length > 0 && (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {detail.skills.map(skill => (
                <div key={skill.name} className="rounded-md border border-border bg-muted/20 p-2.5">
                  <div className="font-medium text-xs text-foreground">{skill.shortDescription || skill.name}</div>
                  <div className="text-[10px] text-muted-foreground mt-1 line-clamp-3">{skill.description}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {loading && plugins.length === 0 ? (
        <div className="h-56 flex items-center justify-center text-sm text-muted-foreground"><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Loading the live Codex catalog…</div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filteredPlugins.map(plugin => {
            const title = plugin.interface?.displayName || plugin.name
            const canInstall = !plugin.installed && (plugin.availability === 'AVAILABLE' || !plugin.availability) && (plugin.installPolicy === 'AVAILABLE' || !plugin.installPolicy)
            return (
              <article key={plugin.id} className={`rounded-xl border bg-card p-3 flex flex-col gap-3 ${isCodexSecurity(plugin) ? 'border-emerald-500/50 ring-1 ring-emerald-500/20' : 'border-border'}`}>
                <div className="flex gap-3 min-w-0">
                  {plugin.interface?.logoUrl || plugin.interface?.composerIconUrl ? (
                    <img src={plugin.interface.logoUrl || plugin.interface.composerIconUrl || ''} alt="" className="w-10 h-10 rounded-lg object-contain bg-muted shrink-0" />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-muted text-muted-foreground flex items-center justify-center shrink-0"><PlugZap className="w-5 h-5" /></div>
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h3 className="font-semibold text-sm text-foreground truncate">{title}</h3>
                      {plugin.installed && <Badge variant="success">Installed</Badge>}
                      {isCodexSecurity(plugin) && <Badge variant="outline">Recommended</Badge>}
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1">{plugin.interface?.shortDescription || 'Codex plugin'}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {plugin.interface?.capabilities.slice(0, 4).map(capability => <Badge key={capability} variant="secondary">{capability}</Badge>)}
                  {featured.has(plugin.id) && <Badge variant="outline">Featured</Badge>}
                </div>
                <div className="flex items-center justify-between gap-2 mt-auto">
                  <span className="text-[10px] text-muted-foreground truncate">{plugin.interface?.developerName || plugin.marketplace.displayName || plugin.marketplace.name}</span>
                  <div className="flex gap-1.5">
                    <Button variant="outline" size="sm" disabled={detailLoadingId === plugin.id} onClick={() => void loadDetail(plugin)}>
                      {detailLoadingId === plugin.id && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />} Details
                    </Button>
                    <Button size="sm" disabled={!canInstall || installingId === plugin.id} onClick={() => void install(plugin)}>
                      {installingId === plugin.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : plugin.installed ? 'Installed' : 'Install'}
                    </Button>
                  </div>
                </div>
                {authorizationApps[plugin.id]?.length > 0 && <button className="text-left text-[11px] font-semibold text-amber-500 hover:underline" onClick={() => void loadDetail(plugin)}>Authorization still required for {authorizationApps[plugin.id].map(app => app.name).join(', ')}</button>}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default PluginManager
