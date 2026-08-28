import React, { Component, type ReactNode } from 'react';
import { recordComponentError } from '@/lib/telemetry';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  componentName?: string;
}

interface State {
  hasError: boolean;
  errorClass: string;
}

/**
 * TelemetryErrorBoundary – wraps child subtrees to catch render errors.
 *
 * On error, records the error class and component name to the backend
 * telemetry pipeline. Does NOT record error messages (which may contain PII).
 */
export class TelemetryErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorClass: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorClass: error?.constructor?.name ?? 'Error',
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    const errorClass = error?.constructor?.name ?? 'Error';
    const component =
      this.props.componentName ??
      // Extract first display name from component stack – never includes user data
      info.componentStack?.trim()?.split('\n')?.[1]?.trim()?.split(' ')?.[1] ??
      'Unknown';

    recordComponentError(errorClass, component);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
            <strong>Something went wrong.</strong>
            <p className="mt-1 text-xs text-red-500">
              This error has been logged. Please reload the page or contact support.
            </p>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

export default TelemetryErrorBoundary;
