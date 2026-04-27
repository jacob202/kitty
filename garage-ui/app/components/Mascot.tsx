"use client";

import React from 'react';

interface MascotProps {
  state: 'idle' | 'thinking' | 'working' | 'error';
  isUnhinged?: boolean;
}

export default function Mascot({ state, isUnhinged }: MascotProps) {
  const isActive = state === 'thinking' || state === 'working';

  return (
    <div
      className={`relative flex-shrink-0 transition-all duration-300 ${isUnhinged ? 'unhinged-glitch' : ''} ${isActive ? 'animate-pulse' : ''}`}
      style={{ width: 40, height: 40 }}
    >
      {isActive && (
        <div
          className="absolute inset-0 rounded-full blur-lg opacity-25"
          style={{ backgroundColor: '#E8743C', transform: 'scale(1.5)' }}
        />
      )}
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="40" height="40">
        {/* Ears */}
        <polygon points="15,38 25,14 35,38" fill="#E8743C"/>
        <polygon points="45,38 55,14 65,38" fill="#E8743C"/>
        {/* Inner ears */}
        <polygon points="19,36 25,20 31,36" fill="#F5A87C"/>
        <polygon points="49,36 55,20 61,36" fill="#F5A87C"/>
        {/* Head */}
        <circle cx="40" cy="48" r="26" fill="#E8743C"/>
        {/* Muzzle */}
        <ellipse cx="40" cy="52" rx="14" ry="10" fill="#F5A87C" opacity="0.6"/>

        {/* Eyes — state-based */}
        {state === 'error' ? (
          <>
            {/* X eyes */}
            <line x1="26" y1="40" x2="36" y2="50" stroke="#1A1614" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="36" y1="40" x2="26" y2="50" stroke="#1A1614" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="44" y1="40" x2="54" y2="50" stroke="#1A1614" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="54" y1="40" x2="44" y2="50" stroke="#1A1614" strokeWidth="2.5" strokeLinecap="round"/>
          </>
        ) : state === 'thinking' ? (
          <>
            {/* Half-closed / squinting */}
            <ellipse cx="31" cy="44" rx="5" ry="3" fill="#1A1614"/>
            <ellipse cx="49" cy="44" rx="5" ry="5.5" fill="#1A1614"/>
            <circle cx="51" cy="42" r="1.5" fill="white"/>
          </>
        ) : state === 'working' ? (
          <>
            {/* Wide alert */}
            <ellipse cx="31" cy="44" rx="5.5" ry="6" fill="#1A1614"/>
            <ellipse cx="49" cy="44" rx="5.5" ry="6" fill="#1A1614"/>
            <circle cx="33" cy="42" r="1.8" fill="white"/>
            <circle cx="51" cy="42" r="1.8" fill="white"/>
          </>
        ) : (
          <>
            {/* Normal */}
            <ellipse cx="31" cy="44" rx="5" ry="5.5" fill="#1A1614"/>
            <ellipse cx="49" cy="44" rx="5" ry="5.5" fill="#1A1614"/>
            <circle cx="33" cy="42" r="1.5" fill="white"/>
            <circle cx="51" cy="42" r="1.5" fill="white"/>
          </>
        )}

        {/* Nose */}
        <polygon points="40,51 37,55 43,55" fill="#C45A2A"/>
        {/* Mouth */}
        <path d="M37,55 Q40,58 43,55" stroke="#C45A2A" strokeWidth="1.2" fill="none" strokeLinecap="round"/>
        {/* Whiskers */}
        <line x1="14" y1="51" x2="30" y2="53" stroke="#1A1614" strokeWidth="1" opacity="0.4"/>
        <line x1="14" y1="55" x2="30" y2="55" stroke="#1A1614" strokeWidth="1" opacity="0.4"/>
        <line x1="66" y1="51" x2="50" y2="53" stroke="#1A1614" strokeWidth="1" opacity="0.4"/>
        <line x1="66" y1="55" x2="50" y2="55" stroke="#1A1614" strokeWidth="1" opacity="0.4"/>
      </svg>
    </div>
  );
}
