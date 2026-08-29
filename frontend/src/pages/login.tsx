import * as React from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { AlertCircleIcon, BookOpenCheckIcon, BuildingIcon, Loader2Icon, LockIcon, UserIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError, getActiveTenant, getAdminToken, loginAdmin } from "@/lib/api"

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const [company, setCompany] = React.useState(() => getActiveTenant())
  const [login, setLogin] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [rememberMe, setRememberMe] = React.useState(true)
  const [isLoading, setIsLoading] = React.useState(false)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)

  // Redirect to admin if already authenticated
  React.useEffect(() => {
    if (getAdminToken()) {
      navigate("/admin", { replace: true })
    }
  }, [navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!login.trim()) {
      setErrorMessage("Please enter your username or email address.")
      return
    }

    if (!password) {
      setErrorMessage("Please enter your password.")
      return
    }

    setIsLoading(true)

    try {
      await loginAdmin(
        {
          company: company.trim() || getActiveTenant(),
          login: login.trim(),
          password,
        },
        rememberMe
      )

      // Redirect back to intended target or /admin
      const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/admin"
      navigate(from, { replace: true })
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrorMessage("Incorrect credentials. Please verify your username and password.")
        } else if (err.status === 404) {
          setErrorMessage(`Tenant '${company}' was not found.`)
        } else {
          setErrorMessage(err.message || "Failed to authenticate. Please try again.")
        }
      } else if (err instanceof Error) {
        setErrorMessage(err.message)
      } else {
        setErrorMessage("An unexpected authentication error occurred.")
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-muted/40 p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
            <BookOpenCheckIcon className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">FastAPI Bookings</h1>
          <p className="text-sm text-muted-foreground">Sign in to access the administrative control centre</p>
        </div>

        <Card className="shadow-lg border-border/80">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl">Admin Authentication</CardTitle>
            <CardDescription>Enter your credentials to manage services, appointments, and settings</CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              {errorMessage && (
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                >
                  <AlertCircleIcon className="h-4 w-4 shrink-0 mt-0.5" />
                  <div className="flex-1 leading-tight">{errorMessage}</div>
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="tenant-company" className="flex items-center gap-1.5 text-xs font-medium">
                  <BuildingIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  Tenant Subdomain / Company
                </Label>
                <Input
                  id="tenant-company"
                  type="text"
                  placeholder="e.g. simplydemo"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  disabled={isLoading}
                  autoComplete="organization"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="admin-login" className="flex items-center gap-1.5 text-xs font-medium">
                  <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  Username or Login
                </Label>
                <Input
                  id="admin-login"
                  type="text"
                  placeholder="admin"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  disabled={isLoading}
                  required
                  autoFocus
                  autoComplete="username"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="admin-password" className="flex items-center gap-1.5 text-xs font-medium">
                  <LockIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  Password
                </Label>
                <Input
                  id="admin-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  required
                  autoComplete="current-password"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <Checkbox
                  id="remember-me"
                  checked={rememberMe}
                  onCheckedChange={(checked) => setRememberMe(checked === true)}
                  disabled={isLoading}
                />
                <Label htmlFor="remember-me" className="text-xs font-normal text-muted-foreground cursor-pointer">
                  Remember this device for 7 days
                </Label>
              </div>
            </CardContent>

            <CardFooter className="pt-2 pb-5 flex flex-col gap-3">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2Icon className="h-4 w-4 animate-spin mr-2" />
                    Signing in...
                  </>
                ) : (
                  "Sign In"
                )}
              </Button>
              <div className="text-center text-xs text-muted-foreground">
                Protected by tenant isolation &amp; role-based access controls
              </div>
            </CardFooter>
          </form>
        </Card>
      </div>
    </main>
  )
}

export default LoginPage
