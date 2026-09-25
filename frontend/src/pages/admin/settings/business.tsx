import { useEffect, useState } from "react"
import { apiClient } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { MobilePageShell } from "@/components/ui/mobile-page-shell"
import { Save } from "lucide-react"
import { toast } from "sonner"

interface BusinessProfile {
  name: string
  email: string
  phone: string
  address: string
  openingHours: {
    day: string
    isOpen: boolean
    openTime: string
    closeTime: string
  }[]
}

const DEFAULT_HOURS = [
  { day: "Monday", isOpen: true, openTime: "09:00", closeTime: "17:00" },
  { day: "Tuesday", isOpen: true, openTime: "09:00", closeTime: "17:00" },
  { day: "Wednesday", isOpen: true, openTime: "09:00", closeTime: "17:00" },
  { day: "Thursday", isOpen: true, openTime: "09:00", closeTime: "17:00" },
  { day: "Friday", isOpen: true, openTime: "09:00", closeTime: "17:00" },
  { day: "Saturday", isOpen: false, openTime: "10:00", closeTime: "14:00" },
  { day: "Sunday", isOpen: false, openTime: "00:00", closeTime: "00:00" },
]

export default function BusinessSettings() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      const data = await apiClient.get<any>("/api/admin/business-profile")
      setProfile({
        name: data.name || "",
        email: data.email || "",
        phone: data.phone || "",
        address: data.address || "",
        openingHours: data.openingHours || DEFAULT_HOURS,
      })
    } catch {
      toast.error("Failed to load business profile")
      setProfile({
        name: "",
        email: "",
        phone: "",
        address: "",
        openingHours: DEFAULT_HOURS,
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!profile) return
    setSaving(true)
    try {
      await apiClient.put("/api/admin/business-profile", profile)
      toast.success("Business profile saved successfully")
    } catch {
      toast.error("Failed to save profile")
    } finally {
      setSaving(false)
    }
  }

  const updateField = (field: keyof BusinessProfile, value: string) => {
    if (profile) setProfile({ ...profile, [field]: value })
  }

  const updateHours = (index: number, updates: Partial<BusinessProfile["openingHours"][0]>) => {
    if (!profile) return
    const newHours = [...profile.openingHours]
    newHours[index] = { ...newHours[index], ...updates }
    setProfile({ ...profile, openingHours: newHours })
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!profile) return null

  return (
    <MobilePageShell
      title="Business Profile"
      description="Manage business contact details, location info, and operational hours"
      actions={
        <Button 
          onClick={handleSave} 
          disabled={saving}
          className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-2"
        >
          <Save className="h-4 w-4" />
          <span>{saving ? "Saving..." : "Save Changes"}</span>
        </Button>
      }
    >
      <div className="space-y-6">
        <Card className="shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base sm:text-lg">Contact Details</CardTitle>
            <CardDescription className="text-xs">
              Primary details shown on your public booking portal and client emails
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Business Name</Label>
              <Input 
                id="name" 
                value={profile.name} 
                onChange={(e) => updateField("name", e.target.value)} 
                className="h-11 min-h-[44px]"
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Email Address</Label>
                <Input 
                  id="email" 
                  type="email" 
                  value={profile.email} 
                  onChange={(e) => updateField("email", e.target.value)} 
                  className="h-11 min-h-[44px]"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="phone" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Phone Number</Label>
                <Input 
                  id="phone" 
                  value={profile.phone} 
                  onChange={(e) => updateField("phone", e.target.value)} 
                  className="h-11 min-h-[44px]"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="address" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Physical Address</Label>
              <Input 
                id="address" 
                value={profile.address} 
                onChange={(e) => updateField("address", e.target.value)} 
                className="h-11 min-h-[44px]"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base sm:text-lg">Opening Hours</CardTitle>
            <CardDescription className="text-xs">
              Set standard business availability for online appointment bookings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {profile.openingHours.map((day, i) => (
                <div 
                  key={day.day} 
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 p-3 rounded-lg border bg-card/60 transition-colors"
                >
                  <div className="flex items-center justify-between sm:justify-start gap-3 sm:w-40">
                    <Label className="font-semibold text-sm cursor-pointer">{day.day}</Label>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={day.isOpen}
                        onCheckedChange={(checked) => updateHours(i, { isOpen: checked })}
                        className="touch-manipulation"
                      />
                      <span className="text-xs text-muted-foreground sm:hidden">
                        {day.isOpen ? 'Open' : 'Closed'}
                      </span>
                    </div>
                  </div>

                  {day.isOpen ? (
                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      <Input
                        type="time"
                        className="flex-1 sm:w-32 h-10 min-h-[44px] text-center"
                        value={day.openTime}
                        onChange={(e) => updateHours(i, { openTime: e.target.value })}
                      />
                      <span className="text-xs text-muted-foreground px-1 shrink-0">to</span>
                      <Input
                        type="time"
                        className="flex-1 sm:w-32 h-10 min-h-[44px] text-center"
                        value={day.closeTime}
                        onChange={(e) => updateHours(i, { closeTime: e.target.value })}
                      />
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground italic py-1 sm:py-0">
                      Closed all day
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
          <CardFooter className="justify-end border-t pt-4">
            <Button 
              onClick={handleSave} 
              disabled={saving}
              className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-2"
            >
              <Save className="h-4 w-4" />
              <span>{saving ? "Saving..." : "Save Changes"}</span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </MobilePageShell>
  )
}
