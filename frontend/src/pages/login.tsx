import { type FormEvent, useEffect, useState, useCallback } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { ShieldCheck, MessageSquare, ChevronDown, ChevronUp, KeyRound, Loader2 } from "lucide-react"

import {
  apiClient,
  getActiveTenantFromHost,
  getAdminAccessToken,
  safePostLoginReturnPath,
  setAdminAccessToken,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type AdminAuthResponse = {
  ok: boolean
  data?: {
    access_token?: string
    chatwoot_sso_url?: string | null
    user?: {
      id: number
      login: string
      email?: string
      role: string
      first_name?: string
      last_name?: string
      avatar_url?: string
    }
  }
}

type PublicAuthConfig = {
  google_client_id: string
  google_sso_enabled: boolean
  chatwoot_enabled: boolean
}

function requestedAdminPath(state: unknown): unknown {
  if (!state || typeof state !== "object" || !("from" in state)) {
    return undefined
  }

  const from = state.from
  if (!from || typeof from !== "object" || !("pathname" in from)) {
    return undefined
  }

  return from.pathname
}

function GoogleIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
      />
    </svg>
  )
}

export default function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const detectedTenant = getActiveTenantFromHost()
  const tenant = detectedTenant || (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname.includes('trycloudflare.com')) ? 'simplydemo' : null)
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [authConfig, setAuthConfig] = useState<PublicAuthConfig | null>(null)
  const [showTokenTester, setShowTokenTester] = useState(false)
  const [manualToken, setManualToken] = useState("")
  const [isGoogleSubmitting, setIsGoogleSubmitting] = useState(false)
  const returnPath = safePostLoginReturnPath(requestedAdminPath(location.state))

  const handleAuthSuccess = useCallback((data?: AdminAuthResponse["data"]) => {
    if (!data?.access_token) {
      throw new Error("Missing access token in authentication response")
    }
    setAdminAccessToken(data.access_token)
    if (data.chatwoot_sso_url) {
      localStorage.setItem("chatwoot_sso_url", data.chatwoot_sso_url)
    }
    navigate(returnPath, { replace: true })
  }, [navigate, returnPath])

  const handleGoogleLogin = useCallback(async (idToken: string) => {
    if (!tenant) return
    setError(null)
    setIsGoogleSubmitting(true)
    try {
      const response = await apiClient.post<AdminAuthResponse>("/api/admin/auth/google", {
        id_token: idToken.trim(),
        company: tenant,
      })
      if (!response.ok || !response.data?.access_token) {
        throw new Error("Google authentication rejected by server")
      }
      handleAuthSuccess(response.data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Google authentication failed. Please check credentials."
      setError(msg)
    } finally {
      setIsGoogleSubmitting(false)
    }
  }, [tenant, handleAuthSuccess])

  // Load public auth configuration from server
  useEffect(() => {
    let isMounted = true
    apiClient
      .get<{ ok: boolean; data: PublicAuthConfig }>("/api/public/auth/config")
      .then((res) => {
        if (isMounted && res?.ok && res.data) {
          const effectiveClientId = res.data.google_client_id || (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) || ""
          setAuthConfig({ ...res.data, google_client_id: effectiveClientId })
          if (effectiveClientId) {
            // Dynamically load Google Identity Services if client ID is configured
            if (!document.getElementById("google-gsi-client")) {
              const script = document.createElement("script")
              script.id = "google-gsi-client"
              script.src = "https://accounts.google.com/gsi/client"
              script.async = true
              script.defer = true
              script.onload = () => {
                // @ts-expect-error Google GSI global
                if (window.google?.accounts?.id) {
                  // @ts-expect-error Google GSI global
                  window.google.accounts.id.initialize({
                    client_id: effectiveClientId,
                    callback: (response: { credential?: string }) => {
                      if (response?.credential) {
                        handleGoogleLogin(response.credential)
                      }
                    },
                  })
                  const btnEl = document.getElementById("google-official-btn")
                  if (btnEl) {
                    // @ts-expect-error Google GSI global
                    window.google.accounts.id.renderButton(btnEl, {
                      theme: "outline",
                      size: "large",
                      width: "100%",
                      text: "signin_with",
                    })
                  }
                }
              }
              document.body.appendChild(script)
            }
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setAuthConfig({ google_client_id: "", google_sso_enabled: true, chatwoot_enabled: true })
        }
      })
    return () => {
      isMounted = false
    }
  }, [handleGoogleLogin])

  if (getAdminAccessToken()) {
    return <Navigate to={returnPath} replace />
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!tenant || isSubmitting) {
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      const response = await apiClient.post<AdminAuthResponse>("/api/admin/auth", {
        company: tenant,
        login: login.trim(),
        password,
      })

      if (!response.ok || !response.data?.access_token) {
        throw new Error("Invalid authentication response")
      }

      handleAuthSuccess(response.data)
    } catch {
      setError("Unable to sign in. Check your credentials and try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoogleButtonClick = () => {
    // @ts-expect-error Google GSI global
    if (authConfig?.google_client_id && window.google?.accounts?.id) {
      // @ts-expect-error Google GSI global
      window.google.accounts.id.prompt()
    } else {
      // Toggle developer / token verification drawer
      setShowTokenTester((prev) => !prev)
    }
  }

  return (
    <main className="grid min-h-svh place-items-center bg-muted/30 p-6">
      <Card className="w-full max-w-md shadow-md border-border">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <CardTitle className="text-xl">Sign in to your workspace</CardTitle>
          <CardDescription>
            {tenant
              ? `Signing in to ${tenant}.`
              : "Use your company’s tenant-specific address to sign in."}
          </CardDescription>
          {authConfig?.chatwoot_enabled && (
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <MessageSquare className="h-3 w-3" />
              <span>Chatwoot Enterprise SSO Ready</span>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Google SSO Action Button */}
          {authConfig?.google_sso_enabled !== false && (
            <div className="space-y-3">
              <div id="google-official-btn" className="w-full min-h-[40px] flex items-center justify-center">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full flex items-center justify-center gap-2 border-input hover:bg-muted font-normal h-10"
                  onClick={handleGoogleButtonClick}
                  disabled={!tenant || isGoogleSubmitting}
                >
                  {isGoogleSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  ) : (
                    <GoogleIcon className="h-4 w-4" />
                  )}
                  <span>Sign in with Google</span>
                </Button>
              </div>

              {/* Developer / SSO Token Tester Drawer */}
              {showTokenTester && (
                <div className="rounded-lg border border-border bg-muted/50 p-3 text-xs space-y-2">
                  <div className="flex items-center justify-between text-muted-foreground font-medium">
                    <span className="flex items-center gap-1">
                      <KeyRound className="h-3.5 w-3.5" />
                      Google OIDC ID Token Verification
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowTokenTester(false)}
                      className="hover:text-foreground"
                    >
                      <ChevronUp className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <p className="text-muted-foreground">
                    {!authConfig?.google_client_id ? (
                      <>
                        <code className="text-foreground">GOOGLE_CLIENT_ID</code> is not configured in <code className="text-foreground">.env</code>. You can paste a Google OAuth ID token directly to test the backend SSO pipeline:
                      </>
                    ) : (
                      "Paste a valid Google ID token to test backend authentication directly:"
                    )}
                  </p>
                  <Input
                    placeholder="eyJhbGciOiJSUzI1NiIs..."
                    value={manualToken}
                    onChange={(e) => setManualToken(e.target.value)}
                    className="font-mono text-[11px] h-8"
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="w-full h-8 text-xs"
                    disabled={!manualToken.trim() || isGoogleSubmitting}
                    onClick={() => handleGoogleLogin(manualToken)}
                  >
                    {isGoogleSubmitting ? "Verifying..." : "Authenticate via /api/admin/auth/google"}
                  </Button>
                </div>
              )}

              <div className="relative my-2">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">Or sign in with username</span>
                </div>
              </div>
            </div>
          )}

          {/* Username / Password Form */}
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="login">Username or Email</Label>
              <Input
                id="login"
                name="login"
                autoComplete="username"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                disabled={!tenant || isSubmitting}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={!tenant || isSubmitting}
                required
              />
            </div>
            {error && (
              <p className="text-sm text-destructive font-medium" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={!tenant || isSubmitting}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          {/* Quick SSO status info footer */}
          <div className="pt-2 text-center text-xs text-muted-foreground">
            <button
              type="button"
              onClick={() => setShowTokenTester((prev) => !prev)}
              className="inline-flex items-center gap-1 hover:underline text-muted-foreground/80"
            >
              <span>Single Sign-On (SSO) & Developer Tools</span>
              {showTokenTester ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

