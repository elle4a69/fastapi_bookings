import { useNavigate } from "react-router-dom";
import {
  Bot,
  Sparkles,
  Sliders,
  Brain,
  BookOpen,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Cpu,
  Layers,
  FlaskConical,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SmsSettingsTab() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-2">
      {/* 1. Authoritative Guidance Banner */}
      <Card className="border-indigo-500/30 bg-gradient-to-r from-indigo-50/60 via-background to-purple-50/40 dark:from-indigo-950/20 dark:via-background dark:to-purple-950/20 shadow-xs">
        <CardContent className="p-5 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-primary text-primary-foreground shadow-xs shrink-0 mt-0.5">
                <Bot className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-lg font-bold tracking-tight text-foreground">
                    Assistant Studio — Canonical AI Governance
                  </h2>
                  <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/30">
                    Channel-Neutral Authority
                  </Badge>
                </div>
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
                  Prompt engineering, Tone & Style Lab calibration, few-shot style curation, and epistemic
                  memory governance are now unified under the authoritative{" "}
                  <strong className="text-foreground">Assistant Studio</strong>. The SMS Assistant workspace
                  remains dedicated to real-time operations (Live Messages, Arrivals, Draft Triage, and Line Routing).
                </p>
              </div>
            </div>

            <Button
              type="button"
              onClick={() => navigate("/admin/assistant-studio")}
              className="gap-2 shrink-0 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs text-xs h-9"
            >
              <Sparkles className="h-4 w-4" />
              <span>Open Assistant Studio</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-border/60 text-xs">
            <div className="flex items-center gap-2 text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>10-Tier Prompt Precedence Hierarchy</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Pervasive Multi-Tenant Epistemic Memory</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Zero-Mock Tool Execution & Safety Benchmarks</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 2. Seamless Quick-Action Navigation Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold tracking-tight text-foreground flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            Assistant Studio Governance Modules
          </h3>
          <span className="text-[11px] text-muted-foreground">
            Direct deep-links into canonical configuration tabs
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {/* Tile 1: Prompt Composer */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=prompts")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 group-hover:scale-105 transition-transform">
                  <Sliders className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Tier 1–6</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Prompt Composer & Policy
              </CardTitle>
              <CardDescription className="text-xs">
                Manage 10-tier prompt hierarchy, clinic tenant policy, provider overlays, and Style Lab behavioral traits.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>Configure prompts</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>

          {/* Tile 2: Knowledge Review & Curator */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=curator")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 group-hover:scale-105 transition-transform">
                  <Brain className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Curator</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Knowledge Review & Curator
              </CardTitle>
              <CardDescription className="text-xs">
                Review pending knowledge proposals, approve durable facts, resolve epistemic gaps, and manage memory lifecycle.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>Review memories</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>

          {/* Tile 3: Simulator Sandbox */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=simulator")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 group-hover:scale-105 transition-transform">
                  <FlaskConical className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Sandbox</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Simulator Sandbox
              </CardTitle>
              <CardDescription className="text-xs">
                Inspect authentic runtime execution, prompt assembly inspection, and live tool ground-truth calling.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>Launch sandbox</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>

          {/* Tile 4: Example Library */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=examples")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 group-hover:scale-105 transition-transform">
                  <BookOpen className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Few-Shot</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Few-Shot Example Library
              </CardTitle>
              <CardDescription className="text-xs">
                Curate positive and negative stylistic dialogue examples injected into Tier 7 of prompt assembly.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>Manage examples</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>

          {/* Tile 5: Variables & Tools */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=variables")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 group-hover:scale-105 transition-transform">
                  <Cpu className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Tools</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Variables & Tool Catalog
              </CardTitle>
              <CardDescription className="text-xs">
                Inspect dynamic template variables, server-enforced tool schemas, and capabilities available to the assistant.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>View tools & vars</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>

          {/* Tile 6: Evaluation & Safety */}
          <Card
            onClick={() => navigate("/admin/assistant-studio?tab=evaluation")}
            className="hover:border-primary/50 hover:shadow-xs transition-all cursor-pointer group border-border/80 bg-card"
          >
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 group-hover:scale-105 transition-transform">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <Badge variant="secondary" className="text-[10px]">Safety Gate</Badge>
              </div>
              <CardTitle className="text-sm font-bold mt-2 group-hover:text-primary transition-colors">
                Evaluation & Safety Audit
              </CardTitle>
              <CardDescription className="text-xs">
                Run automated benchmarks validating hallucination resistance, appointment boundaries, and safety invariants.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-1 flex items-center text-[11px] font-semibold text-primary gap-1">
              <span>Run safety audit</span>
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
