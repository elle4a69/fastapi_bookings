import React, { useState, useEffect, useCallback } from 'react'
import { BookOpen, Search, ExternalLink, Sparkles, Network } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { toast } from 'sonner'
import { codexApi } from './workbench/api/codexApi'
import type { SkillDetail, SkillSearchResult, SkillsStats } from './workbench/types/workbench'

export const SkillsBrowser: React.FC = () => {
  const [skillsQuery, setSkillsQuery] = useState<string>('fastapi concurrency')
  const [skillsList, setSkillsList] = useState<SkillSearchResult[]>([])
  const [loadingSkills, setLoadingSkills] = useState<boolean>(false)
  const [selectedSkillContent, setSelectedSkillContent] = useState<SkillDetail | null>(null)
  const [stats, setStats] = useState<SkillsStats | null>(null)
  const [skillModalOpen, setSkillModalOpen] = useState<boolean>(false)

  const runSearch = useCallback(async (query: string) => {
    const q = query.trim()
    if (!q) return

    try {
      setLoadingSkills(true)
      const res = await codexApi.searchSkills(q, 12)
      setSkillsList(res.results)
    } catch (err: any) {
      toast.error('Failed querying skills: ' + (err.message || 'Unknown error'))
    } finally {
      setLoadingSkills(false)
    }
  }, [])

  const handleSearchSkills = useCallback(async (overrideQuery?: string) => {
    await runSearch(overrideQuery !== undefined ? overrideQuery : skillsQuery)
  }, [runSearch, skillsQuery])

  const handleViewSkill = async (skillId: string) => {
    try {
      setSelectedSkillContent(await codexApi.readSkill(skillId))
      setSkillModalOpen(true)
    } catch (err: any) {
      toast.error('Failed loading skill details: ' + (err.message || 'Error'))
    }
  }

  useEffect(() => {
    void runSearch('fastapi concurrency')
    void codexApi.getSkillsStats().then(setStats).catch(() => {
      toast.error('Skills RAG service on port 8008 is unavailable')
    })
  }, [runSearch])

  return (
    <div className="space-y-6">
      <Card className="border shadow-sm bg-card">
        <CardHeader className="p-5 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary shrink-0" />
                <span>Skills RAG & Engineering Blueprints</span>
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Hybrid semantic retrieval from the live vector and knowledge-graph index on port 8008.
              </p>
              {stats && (
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 rounded-full border px-2 py-1"><Sparkles className="h-3 w-3 text-amber-500" /> {stats.indexedCount.toLocaleString()} indexed skills</span>
                  <span className="inline-flex items-center gap-1 rounded-full border px-2 py-1"><Network className="h-3 w-3 text-primary" /> {stats.graphNodes.toLocaleString()} nodes · {stats.graphEdges.toLocaleString()} edges</span>
                </div>
              )}
            </div>

            {/* Search Input Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSearchSkills()
              }}
              className="flex items-center gap-2 w-full sm:w-auto"
            >
              <Input
                value={skillsQuery}
                onChange={(e) => setSkillsQuery(e.target.value)}
                placeholder="Search skills (e.g. testing, postgres)..."
                className="text-xs h-9 w-full sm:w-72 bg-background"
              />
              <Button type="submit" size="sm" disabled={loadingSkills} className="h-9 px-3 gap-1.5 shrink-0">
                <Search className={`w-3.5 h-3.5 ${loadingSkills ? 'animate-spin' : ''}`} />
                Search
              </Button>
            </form>
          </div>

          {/* Quick Filter Tags */}
          <div className="flex flex-wrap items-center gap-1.5 pt-3 border-t mt-4">
            <span className="text-[11px] font-semibold text-muted-foreground mr-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-500" /> Popular Tags:
            </span>
            {['fastapi', 'concurrency', 'twilio', 'chatwoot', 'postgres', 'testing', 'docker', 'playwright'].map(
              (tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => {
                    setSkillsQuery(tag)
                    handleSearchSkills(tag)
                  }}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                    skillsQuery === tag
                      ? 'bg-primary text-primary-foreground border-primary font-medium'
                      : 'bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  #{tag}
                </button>
              )
            )}
          </div>
        </CardHeader>

        <CardContent className="p-5 pt-2">
          {skillsList.length === 0 && !loadingSkills ? (
            <div className="text-center py-12 text-xs text-muted-foreground">
              No skills found matching &ldquo;{skillsQuery}&rdquo;. Try another search term.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {skillsList.map((skill) => (
                <div
                  key={skill.id}
                  className="p-3.5 rounded-xl border bg-muted/20 hover:bg-muted/40 transition-all text-left flex flex-col justify-between gap-3 group"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-semibold text-xs text-foreground font-mono truncate">
                        {skill.name}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-3 leading-relaxed">
                      {skill.description}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {typeof skill.score === 'number' && <span className="text-[10px] rounded-full bg-primary/10 px-2 py-0.5 text-primary">relevance {(skill.score * 100).toFixed(1)}%</span>}
                      {skill.category && <span className="text-[10px] rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{skill.category}</span>}
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleViewSkill(skill.id)}
                    className="h-7 text-[11px] text-primary hover:text-primary font-medium w-full gap-1"
                  >
                    <ExternalLink className="w-3 h-3" /> View SKILL.md
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 1-Click Skill Viewer Dialog */}
      <Dialog open={skillModalOpen} onOpenChange={setSkillModalOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col p-6">
          <DialogHeader className="pb-3 border-b">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary" />
              <DialogTitle className="text-base font-semibold font-mono">
                {selectedSkillContent?.name}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Full skill content loaded on demand from the port 8008 hybrid index; turn context loads only the top bounded matches.
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto max-h-[60vh] p-4 bg-muted/40 rounded-lg text-xs font-mono whitespace-pre-wrap leading-relaxed border mt-2">
            {selectedSkillContent?.content}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
