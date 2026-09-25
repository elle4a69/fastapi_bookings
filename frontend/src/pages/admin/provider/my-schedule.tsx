import { useEffect, useState, useCallback } from "react"
import {
  CalendarDays,
  Clock,
  MapPin,
  Phone,
  MessageSquare,
  Play,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Sparkles,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface BookingItem {
  id: number
  start_time: string | null
  end_time: string | null
  status: string
  service: {
    id: number
    name: string
    duration: number
    price: number
  } | null
  client: {
    id: number
    name: string
    phone: string
    email: string
    address: string | null
  } | null
  location: {
    id: number
    name: string
    address: string | null
  } | null
}

export default function MySchedulePage() {
  const { user } = useAuth()
  const [selectedDate, setSelectedDate] = useState<Date>(new Date())
  const [bookings, setBookings] = useState<BookingItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchBookings = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<{ ok: boolean; data: BookingItem[] }>("/api/admin/provider/me/bookings")
      if (res?.ok && Array.isArray(res.data)) {
        setBookings(res.data)
      }
    } catch {
      setError("Failed to load schedule. Please check your connection and try again.")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchBookings()
  }, [fetchBookings])

  const handleStartJob = async (bookingId: number) => {
    setActionLoadingId(bookingId)
    try {
      const res = await apiClient.post<{ ok: boolean; data: BookingItem }>(`/api/admin/bookings/${bookingId}/start`)
      if (res?.ok) {
        setBookings((prev) =>
          prev.map((b) => (b.id === bookingId ? { ...b, status: "in_progress" } : b))
        )
      }
    } catch {
      alert("Could not transition job to in-progress.")
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleCompleteJob = async (bookingId: number) => {
    setActionLoadingId(bookingId)
    try {
      const res = await apiClient.post<{ ok: boolean; data: BookingItem }>(`/api/admin/bookings/${bookingId}/complete`)
      if (res?.ok) {
        setBookings((prev) =>
          prev.map((b) => (b.id === bookingId ? { ...b, status: "completed" } : b))
        )
      }
    } catch {
      alert("Could not complete booking.")
    } finally {
      setActionLoadingId(null)
    }
  }

  // Filter bookings for the selected calendar day
  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()

  const dayBookings = bookings.filter((b) => {
    if (!b.start_time) return false
    const date = new Date(b.start_time)
    return isSameDay(date, selectedDate)
  })

  // Date shifting helpers
  const shiftDay = (delta: number) => {
    setSelectedDate((prev) => {
      const next = new Date(prev)
      next.setDate(next.getDate() + delta)
      return next
    })
  }

  const setToday = () => setSelectedDate(new Date())

  const formattedDate = selectedDate.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  })

  const isCurrentDay = isSameDay(selectedDate, new Date())

  // Status badge styling
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "in_progress":
        return (
          <Badge className="bg-amber-500 text-white animate-pulse">
            In Progress
          </Badge>
        )
      case "completed":
        return (
          <Badge className="bg-emerald-600 text-white">
            Completed
          </Badge>
        )
      case "confirmed":
        return (
          <Badge variant="outline" className="border-primary/40 text-primary">
            Confirmed
          </Badge>
        )
      case "cancelled":
        return (
          <Badge variant="destructive">
            Cancelled
          </Badge>
        )
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  // Header metric counts
  const totalToday = dayBookings.length
  const inProgressCount = dayBookings.filter((b) => b.status === "in_progress").length
  const completedCount = dayBookings.filter((b) => b.status === "completed").length

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      {/* Top Welcome Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Technician Schedule
            </h1>
            <Sparkles className="h-5 w-5 text-primary" />
          </div>
          <p className="text-sm text-muted-foreground">
            Welcome back, {user?.login || "Provider"}. Here is your dispatch agenda.
          </p>
        </div>

        {/* Date Selector Navigation */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          <Button variant="outline" size="sm" onClick={() => shiftDay(-1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant={isCurrentDay ? "default" : "outline"}
            size="sm"
            onClick={setToday}
            className="font-medium"
          >
            Today
          </Button>
          <Button variant="outline" size="sm" onClick={() => shiftDay(1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Date banner & stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="p-4 pb-1">
            <CardDescription className="text-xs uppercase tracking-wider font-semibold text-primary">Selected Day</CardDescription>
            <CardTitle className="text-base font-bold flex items-center gap-1.5">
              <CalendarDays className="h-4 w-4 text-primary" />
              {formattedDate}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <span className="text-xs text-muted-foreground">{totalToday} job(s) assigned</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-4 pb-1">
            <CardDescription className="text-xs uppercase tracking-wider font-semibold">Active Jobs</CardDescription>
            <CardTitle className="text-2xl font-bold text-amber-600">{inProgressCount}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <span className="text-xs text-muted-foreground">Currently in progress</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-4 pb-1">
            <CardDescription className="text-xs uppercase tracking-wider font-semibold">Done Today</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-600">{completedCount}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <span className="text-xs text-muted-foreground">Successfully completed</span>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Agenda Bookings List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="flex h-48 w-full items-center justify-center text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>Loading your schedule...</span>
            </div>
          </div>
        ) : dayBookings.length === 0 ? (
          <Card className="border-dashed p-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <CalendarDays className="h-6 w-6" />
            </div>
            <h3 className="mt-4 text-base font-semibold">No jobs scheduled for {formattedDate}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Enjoy your time off or check adjacent dates for upcoming appointments.
            </p>
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="outline" size="sm" onClick={() => shiftDay(1)}>
                View Tomorrow
              </Button>
            </div>
          </Card>
        ) : (
          dayBookings.map((booking) => {
            const startTimeStr = booking.start_time
              ? new Date(booking.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "--:--"
            const endTimeStr = booking.end_time
              ? new Date(booking.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "--:--"

            const isActionLoading = actionLoadingId === booking.id

            return (
              <Card
                key={booking.id}
                className={`overflow-hidden transition-all duration-200 ${
                  booking.status === "in_progress"
                    ? "border-amber-500/60 shadow-md ring-1 ring-amber-500/20"
                    : booking.status === "completed"
                    ? "border-emerald-500/40 opacity-90"
                    : "border-border/80 hover:border-primary/40 hover:shadow-xs"
                }`}
              >
                <div className="p-5 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  {/* Left Column: Time & Job Details */}
                  <div className="space-y-3 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="flex items-center gap-1.5 font-bold text-sm bg-muted px-2.5 py-1 rounded-md text-foreground">
                        <Clock className="h-3.5 w-3.5 text-primary" />
                        {startTimeStr} - {endTimeStr}
                      </span>
                      {renderStatusBadge(booking.status)}
                    </div>

                    <div>
                      <h4 className="font-semibold text-lg text-foreground truncate">
                        {booking.service?.name || "General Service"}
                      </h4>
                      <p className="text-xs text-muted-foreground">
                        Duration: {booking.service?.duration || 60} mins
                        {booking.service?.price ? ` • $${booking.service.price}` : ""}
                      </p>
                    </div>

                    {/* Customer Info */}
                    <div className="bg-muted/40 rounded-lg p-3 space-y-1.5 border border-border/40">
                      <p className="text-sm font-medium text-foreground flex items-center justify-between">
                        <span>Customer: {booking.client?.name || "Anonymous Client"}</span>
                      </p>

                      {booking.client?.phone && (
                        <div className="flex items-center gap-3 pt-1">
                          <a
                            href={`tel:${booking.client.phone}`}
                            className="inline-flex items-center gap-1.5 text-xs text-primary font-medium hover:underline"
                          >
                            <Phone className="h-3 w-3" />
                            {booking.client.phone}
                          </a>
                          <a
                            href={`sms:${booking.client.phone}`}
                            className="inline-flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 font-medium hover:underline"
                          >
                            <MessageSquare className="h-3 w-3" />
                            Send SMS
                          </a>
                        </div>
                      )}

                      {(booking.location?.address || booking.client?.address) && (
                        <div className="flex items-start gap-1.5 text-xs text-muted-foreground pt-1">
                          <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70 mt-0.5" />
                          <span className="truncate">
                            {booking.location?.address || booking.client?.address}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Column: Mobile-Friendly Actions */}
                  <div className="flex flex-row sm:flex-col items-center sm:items-end justify-end gap-2 shrink-0 border-t sm:border-t-0 pt-3 sm:pt-0">
                    {booking.status !== "completed" && booking.status !== "cancelled" && (
                      <>
                        {booking.status !== "in_progress" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-amber-500/40 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30 flex items-center gap-1.5 w-full sm:w-auto"
                            disabled={isActionLoading}
                            onClick={() => handleStartJob(booking.id)}
                          >
                            <Play className="h-3.5 w-3.5 fill-current" />
                            Mark In Progress
                          </Button>
                        )}
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white flex items-center gap-1.5 w-full sm:w-auto"
                          disabled={isActionLoading}
                          onClick={() => handleCompleteJob(booking.id)}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Complete Job
                        </Button>
                      </>
                    )}

                    {booking.status === "completed" && (
                      <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="h-4 w-4" />
                        Completed
                      </span>
                    )}
                  </div>
                </div>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}
