import * as React from "react";
import { Check, AlertCircle, RefreshCw, Cloud } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type SaveState = "idle" | "saving" | "saved" | "failed";

interface AutoSaveStatusProps {
  state: SaveState;
  onRetry?: () => void;
}

export function AutoSaveStatus({ state, onRetry }: AutoSaveStatusProps) {
  switch (state) {
    case "saving":
      return (
        <Badge variant="secondary" className="flex items-center gap-1.5 py-1 px-2.5 text-xs text-muted-foreground animate-pulse">
          <RefreshCw className="h-3 w-3 animate-spin text-primary" />
          <span>Saving...</span>
        </Badge>
      );
    case "saved":
      return (
        <Badge variant="outline" className="flex items-center gap-1.5 py-1 px-2.5 text-xs border-green-500 bg-green-500/10 text-green-700 dark:text-green-400">
          <Check className="h-3 w-3" />
          <span>Saved</span>
        </Badge>
      );
    case "failed":
      return (
        <div className="flex items-center gap-2">
          <Badge variant="destructive" className="flex items-center gap-1.5 py-1 px-2.5 text-xs">
            <AlertCircle className="h-3 w-3" />
            <span>Save failed</span>
          </Badge>
          {onRetry && (
            <Button
              variant="outline"
              size="xs"
              onClick={onRetry}
              className="h-7 px-2 text-xs flex items-center gap-1 hover:bg-muted"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          )}
        </div>
      );
    case "idle":
    default:
      return (
        <Badge variant="outline" className="flex items-center gap-1.5 py-1 px-2.5 text-xs text-muted-foreground">
          <Cloud className="h-3 w-3" />
          <span>Saved</span>
        </Badge>
      );
  }
}
