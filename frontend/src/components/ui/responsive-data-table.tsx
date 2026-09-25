import React, { useState, useMemo } from 'react';
import { 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown, 
  SlidersHorizontal 
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

export interface ColumnDef<T> {
  id: string;
  header: string;
  accessorKey?: keyof T;
  cell?: (row: T, index: number) => React.ReactNode;
  sortable?: boolean;
  hideable?: boolean;
  defaultHidden?: boolean;
  align?: 'left' | 'center' | 'right';
  className?: string;
  headerClassName?: string;
}

export interface ResponsiveDataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  keyExtractor: (row: T, index: number) => string | number;
  isLoading?: boolean;
  emptyState?: React.ReactNode;
  onRowClick?: (row: T) => void;
  renderMobileCard?: (row: T, index: number) => React.ReactNode;
  className?: string;
  cardClassName?: string;
  defaultSort?: {
    key: string;
    direction: 'asc' | 'desc';
  };
  showColumnSelector?: boolean;
  headerExtra?: React.ReactNode;
  density?: 'default' | 'compact';
}

export function ColumnVisibilityPicker({
  columns,
  visibleColumns,
  onToggleColumn,
  density = 'default',
}: {
  columns: ColumnDef<any>[];
  visibleColumns: Record<string, boolean>;
  onToggleColumn: (id: string) => void;
  density?: 'default' | 'compact';
}) {
  const hideableColumns = columns.filter((col) => col.hideable !== false);

  if (hideableColumns.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className={cn(
            "touch-manipulation font-medium",
            density === 'compact'
              ? "h-8 min-h-0 px-2.5 gap-1.5 text-xs"
              : "h-10 min-h-[44px] px-3 gap-2 text-xs sm:text-sm"
          )}
          aria-label="Toggle visible columns"
        >
          <SlidersHorizontal className={cn("shrink-0 text-muted-foreground", density === 'compact' ? "h-3.5 w-3.5" : "h-4 w-4")} />
          <span className="hidden sm:inline">Columns</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel className="text-xs">Toggle Columns</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {hideableColumns.map((col) => (
          <DropdownMenuCheckboxItem
            key={col.id}
            checked={visibleColumns[col.id] !== false}
            onCheckedChange={() => onToggleColumn(col.id)}
            className="min-h-[38px] text-sm touch-manipulation cursor-pointer"
          >
            {col.header}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ResponsiveDataTable<T>({
  data,
  columns,
  keyExtractor,
  isLoading = false,
  emptyState,
  onRowClick,
  renderMobileCard,
  className,
  cardClassName,
  defaultSort,
  showColumnSelector = true,
  headerExtra,
  density = 'default',
}: ResponsiveDataTableProps<T>) {
  // Column visibility state
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    columns.forEach((col) => {
      initial[col.id] = col.defaultHidden !== true;
    });
    return initial;
  });

  // Sort state
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: 'asc' | 'desc';
  } | null>(defaultSort || null);

  const toggleColumn = (id: string) => {
    setVisibleColumns((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleSort = (columnId: string) => {
    setSortConfig((prev) => {
      if (prev && prev.key === columnId) {
        if (prev.direction === 'asc') {
          return { key: columnId, direction: 'desc' };
        }
        return null; // reset
      }
      return { key: columnId, direction: 'asc' };
    });
  };

  // Filter columns to visible only
  const activeColumns = useMemo(
    () => columns.filter((col) => visibleColumns[col.id] !== false),
    [columns, visibleColumns]
  );

  // Sorted data
  const sortedData = useMemo(() => {
    if (!sortConfig) return data;
    const colDef = columns.find((c) => c.id === sortConfig.key);
    if (!colDef) return data;

    return [...data].sort((a, b) => {
      const aVal = colDef.accessorKey ? a[colDef.accessorKey] : undefined;
      const bVal = colDef.accessorKey ? b[colDef.accessorKey] : undefined;

      if (aVal === bVal) return 0;
      if (aVal === undefined || aVal === null) return 1;
      if (bVal === undefined || bVal === null) return -1;

      const compare = aVal < bVal ? -1 : 1;
      return sortConfig.direction === 'asc' ? compare : -compare;
    });
  }, [data, columns, sortConfig]);

  const defaultEmptyState = (
    <div className="py-12 text-center text-sm text-muted-foreground">
      No records found.
    </div>
  );

  const renderCellContent = (col: ColumnDef<T>, item: T, index: number) => {
    if (col.cell) {
      return col.cell(item, index);
    }
    if (col.accessorKey) {
      const val = item[col.accessorKey];
      if (val === null || val === undefined) return '—';
      return String(val);
    }
    return '—';
  };

  const isCompact = density === 'compact';

  return (
    <div className={cn(isCompact ? 'space-y-2' : 'space-y-3', 'min-w-0 w-full', className)}>
      {(showColumnSelector || headerExtra) && (
        <div className={cn("flex items-center justify-between gap-2 min-w-0", isCompact && "py-1.5")}>
          <div className="min-w-0 flex-1">{headerExtra}</div>
          {showColumnSelector && (
            <ColumnVisibilityPicker
              columns={columns}
              visibleColumns={visibleColumns}
              onToggleColumn={toggleColumn}
              density={density}
            />
          )}
        </div>
      )}

      {/* Desktop Table View (>= 768px) */}
      <div className="hidden md:block rounded-lg border bg-card text-card-foreground shadow-xs overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {activeColumns.map((col) => {
                const isSorted = sortConfig?.key === col.id;
                return (
                  <TableHead
                    key={col.id}
                    className={cn(
                      isCompact && 'h-8 py-1 px-2.5 sm:px-3 text-xs',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                      col.headerClassName
                    )}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        onClick={() => handleSort(col.id)}
                        className={cn(
                          'inline-flex items-center font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground touch-manipulation',
                          isCompact ? 'h-8 py-1 text-xs gap-1' : 'h-10 min-h-[44px] px-1 text-xs gap-1.5',
                          col.align === 'right' && 'ml-auto justify-end',
                          col.align === 'center' && 'mx-auto justify-center'
                        )}
                      >
                        <span>{col.header}</span>
                        {isSorted ? (
                          sortConfig?.direction === 'asc' ? (
                            <ArrowUp className="h-3.5 w-3.5 shrink-0 text-primary" />
                          ) : (
                            <ArrowDown className="h-3.5 w-3.5 shrink-0 text-primary" />
                          )
                        ) : (
                          <ArrowUpDown className="h-3.5 w-3.5 shrink-0 opacity-40 hover:opacity-100" />
                        )}
                      </button>
                    ) : (
                      <span className={cn(
                        "font-semibold uppercase tracking-wider text-muted-foreground inline-flex items-center",
                        isCompact ? 'h-8 py-1 text-xs' : 'text-xs'
                      )}>
                        {col.header}
                      </span>
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={activeColumns.length}
                  className="h-32 text-center text-sm text-muted-foreground"
                >
                  <div className="flex items-center justify-center gap-2">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    <span>Loading data...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : sortedData.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={activeColumns.length}
                  className="h-32 text-center"
                >
                  {emptyState || defaultEmptyState}
                </TableCell>
              </TableRow>
            ) : (
              sortedData.map((item, index) => (
                <TableRow
                  key={keyExtractor(item, index)}
                  onClick={() => onRowClick?.(item)}
                  className={cn(
                    'transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-muted/50 active:bg-muted/70'
                  )}
                >
                  {activeColumns.map((col) => (
                    <TableCell
                      key={col.id}
                      className={cn(
                        isCompact ? 'py-1.5 sm:py-2 px-2.5 sm:px-3 text-xs' : 'py-3.5 px-3',
                        col.align === 'right' && 'text-right',
                        col.align === 'center' && 'text-center',
                        col.className
                      )}
                    >
                      {renderCellContent(col, item, index)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Mobile Card-View Fallback (< 768px) */}
      <div className={cn("md:hidden", isCompact ? "space-y-2" : "space-y-3")}>
        {isLoading ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              <div className="flex items-center justify-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                <span>Loading data...</span>
              </div>
            </CardContent>
          </Card>
        ) : sortedData.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center">
              {emptyState || defaultEmptyState}
            </CardContent>
          </Card>
        ) : (
          sortedData.map((item, index) => {
            const key = keyExtractor(item, index);

            if (renderMobileCard) {
              return (
                <div 
                  key={key} 
                  onClick={() => onRowClick?.(item)}
                  className={cn(onRowClick && 'cursor-pointer touch-manipulation')}
                >
                  {renderMobileCard(item, index)}
                </div>
              );
            }

            // Default auto mobile card generator
            return (
              <Card
                key={key}
                onClick={() => onRowClick?.(item)}
                className={cn(
                  'touch-manipulation border bg-card transition-all active:scale-[0.99] active:bg-accent/50',
                  onRowClick && 'cursor-pointer',
                  cardClassName
                )}
              >
                <CardContent className={cn(isCompact ? "p-2.5 space-y-1.5" : "p-3.5 space-y-2.5")}>
                  {activeColumns.map((col) => (
                    <div
                      key={col.id}
                      className={cn(
                        'flex items-start justify-between gap-2',
                        isCompact ? 'text-xs' : 'text-sm',
                        col.align === 'right' && 'text-right'
                      )}
                    >
                      <span className="text-xs font-medium text-muted-foreground shrink-0">
                        {col.header}
                      </span>
                      <span className="font-normal text-foreground break-words min-w-0">
                        {renderCellContent(col, item, index)}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
