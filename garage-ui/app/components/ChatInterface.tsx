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
  isStreaming: boolean;
  uiState: string;
  currentMode: string;
  systemHealth: {
    mlx_engine: string;
    memory_engine: string;
    websocket: string;
  };
  isAnalyzing: boolean;
  activeNodes: Record<string, any>;
}

const MODE_PLACEHOLDERS: Record<string, string[]> = {
  hardware: [
    'What are you building?',
    'Describe the fault...',
    'Which component is suspect?',
    'What does the schematic show?',
  ],
  investigative: [
    'What are you tracking?',
    'Who or what is the subject?',
    'What does the evidence say?',
    'Connect the threads...',
  ],
  'self-improvement': [
    "What's on your mind?",
    'How are you actually doing?',
    'What are you avoiding?',
    "What's the smallest next step?",
  ],
  default: [
    'Say something.',
    'What do you need?',
    'Ask anything.',
  ],
};

function getPlaceholder(mode: string): string {
  const pool = MODE_PLACEHOLDERS[mode] ?? MODE_PLACEHOLDERS.default;
  return pool[Math.floor(Date.now() / 60000) % pool.length];
}

const EMPTY_STATE: Record<string, { line1: string; line2: string }> = {
  hardware: {
    line1: '[ BENCH READY ]',
    line2: 'Upload a schematic or describe the fault.',
  },
  investigative: {
    line1: '[ OPTIC ONLINE ]',
    line2: 'Name a subject. Start the thread.',
  },
  'self-improvement': {
    line1: '[ PRESENT ]',
    line2: "Hey. What's going on today?",
  },
  default: {
    line1: '[ KITTY READY ]',
    line2: 'Ask anything.',
  },
};

const ChatInterface = React.memo(({
  messages,
  input,
  setInput,
  onSubmit,
  onVoiceToggle,
  isRecording,
  isStreaming,
  uiState,
  currentMode,
  systemHealth,
  isAnalyzing,
  activeNodes,
}: ChatInterfaceProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const renderMessage = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\[Source\]\(log:\/\/[^)]+\))/);
    return parts.map((part, idx) => {
      if (part.startsWith('[Source]')) {
        const match = part.match(/log:\/\/([^)]+)/);
        return <SourcePill key={idx} entityId={match ? match[1] : 'unknown'} />;
      }
      return <span key={idx} className="whitespace-pre-wrap">{part}</span>;
    });
  };

  const getMascotState = (): 'idle' | 'thinking' | 'working' | 'error' => {
    if (systemHealth.websocket !== 'connected') return 'error';
    if (isAnalyzing || isStreaming) return 'working';
    if (Object.keys(activeNodes).length > 0) return 'thinking';
    return 'idle';
  };

  const empty = EMPTY_STATE[currentMode] ?? EMPTY_STATE.default;
  const placeholder = getPlaceholder(currentMode);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Mascot Header */}
      <div
        className="h-14 border-b flex-shrink-0 flex items-center justify-center gap-3"
        style={{ borderColor: 'var(--accent-color)' }}
      >
        <Mascot state={getMascotState()} isUnhinged={uiState === 'unhinged'} />
        <span
          className={`text-lg font-black tracking-tighter ${uiState === 'unhinged' ? 'unhinged-glitch' : ''}`}
          style={{ color: 'var(--accent-color)', filter: 'var(--mascot-filter)' }}
        >
          {uiState === 'unhinged' ? '⚠ KITTY [UNHINGED] ⚠' : 'KITTY'}
        </span>
      </div>

      {/* Chat stream */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-3 font-mono text-[var(--font-size-base)] no-scrollbar">
        {messages.length === 0 ? (
          /* Empty state — mode-aware */
          <div className="h-full flex flex-col items-center justify-center gap-2 opacity-20 select-none">
            <div className="text-xs font-bold tracking-widest" style={{ color: 'var(--accent-color)' }}>
              {empty.line1}
            </div>
            <div className="text-xs">{empty.line2}</div>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isLast = idx === messages.length - 1;
            const isKitty = msg.role === 'kitty';
            const isPending = isKitty && isLast && msg.text === '' && isStreaming;

            return (
              <div
                key={idx}
                className={`flex ${isKitty ? 'justify-start' : 'justify-end'}`}
              >
                {isKitty ? (
                  /* Kitty bubble: no background, accent left border */
                  <div
                    className="max-w-[88%] pl-3 pr-1 py-2 border-l-2 text-[var(--text-main)]"
                    style={{ borderColor: 'var(--accent-color)' }}
                  >
                    {isPending ? (
                      <span className="animate-pulse opacity-60" style={{ color: 'var(--accent-color)' }}>
                        ▋
                      </span>
                    ) : (
                      renderMessage(msg.text)
                    )}
                  </div>
                ) : (
                  /* User bubble: right-aligned, glass */
                  <div className="max-w-[80%] px-3 py-2 rounded bg-white bg-opacity-10 text-[var(--text-main)]">
                    {msg.text}
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Streaming status */}
      <div
        className={`px-4 py-1 text-[10px] font-mono tracking-widest transition-opacity duration-300 ${isStreaming ? 'opacity-60' : 'opacity-0'}`}
        style={{ color: 'var(--accent-color)' }}
      >
        KITTY PROCESSING...
      </div>

      {/* Input bar */}
      <form
        onSubmit={onSubmit}
        className="p-4 border-t flex gap-2 flex-shrink-0"
        style={{ borderColor: 'var(--accent-color)' }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          className="flex-1 bg-transparent border-b outline-none px-2 font-mono text-[var(--font-size-base)]"
          style={{ borderColor: 'var(--accent-color)', color: 'var(--text-main)' }}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          inputMode="text"
          enterKeyHint="send"
        />
        <button
          type="button"
          onClick={onVoiceToggle}
          className={`px-3 py-2 rounded font-bold text-sm transition-all ${isRecording ? 'animate-pulse' : ''}`}
          style={{
            backgroundColor: isRecording ? '#c00' : 'transparent',
            color: 'var(--accent-color)',
            border: '1px solid var(--accent-color)',
          }}
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? '⏹' : '🎙'}
        </button>
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          className="px-4 py-2 rounded font-bold text-sm transition-all disabled:opacity-40"
          style={{ backgroundColor: 'var(--accent-color)', color: 'var(--bg-color)' }}
        >
          SEND
        </button>
      </form>
    </div>
  );
});

ChatInterface.displayName = 'ChatInterface';

export default ChatInterface;
