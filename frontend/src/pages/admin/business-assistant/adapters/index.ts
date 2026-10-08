export * from './registry.ts'
export * from './business-settings-adapter.ts'
export * from './catalog-services-adapter.ts'

import { formAdapterRegistry } from './registry.ts'
import { BusinessSettingsAdapter } from './business-settings-adapter.ts'
import { CatalogServicesAdapter } from './catalog-services-adapter.ts'

// Pre-register singleton adapter instances
export const defaultBusinessSettingsAdapter = new BusinessSettingsAdapter()
export const defaultCatalogServicesAdapter = new CatalogServicesAdapter()

formAdapterRegistry.registerAdapter(defaultBusinessSettingsAdapter)
formAdapterRegistry.registerAdapter(defaultCatalogServicesAdapter)
