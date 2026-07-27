import type { LucideIcon } from "lucide-react"
import {
  BoxesIcon,
  BriefcaseBusinessIcon,
  CalendarClockIcon,
  CalendarDaysIcon,
  ClipboardCheckIcon,
  ClipboardListIcon,
  FileInputIcon,
  FileTextIcon,
  GiftIcon,
  GitBranchIcon,
  LandmarkIcon,
  LayoutDashboardIcon,
  MapPinIcon,
  SendIcon,
  SettingsIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  SparklesIcon,
  StarIcon,
  TagsIcon,
  UsersIcon,
  UserRoundCogIcon,
  WrenchIcon,
} from "lucide-react"

export type NavItem = {
  title: string
  url?: string
  icon: LucideIcon
  children?: Array<{ title: string; url: string }>
}

type NavSection = {
  label: string
  items: NavItem[]
}

export const navigation: NavSection[] = [
  {
    label: "Main",
    items: [
      { title: "Dashboard", url: "/admin", icon: LayoutDashboardIcon },
      { title: "Calendar", url: "/admin/calendar", icon: CalendarDaysIcon },
      { title: "Bookings", url: "/admin/bookings", icon: ClipboardListIcon },
    ],
  },
  {
    label: "Catalog",
    items: [
      {
        title: "Locations",
        icon: MapPinIcon,
        children: [
          { title: "Locations", url: "/admin/catalog/locations" },
          { title: "Location Resources", url: "/admin/resources" },
        ],
      },
      { title: "Providers", url: "/admin/catalog/providers", icon: UserRoundCogIcon },
      { title: "Scheduling", url: "/admin/catalog/scheduling", icon: CalendarClockIcon },
      { title: "Services", url: "/admin/catalog/services", icon: BriefcaseBusinessIcon },
      { title: "Categories", url: "/admin/catalog/categories", icon: TagsIcon },
      { title: "Add-ons", url: "/admin/catalog/add-ons", icon: SparklesIcon },
      { title: "Products", url: "/admin/catalog/products", icon: ShoppingBagIcon },
      { title: "Packages", url: "/admin/catalog/packages", icon: GiftIcon },
    ],
  },
  {
    label: "Operations",
    items: [
      { title: "Relationships", url: "/admin/relationships", icon: GitBranchIcon },
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
    items: [
      {
        title: "Finance",
        icon: LandmarkIcon,
        children: [
          { title: "Invoices", url: "/admin/finance/invoices" },
          { title: "Payments", url: "/admin/finance/payments" },
          { title: "Promotions", url: "/admin/finance/promotions" },
          { title: "Tax Rates", url: "/admin/finance/tax-rates" },
          { title: "Processors", url: "/admin/finance/processors" },
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
      { title: "Booking Forms", url: "/admin/booking-forms", icon: FileInputIcon },
      { title: "Reviews", url: "/admin/reviews", icon: StarIcon },
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
          { title: "Webhooks", url: "/admin/settings/webhooks" },
          { title: "Plugins", url: "/admin/settings/plugins" },
        ],
      },
    ],
  },
  {
    label: "Compliance & System",
    items: [
      { title: "GDPR", url: "/admin/compliance/gdpr", icon: ShieldCheckIcon },
      { title: "Audit Log", url: "/admin/audit", icon: ClipboardCheckIcon },
      { title: "System", url: "/admin/system", icon: WrenchIcon },
    ],
  },
]
