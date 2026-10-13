import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition-colors border',
  {
    variants: {
      variant: {
        default: 'bg-[var(--accent-subtle)] text-[var(--accent)] border-transparent',
        secondary: 'bg-[var(--surface-secondary)] text-[var(--text-secondary)] border-[var(--border)]',
        success: 'bg-[var(--success-subtle)] text-[var(--success)] border-transparent',
        warning: 'bg-[var(--warning-subtle)] text-[var(--warning)] border-transparent',
        danger: 'bg-[var(--danger-subtle)] text-[var(--danger)] border-transparent',
        outline: 'text-[var(--text-primary)] border-[var(--border)] bg-transparent'
      }
    },
    defaultVariants: {
      variant: 'default'
    }
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
