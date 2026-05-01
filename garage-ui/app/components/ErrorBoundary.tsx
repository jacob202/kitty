"use client";

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center bg-[#1A1614] text-[#F5EFE8]">
          <div className="max-w-md p-8 rounded-lg border border-[#E8743C] bg-[#241E1A] shadow-2xl">
            <h1 className="text-2xl font-bold text-[#E8743C] mb-4">SYSTEM MALFUNCTION</h1>
            <p className="mb-6 opacity-80">
              Kitty has encountered a component-level error. The neural link remains active, but the interface needs a reset.
            </p>
            <div className="text-left bg-black bg-opacity-30 p-4 rounded mb-6 overflow-auto max-h-40">
              <code className="text-xs text-red-400 font-mono">
                {this.state.error?.toString()}
              </code>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-[#E8743C] text-white rounded font-bold hover:bg-[#D4622A] transition-colors"
            >
              REBOOT INTERFACE
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
