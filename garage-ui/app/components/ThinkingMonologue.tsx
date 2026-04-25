"use client";

import React from 'react';

export interface Thought {
  id: string;
  message: string;
  node?: string;
  status: 'thinking' | 'resolved';
}

interface ThinkingMonologueProps {
  thoughts: Thought[];
}

const ThinkingMonologue = React.memo(({ thoughts }: ThinkingMonologueProps) => {
  if (thoughts.length === 0) return null;

  return (
    <div className="space-y-2 mb-6">
      <h3 className="label text-[9px] mb-2 opacity-50 uppercase tracking-tighter">Cognitive Stream</h3>
      <div className="flex flex-col gap-1.5">
        {thoughts.map((thought) => (
          <div 
            key={thought.id} 
            className="thinking-bubble p-2 bg-white bg-opacity-5 rounded border-l-2 text-[10px] leading-tight"
            style={{ borderLeftColor: 'var(--accent-color)' }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="opacity-40 font-mono text-[8px] uppercase">{thought.node || 'core'}</span>
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" style={{ backgroundColor: 'var(--accent-color)' }}></span>
            </div>
            <div className="opacity-80 italic">
              "{thought.message}"
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});

ThinkingMonologue.displayName = 'ThinkingMonologue';

export default ThinkingMonologue;
