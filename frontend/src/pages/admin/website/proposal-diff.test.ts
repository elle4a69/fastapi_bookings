// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  computeWebsiteDiff,
  isProposalStale,
  rebaseProposalOnCurrentConfig,
} from './proposal-diff.ts'

// ── 1. PROPOSAL DIFF COMPUTATION TESTS ──────────────────────────────────

test('computeWebsiteDiff identifies clean per-section modifications for hero and about', () => {
  const currentConfig = {
    template_id: 'minimalist',
    theme_id: 'ocean_slate',
    sections_data: {
      hero: {
        headline: 'Original Hero Headline',
        subhead: 'Original Subhead',
        cta_text: 'Book Now',
        bg_image_url: 'https://example.com/hero.jpg',
        enabled: true,
      },
      about: {
        badge: 'Our Story',
        headline: 'Dedicated Care',
        story: 'We provide care since 2010.',
        enabled: true,
      },
      services: {
        headline: 'Our Services',
        subhead: 'Check our treatments',
        enabled: true,
      },
    },
  }

  const proposedPayload = {
    sections_data: {
      hero: {
        headline: 'Rejuvenate Your Senses - Luxury Spa Experience',
        subhead: 'Original Subhead', // Untouched
        cta_text: 'Reserve Your Treatment',
        bg_image_url: 'https://example.com/hero-new.jpg',
        enabled: true,
      },
      about: {
        story: 'Expanded story: Award-winning wellness and bespoke holistic therapies.',
      },
    },
  }

  const result = computeWebsiteDiff(currentConfig, proposedPayload)

  assert.equal(result.hasAnyChanges, true)
  assert.equal(result.changedSectionKeys.includes('hero'), true)
  assert.equal(result.changedSectionKeys.includes('about'), true)
  assert.equal(result.changedSectionKeys.includes('services'), false) // services was not modified

  const heroDiff = result.sectionDiffs.find((s) => s.sectionKey === 'hero')
  assert.ok(heroDiff)
  assert.equal(heroDiff!.changes.length, 3) // headline, cta_text, bg_image_url

  const headlineChange = heroDiff!.changes.find((c) => c.fieldKey === 'headline')
  assert.ok(headlineChange)
  assert.equal(headlineChange!.before, 'Original Hero Headline')
  assert.equal(headlineChange!.after, 'Rejuvenate Your Senses - Luxury Spa Experience')
  assert.equal(headlineChange!.changeType, 'modified')

  const aboutDiff = result.sectionDiffs.find((s) => s.sectionKey === 'about')
  assert.ok(aboutDiff)
  assert.equal(aboutDiff!.changes.length, 1)
  assert.equal(aboutDiff!.changes[0].fieldKey, 'story')
  assert.equal(aboutDiff!.changes[0].changeType, 'modified')
})

test('computeWebsiteDiff detects changes in services list and gallery updates', () => {
  const currentConfig = {
    sections_data: {
      services: {
        headline: 'Services',
        subhead: 'Old Subhead',
        selected_service_ids: [1, 2],
        show_prices: true,
      },
      gallery: {
        headline: 'Gallery',
        images: ['https://example.com/pic1.jpg'],
      },
    },
  }

  const proposedPayload = {
    sections_data: {
      services: {
        selected_service_ids: [1, 2, 3, 4],
        show_prices: false,
      },
      gallery: {
        headline: 'Curated Photo Gallery',
        images: ['https://example.com/pic1.jpg', 'https://example.com/pic2.jpg'],
      },
    },
  }

  const result = computeWebsiteDiff(currentConfig, proposedPayload)
  assert.equal(result.changedSectionKeys.includes('services'), true)
  assert.equal(result.changedSectionKeys.includes('gallery'), true)

  const servicesDiff = result.sectionDiffs.find((s) => s.sectionKey === 'services')
  assert.ok(servicesDiff)
  const priceChange = servicesDiff!.changes.find((c) => c.fieldKey === 'show_prices')
  assert.ok(priceChange)
  assert.equal(priceChange!.before, true)
  assert.equal(priceChange!.after, false)

  const galleryDiff = result.sectionDiffs.find((s) => s.sectionKey === 'gallery')
  assert.ok(galleryDiff)
  const imagesChange = galleryDiff!.changes.find((c) => c.fieldKey === 'images')
  assert.ok(imagesChange)
  assert.equal(imagesChange!.changeType, 'modified')
})

test('computeWebsiteDiff returns hasAnyChanges=false when payload matches current config', () => {
  const currentConfig = {
    template_id: 'minimalist',
    theme_id: 'ocean_slate',
    sections_data: {
      hero: {
        headline: 'Welcome',
        subhead: 'Enjoy your stay',
      },
    },
  }

  const proposedPayload = {
    template_id: 'minimalist',
    theme_id: 'ocean_slate',
    sections_data: {
      hero: {
        headline: 'Welcome',
        subhead: 'Enjoy your stay',
      },
    },
  }

  const result = computeWebsiteDiff(currentConfig, proposedPayload)
  assert.equal(result.hasAnyChanges, false)
  assert.equal(result.totalChangesCount, 0)
  assert.equal(result.sectionDiffs.length, 0)
})

// ── 2. STALE PROPOSAL INVALIDATION TESTS ─────────────────────────────────

test('isProposalStale detects when base website version has advanced', () => {
  // Proposal was created at version 2, but website is now at version 3
  const stale = isProposalStale(
    { version: 2 },
    { version: 3, hasUnsavedChanges: false },
  )
  assert.equal(stale, true)
})

test('isProposalStale detects when expected_version does not match current version', () => {
  const stale = isProposalStale(
    { expected_version: 1 },
    { version: 2, hasUnsavedChanges: false },
  )
  assert.equal(stale, true)
})

test('isProposalStale detects when editor has unsaved changes', () => {
  const stale = isProposalStale(
    { version: 2 },
    { version: 2, hasUnsavedChanges: true },
  )
  assert.equal(stale, true)
})

test('isProposalStale returns false when proposal matches active version without conflicting changes', () => {
  const fresh = isProposalStale(
    {
      version: 2,
      expected_version: 2,
      created_at: new Date('2026-10-08T10:00:00Z').toISOString(),
    },
    {
      version: 2,
      updated_at: new Date('2026-10-08T09:50:00Z').toISOString(),
      hasUnsavedChanges: false,
    },
  )
  assert.equal(fresh, false)
})

test('rebaseProposalOnCurrentConfig merges delta onto newest current configuration', () => {
  const currentConfig = {
    template_id: 'wellness',
    theme_id: 'emerald_oasis',
    sections_data: {
      hero: {
        headline: 'Current Headline',
        subhead: 'Current Subhead',
        cta_text: 'Current CTA',
      },
      about: {
        headline: 'Current About',
      },
    },
  }

  const proposalPayload = {
    sections_data: {
      hero: {
        headline: 'New Proposed Headline',
      },
    },
  }

  const rebased = rebaseProposalOnCurrentConfig(currentConfig, proposalPayload)
  const rebasedHero = (rebased.sections_data as any).hero
  assert.equal(rebasedHero.headline, 'New Proposed Headline')
  assert.equal(rebasedHero.subhead, 'Current Subhead') // Preserved
  assert.equal(rebasedHero.cta_text, 'Current CTA') // Preserved
  assert.equal((rebased.sections_data as any).about.headline, 'Current About') // Preserved
})
