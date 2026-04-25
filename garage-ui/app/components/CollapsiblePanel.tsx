"use client";

import React, { ReactNode } from 'react';

interface CollapsiblePanelProps {
  id: string;
  isCollapsed: boolean;
  onToggle: () => void;
  widthVar: string; // e.g. "--sidebar-width"
  expandedWidth: string; // e.g. "240px"
  side: 'left' | 'right';
  title?: string;
  children: ReactNode;
  className?: string;
}

export default function CollapsiblePanel({
  id,
  isCollapsed,
  onToggle,
  widthVar,
  expandedWidth,
  side,
  title,
  children,
  className = ""
}: CollapsiblePanelProps) {
  return (
    <div 
      className={`relative h-full flex flex-col border-color transition-all duration-300 ease-in-out ${className}`}
      style={{ 
        width: `var(${widthVar})`,
        borderRight: side === 'left' ? '1px solid var(--border-color)' : 'none',
        borderLeft: side === 'right' ? '1px solid var(--border-color)' : 'none',
        overflow: 'hidden',
        flexShrink: 0
      } as React.CSSProperties}
    >
      {/* Header / Toggle area */}
      <div className="flex items-center justify-between p-2 h-12 border-b border-color bg-panel-bg">
        {!isCollapsed && title && (
          <span className="font-mono text-xs uppercase tracking-wider opacity-60 ml-2">
            {title}
          </span>
        )}
        <button 
          onClick={onToggle}
          className={`p-1 hover:bg-white hover:bg-opacity-5 rounded transition-transform ${isCollapsed ? 'mx-auto' : 'ml-auto'}`}
          title={isCollapsed ? "Expand" : "Collapse"}
        >
          {side === 'left' ? (
            isCollapsed ? '→' : '←'
          ) : (
            isCollapsed ? '←' : '→'
          )}
        </button>
      </div>

      {/* Content */}
      <div className={`flex-1 overflow-y-auto ${isCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'} transition-opacity duration-200`}>
        {children}
      </div>

      {/* CSS variable injection/update logic is handled by the parent in globals.css or inline style on the root */}
      <style jsx>{`
        .border-color {
          border-color: var(--border-color);
        }
        .bg-panel-bg {
          background-color: var(--panel-bg);
        }
      `}</style>
    </div>
  );
}
