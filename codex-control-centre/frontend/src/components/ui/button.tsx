import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)] shadow-xs font-semibold',
        secondary: 'bg-[var(--surface-secondary)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] border border-[var(--border)]',
        outline: 'border border-[var(--border)] bg-transparent hover:bg-[var(--surface-hover)] text-[var(--text-primary)]',
        ghost: 'hover:bg-[var(--surface-hover)] text-[var(--text-primary)]',
        danger: 'bg-[var(--danger)] text-white hover:opacity-90 shadow-xs',
        dangerOutline: 'border border-[var(--danger)] text-[var(--danger)] hover:bg-[var(--danger-subtle)]',
        success: 'bg-[var(--success)] text-white hover:opacity-90 shadow-xs',
        link: 'text-[var(--accent)] underline-offset-4 hover:underline'
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-7 rounded px-2.5 text-xs',
        lg: 'h-10 rounded-md px-6 text-base',
        icon: 'h-8 w-8 p-0'
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'default'
    }
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'
