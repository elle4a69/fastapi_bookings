import { useEffect, useState, useCallback } from "react"
import {
  ClipboardList,
  Clock,
  MapPin,
  Phone,
  MessageSquare,
  Play,
  CheckCircle2,
  AlertCircle,
  Filter,
} from "lucide-react"
import { apiClient } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

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

export default function MyJobsPage() {
  const [bookings, setBookings] = useState<BookingItem[]>([])
  const [filterTab, setFilterTab] = useState<string>("all")
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
      setError("Failed to load jobs list. Please refresh the page.")
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
      alert("Could not start job.")
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
      alert("Could not complete job.")
    } finally {
      setActionLoadingId(null)
    }
  }

  const filteredBookings = bookings.filter((b) => {
    if (filterTab === "all") return true
    if (filterTab === "active") return b.status === "confirmed" || b.status === "in_progress"
    if (filterTab === "in_progress") return b.status === "in_progress"
    if (filterTab === "completed") return b.status === "completed"
    return true
  })

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "in_progress":
        return <Badge className="bg-amber-500 text-white">In Progress</Badge>
      case "completed":
        return <Badge className="bg-emerald-600 text-white">Completed</Badge>
      case "confirmed":
        return <Badge variant="outline" className="border-primary/40 text-primary">Confirmed</Badge>
      case "cancelled":
        return <Badge variant="destructive">Cancelled</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-primary" />
            My Bookings & Jobs
          </h1>
          <p className="text-sm text-muted-foreground">
            View all assignments and update technician job statuses.
          </p>
        </div>

        <Tabs value={filterTab} onValueChange={setFilterTab}>
          <TabsList>
            <TabsTrigger value="all">All ({bookings.length})</TabsTrigger>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="in_progress">In Progress</TabsTrigger>
            <TabsTrigger value="completed">Completed</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex h-48 w-full items-center justify-center text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <span>Loading jobs...</span>
          </div>
        </div>
      ) : filteredBookings.length === 0 ? (
        <Card className="border-dashed p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Filter className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-base font-semibold">No jobs match this filter</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Select a different filter or check back later.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredBookings.map((booking) => {
            const dateStr = booking.start_time
              ? new Date(booking.start_time).toLocaleDateString([], { month: "short", day: "numeric", weekday: "short" })
              : ""
            const timeStr = booking.start_time
              ? new Date(booking.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "--:--"
            const isActionLoading = actionLoadingId === booking.id

            return (
              <Card key={booking.id} className="p-5 border hover:border-primary/40 transition-all">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="flex items-center gap-1.5 font-bold text-sm bg-muted px-2.5 py-1 rounded-md text-foreground">
                        <Clock className="h-3.5 w-3.5 text-primary" />
                        {dateStr} • {timeStr}
                      </span>
                      {renderStatusBadge(booking.status)}
                    </div>

                    <h4 className="font-semibold text-lg text-foreground truncate">
                      {booking.service?.name || "Service Appointment"}
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      Client: {booking.client?.name || "Anonymous Client"} • Duration: {booking.service?.duration || 60} mins
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
                          SMS
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

                  <div className="flex sm:flex-col items-center sm:items-end justify-end gap-2 shrink-0 border-t sm:border-t-0 pt-3 sm:pt-0">
                    {booking.status !== "completed" && booking.status !== "cancelled" && (
                      <>
                        {booking.status !== "in_progress" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-amber-500/40 text-amber-700 dark:text-amber-400"
                            disabled={isActionLoading}
                            onClick={() => handleStartJob(booking.id)}
                          >
                            <Play className="h-3.5 w-3.5 mr-1" />
                            Start
                          </Button>
                        )}
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white"
                          disabled={isActionLoading}
                          onClick={() => handleCompleteJob(booking.id)}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                          Complete
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
