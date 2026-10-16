/**
 * Proposal Diffing and Stale Invalidation Engine for Website Builder.
 *
 * Compares current website draft configuration against proposed updates cleanly per section,
 * identifying changes in hero, about, services, gallery, booking, testimonials, contact, etc.
 * Also handles stale proposal invalidation and re-sync rebasing.
 */

export interface FieldDiff {
  fieldKey: string
  fieldLabel: string
  before: unknown
  after: unknown
  changeType: 'added' | 'modified' | 'removed'
}

export interface SectionDiff {
  sectionKey: string
  sectionTitle: string
  hasChanges: boolean
  changes: FieldDiff[]
}

export interface ProposalDiffResult {
  hasAnyChanges: boolean
  totalChangesCount: number
  sectionDiffs: SectionDiff[]
  changedSectionKeys: string[]
}

export const SECTION_TITLES: Record<string, string> = {
  hero: 'Hero Section',
  about: 'About Us Section',
  services: 'Services Section',
  gallery: 'Photo Gallery Section',
  booking: 'Booking Widget Section',
  testimonials: 'Testimonials & Reviews',
  contact: 'Contact & Hours Section',
  footer: 'Footer Section',
  chat_widget: 'Live Chat Widget',
  styling: 'Theme & Template Styling',
  seo: 'SEO & Metadata',
}

export const FIELD_LABELS: Record<string, string> = {
  headline: 'Headline',
  subhead: 'Subheadline',
  cta_text: 'CTA Button Text',
  cta_link: 'CTA Link',
  bg_image_url: 'Background Image URL',
  badge: 'Badge Text',
  story: 'Story / Description',
  image_url: 'Section Image URL',
  show_prices: 'Show Prices',
  selected_service_ids: 'Selected Services',
  items: 'Item List',
  images: 'Gallery Images',
  embedded_style: 'Embedded Layout Style',
  booking_mode: 'Booking Mode',
  calcom_link: 'Cal.com Link',
  calcom_layout: 'Cal.com Layout',
  address: 'Address',
  phone: 'Phone Number',
  email: 'Email Address',
  hours: 'Operating Hours',
  copyright: 'Copyright Notice',
  social_links: 'Social Links',
  template_id: 'Website Template',
  theme_id: 'Color Theme',
  custom_colors: 'Custom Palette',
  seo_title: 'SEO Title',
  seo_description: 'SEO Description',
  enabled: 'Section Enabled',
  invitation_title: 'Chat Invitation Title',
  invitation_message: 'Chat Invitation Message',
  invitation_delay_seconds: 'Invitation Delay (seconds)',
  show_sms_fallback: 'Show SMS Fallback',
}

function areValuesEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null && b == null) return true
  if (a == null || b == null) return false

  if (typeof a === 'object' && typeof b === 'object') {
    return JSON.stringify(a) === JSON.stringify(b)
  }
  return false
}

/**
 * Computes deep visual diff per section between current website config and proposed changes.
 */
export function computeWebsiteDiff(
  currentConfig: Record<string, unknown>,
  proposedPayload: Record<string, unknown>,
): ProposalDiffResult {
  const currentSections =
    (currentConfig.sections_data as Record<string, Record<string, unknown>>) || {}

  // The proposed payload can either be a wrapped proposal payload (with .sections_data or .content_payload)
  // or a full proposed WebsiteConfigData object
  let proposedSections: Record<string, Record<string, unknown>> = {}
  if (proposedPayload.sections_data && typeof proposedPayload.sections_data === 'object') {
    proposedSections = proposedPayload.sections_data as Record<string, Record<string, unknown>>
  } else if (
    proposedPayload.content_payload &&
    typeof proposedPayload.content_payload === 'object' &&
    (proposedPayload.content_payload as Record<string, unknown>).sections_data
  ) {
    proposedSections = (proposedPayload.content_payload as Record<string, unknown>)
      .sections_data as Record<string, Record<string, unknown>>
  } else {
    // If proposedPayload contains section keys directly (e.g. hero, about)
    proposedSections = proposedPayload as Record<string, Record<string, unknown>>
  }

  const allSectionKeys = Array.from(
    new Set([
      'hero',
      'about',
      'services',
      'gallery',
      'booking',
      'testimonials',
      'contact',
      'footer',
      'chat_widget',
      ...Object.keys(currentSections),
      ...Object.keys(proposedSections).filter(
        (k) =>
          ![
            'template_id',
            'theme_id',
            'custom_colors',
            'seo_title',
            'seo_description',
            'is_published',
            'content_payload',
            'title',
            'sections_data',
          ].includes(k),
      ),
    ]),
  )

  const sectionDiffs: SectionDiff[] = []
  let totalChanges = 0
  const changedSectionKeys: string[] = []

  // 1. Diff each section
  for (const sectionKey of allSectionKeys) {
    const currentSec = currentSections[sectionKey] || {}
    const proposedSec = proposedSections[sectionKey]

    // If section wasn't touched in proposed changes, skip it
    if (!proposedSec) {
      continue
    }

    const fieldKeys = Array.from(
      new Set([...Object.keys(currentSec), ...Object.keys(proposedSec)]),
    )

    const changes: FieldDiff[] = []

    for (const fieldKey of fieldKeys) {
      const beforeVal = currentSec[fieldKey]
      const afterVal = proposedSec[fieldKey]

      if (afterVal === undefined) {
        // Unspecified fields in proposal preserve existing values
        continue
      }

      if (!areValuesEqual(beforeVal, afterVal)) {
        let changeType: 'added' | 'modified' | 'removed' = 'modified'
        if (beforeVal === undefined || beforeVal === null || beforeVal === '') {
          changeType = 'added'
        } else if (afterVal === null || afterVal === '') {
          changeType = 'removed'
        }

        changes.push({
          fieldKey,
          fieldLabel: FIELD_LABELS[fieldKey] || fieldKey.replace(/_/g, ' '),
          before: beforeVal,
          after: afterVal,
          changeType,
        })
      }
    }

    if (changes.length > 0) {
      sectionDiffs.push({
        sectionKey,
        sectionTitle: SECTION_TITLES[sectionKey] || `${sectionKey.replace(/_/g, ' ')} Section`,
        hasChanges: true,
        changes,
      })
      totalChanges += changes.length
      changedSectionKeys.push(sectionKey)
    }
  }

  // 2. Diff Styling (template_id, theme_id, custom_colors)
  const stylingChanges: FieldDiff[] = []
  const styleKeys = ['template_id', 'theme_id', 'custom_colors']
  for (const key of styleKeys) {
    const beforeVal = currentConfig[key]
    const afterVal =
      proposedPayload[key] !== undefined
        ? proposedPayload[key]
        : proposedPayload.content_payload &&
            typeof proposedPayload.content_payload === 'object' &&
            (proposedPayload.content_payload as Record<string, unknown>)[key] !== undefined
          ? (proposedPayload.content_payload as Record<string, unknown>)[key]
          : undefined

    if (afterVal !== undefined && !areValuesEqual(beforeVal, afterVal)) {
      stylingChanges.push({
        fieldKey: key,
        fieldLabel: FIELD_LABELS[key] || key,
        before: beforeVal,
        after: afterVal,
        changeType: beforeVal == null ? 'added' : 'modified',
      })
    }
  }

  if (stylingChanges.length > 0) {
    sectionDiffs.push({
      sectionKey: 'styling',
      sectionTitle: SECTION_TITLES.styling,
      hasChanges: true,
      changes: stylingChanges,
    })
    totalChanges += stylingChanges.length
    changedSectionKeys.push('styling')
  }

  // 3. Diff SEO fields
  const seoChanges: FieldDiff[] = []
  const seoKeys = ['seo_title', 'seo_description']
  for (const key of seoKeys) {
    const beforeVal = currentConfig[key]
    const afterVal =
      proposedPayload[key] !== undefined
        ? proposedPayload[key]
        : proposedPayload.content_payload &&
            typeof proposedPayload.content_payload === 'object' &&
            (proposedPayload.content_payload as Record<string, unknown>)[key] !== undefined
          ? (proposedPayload.content_payload as Record<string, unknown>)[key]
          : undefined

    if (afterVal !== undefined && !areValuesEqual(beforeVal, afterVal)) {
      seoChanges.push({
        fieldKey: key,
        fieldLabel: FIELD_LABELS[key] || key,
        before: beforeVal,
        after: afterVal,
        changeType: beforeVal == null ? 'added' : 'modified',
      })
    }
  }

  if (seoChanges.length > 0) {
    sectionDiffs.push({
      sectionKey: 'seo',
      sectionTitle: SECTION_TITLES.seo,
      hasChanges: true,
      changes: seoChanges,
    })
    totalChanges += seoChanges.length
    changedSectionKeys.push('seo')
  }

  return {
    hasAnyChanges: totalChanges > 0,
    totalChangesCount: totalChanges,
    sectionDiffs,
    changedSectionKeys,
  }
}

/**
 * Determines whether a pending proposal has become stale due to base website version advancement
 * or conflicting edits.
 */
export function isProposalStale(
  proposal: {
    version?: number
    expected_version?: number | null
    created_at?: string
  },
  currentWebsite: {
    version?: number
    updated_at?: string | null
    hasUnsavedChanges?: boolean
  },
): boolean {
  // If expected_version was explicitly set and does not match the active website version
  if (
    typeof proposal.expected_version === 'number' &&
    typeof currentWebsite.version === 'number' &&
    proposal.expected_version !== currentWebsite.version
  ) {
    return true
  }

  // If website version advanced beyond the version at proposal creation
  if (
    typeof proposal.version === 'number' &&
    typeof currentWebsite.version === 'number' &&
    currentWebsite.version > proposal.version
  ) {
    return true
  }

  // If there are unsaved pending edits in the active editor
  if (currentWebsite.hasUnsavedChanges) {
    return true
  }

  // If website was modified after the proposal was created
  if (proposal.created_at && currentWebsite.updated_at) {
    const proposalTime = new Date(proposal.created_at).getTime()
    const websiteTime = new Date(currentWebsite.updated_at).getTime()
    if (!isNaN(proposalTime) && !isNaN(websiteTime) && websiteTime > proposalTime + 500) {
      return true
    }
  }

  return false
}

/**
 * Rebases a proposal payload on top of current website configuration, producing a fresh merged preview.
 */
export function rebaseProposalOnCurrentConfig(
  currentConfig: Record<string, unknown>,
  proposalPayload: Record<string, unknown>,
): Record<string, unknown> {
  const currentSections =
    (currentConfig.sections_data as Record<string, Record<string, unknown>>) || {}

  let proposedSections: Record<string, Record<string, unknown>> = {}
  if (proposalPayload.sections_data && typeof proposalPayload.sections_data === 'object') {
    proposedSections = proposalPayload.sections_data as Record<string, Record<string, unknown>>
  } else if (
    proposalPayload.content_payload &&
    typeof proposalPayload.content_payload === 'object' &&
    (proposalPayload.content_payload as Record<string, unknown>).sections_data
  ) {
    proposedSections = (proposalPayload.content_payload as Record<string, unknown>)
      .sections_data as Record<string, Record<string, unknown>>
  } else {
    proposedSections = proposalPayload as Record<string, Record<string, unknown>>
  }

  const mergedSections: Record<string, Record<string, unknown>> = { ...currentSections }

  for (const [secKey, secUpdates] of Object.entries(proposedSections)) {
    if (typeof secUpdates === 'object' && secUpdates !== null) {
      mergedSections[secKey] = {
        ...(mergedSections[secKey] || {}),
        ...secUpdates,
      }
    }
  }

  return {
    ...currentConfig,
    template_id: proposalPayload.template_id || currentConfig.template_id,
    theme_id: proposalPayload.theme_id || currentConfig.theme_id,
    custom_colors: proposalPayload.custom_colors || currentConfig.custom_colors,
    seo_title: proposalPayload.seo_title || currentConfig.seo_title,
    seo_description: proposalPayload.seo_description || currentConfig.seo_description,
    sections_data: mergedSections,
  }
}
