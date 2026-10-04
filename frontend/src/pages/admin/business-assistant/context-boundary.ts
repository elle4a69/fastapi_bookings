export type PageContextInfo = {
  current_path: string
  module_name: string
}

/**
 * Context Awareness Boundary:
 * Strictly resolves only route and module identifiers.
 * NEVER inspects the DOM, scraped page text, form values, credentials, or tokens.
 */
export function resolvePageContext(pathname: string): PageContextInfo {
  const path = pathname.split('?')[0].split('#')[0]

  let moduleName = 'general_admin'
  if (path === '/admin' || path === '/admin/dashboard') {
    moduleName = 'dashboard'
  } else if (path.startsWith('/admin/calendar')) {
    moduleName = 'calendar'
  } else if (path.startsWith('/admin/bookings')) {
    moduleName = 'bookings'
  } else if (path.startsWith('/admin/sms-assistant') || path.startsWith('/admin/sms')) {
    moduleName = 'sms_assistant'
  } else if (path.startsWith('/admin/catalog/locations')) {
    moduleName = 'locations'
  } else if (path.startsWith('/admin/catalog/providers')) {
    moduleName = 'multiple_providers'
  } else if (path.startsWith('/admin/catalog/scheduling')) {
    moduleName = 'multiple_providers'
  } else if (path.startsWith('/admin/catalog/services')) {
    moduleName = 'catalog_services'
  } else if (path.startsWith('/admin/catalog/categories')) {
    moduleName = 'categories'
  } else if (path.startsWith('/admin/catalog/add-ons')) {
    moduleName = 'addons'
  } else if (path.startsWith('/admin/catalog/products')) {
    moduleName = 'products'
  } else if (path.startsWith('/admin/catalog/packages')) {
    moduleName = 'packages'
  } else if (path.startsWith('/admin/relationships')) {
    moduleName = 'relationship_matrix'
  } else if (path.startsWith('/admin/finance')) {
    moduleName = 'finance_invoicing'
  } else if (path.startsWith('/admin/website')) {
    moduleName = 'website'
  } else if (path.startsWith('/admin/media')) {
    moduleName = 'media'
  } else if (path.startsWith('/admin/booking-forms')) {
    moduleName = 'booking_forms'
  } else if (path.startsWith('/admin/clients')) {
    moduleName = 'clients'
  } else if (path.startsWith('/admin/settings/business')) {
    moduleName = 'business_settings'
  } else if (path.startsWith('/admin/settings/modules')) {
    moduleName = 'tenant_modules'
  } else if (path.startsWith('/admin/settings')) {
    moduleName = 'settings'
  } else if (path.startsWith('/admin/business-assistant')) {
    moduleName = 'business_assistant'
  } else if (path.startsWith('/admin/assistant-studio')) {
    moduleName = 'assistant_studio'
  } else if (path.startsWith('/admin/resident-agent')) {
    moduleName = 'resident_agent'
  }

  return {
    current_path: path,
    module_name: moduleName,
  }
}
