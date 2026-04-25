"use client";

import React from 'react';
import ThinkingMonologue, { Thought } from './ThinkingMonologue';
import SuggestionSidebar from './SuggestionSidebar';

interface SidebarProps {
  currentMode: string;
  systemHealth: {
    mlx_engine: string;
    memory_engine: string;
    websocket: string;
  };
  thoughts: Thought[];
  onAction: (action: string) => void;
}

const Sidebar = React.memo(({ currentMode, systemHealth, thoughts, onAction }: SidebarProps) => {
  return (
    <div className="flex flex-col gap-4 p-4 h-full">
      <div className="flex-1 overflow-y-auto no-scrollbar relative">
        <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--accent-color)' }}>THE BENCH</h2>
        <p className="text-sm opacity-70 mb-4">Active Project: Orange Lab PKA</p>
        
        {/* Enhanced Thinking Monologue (Stack of thoughts) */}
        <ThinkingMonologue thoughts={thoughts} />

        <div className="mt-8">
          <h3 className="label text-[9px] mb-2 opacity-50 uppercase">Capabilities</h3>
          <ul className="text-xs space-y-2 opacity-70">
            <li className="flex items-center gap-2">
              <span className={`w-1 h-1 rounded-full ${systemHealth.mlx_engine === 'active' ? 'bg-green-400' : 'bg-red-400'}`}></span>
              Intent Routing (MLX)
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-blue-400"></span>
              Schematic Mapping (Vision)
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-purple-400"></span>
              Investigative Graph (DuckDB)
            </li>
            <li className="flex items-center gap-2">
              <span className={`w-1 h-1 rounded-full ${systemHealth.memory_engine === 'active' ? 'bg-green-400' : 'bg-red-400'}`}></span>
              Memory Engine (SQLite-Vec)
            </li>
          </ul>
        </div>
        
        <SuggestionSidebar 
          domain={currentMode === 'hardware' ? 'electronics' : currentMode} 
          onAction={onAction}
        />
      </div>
    </div>
  );
});

Sidebar.displayName = 'Sidebar';

export default Sidebar;
