import { useEffect, useRef, useCallback, useState } from 'react';

const SSE_URL = '/proxy/stream';
const RECONNECT_DELAY_MS = 3000;

export type SSEStatus = 'connecting' | 'open' | 'closed';

export interface UseSSEOptions {
  onStateUpdated?: () => void;
}

export function useSSE({ onStateUpdated }: UseSSEOptions) {
  const [status, setStatus] = useState<SSEStatus>('connecting');
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    setStatus('connecting');
    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => setStatus('open');

    es.onmessage = (event) => {
      if (event.data === 'state_updated' && onStateUpdated) {
        onStateUpdated();
      }
    };

    es.onerror = () => {
      setStatus('closed');
      es.close();
      esRef.current = null;
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };
  }, [onStateUpdated]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  return status;
}
