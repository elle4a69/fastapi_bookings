import React from 'react';
import { ChevronLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface MobileBackButtonProps {
  label?: string;
  onClick: () => void;
  className?: string;
}

export function MobileBackButton({
  label = 'Back',
  onClick,
  className,
}: MobileBackButtonProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={onClick}
      className={cn(
        'h-11 min-h-[44px] min-w-[44px] px-2.5 -ml-1 text-sm font-medium gap-1.5 touch-manipulation hover:bg-accent text-foreground inline-flex items-center',
        className
      )}
    >
      <ChevronLeft className="h-5 w-5 shrink-0 text-muted-foreground" />
      <span>{label}</span>
    </Button>
  );
}

export interface MobilePageShellProps {
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  backAction?: {
    label?: string;
    onClick: () => void;
  };
  children: React.ReactNode;
  className?: string;
  headerClassName?: string;
  density?: 'default' | 'compact';
}

export function MobilePageShell({
  title,
  description,
  actions,
  backAction,
  children,
  className,
  headerClassName,
  density = 'default',
}: MobilePageShellProps) {
  const isCompact = density === 'compact';
  const hasHeader = title || description || actions || backAction;

  return (
    <div className={cn(
      'w-full min-w-0 max-w-7xl mx-auto',
      isCompact ? 'space-y-2 sm:space-y-2.5' : 'space-y-4 sm:space-y-6',
      className
    )}>
      {hasHeader && (
        <div className={cn(
          isCompact ? 'space-y-1 sm:space-y-1.5' : 'space-y-3 sm:space-y-4',
          'min-w-0',
          headerClassName
        )}>
          {backAction && (
            <div className={cn("flex items-center", isCompact ? "-mb-0.5" : "-mb-1")}>
              <MobileBackButton
                label={backAction.label}
                onClick={backAction.onClick}
                className={isCompact ? "h-8 min-h-0 min-w-0 px-2 text-xs" : undefined}
              />
            </div>
          )}
          <div className={cn(
            "flex flex-col sm:flex-row sm:items-center sm:justify-between min-w-0",
            isCompact ? "gap-1.5 sm:gap-2" : "gap-3"
          )}>
            <div className="min-w-0 flex-1">
              {title && (
                typeof title === 'string' ? (
                  <h1 className={cn(
                    "font-bold tracking-tight text-foreground truncate",
                    isCompact ? "text-lg sm:text-xl" : "text-xl sm:text-2xl md:text-3xl"
                  )}>
                    {title}
                  </h1>
                ) : (
                  title
                )
              )}
              {description && (
                typeof description === 'string' ? (
                  <p className={cn(
                    "text-muted-foreground mt-0.5",
                    isCompact ? "text-xs line-clamp-1" : "text-xs sm:text-sm line-clamp-2 sm:line-clamp-none"
                  )}>
                    {description}
                  </p>
                ) : (
                  description
                )
              )}
            </div>
            {actions && (
              <div className={cn(
                "flex flex-wrap items-center shrink-0 w-full sm:w-auto",
                isCompact ? "gap-1.5" : "gap-2"
              )}>
                {actions}
              </div>
            )}
          </div>
        </div>
      )}
      <div className="min-w-0 w-full">
        {children}
      </div>
    </div>
  );
}
