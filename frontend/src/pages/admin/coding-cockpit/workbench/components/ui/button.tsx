import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs font-semibold',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border',
        outline: 'border border-border bg-background hover:bg-muted hover:text-foreground text-foreground',
        ghost: 'hover:bg-muted hover:text-foreground text-foreground',
        danger: 'bg-destructive text-white hover:bg-destructive/90 shadow-xs',
        destructive: 'bg-destructive text-white hover:bg-destructive/90 shadow-xs',
        dangerOutline: 'border border-destructive/40 text-destructive hover:bg-destructive/10',
        success: 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs',
        link: 'text-primary underline-offset-4 hover:underline'
      },
      size: {
        default: 'h-8 px-3 text-xs sm:text-sm',
        sm: 'h-7 rounded-md px-2.5 text-xs',
        xs: 'h-6 rounded px-2 text-[11px]',
        lg: 'h-9 rounded-md px-4 text-sm',
        icon: 'h-8 w-8 p-0',
        'icon-sm': 'h-7 w-7 p-0'
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

export default Button
