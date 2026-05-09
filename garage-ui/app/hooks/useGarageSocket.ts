import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';

export function useGarageSocket(onMessage?: (data: any) => void) {
  const socketRef = useRef<any>(null);
  
  useEffect(() => {
    const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const socket = io(`http://${backendHost}:5001`);
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[Garage] Socket connected');
    });

    socket.on('disconnect', () => {
      console.log('[Garage] Socket disconnected');
    });

    if (onMessage) {
      socket.on('message', onMessage);
      socket.on('node_status', onMessage);
    }

    return () => {
      socket.disconnect();
    };
  }, [onMessage]);

  return socketRef;
}