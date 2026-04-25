"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Density = 'compact' | 'comfortable';

interface DensityContextType {
  density: Density;
  setDensity: (d: Density) => void;
  toggleDensity: () => void;
}

const DensityContext = createContext<DensityContextType | undefined>(undefined);

export function DensityProvider({ children }: { children: ReactNode }) {
  const [density, setDensity] = useState<Density>('comfortable');

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('kitty-ui-density');
    if (saved === 'compact' || saved === 'comfortable') {
      setDensity(saved);
    }
  }, []);

  // Save to localStorage when changed
  useEffect(() => {
    localStorage.setItem('kitty-ui-density', density);
    document.body.setAttribute('data-density', density);
  }, [density]);

  const toggleDensity = () => {
    setDensity(prev => prev === 'compact' ? 'comfortable' : 'compact');
  };

  return (
    <DensityContext.Provider value={{ density, setDensity, toggleDensity }}>
      {children}
    </DensityContext.Provider>
  );
}

export function useDensity() {
  const context = useContext(DensityContext);
  if (context === undefined) {
    throw new Error('useDensity must be used within a DensityProvider');
  }
  return context;
}
