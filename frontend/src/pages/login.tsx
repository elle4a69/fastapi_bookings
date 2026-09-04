import { type FormEvent, useState } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"

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
  }
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

export default function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const tenant = getActiveTenantFromHost()
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const returnPath = safePostLoginReturnPath(requestedAdminPath(location.state))

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
      const accessToken = response.data?.access_token

      if (!response.ok || typeof accessToken !== "string" || !accessToken.trim()) {
        throw new Error("Invalid authentication response")
      }

      setAdminAccessToken(accessToken)
      navigate(returnPath, { replace: true })
    } catch {
      setError("Unable to sign in. Check your credentials and try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-svh place-items-center bg-muted/30 p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign in to your admin workspace</CardTitle>
          <CardDescription>
            {tenant
              ? `Signing in to ${tenant}.`
              : "Use your company’s tenant-specific address to sign in."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="login">Username</Label>
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
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={!tenant || isSubmitting}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
