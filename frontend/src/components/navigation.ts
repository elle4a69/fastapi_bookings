import type { LucideIcon } from "lucide-react"
import {
  Activity,
  BriefcaseBusinessIcon,
  CalendarClockIcon,
  CalendarDaysIcon,
  ClipboardCheckIcon,
  ClipboardListIcon,
  Cpu,
  FileInputIcon,
  FileTextIcon,
  GiftIcon,
  GitBranchIcon,
  GlobeIcon,
  LandmarkIcon,
  LayoutDashboardIcon,
  MapPinIcon,
  MessageSquareTextIcon,
  SendIcon,
  SettingsIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  SparklesIcon,
  StarIcon,
  TagsIcon,
  UsersIcon,
  ImagesIcon,
  UserRoundCogIcon,
  WrenchIcon,
  Code2,
} from "lucide-react"

export type NavItem = {
  title: string
  url?: string
  icon: LucideIcon
  moduleKey?: string
  children?: Array<{ title: string; url: string; moduleKey?: string }>
}

export type NavSection = {
  label: string
  moduleKey?: string
  items: NavItem[]
}

export const providerNavigation: NavSection[] = [
  {
    label: "My Workspace",
    items: [
      { title: "My Schedule", url: "/admin/my-schedule", icon: CalendarClockIcon },
      { title: "My Bookings / Jobs", url: "/admin/my-jobs", icon: ClipboardListIcon },
      { title: "Profile / Working Hours", url: "/admin/my-profile", icon: UserRoundCogIcon },
    ],
  },
]

export const navigation: NavSection[] = [
  {
    label: "Main",
    items: [
      { title: "Dashboard", url: "/admin", icon: LayoutDashboardIcon, moduleKey: "dashboard" },
      { title: "Calendar", url: "/admin/calendar", icon: CalendarDaysIcon, moduleKey: "calendar" },
      { title: "Bookings", url: "/admin/bookings", icon: ClipboardListIcon, moduleKey: "bookings" },
      { title: "SMS Assistant", url: "/admin/sms-assistant", icon: MessageSquareTextIcon, moduleKey: "sms_assistant" },
    ],
  },
  {
    label: "Catalog",
    items: [
      {
        title: "Locations",
        icon: MapPinIcon,
        moduleKey: "locations",
        children: [
          { title: "Locations", url: "/admin/catalog/locations", moduleKey: "locations" },
          { title: "Location Resources", url: "/admin/resources", moduleKey: "locations" },
        ],
      },
      { title: "Providers", url: "/admin/catalog/providers", icon: UserRoundCogIcon, moduleKey: "providers" },
      { title: "Scheduling", url: "/admin/catalog/scheduling", icon: CalendarClockIcon, moduleKey: "providers" },
      { title: "Services", url: "/admin/catalog/services", icon: BriefcaseBusinessIcon },
      { title: "Categories", url: "/admin/catalog/categories", icon: TagsIcon },
      { title: "Add-ons", url: "/admin/catalog/add-ons", icon: SparklesIcon },
      { title: "Products", url: "/admin/catalog/products", icon: ShoppingBagIcon },
      { title: "Packages", url: "/admin/catalog/packages", icon: GiftIcon, moduleKey: "packages" },
    ],
  },
  {
    label: "Operations",
    items: [
      { title: "Relationships", url: "/admin/relationships", icon: GitBranchIcon, moduleKey: "providers" },
      {
        title: "Schedule",
        icon: CalendarClockIcon,
        children: [
          { title: "Workdays", url: "/admin/schedule/workdays" },
          { title: "Exceptions", url: "/admin/schedule/exceptions" },
        ],
      },
      { title: "Clients", url: "/admin/clients", icon: UsersIcon },
    ],
  },
  {
    label: "Finance",
    moduleKey: "finance_invoicing",
    items: [
      {
        title: "Finance",
        icon: LandmarkIcon,
        moduleKey: "finance_invoicing",
        children: [
          { title: "Invoices", url: "/admin/finance/invoices", moduleKey: "finance_invoicing" },
          { title: "Payments", url: "/admin/finance/payments", moduleKey: "finance_invoicing" },
          { title: "Promotions", url: "/admin/finance/promotions", moduleKey: "finance_invoicing" },
          { title: "Tax Rates", url: "/admin/finance/tax-rates", moduleKey: "finance_invoicing" },
          { title: "Processors", url: "/admin/finance/processors", moduleKey: "finance_invoicing" },
        ],
      },
    ],
  },
  {
    label: "Notifications",
    items: [
      {
        title: "Notifications",
        icon: SendIcon,
        children: [
          { title: "Messages", url: "/admin/notifications/messages" },
          { title: "Templates", url: "/admin/notifications/templates" },
          { title: "Reminders", url: "/admin/notifications/reminders" },
        ],
      },
    ],
  },
  {
    label: "More",
    items: [
      { title: "Website", url: "/admin/website", icon: GlobeIcon, moduleKey: "website" },
      { title: "Media", url: "/admin/media", icon: ImagesIcon, moduleKey: "media" },
      { title: "Booking Forms", url: "/admin/booking-forms", icon: FileInputIcon, moduleKey: "booking_forms" },
      { title: "Reviews", url: "/admin/reviews", icon: StarIcon, moduleKey: "reviews" },
      {
        title: "Additional Fields",
        url: "/admin/configuration/additional-fields",
        icon: FileTextIcon,
      },
    ],
  },
  {
    label: "Settings",
    items: [
      {
        title: "Settings",
        icon: SettingsIcon,
        children: [
          { title: "Business Profile", url: "/admin/settings/business" },
          { title: "Modules & App Store", url: "/admin/settings/modules" },
          { title: "Webhooks", url: "/admin/settings/webhooks" },
          { title: "Plugins", url: "/admin/settings/plugins" },
        ],
      },
    ],
  },
  {
    label: "Compliance & System",
    items: [
      { title: "Resident Agent", url: "/admin/resident-agent", icon: Cpu },
      { title: "Conversational Coding Studio", url: "/admin/coding-studio", icon: Code2 },
      { title: "Telemetry", url: "/admin/telemetry", icon: Activity },
      { title: "GDPR", url: "/admin/compliance/gdpr", icon: ShieldCheckIcon },
      { title: "Audit Log", url: "/admin/audit", icon: ClipboardCheckIcon },
      { title: "System", url: "/admin/system", icon: WrenchIcon },
    ],
  },
]

/**
 * Filter navigation sections and items based on the tenant's active module keys.
 * If a section or item has a moduleKey that is not enabled, it is omitted.
 */
export function filterNavigationByModules(
  sections: NavSection[],
  enabledModules: string[]
): NavSection[] {
  if (!enabledModules || enabledModules.length === 0) {
    return sections
  }

  const moduleSet = new Set(enabledModules.map((m) => m.toLowerCase()))

  return sections
    .filter((section) => {
      // If the section as a whole requires a module, ensure it's enabled
      if (section.moduleKey && !moduleSet.has(section.moduleKey.toLowerCase())) {
        return false
      }
      return true
    })
    .map((section) => {
      const filteredItems = section.items
        .filter((item) => {
          if (item.moduleKey && !moduleSet.has(item.moduleKey.toLowerCase())) {
            return false
          }
          return true
        })
        .map((item) => {
          if (!item.children) return item
          const filteredChildren = item.children.filter((child) => {
            if (child.moduleKey && !moduleSet.has(child.moduleKey.toLowerCase())) {
              return false
            }
            return true
          })
          return { ...item, children: filteredChildren }
        })
        .filter((item) => {
          // If the item had children originally but all got filtered out, exclude item
          if (item.children && item.children.length === 0) {
            return false
          }
          return true
        })

      return { ...section, items: filteredItems }
    })
    .filter((section) => section.items.length > 0)
}

