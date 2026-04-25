"use client";

import React from 'react';

interface Suggestion {
  label: string;
  action: string;
  description?: string;
}

interface SuggestionSidebarProps {
  domain: string;
  onAction: (action: string) => void;
}

const suggestionsMap: Record<string, Suggestion[]> = {
  electronics: [
    { label: "Generate BOM", action: "generate_bom", description: "Create Bill of Materials CSV" },
    { label: "Trace signal path", action: "trace_signal", description: "Map circuit connectivity" },
    { label: "Find all capacitors", action: "find_capacitors", description: "Highlight caps in SVG" }
  ],
  investigative: [
    { label: "Expand network", action: "expand_network", description: "Search for related entities" },
    { label: "Cross-reference", action: "crossref", description: "Link findings with archives" }
  ],
  default: [
    { label: "Open schematic", action: "open_schematic", description: "Load PDF for analysis" },
    { label: "Run diagnostics", action: "run_diagnostics", description: "Check system health" }
  ]
};

export default function SuggestionSidebar({ domain, onAction }: SuggestionSidebarProps) {
  const suggestions = suggestionsMap[domain] || suggestionsMap.default;

  return (
    <div className="flex flex-col gap-3 p-4 rounded-lg bg-white bg-opacity-5 border border-white border-opacity-10 mt-4">
      <h3 className="label text-[10px] opacity-50 uppercase tracking-widest">You could also…</h3>
      <div className="flex flex-col gap-2">
        {suggestions.map((s) => (
          <button
            key={s.action}
            onClick={() => onAction(s.action)}
            className="flex flex-col text-left p-2 rounded transition-all hover:bg-white hover:bg-opacity-10 group"
          >
            <span className="text-xs font-bold group-hover:text-orange-500 transition-colors" style={{ color: 'var(--accent-color)' }}>
              {s.label}
            </span>
            {s.description && (
              <span className="text-[10px] opacity-50 mt-1">
                {s.description}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
