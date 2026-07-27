import { useEffect, useState } from "react"
import { apiClient } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
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
      // Fallback if data is missing some fields
      setProfile({
        name: data.name || "",
        email: data.email || "",
        phone: data.phone || "",
        address: data.address || "",
        openingHours: data.openingHours || DEFAULT_HOURS,
      })
    } catch (error) {
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
    } catch (error) {
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
      <div className="space-y-6">
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  if (!profile) return null

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Business Profile</h1>
        <p className="text-muted-foreground">Manage your business details and operational hours.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Contact Details</CardTitle>
          <CardDescription>Basic information about your business shown to customers.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="name">Business Name</Label>
            <Input id="name" value={profile.name} onChange={(e) => updateField("name", e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={profile.email} onChange={(e) => updateField("email", e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" value={profile.phone} onChange={(e) => updateField("phone", e.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="address">Address</Label>
            <Input id="address" value={profile.address} onChange={(e) => updateField("address", e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Opening Hours</CardTitle>
          <CardDescription>Configure your regular weekly schedule.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {profile.openingHours.map((day, i) => (
              <div key={day.day} className="flex items-center gap-4">
                <div className="w-32 flex items-center gap-2">
                  <Switch
                    checked={day.isOpen}
                    onCheckedChange={(checked) => updateHours(i, { isOpen: checked })}
                  />
                  <Label>{day.day}</Label>
                </div>
                <Input
                  type="time"
                  className="w-32"
                  value={day.openTime}
                  disabled={!day.isOpen}
                  onChange={(e) => updateHours(i, { openTime: e.target.value })}
                />
                <span className="text-muted-foreground">to</span>
                <Input
                  type="time"
                  className="w-32"
                  value={day.closeTime}
                  disabled={!day.isOpen}
                  onChange={(e) => updateHours(i, { closeTime: e.target.value })}
                />
              </div>
            ))}
          </div>
        </CardContent>
        <CardFooter className="justify-end border-t pt-6">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
