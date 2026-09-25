import { useEffect, useState, useCallback } from "react"
import {
  UserRound,
  Mail,
  Phone,
  Clock,
  Briefcase,
  Save,
  CheckCircle2,
  AlertCircle,
  CalendarCheck,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface ProviderData {
  id: number
  name: string
  email: string | null
  phone: string | null
  color: string | null
  description: string | null
  image: string | null
  in_call_address: string | null
  out_call_radius_km: number
  turnaround_buffer_mins: number
  weekly_schedule: Record<string, any> | null
}

interface AssignedService {
  id: number
  name: string
  duration: number
  price: number
  description: string | null
}

interface WorkDay {
  id?: number
  weekday: number
  start_time: string
  end_time: string
  is_working: boolean
}

const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
]

const DEFAULT_DAYS: WorkDay[] = [
  { weekday: 0, start_time: "09:00", end_time: "17:00", is_working: true },
  { weekday: 1, start_time: "09:00", end_time: "17:00", is_working: true },
  { weekday: 2, start_time: "09:00", end_time: "17:00", is_working: true },
  { weekday: 3, start_time: "09:00", end_time: "17:00", is_working: true },
  { weekday: 4, start_time: "09:00", end_time: "17:00", is_working: true },
  { weekday: 5, start_time: "09:00", end_time: "14:00", is_working: false },
  { weekday: 6, start_time: "09:00", end_time: "14:00", is_working: false },
]

export default function MyProfilePage() {
  const [provider, setProvider] = useState<ProviderData | null>(null)
  const [services, setServices] = useState<AssignedService[]>([])
  const [workdays, setWorkdays] = useState<WorkDay[]>(DEFAULT_DAYS)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<{
        ok: boolean
        data: {
          provider: ProviderData
          services: AssignedService[]
          work_days: WorkDay[]
        }
      }>("/api/admin/provider/me")

      if (res?.ok && res.data) {
        setProvider(res.data.provider)
        setServices(res.data.services || [])

        if (Array.isArray(res.data.work_days) && res.data.work_days.length > 0) {
          const merged = DEFAULT_DAYS.map((defDay) => {
            const found = res.data.work_days.find((w) => w.weekday === defDay.weekday)
            return found
              ? {
                  weekday: defDay.weekday,
                  start_time: found.start_time || "09:00",
                  end_time: found.end_time || "17:00",
                  is_working: found.is_working,
                }
              : defDay
          })
          setWorkdays(merged)
        }
      }
    } catch {
      setError("Failed to load provider profile.")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const handleDayToggle = (weekday: number, checked: boolean) => {
    setWorkdays((prev) =>
      prev.map((d) => (d.weekday === weekday ? { ...d, is_working: checked } : d))
    )
  }

  const handleTimeChange = (weekday: number, field: "start_time" | "end_time", value: string) => {
    setWorkdays((prev) =>
      prev.map((d) => (d.weekday === weekday ? { ...d, [field]: value } : d))
    )
  }

  const handleSaveSchedule = async () => {
    setIsSaving(true)
    setSuccessMessage(null)
    setError(null)

    try {
      const weekly_schedule: Record<string, any> = {}
      const dayKeys = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

      workdays.forEach((wd) => {
        const key = dayKeys[wd.weekday]
        weekly_schedule[key] = {
          is_working: wd.is_working,
          start_time: wd.start_time,
          end_time: wd.end_time,
          recurring: true,
        }
      })

      const res = await apiClient.put<{ ok: boolean }>("/api/admin/provider/me/schedule", {
        weekly_schedule,
        workdays,
      })

      if (res?.ok) {
        setSuccessMessage("Working schedule updated successfully!")
        setTimeout(() => setSuccessMessage(null), 4000)
      }
    } catch {
      setError("Failed to save schedule changes. Please try again.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl flex items-center gap-2">
          <UserRound className="h-6 w-6 text-primary" />
          Technician Profile & Working Hours
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage your personal working availability and view your assigned service capabilities.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {successMessage && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          {successMessage}
        </div>
      )}

      {/* Provider Details Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <UserRound className="h-5 w-5 text-primary" />
            Profile Details
          </CardTitle>
          <CardDescription>
            Account details linked to your service provider profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Full Name</Label>
            <p className="font-semibold text-foreground text-base">
              {provider?.name || "Technician"}
            </p>
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Email</Label>
            <p className="text-sm text-foreground flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-muted-foreground" />
              {provider?.email || "No email on file"}
            </p>
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Phone</Label>
            <p className="text-sm text-foreground flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-muted-foreground" />
              {provider?.phone || "No phone on file"}
            </p>
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Turnaround Buffer</Label>
            <p className="text-sm text-foreground flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              {provider?.turnaround_buffer_mins ?? 15} minutes between appointments
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Assigned Services Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            Assigned Services
          </CardTitle>
          <CardDescription>
            Services you are eligible and scheduled to deliver.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {services.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No specific services assigned yet. Contact your clinic manager.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {services.map((svc) => (
                <div
                  key={svc.id}
                  className="rounded-lg border bg-muted/40 px-3 py-2 text-sm flex items-center gap-2"
                >
                  <span className="font-medium">{svc.name}</span>
                  <Badge variant="outline" className="text-xs">
                    {svc.duration}m
                  </Badge>
                  {svc.price ? (
                    <span className="text-xs text-muted-foreground">${svc.price}</span>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Weekly Working Schedule Card */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <CalendarCheck className="h-5 w-5 text-primary" />
              Weekly Working Hours
            </CardTitle>
            <CardDescription>
              Toggle which days you work and customize your standard shift times.
            </CardDescription>
          </div>
          <Button
            onClick={handleSaveSchedule}
            disabled={isSaving || isLoading}
            className="flex items-center gap-1.5 self-start sm:self-auto"
          >
            <Save className="h-4 w-4" />
            {isSaving ? "Saving..." : "Save Schedule"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="divide-y divide-border/60">
            {workdays.map((wd) => (
              <div
                key={wd.weekday}
                className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="flex items-center gap-3 w-40">
                  <Switch
                    checked={wd.is_working}
                    onCheckedChange={(checked) => handleDayToggle(wd.weekday, checked)}
                    id={`day-switch-${wd.weekday}`}
                  />
                  <Label
                    htmlFor={`day-switch-${wd.weekday}`}
                    className={`font-semibold cursor-pointer ${
                      wd.is_working ? "text-foreground" : "text-muted-foreground"
                    }`}
                  >
                    {WEEKDAY_NAMES[wd.weekday]}
                  </Label>
                </div>

                {wd.is_working ? (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5">
                      <Label className="text-xs text-muted-foreground">From</Label>
                      <Input
                        type="time"
                        value={wd.start_time}
                        onChange={(e) =>
                          handleTimeChange(wd.weekday, "start_time", e.target.value)
                        }
                        className="w-28 h-9 text-xs"
                      />
                    </div>
                    <span className="text-muted-foreground text-xs">to</span>
                    <div className="flex items-center gap-1.5">
                      <Label className="text-xs text-muted-foreground">To</Label>
                      <Input
                        type="time"
                        value={wd.end_time}
                        onChange={(e) =>
                          handleTimeChange(wd.weekday, "end_time", e.target.value)
                        }
                        className="w-28 h-9 text-xs"
                      />
                    </div>
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground italic">Off Duty / Unavailable</span>
                )}
              </div>
            ))}
          </div>

          <div className="pt-3 flex justify-end">
            <Button
              onClick={handleSaveSchedule}
              disabled={isSaving || isLoading}
              className="flex items-center gap-1.5"
            >
              <Save className="h-4 w-4" />
              {isSaving ? "Saving..." : "Save Working Hours"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
