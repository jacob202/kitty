"use client";

import React, { useState, useEffect, createContext, useContext, useCallback, ReactNode } from 'react';

type ToastType = 'info' | 'success' | 'warning' | 'error';

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'info', duration = 3000) => {
    const id = Math.random().toString(36).substring(7);
    setToasts(prev => [...prev, { id, message, type, duration }]);
    setTimeout(() => removeToast(id), duration);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-2 rounded shadow-lg text-sm font-medium transition-all animate-in slide-in-from-right duration-300 ${
              t.type === 'error' ? 'bg-red-600 text-white' :
              t.type === 'success' ? 'bg-green-600 text-white' :
              t.type === 'warning' ? 'bg-yellow-600 text-black' :
              'bg-[#241E1A] text-[#F5EFE8] border border-[#3D3028]'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
