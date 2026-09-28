"""Central Resident Autonomous Agent Engine.

Orchestrates audits, background telemetry monitoring, issue tracking, safe fix
generation/execution, and conversational AI advisory with web research.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

try:
    from openai import AsyncOpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

from .code_auditor import code_auditor
from .telemetry_sentinel import telemetry_sentinel
from .remediation_planner import remediation_planner
from .executor import safe_fix_executor, FixExecutionError
from .web_researcher import web_researcher
from .event_broker import event_broker
from .skill_library import skill_library
from .alert_dispatcher import alert_dispatcher

logger = logging.getLogger(__name__)

_ADVISORY_SYSTEM_PROMPT = """\
You are the Resident Agent — an expert autonomous software engineer and architect \
embedded inside the FastAPI Bookings platform.

Platform context:
- Python FastAPI backend (SQLAlchemy, Alembic, Pydantic v2, async)
- React 19 + Vite + TypeScript frontend (Tailwind, Radix UI / shadcn)
- Multi-tenant SaaS: tenants, providers, locations, resources, services, bookings
- SMS outbox (Twilio), real-time voice, OpenTelemetry → SigNoz, Stripe payments
- Monorepo: app/, frontend/, codex-control-centre/, signoz/, mapbox/, shortURLs/
- Autonomous monitoring via Resident Agent (health score, sentinel scheduler, \
remediation planner, fix executor)
- Governance rules enforced via AGENTS.md: scope discipline, no secrets in logs, \
no blanket git staging, no destructive actions without explicit approval

Your role in this conversation:
- Answer the user's technical or architectural question directly and concisely
- Cite relevant files or services when helpful (e.g. app/services/sms/, \
app/api/routers/)
- When relevant, suggest the smallest safe change rather than a full redesign
- Flag any AGENTS.md constraints that apply
- If web research results are provided, synthesise them into your answer
- Format your response in clean markdown with headers and code blocks where useful
"""



class ResidentAgentEngine:
    """Central supervisor managing autonomous health, issues, and advisory."""

    def __init__(self) -> None:
        self._active_issues: Dict[str, Dict[str, Any]] = {}
        self._plans: Dict[str, Dict[str, Any]] = {}
        self._latest_audit: Optional[Dict[str, Any]] = None
        self._latest_health_score: int = 100
        self._latest_status_str: str = "HEALTHY"

    def get_system_status(self, db: Session) -> Dict[str, Any]:
        """Return overall health score, latest code audit summary, telemetry baseline, and active issues."""
        sentinel_res = telemetry_sentinel.compute_health(db)
        self._latest_health_score = sentinel_res["health_score"]
        self._latest_status_str = sentinel_res["status"]

        # Merge newly detected sentinel issues into registry
        for issue in sentinel_res.get("detected_issues", []):
            issue_id = issue["id"]
            if issue_id not in self._active_issues:
                self._active_issues[issue_id] = {
                    **issue,
                    "status": "OPEN",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "health_score": self._latest_health_score,
            "status": self._latest_status_str,
            "telemetry_baseline": sentinel_res["telemetry"],
            "outbox_status": sentinel_res["outbox"],
            "chatwoot_status": sentinel_res["chatwoot"],
            "latest_code_audit": self._latest_audit,
            "active_issues": list(self._active_issues.values()),
            "alert_dispatch_status": alert_dispatcher.get_dispatch_status(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def run_deep_audit(self, db: Session) -> Dict[str, Any]:
        """Trigger an immediate deep audit (Code + Telemetry + Outbox) and stream progress."""
        await event_broker.publish(
            "thought",
            "Initiating comprehensive system deep audit across codebase, telemetry pipelines, and message queues...",
            title="Audit Started",
        )

        # 1. Codebase Audit
        await event_broker.publish(
            "step",
            {"phase": "code_audit", "status": "scanning git worktree, security patterns, and TypeScript configs"},
            title="Phase 1: Codebase Audit",
        )
        code_res = code_auditor.run_audit()
        self._latest_audit = code_res

        await event_broker.publish(
            "step",
            {"phase": "code_audit_complete", "score": code_res["score"], "clean_git": code_res["git"]["clean"]},
            title=f"Codebase Audit Complete (Score: {code_res['score']}/100)",
        )

        # 2. Telemetry & Queue Sentinel
        await event_broker.publish(
            "step",
            {"phase": "telemetry_sentinel", "status": "querying OTel pipeline and outbox tables"},
            title="Phase 2: Telemetry Sentinel",
        )
        sentinel_res = telemetry_sentinel.compute_health(db)
        self._latest_health_score = sentinel_res["health_score"]
        self._latest_status_str = sentinel_res["status"]

        # Register any new issues
        new_count = 0
        for issue in sentinel_res.get("detected_issues", []):
            issue_id = issue["id"]
            if issue_id not in self._active_issues:
                self._active_issues[issue_id] = {
                    **issue,
                    "status": "OPEN",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                }
                new_count += 1

        # Check code secret leaks for issues
        if not code_res["secrets"]["passed"]:
            sec_id = "ISSUE-SEC-001"
            self._active_issues[sec_id] = {
                "id": sec_id,
                "category": "security",
                "title": f"Potential Secret Leak Detected ({code_res['secrets']['secret_leaks_found']} patterns)",
                "severity": "CRITICAL",
                "description": "Sensitive credentials or API key patterns detected in codebase.",
                "status": "OPEN",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }

        await event_broker.publish(
            "thought",
            f"Deep audit finished. Composite Health Score: {self._latest_health_score}%. Active tracked issues: {len(self._active_issues)}.",
            title="Audit Concluded",
            severity="INFO" if self._latest_health_score >= 80 else "WARNING",
        )

        audit_summary = {
            "health_score": self._latest_health_score,
            "status": self._latest_status_str,
            "code_audit": code_res,
            "telemetry_audit": sentinel_res,
            "new_issues_discovered": new_count,
            "total_active_issues": len(self._active_issues),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await event_broker.publish(
            "audit",
            audit_summary,
            title="Deep Audit Summary Report",
        )

        return audit_summary

    def plan_remediation_for_issue(
        self,
        issue_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate an automated remediation plan for a selected issue."""
        issue = self._active_issues.get(issue_id, {})
        title = issue.get("title", f"Issue {issue_id}")
        category = issue.get("category", "general")

        merged_context = {
            "description": issue.get("description", ""),
            "severity": issue.get("severity", "WARNING"),
            **(context or {}),
        }

        plan = remediation_planner.generate_plan(
            issue_id=issue_id,
            issue_title=title,
            category=category,
            context=merged_context,
        )

        self._plans[plan["plan_id"]] = plan
        return plan

    async def execute_remediation_plan(
        self,
        plan_id: str,
        approved: bool = False,
        simulate_only: bool = False,
    ) -> Dict[str, Any]:
        """Safely execute an approved remediation plan with rollback and verification."""
        plan = self._plans.get(plan_id)
        if not plan:
            # Fallback to generating on the fly if plan_id matches an issue
            plan = self.plan_remediation_for_issue(plan_id)

        exec_res = await safe_fix_executor.execute_plan(
            plan=plan,
            approved=approved,
            simulate_only=simulate_only,
        )

        if exec_res.get("success"):
            issue_id = plan.get("issue_id")
            if issue_id in self._active_issues:
                self._active_issues[issue_id]["status"] = "RESOLVED"
                self._active_issues[issue_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            plan["status"] = "EXECUTED"

        return exec_res

    async def provide_advisory(
        self,
        prompt: str,
        enable_web_research: bool = True,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Conversational AI advisory endpoint — calls GPT-4o with project context,
        web research results, and local skill citations. Falls back to a structured
        template response if the OpenAI key is absent or the call fails."""
        await event_broker.publish(
            "thought",
            f"Analyzing advisory inquiry: '{prompt[:100]}...'",
            title="Advisory Request Received",
        )

        # ── 1. Web research ──────────────────────────────────────────────────
        research_data = None
        if enable_web_research:
            await event_broker.publish(
                "step",
                {"step": "web_research", "query": prompt, "domain": domain},
                title="Executing Documentation & Web Research",
            )
            research_data = await web_researcher.research(query=prompt, domain=domain)

        recommendations: List[str] = []
        if research_data:
            recommendations.extend(research_data.get("recommendations", []))

        # ── 2. Local skill citations ─────────────────────────────────────────
        skills: List[Any] = []
        if research_data and research_data.get("skills"):
            skills = research_data["skills"]
        else:
            skills = skill_library.find_relevant_skills(prompt, top_k=3)

        # ── 3. LLM advisory call ─────────────────────────────────────────────
        api_key = os.getenv("OPENAI_API_KEY", "")
        try:
            from app.core.config import settings as _settings
            api_key = api_key or getattr(_settings, "OPENAI_API_KEY", "") or ""
        except Exception:
            pass

        analysis: str
        if _OPENAI_AVAILABLE and api_key:
            await event_broker.publish(
                "step",
                {"step": "llm_synthesis", "model": "gpt-4o"},
                title="Synthesising Advisory with GPT-4o",
            )
            try:
                # Build a rich user message including research context
                user_parts: List[str] = [f"**User question:** {prompt}"]

                if research_data and research_data.get("summary"):
                    user_parts.append(
                        f"\n**Web research summary:**\n{research_data['summary']}"
                    )
                if research_data and research_data.get("sources"):
                    src_lines = "\n".join(
                        f"- {s}" for s in research_data["sources"][:5]
                    )
                    user_parts.append(f"\n**Sources consulted:**\n{src_lines}")
                if recommendations:
                    rec_lines = "\n".join(f"- {r}" for r in recommendations[:5])
                    user_parts.append(
                        f"\n**Curated best-practice recommendations:**\n{rec_lines}"
                    )
                if skills:
                    skill_lines = "\n".join(
                        f"- **{sk['name']}**: {sk['description']}" for sk in skills[:3]
                    )
                    user_parts.append(
                        f"\n**Relevant local engineering skills:**\n{skill_lines}"
                    )
                if self._active_issues:
                    active = list(self._active_issues.values())[:3]
                    issue_lines = "\n".join(
                        f"- [{i['severity']}] {i['title']}" for i in active
                    )
                    user_parts.append(
                        f"\n**Currently active system issues:**\n{issue_lines}"
                    )

                user_message = "\n".join(user_parts)

                client = AsyncOpenAI(api_key=api_key)
                completion = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": _ADVISORY_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                    max_tokens=1500,
                )
                analysis = completion.choices[0].message.content or ""
                logger.info(
                    "Advisory GPT-4o call succeeded — %d prompt tokens, %d completion tokens",
                    completion.usage.prompt_tokens if completion.usage else 0,
                    completion.usage.completion_tokens if completion.usage else 0,
                )
            except Exception as exc:
                logger.warning("GPT-4o advisory call failed (%s); using fallback template.", exc)
                analysis = self._fallback_advisory_template(prompt, skills)
        else:
            if not api_key:
                logger.info("OPENAI_API_KEY not set — advisory using fallback template.")
            analysis = self._fallback_advisory_template(prompt, skills)

        # ── 4. Publish completion ────────────────────────────────────────────
        await event_broker.publish(
            "thought",
            "Advisory synthesis complete.",
            title="Advisory Response Ready",
        )

        return {
            "prompt": prompt,
            "web_research_enabled": enable_web_research,
            "research_summary": research_data.get("summary") if research_data else None,
            "sources": research_data.get("sources", []) if research_data else [],
            "skills": skills,
            "recommendations": recommendations or [
                "Verify backward compatibility with existing Alembic database migrations.",
                "Enforce atomic updates with automatic verification test gates.",
            ],
            "advisory_markdown": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fallback_advisory_template(prompt: str, skills: List[Any]) -> str:
        """Structured fallback used when the LLM is unavailable."""
        lines = [
            "Based on repository architecture and guidelines in AGENTS.md, here is the architectural strategy for your inquiry:",
            "",
            "• **Scope Discipline**: Isolate service modifications strictly within relevant domain packages (`app/services/`).",
            "• **Concurrency & Locking**: Use transactional row leases when coordinating multi-worker outbox or calendar tasks.",
            "• **Privacy & Telemetry**: Ensure customer PII and credential secrets are strictly redacted from logs and tracing attributes.",
        ]
        if skills:
            lines.append("\n\n**Referenced Engineering Skills (Local Library `C:\\Users\\Frank\\skills`):**")
            for sk in skills:
                lines.append(f"• **{sk['name']}**: {sk['description']}")
        lines.append("\n> ⚠️ *GPT-4o advisory unavailable — set `OPENAI_API_KEY` in `.env` to enable live AI responses.*")
        return "\n".join(lines)


# Global resident agent engine singleton
resident_agent_engine = ResidentAgentEngine()
