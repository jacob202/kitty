import { useState, useCallback, useRef, useEffect } from 'react';

const RECORDING_MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4;codecs=mp4a.40.2',
  'audio/mp4',
  'audio/wav',
];

export function useVoiceRecording(onDataAvailable?: (blob: Blob) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [mimeType, setMimeType] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (typeof window !== 'undefined' && typeof MediaRecorder !== 'undefined') {
      const supported = RECORDING_MIME_CANDIDATES.find(type => MediaRecorder.isTypeSupported(type));
      setMimeType(supported || '');
    }
  }, []);

  const startRecording = useCallback(() => {
    if (!mimeType || typeof window === 'undefined') return;

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        const recorder = new MediaRecorder(stream, { mimeType });
        mediaRecorderRef.current = recorder;
        chunksRef.current = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            chunksRef.current.push(e.data);
          }
        };

        recorder.onstop = () => {
          const blob = new Blob(chunksRef.current, { type: mimeType });
          onDataAvailable?.(blob);
          stream.getTracks().forEach(track => track.stop());
        };

        recorder.start(100);
        setIsRecording(true);
      });
  }, [mimeType, onDataAvailable]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  return {
    isRecording,
    mimeType,
    startRecording,
    stopRecording,
  };
}

export function extensionForMimeType(mimeType: string): string {
  const normalized = mimeType.toLowerCase();
  if (normalized.includes('mp4')) return 'mp4';
  if (normalized.includes('wav')) return 'wav';
  return 'webm';
}