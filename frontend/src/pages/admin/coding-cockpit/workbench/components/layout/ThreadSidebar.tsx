import React from 'react'
import { UnifiedSidebar } from './UnifiedSidebar'

/**
 * ThreadSidebar legacy shim:
 * Consolidates into the single UnifiedSidebar tree component.
 */
export const ThreadSidebar: React.FC = () => {
  return <UnifiedSidebar />
}

export default ThreadSidebar
