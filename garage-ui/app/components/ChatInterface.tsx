"use client";

import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
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
  hardware: ['What are you building?', 'Describe the fault...', 'Which component is suspect?'],
  investigative: ['What are you tracking?', 'Who or what is the subject?', 'Connect the threads...'],
  'self-improvement': ["What's on your mind?", 'How are you actually doing?', "What's the smallest next step?"],
  default: ['Say something.', 'What do you need?', 'Ask anything.'],
};

function getPlaceholder(mode: string): string {
  const pool = MODE_PLACEHOLDERS[mode] ?? MODE_PLACEHOLDERS.default;
  return pool[Math.floor(Date.now() / 60000) % pool.length];
}

const EMPTY_STATE: Record<string, { line1: string; line2: string }> = {
  hardware: { line1: 'BENCH READY', line2: 'Upload a schematic or describe the fault.' },
  investigative: { line1: 'OPTIC ONLINE', line2: 'Name a subject. Start the thread.' },
  'self-improvement': { line1: 'PRESENT', line2: "Hey. What's going on today?" },
  default: { line1: 'KITTY READY', line2: 'Ask anything.' },
};

/** Strip [Source](log://...) markers and return remaining plain text + pills */
function renderKittyMessage(text: string) {
  const sourcePillRe = /\[Source\]\(log:\/\/([^)]+)\)/g;
  const pills: { idx: number; entityId: string }[] = [];
  let clean = text.replace(sourcePillRe, (_, id) => {
    pills.push({ idx: pills.length, entityId: id });
    return '';
  }).trim();

  return (
    <>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold" style={{ color: 'var(--accent-color)' }}>{children}</strong>,
          em: ({ children }) => <em className="opacity-80">{children}</em>,
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-');
            return isBlock ? (
              <code className="block mt-2 mb-2 p-3 rounded text-xs font-mono overflow-x-auto" style={{ background: 'rgba(0,0,0,0.3)', color: '#F5EFE8' }}>{children}</code>
            ) : (
              <code className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: 'rgba(232,116,60,0.15)', color: 'var(--accent-color)' }}>{children}</code>
            );
          },
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 opacity-90">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 opacity-90">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => <h1 className="text-base font-bold mb-2 mt-3" style={{ color: 'var(--accent-color)' }}>{children}</h1>,
          h2: ({ children }) => <h2 className="text-sm font-bold mb-1 mt-2 uppercase tracking-wide opacity-80">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2">{children}</h3>,
          blockquote: ({ children }) => <blockquote className="border-l-2 pl-3 my-2 opacity-70 italic" style={{ borderColor: 'var(--accent-color)' }}>{children}</blockquote>,
          hr: () => <hr className="my-3 opacity-20" />,
          a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="underline opacity-80 hover:opacity-100" style={{ color: 'var(--accent-color)' }}>{children}</a>,
        }}
      >
        {clean}
      </ReactMarkdown>
      {pills.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {pills.map(p => <SourcePill key={p.idx} entityId={p.entityId} />)}
        </div>
      )}
    </>
  );
}

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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const getMascotState = (): 'idle' | 'thinking' | 'working' | 'error' => {
    if (systemHealth.websocket !== 'connected') return 'error';
    if (isAnalyzing || isStreaming) return 'working';
    if (Object.keys(activeNodes).length > 0) return 'thinking';
    return 'idle';
  };

  const empty = EMPTY_STATE[currentMode] ?? EMPTY_STATE.default;
  const placeholder = getPlaceholder(currentMode);

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ fontFamily: 'var(--font-sans, system-ui, sans-serif)' }}>

      {/* Mascot header */}
      <div
        className="h-14 border-b flex-shrink-0 flex items-center justify-center gap-3"
        style={{ borderColor: 'var(--border-color)', background: 'var(--panel-bg)' }}
      >
        <Mascot state={getMascotState()} isUnhinged={uiState === 'unhinged'} />
        <div className="flex flex-col items-start leading-tight">
          <span
            className={`text-base font-bold tracking-tight ${uiState === 'unhinged' ? 'unhinged-glitch' : ''}`}
            style={{ color: 'var(--accent-color)' }}
          >
            {uiState === 'unhinged' ? '⚠ KITTY [UNHINGED] ⚠' : 'Kitty'}
          </span>
          <span className="text-[10px] opacity-40 uppercase tracking-widest">
            {isStreaming ? 'thinking...' : currentMode}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4 no-scrollbar text-sm">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 select-none">
            <div className="opacity-30">
              <Mascot state="idle" />
            </div>
            <div className="text-center opacity-30">
              <div className="text-xs font-bold tracking-widest uppercase mb-1" style={{ color: 'var(--accent-color)' }}>
                {empty.line1}
              </div>
              <div className="text-xs" style={{ color: 'var(--dim-text)' }}>{empty.line2}</div>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isLast = idx === messages.length - 1;
            const isKitty = msg.role === 'kitty';
            const isPending = isKitty && isLast && msg.text === '' && isStreaming;

            return (
              <div key={idx} className={`flex ${isKitty ? 'justify-start' : 'justify-end'}`}>
                {isKitty ? (
                  <div
                    className="max-w-[90%] md:max-w-[80%] pl-4 pr-2 py-3 border-l-2 text-sm leading-relaxed"
                    style={{ borderColor: 'var(--accent-color)', color: 'var(--text-main)' }}
                  >
                    {isPending ? (
                      <span className="animate-pulse" style={{ color: 'var(--accent-color)' }}>▋</span>
                    ) : (
                      renderKittyMessage(msg.text)
                    )}
                  </div>
                ) : (
                  <div
                    className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm leading-relaxed"
                    style={{ backgroundColor: 'var(--accent-color)', color: '#fff' }}
                  >
                    {msg.text}
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Typing indicator */}
      <div
        className={`px-4 py-1 text-[10px] font-mono tracking-widest transition-opacity duration-300 ${isStreaming ? 'opacity-50' : 'opacity-0'}`}
        style={{ color: 'var(--accent-color)' }}
      >
        ● ● ●
      </div>

      {/* Input bar */}
      <form
        onSubmit={onSubmit}
        className="px-3 pb-3 pt-2 flex-shrink-0"
        style={{ borderTop: '1px solid var(--border-color)' }}
      >
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-2xl"
          style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)' }}
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: 'var(--text-main)' }}
            placeholder={placeholder}
            autoComplete="off"
            spellCheck={false}
            inputMode="text"
            enterKeyHint="send"
          />
          <button
            type="button"
            onClick={onVoiceToggle}
            className={`w-8 h-8 flex items-center justify-center rounded-full flex-shrink-0 transition-all text-base ${isRecording ? 'animate-pulse' : 'opacity-60 hover:opacity-100'}`}
            style={{ backgroundColor: isRecording ? '#c00' : 'transparent' }}
            title={isRecording ? 'Stop' : 'Voice'}
          >
            {isRecording ? '⏹' : '🎙'}
          </button>
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="w-8 h-8 flex items-center justify-center rounded-full flex-shrink-0 font-bold text-xs transition-all disabled:opacity-30"
            style={{ backgroundColor: 'var(--accent-color)', color: '#fff' }}
          >
            ↑
          </button>
        </div>
      </form>
    </div>
  );
});

ChatInterface.displayName = 'ChatInterface';

export default ChatInterface;
