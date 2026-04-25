"use client";

import React, { useState, useEffect, useRef } from 'react';

interface Command {
  id: string;
  label: string;
  description: string;
  action: () => void;
  category: 'system' | 'mode' | 'action';
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onExecuteCommand: (command: string) => void;
  onViewChange?: (view: 'chat' | 'journal') => void;
  currentMode: string;
}

export default function CommandPalette({ isOpen, onClose, onExecuteCommand, onViewChange, currentMode }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Command[] = [
    // System Commands
    { id: 'vibe', label: '/vibe', description: 'Check current system vibe', action: () => onExecuteCommand('/vibe'), category: 'system' },
    { id: 'status', label: '/status', description: 'Show system status', action: () => onExecuteCommand('/status'), category: 'system' },
    { id: 'brief', label: '/brief', description: 'Morning briefing', action: () => onExecuteCommand('/brief'), category: 'system' },
    { id: 'stuck', label: '/stuck', description: 'ADHD rescue protocol', action: () => onExecuteCommand('/stuck'), category: 'system' },
    
    // Mode Commands
    { id: 'hardware', label: '/bench hardware', description: 'Switch to hardware mode', action: () => onExecuteCommand('/bench hardware'), category: 'mode' },
    { id: 'investigative', label: '/bench investigative', description: 'Switch to investigative mode', action: () => onExecuteCommand('/bench investigative'), category: 'mode' },
    { id: 'self-improvement', label: '/bench self', description: 'Switch to self-improvement mode', action: () => onExecuteCommand('/bench self'), category: 'mode' },
    
    // Action Commands
    { id: 'search', label: '/deepsearch', description: 'Deep web search', action: () => onExecuteCommand('/deepsearch '), category: 'action' },
    { id: 'screen', label: '/screen', description: 'Capture and analyze screen', action: () => onExecuteCommand('/screen'), category: 'action' },
    { id: 'council', label: '/council', description: 'Assemble expert council', action: () => onExecuteCommand('/council '), category: 'action' },
  ];

  const filteredCommands = commands.filter(cmd => 
    cmd.label.toLowerCase().includes(query.toLowerCase()) ||
    cmd.description.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery(''); // Clear query when opening
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action();
          onClose();
        }
        break;
      case 'Escape':
        onClose();
        break;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-start justify-center pt-32 z-50">
      <div className="rounded-lg shadow-2xl w-full max-w-2xl mx-4" style={{
        backgroundColor: 'var(--panel-bg)',
        borderColor: 'var(--accent-color)',
        border: '1px solid var(--accent-color)'
      }}>
        <div className="p-4 border-b" style={{borderColor: 'var(--border-color)'}}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command..."
            className="w-full bg-transparent text-lg outline-none"
            style={{color: 'var(--text-main)'}}
          />
        </div>
        
        <div className="max-h-96 overflow-y-auto">
          {filteredCommands.length === 0 ? (
            <div className="p-4 text-center opacity-50">No commands found</div>
          ) : (
            filteredCommands.map((command, index) => (
              <div
                key={command.id}
                className={`p-3 cursor-pointer border-l-2 ${
                  index === selectedIndex 
                    ? 'bg-white bg-opacity-10' 
                    : 'border-transparent hover:bg-white hover:bg-opacity-5'
                }`}
                style={{
                  borderLeftColor: index === selectedIndex ? 'var(--accent-color)' : 'transparent'
                }}
                onClick={() => {
                  command.action();
                  onClose();
                }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-mono text-sm" style={{color: 'var(--accent-color)'}}>
                      {command.label}
                    </div>
                    <div className="text-xs opacity-70 mt-1">
                      {command.description}
                    </div>
                  </div>
                  <div className="text-xs opacity-40 uppercase">
                    {command.category}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        
        <div className="p-3 border-t text-xs opacity-50 flex items-center justify-between" style={{borderColor: 'var(--border-color)'}}>
          <span>↑↓ Navigate • Enter Execute • Esc Close</span>
          <span>Mode: {currentMode.toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
}
