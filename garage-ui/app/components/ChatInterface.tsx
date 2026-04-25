"use client";

import React, { useRef, useEffect } from 'react';
import Mascot from './Mascot';
import SourcePill from './SourcePill';

interface ChatInterfaceProps {
  messages: { role: string; text: string }[];
  input: string;
  setInput: (s: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onVoiceToggle: () => void;
  isRecording: boolean;
  uiState: string;
  systemHealth: {
    mlx_engine: string;
    memory_engine: string;
    websocket: string;
  };
  isAnalyzing: boolean;
  activeNodes: Record<string, any>;
}

const ChatInterface = React.memo(({
  messages,
  input,
  setInput,
  onSubmit,
  onVoiceToggle,
  isRecording,
  uiState,
  systemHealth,
  isAnalyzing,
  activeNodes
}: ChatInterfaceProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const renderMessage = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\[Source\]\(log:\/\/[^)]+\))/);
    return parts.map((part, idx) => {
      if (part.startsWith('[Source]')) {
        const match = part.match(/log:\/\/([^)]+)/);
        const id = match ? match[1] : 'unknown';
        return <SourcePill key={idx} entityId={id} />;
      }
      return <span key={idx} className="whitespace-pre-wrap">{part}</span>;
    });
  };

  const getMascotState = (): 'idle' | 'thinking' | 'working' | 'error' => {
    if (systemHealth.websocket !== 'connected') return 'error';
    if (isAnalyzing) return 'working';
    if (Object.keys(activeNodes).length > 0) return 'thinking';
    return 'idle';
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Mascot Header */}
      <div className="h-16 border-b flex-shrink-0 flex items-center justify-center gap-4" style={{ borderColor: 'var(--accent-color)' }}>
        <Mascot state={getMascotState()} isUnhinged={uiState === 'unhinged'} />
        <span className={`text-xl font-black ${uiState === 'unhinged' ? 'unhinged-glitch' : ''}`} style={{ color: 'var(--accent-color)', filter: 'var(--mascot-filter)' }}>
          {uiState === 'unhinged' ? '⚠ KITTY [UNHINGED] ⚠' : 'KITTY [FOCUSED]'}
        </span>
      </div>

      {/* Chat Stream */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 font-mono text-[var(--font-size-base)] no-scrollbar">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-[var(--bubble-padding)] rounded ${msg.role === 'user' ? 'bg-opacity-20 bg-white' : 'border border-[var(--accent-color)]'}`}>
              {msg.role === 'kitty' ? renderMessage(msg.text) : msg.text}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={onSubmit} className="p-4 border-t flex gap-2" style={{ borderColor: 'var(--accent-color)' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-transparent border-b outline-none px-2 font-mono text-[var(--font-size-base)]"
          style={{ borderColor: 'var(--accent-color)', color: 'var(--text-main)' }}
          placeholder="Inject query..."
        />
        <button
          type="button"
          onClick={onVoiceToggle}
          className={`px-3 py-2 rounded font-bold transition-all text-sm ${isRecording ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: isRecording ? '#ff3333' : 'transparent', color: 'var(--accent-color)', border: '1px solid var(--accent-color)' }}
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? '⏹' : '🎙'}
        </button>
        <button type="submit" className="px-4 py-2 rounded font-bold transition-all text-sm" style={{ backgroundColor: 'var(--accent-color)', color: 'var(--bg-color)' }}>
          EXECUTE
        </button>
      </form>
    </div>
  );
});

ChatInterface.displayName = 'ChatInterface';

export default ChatInterface;
