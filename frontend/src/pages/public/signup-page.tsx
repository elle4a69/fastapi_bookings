import React, { useState, useEffect } from "react"
import { useNavigate, useSearchParams, Link } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Building2,
  User,
  Mail,
  Lock,
  Zap,
  Check,
  AlertCircle,
  Loader2,
  Globe,
  Phone,
} from "lucide-react"

import { apiClient, setAdminAccessToken } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"

interface InvitationData {
  token: string
  email: string
  role: string
  status: string
  is_valid: boolean
  tenant_id: number
  tenant_name: string
  tenant_subdomain: string
  expires_at: string | null
}

interface PlanOption {
  id: "starter" | "growth" | "unlimited"
  name: string
  tagline: string
  monthlyPrice: number
  annualPrice: number
  recommended?: boolean
  features: string[]
  badge?: string
  accentColor: string
}

const PLANS: PlanOption[] = [
  {
    id: "starter",
    name: "Starter",
    tagline: "Ideal for boutique studios & independent professionals",
    monthlyPrice: 29,
    annualPrice: 23,
    accentColor: "from-blue-500/20 to-cyan-500/20",
    features: [
      "1 Dedicated Provider & Calendar",
      "1 Business Location / Service Area",
      "Real-Time Booking & Scheduling Engine",
      "Mobile-Optimized Client Self-Service Portal",
      "Automated Email Confirmations & Reminders",
      "Client History & Intake Forms",
    ],
  },
  {
    id: "growth",
    name: "Growth",
    tagline: "High-velocity practices needing multi-staff & 2-way SMS",
    monthlyPrice: 79,
    annualPrice: 63,
    recommended: true,
    badge: "MOST POPULAR",
    accentColor: "from-fuchsia-500/20 via-primary/20 to-purple-500/20",
    features: [
      "Up to 5 Providers & Multi-Staff Scheduling",
      "Up to 3 Physical or Virtual Locations",
      "2-Way Autonomous SMS Assistant & Reminders",
      "3 Add-On Modules (Invoicing, Packages, Reviews)",
      "Dynamic Travel Charges & Location Origin Rules",
      "Automated Waitlist & Cancellation Fill Engine",
      "Custom Branding & White-Label Domain",
    ],
  },
  {
    id: "unlimited",
    name: "Scale / Unlimited",
    tagline: "Autonomous AI operations, voice studio & enterprise CRM",
    monthlyPrice: 199,
    annualPrice: 159,
    badge: "AI-NATIVE",
    accentColor: "from-amber-500/20 via-orange-500/20 to-rose-500/20",
    features: [
      "Unlimited Providers & Unlimited Locations",
      "Real-Time Voice AI Assistant Studio (LiveKit)",
      "Full SMS Curator & Intelligent Multi-Turn Routing",
      "Omnichannel Chatwoot CRM Bridge",
      "All Add-On Modules & Unlimited Relationships",
      "Dedicated Enterprise Onboarding & 24/7 Priority SLA",
      "Custom Telemetry & Granular Audit Logging",
    ],
  },
]

const INDUSTRIES = [
  "Hair, Nails & Beauty",
  "Medical, Dental & Clinic",
  "Wellness, Spa & Massage",
  "Fitness, Yoga & Personal Training",
  "Consulting, Legal & Professional",
  "Trades & In-Home Mobile Services",
  "Other Services",
]

export default function SignupPage({ defaultTab }: { defaultTab?: "pricing" | "signup" }) {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Token from query param (if user received single-use invite link)
  const tokenParam = searchParams.get("token") || searchParams.get("invite")

  // Modes: 'invite' if token provided, otherwise 3-step 'wizard'
  const isInviteMode = Boolean(tokenParam)

  // Invitation state
  const [invitationLoading, setInvitationLoading] = useState(isInviteMode)
  const [invitation, setInvitation] = useState<InvitationData | null>(null)
  const [invitationError, setInvitationError] = useState<string | null>(null)

  // Wizard state
  const [currentStep, setCurrentStep] = useState<number>(defaultTab === "pricing" ? 1 : 1)
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("annual")
  const [selectedPlan, setSelectedPlan] = useState<"starter" | "growth" | "unlimited">(
    (searchParams.get("plan") as any) || "growth"
  )

  // Step 2 Form: Business
  const [businessName, setBusinessName] = useState("")
  const [subdomain, setSubdomain] = useState("")
  const [subdomainStatus, setSubdomainStatus] = useState<"idle" | "checking" | "available" | "taken">("idle")
  const [industry, setIndustry] = useState(INDUSTRIES[0])
  const [businessPhone, setBusinessPhone] = useState("")

  // Step 3 Form: Owner & Identity
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [agreedTerms, setAgreedTerms] = useState(true)

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionStage, setSubmissionStage] = useState<string>("")
  const [launchSuccess, setLaunchSuccess] = useState(false)

  // 1. Fetch Invitation details if token is present
  useEffect(() => {
    if (!tokenParam) return

    let isMounted = true
    setInvitationLoading(true)
    setInvitationError(null)

    apiClient
      .get<{ ok: boolean; data: InvitationData }>(`/api/auth/invitations/${encodeURIComponent(tokenParam)}`)
      .then((res) => {
        if (!isMounted) return
        if (res?.ok && res.data) {
          setInvitation(res.data)
          if (res.data.email) {
            setEmail(res.data.email)
          }
        } else {
          setInvitationError("Invitation details could not be retrieved.")
        }
      })
      .catch((err: any) => {
        if (!isMounted) return
        setInvitationError(err?.message || "Invitation token is invalid or has expired.")
      })
      .finally(() => {
        if (isMounted) setInvitationLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [tokenParam])

  // 2. Auto-generate subdomain slug from business name
  const handleBusinessNameChange = (val: string) => {
    setBusinessName(val)
    if (subdomainStatus === "idle" || !subdomain) {
      const generated = val
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 30)
      setSubdomain(generated)
    }
  }

  // 3. Debounced Subdomain availability check
  useEffect(() => {
    if (!subdomain || subdomain.length < 2) {
      setSubdomainStatus("idle")
      return
    }

    setSubdomainStatus("checking")
    const timer = setTimeout(() => {
      apiClient
        .get<{ ok: boolean; data: { available: boolean } }>(`/api/public/check-subdomain?subdomain=${encodeURIComponent(subdomain)}`)
        .then((res) => {
          if (res?.ok && res.data?.available) {
            setSubdomainStatus("available")
          } else {
            setSubdomainStatus("taken")
          }
        })
        .catch(() => {
          setSubdomainStatus("taken")
        })
    }, 400)

    return () => clearTimeout(timer)
  }, [subdomain])

  // 4. Handle Invitation Acceptance
  const handleAcceptInvitation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tokenParam) return

    if (!password || password.length < 6) {
      toast.error("Password must be at least 6 characters long.")
      return
    }
    if (password !== confirmPassword) {
      toast.error("Passwords do not match.")
      return
    }

    try {
      setIsSubmitting(true)
      setSubmissionStage("Redeeming invitation & provisioning account...")

      const res = await apiClient.post<any>("/api/auth/invitations/accept", {
        token: tokenParam,
        password: password,
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
      })

      if (res?.ok && res.data?.access_token) {
        setAdminAccessToken(res.data.access_token)
        if (res.data.user?.tenant_subdomain) {
          localStorage.setItem("tenant", res.data.user.tenant_subdomain)
          localStorage.setItem("tenant_subdomain", res.data.user.tenant_subdomain)
        }
        setLaunchSuccess(true)
        toast.success("Workspace claimed successfully! Redirecting...")
        setTimeout(() => {
          navigate("/admin/dashboard", { replace: true })
        }, 1200)
      } else {
        throw new Error(res?.detail || "Invitation acceptance failed")
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to redeem invitation.")
      setIsSubmitting(false)
    }
  }

  // 5. Handle New Workspace Registration
  const handleRegisterWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!businessName.trim()) {
      toast.error("Please enter your business name.")
      setCurrentStep(2)
      return
    }
    if (!subdomain.trim() || subdomainStatus === "taken") {
      toast.error("Please choose a valid, available subdomain.")
      setCurrentStep(2)
      return
    }
    if (!email.trim() || !email.includes("@")) {
      toast.error("Please provide a valid work email.")
      return
    }
    if (!password || password.length < 6) {
      toast.error("Password must be at least 6 characters.")
      return
    }
    if (password !== confirmPassword) {
      toast.error("Passwords do not match.")
      return
    }
    if (!agreedTerms) {
      toast.error("Please agree to the Terms of Service to continue.")
      return
    }

    try {
      setIsSubmitting(true)
      setSubmissionStage("Creating isolated tenant workspace...")

      const payload = {
        name: businessName.trim(),
        subdomain: subdomain.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
        password: password,
        first_name: firstName.trim() || "Owner",
        last_name: lastName.trim() || "",
        subscription_tier: selectedPlan,
        billing_cycle: billingCycle,
        phone: businessPhone.trim() || undefined,
      }

      const res = await apiClient.post<any>("/api/public/signup", payload)

      if (res?.ok && res.data?.access_token) {
        setSubmissionStage("Finalizing workspace credentials...")
        setAdminAccessToken(res.data.access_token)
        if (res.data.tenant?.subdomain) {
          localStorage.setItem("tenant", res.data.tenant.subdomain)
          localStorage.setItem("tenant_subdomain", res.data.tenant.subdomain)
        }
        setLaunchSuccess(true)
        toast.success("Workspace created! Welcome aboard.")
        setTimeout(() => {
          navigate("/admin/dashboard", { replace: true })
        }, 1400)
      } else {
        throw new Error(res?.detail || "Registration failed")
      }
    } catch (err: any) {
      toast.error(err?.message || "Workspace creation failed. Please check details.")
      setIsSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full bg-background text-foreground overflow-x-hidden selection:bg-primary/20">
      {/* Dynamic Ambient Background Glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-gradient-to-tr from-primary/25 to-purple-600/20 blur-[130px] opacity-70 animate-pulse" />
        <div className="absolute top-1/3 -right-40 h-[650px] w-[650px] rounded-full bg-gradient-to-bl from-blue-600/20 via-fuchsia-500/15 to-transparent blur-[140px] opacity-60" />
        <div className="absolute -bottom-40 left-1/3 h-[550px] w-[550px] rounded-full bg-gradient-to-t from-pink-500/20 to-primary/10 blur-[120px] opacity-50" />
      </div>

      {/* Top Header Navigation */}
      <header className="relative z-20 border-b border-border/40 bg-background/70 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-primary-foreground shadow-md shadow-primary/20 group-hover:scale-105 transition-transform duration-200">
              <Zap className="h-5 w-5 fill-current" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70">
                BookMe
              </span>
              <span className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground -mt-1">
                Autonomous SaaS
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground font-medium bg-muted/50 px-3 py-1.5 rounded-full border border-border/50">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
              <span>PCI-DSS Level 1 Encrypted</span>
            </div>
            <Link
              to="/login"
              className="text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16">
        {launchSuccess ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-w-md mx-auto text-center p-8 bg-card/90 backdrop-blur-2xl border border-primary/30 rounded-2xl shadow-2xl space-y-4"
          >
            <div className="h-16 w-16 rounded-full bg-emerald-500/10 text-emerald-500 mx-auto flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <h2 className="text-2xl font-bold">Workspace Ready!</h2>
            <p className="text-sm text-muted-foreground">
              Redirecting you to your administrative cockpit...
            </p>
            <Loader2 className="h-5 w-5 animate-spin mx-auto text-primary" />
          </motion.div>
        ) : isInviteMode ? (
          <div className="max-w-xl mx-auto">
            {invitationLoading && (
              <Card className="border-border/60 bg-card/75 backdrop-blur-xl shadow-2xl p-8 text-center space-y-4">
                <Loader2 className="h-10 w-10 text-primary animate-spin mx-auto" />
                <h3 className="text-lg font-semibold">Validating Workspace Invitation...</h3>
                <p className="text-sm text-muted-foreground">Checking cryptographic signature and expiry window...</p>
              </Card>
            )}

            {!invitationLoading && invitationError && (
              <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }}>
                <Card className="border-destructive/30 bg-destructive/5 backdrop-blur-xl shadow-2xl overflow-hidden">
                  <CardHeader className="text-center pb-4">
                    <div className="mx-auto h-12 w-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center mb-2">
                      <AlertCircle className="h-6 w-6" />
                    </div>
                    <CardTitle className="text-xl">Invitation Unavailable</CardTitle>
                    <CardDescription>{invitationError}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4 text-center">
                    <p className="text-xs text-muted-foreground">
                      This invitation token may have expired or already been redeemed. Please contact your workspace administrator for a fresh link.
                    </p>
                  </CardContent>
                  <CardFooter className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
                    <Button variant="outline" onClick={() => navigate("/login")}>
                      Return to Sign In
                    </Button>
                    <Button onClick={() => navigate("/join")}>Create New Workspace</Button>
                  </CardFooter>
                </Card>
              </motion.div>
            )}

            {!invitationLoading && invitation && invitation.is_valid && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
                <Card className="border-border/60 bg-card/85 backdrop-blur-2xl shadow-2xl rounded-2xl overflow-hidden border">
                  {/* Top Glowing Banner */}
                  <div className="bg-gradient-to-r from-primary/15 via-purple-500/15 to-blue-500/15 p-6 border-b border-border/40 text-center relative overflow-hidden">
                    <div className="absolute top-2 right-2">
                      <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 gap-1 text-[11px] font-semibold">
                        <CheckCircle2 className="h-3 w-3" /> Valid Token
                      </Badge>
                    </div>
                    <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-primary to-purple-600 text-primary-foreground mx-auto flex items-center justify-center shadow-lg shadow-primary/25 mb-3">
                      <Building2 className="h-7 w-7" />
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">
                      Join {invitation.tenant_name}
                    </h2>
                    <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                      You've been invited as a founding <span className="font-semibold text-foreground uppercase">{invitation.role}</span>
                    </p>
                    <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-background/80 border border-border/50 text-xs font-mono text-muted-foreground">
                      <Globe className="h-3.5 w-3.5 text-primary" />
                      https://{invitation.tenant_subdomain}.bookme.app
                    </div>
                  </div>

                  <form onSubmit={handleAcceptInvitation}>
                    <CardContent className="space-y-4 p-6 sm:p-8">
                      {/* Invitee Email (Read-Only) */}
                      <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          Invited Work Email
                        </Label>
                        <div className="relative">
                          <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            type="email"
                            value={invitation.email}
                            disabled
                            className="pl-9 bg-muted/40 font-medium"
                          />
                        </div>
                      </div>

                      {/* Name Fields */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <Label htmlFor="inv-first-name" className="text-xs font-semibold">
                            First Name
                          </Label>
                          <div className="relative">
                            <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                            <Input
                              id="inv-first-name"
                              value={firstName}
                              onChange={(e) => setFirstName(e.target.value)}
                              placeholder="Elena"
                              className="pl-9"
                              required
                            />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="inv-last-name" className="text-xs font-semibold">
                            Last Name
                          </Label>
                          <Input
                            id="inv-last-name"
                            value={lastName}
                            onChange={(e) => setLastName(e.target.value)}
                            placeholder="Rostova"
                            required
                          />
                        </div>
                      </div>

                      {/* Password Fields */}
                      <div className="space-y-1.5">
                        <Label htmlFor="inv-password" className="text-xs font-semibold">
                          Create Workspace Password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            id="inv-password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="At least 6 characters"
                            className="pl-9"
                            required
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="inv-confirm-password" className="text-xs font-semibold">
                          Confirm Password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            id="inv-confirm-password"
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            placeholder="Repeat password"
                            className="pl-9"
                            required
                          />
                        </div>
                      </div>
                    </CardContent>

                    <CardFooter className="px-6 sm:px-8 pb-8 flex flex-col gap-3">
                      <Button
                        type="submit"
                        className="w-full h-11 text-sm font-semibold bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90 text-primary-foreground shadow-lg shadow-primary/20"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            {submissionStage || "Activating Workspace..."}
                          </>
                        ) : (
                          <>
                            Claim Workspace & Activate Account
                            <ArrowRight className="h-4 w-4 ml-2" />
                          </>
                        )}
                      </Button>
                      <p className="text-[11px] text-center text-muted-foreground">
                        By accepting, your owner account is instantly provisioned with full admin rights.
                      </p>
                    </CardFooter>
                  </form>
                </Card>
              </motion.div>
            )}
          </div>
        ) : (
          /* ================================================================= */
          /* MODE B: HIGH-CONVERTING 3-STEP PUBLIC SIGN-UP WIZARD               */
          /* ================================================================= */
          <div className="space-y-10">
            {/* Header Hero Section */}
            <div className="text-center max-w-3xl mx-auto space-y-4">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-xs font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Modern Autonomous Booking & Practice OS</span>
              </div>
              <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight">
                Supercharge Your Practice with{" "}
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary via-purple-500 to-indigo-500">
                  AI-Powered Bookings
                </span>
              </h1>
              <p className="text-base sm:text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                Real-time voice AI assistant, automated 2-way SMS reminders, multi-provider calendar sync, and isolated multi-tenant data safety.
              </p>

              {/* Step Navigation Pill Indicator */}
              <div className="pt-4 flex items-center justify-center gap-2 sm:gap-4 text-xs font-semibold">
                <div
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all cursor-pointer ${
                    currentStep === 1
                      ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                      : "bg-muted/70 text-muted-foreground hover:bg-muted"
                  }`}
                  onClick={() => setCurrentStep(1)}
                >
                  <span className="h-4 w-4 rounded-full bg-background/20 flex items-center justify-center text-[10px]">
                    1
                  </span>
                  <span>1. Choose Plan</span>
                </div>
                <div className="h-0.5 w-6 bg-border" />
                <div
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all cursor-pointer ${
                    currentStep === 2
                      ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                      : "bg-muted/70 text-muted-foreground hover:bg-muted"
                  }`}
                  onClick={() => setCurrentStep(2)}
                >
                  <span className="h-4 w-4 rounded-full bg-background/20 flex items-center justify-center text-[10px]">
                    2
                  </span>
                  <span>2. Business Details</span>
                </div>
                <div className="h-0.5 w-6 bg-border" />
                <div
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all cursor-pointer ${
                    currentStep === 3
                      ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                      : "bg-muted/70 text-muted-foreground hover:bg-muted"
                  }`}
                  onClick={() => setCurrentStep(3)}
                >
                  <span className="h-4 w-4 rounded-full bg-background/20 flex items-center justify-center text-[10px]">
                    3
                  </span>
                  <span>3. Founding Account</span>
                </div>
              </div>
            </div>

            {/* Step Wizard Content */}
            <AnimatePresence mode="wait">
              {/* STEP 1: CHOOSE PLAN & BILLING CADENCE */}
              {currentStep === 1 && (
                <motion.div
                  key="step-1"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.25 }}
                  className="space-y-8"
                >
                  {/* Monthly vs Annual Toggle */}
                  <div className="flex items-center justify-center gap-3">
                    <span
                      className={`text-xs sm:text-sm font-semibold cursor-pointer ${
                        billingCycle === "monthly" ? "text-foreground" : "text-muted-foreground"
                      }`}
                      onClick={() => setBillingCycle("monthly")}
                    >
                      Billed Monthly
                    </span>
                    <div
                      className="relative w-14 h-7 rounded-full bg-muted border border-border/80 p-0.5 cursor-pointer transition-colors"
                      onClick={() => setBillingCycle(billingCycle === "monthly" ? "annual" : "monthly")}
                    >
                      <motion.div
                        className="h-5.5 w-5.5 rounded-full bg-primary shadow-sm"
                        animate={{ x: billingCycle === "annual" ? 28 : 2 }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    </div>
                    <div
                      className="flex items-center gap-1.5 cursor-pointer"
                      onClick={() => setBillingCycle("annual")}
                    >
                      <span
                        className={`text-xs sm:text-sm font-semibold ${
                          billingCycle === "annual" ? "text-foreground" : "text-muted-foreground"
                        }`}
                      >
                        Billed Annually
                      </span>
                      <Badge className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-0 text-[10px] font-bold py-0.5 px-2 tracking-wide uppercase">
                        Save 20%
                      </Badge>
                    </div>
                  </div>

                  {/* Pricing Cards Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 items-stretch">
                    {PLANS.map((plan) => {
                      const isSelected = selectedPlan === plan.id
                      const price = billingCycle === "annual" ? plan.annualPrice : plan.monthlyPrice

                      return (
                        <div
                          key={plan.id}
                          onClick={() => setSelectedPlan(plan.id)}
                          className={`relative rounded-2xl transition-all duration-300 flex flex-col cursor-pointer border ${
                            isSelected
                              ? "border-primary ring-2 ring-primary/40 bg-card/90 shadow-2xl scale-[1.02]"
                              : "border-border/60 bg-card/65 hover:border-border hover:bg-card/85 shadow-lg"
                          } backdrop-blur-xl p-6 sm:p-7`}
                        >
                          {plan.recommended && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                              <Badge className="bg-gradient-to-r from-primary to-purple-600 text-primary-foreground border-0 text-[10px] font-extrabold tracking-wider px-3 py-1 shadow-md shadow-primary/25">
                                {plan.badge}
                              </Badge>
                            </div>
                          )}

                          <div className="flex-1 space-y-4">
                            <div>
                              <h3 className="text-xl font-bold">{plan.name}</h3>
                              <p className="text-xs text-muted-foreground min-h-[36px] pt-1">
                                {plan.tagline}
                              </p>
                            </div>

                            <div className="flex items-baseline gap-1 pt-2">
                              <span className="text-4xl font-extrabold tracking-tight">${price}</span>
                              <span className="text-xs text-muted-foreground font-medium">/ month</span>
                            </div>
                            <p className="text-[11px] text-muted-foreground">
                              {billingCycle === "annual" ? "Billed annually ($" + price * 12 + "/yr)" : "Billed monthly, cancel anytime"}
                            </p>

                            <div className="h-px w-full bg-border/60 my-4" />

                            <ul className="space-y-2.5 text-xs text-muted-foreground">
                              {plan.features.map((feat, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                                  <span className="text-foreground/90 font-medium">{feat}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="pt-6">
                            <Button
                              type="button"
                              variant={isSelected ? "default" : "outline"}
                              className={`w-full font-semibold ${
                                isSelected
                                  ? "bg-gradient-to-r from-primary to-purple-600 text-primary-foreground shadow-md shadow-primary/25"
                                  : "border-border/80"
                              }`}
                              onClick={(e) => {
                                e.stopPropagation()
                                setSelectedPlan(plan.id)
                                setCurrentStep(2)
                              }}
                            >
                              {isSelected ? "Selected — Continue" : "Select " + plan.name}
                            </Button>
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  <div className="flex justify-end pt-4">
                    <Button
                      size="lg"
                      className="px-8 font-semibold bg-gradient-to-r from-primary to-purple-600 text-primary-foreground shadow-lg shadow-primary/20"
                      onClick={() => setCurrentStep(2)}
                    >
                      Next: Business Details
                      <ArrowRight className="h-4 w-4 ml-2" />
                    </Button>
                  </div>
                </motion.div>
              )}

              {/* STEP 2: BUSINESS & WORKSPACE SLUG */}
              {currentStep === 2 && (
                <motion.div
                  key="step-2"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.25 }}
                  className="max-w-2xl mx-auto"
                >
                  <Card className="border-border/60 bg-card/85 backdrop-blur-2xl shadow-2xl rounded-2xl">
                    <CardHeader>
                      <CardTitle className="text-2xl font-bold flex items-center gap-2">
                        <Building2 className="h-6 w-6 text-primary" />
                        Configure Your Business Workspace
                      </CardTitle>
                      <CardDescription>
                        Set up your organization identity and dedicated booking subdomain.
                      </CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-5">
                      {/* Business Name */}
                      <div className="space-y-1.5">
                        <Label htmlFor="biz-name" className="text-xs font-semibold">
                          Business or Practice Name
                        </Label>
                        <Input
                          id="biz-name"
                          value={businessName}
                          onChange={(e) => handleBusinessNameChange(e.target.value)}
                          placeholder="e.g. Apex Health & Aesthetics"
                          className="h-11"
                          required
                        />
                      </div>

                      {/* Subdomain Slug with live checking */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="subdomain" className="text-xs font-semibold">
                            Dedicated Booking Subdomain
                          </Label>
                          {subdomainStatus === "checking" && (
                            <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                              <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                            </span>
                          )}
                          {subdomainStatus === "available" && (
                            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" /> Subdomain available!
                            </span>
                          )}
                          {subdomainStatus === "taken" && (
                            <span className="text-[11px] text-destructive font-semibold flex items-center gap-1">
                              <AlertCircle className="h-3 w-3" /> Already taken
                            </span>
                          )}
                        </div>

                        <div className="flex items-center rounded-md border border-input bg-background/50 overflow-hidden focus-within:ring-2 focus-within:ring-primary">
                          <span className="pl-3 text-xs text-muted-foreground font-mono select-none">https://</span>
                          <Input
                            id="subdomain"
                            value={subdomain}
                            onChange={(e) =>
                              setSubdomain(
                                e.target.value
                                  .toLowerCase()
                                  .replace(/[^a-z0-9-]/g, "")
                                  .slice(0, 30)
                              )
                            }
                            placeholder="apex-health"
                            className="border-0 shadow-none focus-visible:ring-0 px-1 font-mono text-sm font-semibold"
                            required
                          />
                          <span className="pr-3 text-xs text-muted-foreground font-mono select-none">.bookme.app</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          This URL is where your staff will access their dashboard and clients will book appointments.
                        </p>
                      </div>

                      {/* Industry / Category */}
                      <div className="space-y-1.5">
                        <Label htmlFor="industry" className="text-xs font-semibold">
                          Practice Industry & Specialty
                        </Label>
                        <select
                          id="industry"
                          value={industry}
                          onChange={(e) => setIndustry(e.target.value)}
                          className="w-full h-11 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        >
                          {INDUSTRIES.map((ind) => (
                            <option key={ind} value={ind}>
                              {ind}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Business Phone (Optional) */}
                      <div className="space-y-1.5">
                        <Label htmlFor="biz-phone" className="text-xs font-semibold">
                          Business Phone (Optional, for SMS setup)
                        </Label>
                        <div className="relative">
                          <Phone className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input
                            id="biz-phone"
                            type="tel"
                            value={businessPhone}
                            onChange={(e) => setBusinessPhone(e.target.value)}
                            placeholder="+1 (555) 019-2834"
                            className="pl-9"
                          />
                        </div>
                      </div>
                    </CardContent>

                    <CardFooter className="flex justify-between pt-2 pb-6">
                      <Button variant="ghost" onClick={() => setCurrentStep(1)}>
                        <ArrowLeft className="h-4 w-4 mr-1.5" />
                        Back to Plans
                      </Button>
                      <Button
                        className="bg-gradient-to-r from-primary to-purple-600 text-primary-foreground shadow-md shadow-primary/20"
                        onClick={() => {
                          if (!businessName.trim()) {
                            toast.error("Please enter your business name.")
                            return
                          }
                          if (!subdomain.trim() || subdomainStatus === "taken") {
                            toast.error("Please enter an available subdomain.")
                            return
                          }
                          setCurrentStep(3)
                        }}
                      >
                        Next: Owner Account
                        <ArrowRight className="h-4 w-4 ml-1.5" />
                      </Button>
                    </CardFooter>
                  </Card>
                </motion.div>
              )}

              {/* STEP 3: FOUNDING OWNER ACCOUNT */}
              {currentStep === 3 && (
                <motion.div
                  key="step-3"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.25 }}
                  className="max-w-2xl mx-auto"
                >
                  <Card className="border-border/60 bg-card/85 backdrop-blur-2xl shadow-2xl rounded-2xl">
                    <CardHeader>
                      <CardTitle className="text-2xl font-bold flex items-center gap-2">
                        <User className="h-6 w-6 text-primary" />
                        Create Founding Owner Account
                      </CardTitle>
                      <CardDescription>
                        You will be the primary administrator with full access to billing, scheduling, and staff controls.
                      </CardDescription>
                    </CardHeader>

                    <form onSubmit={handleRegisterWorkspace}>
                      <CardContent className="space-y-4">
                        {/* Name Fields */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <Label htmlFor="owner-first-name" className="text-xs font-semibold">
                              First Name
                            </Label>
                            <Input
                              id="owner-first-name"
                              value={firstName}
                              onChange={(e) => setFirstName(e.target.value)}
                              placeholder="Elena"
                              required
                            />
                          </div>
                          <div className="space-y-1.5">
                            <Label htmlFor="owner-last-name" className="text-xs font-semibold">
                              Last Name
                            </Label>
                            <Input
                              id="owner-last-name"
                              value={lastName}
                              onChange={(e) => setLastName(e.target.value)}
                              placeholder="Rostova"
                              required
                            />
                          </div>
                        </div>

                        {/* Email */}
                        <div className="space-y-1.5">
                          <Label htmlFor="owner-email" className="text-xs font-semibold">
                            Work Email (Login ID)
                          </Label>
                          <div className="relative">
                            <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                            <Input
                              id="owner-email"
                              type="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                              placeholder="elena@apexhealth.com"
                              className="pl-9"
                              required
                            />
                          </div>
                        </div>

                        {/* Password */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <Label htmlFor="owner-password" className="text-xs font-semibold">
                              Password
                            </Label>
                            <div className="relative">
                              <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                              <Input
                                id="owner-password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Min 6 characters"
                                className="pl-9"
                                required
                              />
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            <Label htmlFor="owner-confirm-password" className="text-xs font-semibold">
                              Confirm Password
                            </Label>
                            <div className="relative">
                              <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                              <Input
                                id="owner-confirm-password"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Repeat password"
                                className="pl-9"
                                required
                              />
                            </div>
                          </div>
                        </div>

                        {/* Summary Pill */}
                        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 space-y-2 text-xs">
                          <div className="flex justify-between items-center text-muted-foreground">
                            <span>Selected Plan:</span>
                            <span className="font-semibold text-foreground uppercase">{selectedPlan} (${billingCycle === "annual" ? PLANS.find(p=>p.id===selectedPlan)?.annualPrice : PLANS.find(p=>p.id===selectedPlan)?.monthlyPrice}/mo)</span>
                          </div>
                          <div className="flex justify-between items-center text-muted-foreground">
                            <span>Workspace URL:</span>
                            <span className="font-mono font-medium text-primary">https://{subdomain}.bookme.app</span>
                          </div>
                          <div className="flex justify-between items-center text-muted-foreground">
                            <span>Free Trial:</span>
                            <span className="font-semibold text-emerald-600 dark:text-emerald-400">14 Days Free (No credit card required)</span>
                          </div>
                        </div>

                        {/* Terms checkbox */}
                        <div className="flex items-start gap-2 pt-2">
                          <input
                            type="checkbox"
                            id="terms"
                            checked={agreedTerms}
                            onChange={(e) => setAgreedTerms(e.target.checked)}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary mt-0.5 cursor-pointer"
                          />
                          <Label htmlFor="terms" className="text-xs text-muted-foreground leading-tight cursor-pointer">
                            I agree to the Terms of Service, Privacy Policy, and Acceptable Use Safeguards.
                          </Label>
                        </div>
                      </CardContent>

                      <CardFooter className="flex justify-between pt-2 pb-6">
                        <Button type="button" variant="ghost" onClick={() => setCurrentStep(2)}>
                          <ArrowLeft className="h-4 w-4 mr-1.5" />
                          Back
                        </Button>
                        <Button
                          type="submit"
                          className="h-11 px-6 font-semibold bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90 text-primary-foreground shadow-lg shadow-primary/20"
                          disabled={isSubmitting}
                        >
                          {isSubmitting ? (
                            <>
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              {submissionStage || "Provisioning Workspace..."}
                            </>
                          ) : (
                            <>
                              Launch Workspace & Start Trial
                              <Sparkles className="h-4 w-4 ml-2" />
                            </>
                          )}
                        </Button>
                      </CardFooter>
                    </form>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 py-8 text-center text-xs text-muted-foreground">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} BookMe Autonomous Operations. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link to="/directory" className="hover:text-foreground transition-colors">
              Directory
            </Link>
            <Link to="/login" className="hover:text-foreground transition-colors">
              Sign In
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
