"use client";

import React from 'react';

interface MascotProps {
  state: 'idle' | 'thinking' | 'working' | 'error';
  isUnhinged?: boolean;
}

export default function Mascot({ state, isUnhinged }: MascotProps) {
  // Use CSS variables for colors where possible
  const getPrimaryColor = () => {
    if (state === 'error') return '#ff4444';
    // We still allow JS overrides for specific states, but prefer var(--accent-color)
    return 'var(--accent-color)';
  };

  const color = getPrimaryColor();

  return (
    <div className="relative w-8 h-8 md:w-10 md:h-10 flex items-center justify-center flex-shrink-0 transition-all">
      {/* Outer Glow / Aura */}
      <div 
        className={`absolute inset-0 rounded-full blur-md opacity-20 transition-all duration-500 ${
          state === 'thinking' ? 'animate-pulse' : 
          state === 'working' ? 'animate-ping' : 
          state === 'error' ? 'bg-red-500 opacity-40' : ''
        }`}
        style={{ backgroundColor: color }}
      />

      {/* Mascot Body (Abstract Hexagon/Circle) */}
      <div 
        className={`relative w-7 h-7 md:w-8 md:h-8 border-2 rounded flex items-center justify-center transition-all duration-300 ${
          isUnhinged ? 'unhinged-glitch' : ''
        } ${state === 'working' ? 'rotate-45' : ''}`}
        style={{ borderColor: color, boxShadow: `0 0 10px ${color}44` }}
      >
        {/* Eyes */}
        <div className="flex gap-1.5">
          <div 
            className={`w-1 h-1 rounded-full transition-all duration-300 ${
              state === 'thinking' ? 'animate-bounce' : 
              state === 'error' ? 'h-0.5 w-2' : ''
            }`}
            style={{ backgroundColor: color, boxShadow: `0 0 5px ${color}` }}
          />
          <div 
            className={`w-1 h-1 rounded-full transition-all duration-300 ${
              state === 'thinking' ? 'animate-bounce delay-75' : 
              state === 'error' ? 'h-0.5 w-2' : ''
            }`}
            style={{ backgroundColor: color, boxShadow: `0 0 5px ${color}` }}
          />
        </div>

        {/* Scanning Line (Thinking Mode) */}
        {state === 'thinking' && (
          <div 
            className="absolute inset-x-0 h-0.5 opacity-50 animate-scan"
            style={{ backgroundColor: color }}
          />
        )}
      </div>

      <style jsx>{`
        @keyframes scan {
          0% { top: 0; }
          100% { top: 100%; }
        }
        .animate-scan {
          animation: scan 1.5s linear infinite;
        }
        .delay-75 {
          animation-delay: 0.1s;
        }
      `}</style>
    </div>
  );
}
