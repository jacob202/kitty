"use client";

import React from 'react';

interface SourcePillProps {
  entityId: string;
}

export default function SourcePill({ entityId }: SourcePillProps) {
  return (
    <a 
      href={`/api/source/${entityId}`} 
      target="_blank" 
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-orange-500 bg-opacity-20 border border-orange-500 border-opacity-30 text-[10px] font-mono hover:bg-opacity-40 transition-all no-underline"
      style={{ color: 'var(--accent-color)', borderColor: 'var(--accent-color)' }}
    >
      <span className="opacity-70">📄</span>
      <span>SOURCE_{entityId.substring(0, 6).toUpperCase()}</span>
    </a>
  );
}
