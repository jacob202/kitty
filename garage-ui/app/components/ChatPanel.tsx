"use client";

import { useState, useCallback } from 'react';
import ChatInterface from './components/ChatInterface';
import { useToast } from './components/Toast';

interface ChatPanelProps {
  messages: { role: string; text: string }[];
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  isRecording: boolean;
  isStreaming: boolean;
  uiState: string;
  currentMode: string;
  systemHealth: any;
  isAnalyzing: boolean;
  activeNodes: Record<string, any>;
  executeCommand: (command: string) => void;
  handleVoiceToggle: () => Promise<void>;
  handleSubmit: (e: React.FormEvent) => void;
  handleSchematicUpload: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  toggleDensity: () => void;
  density: string;
}

export function ChatPanel({
  messages,
  input,
  setInput,
  isRecording,
  isStreaming,
  uiState,
  currentMode,
  systemHealth,
  isAnalyzing,
  activeNodes,
  executeCommand,
  handleVoiceToggle,
  handleSubmit,
  handleSchematicUpload,
  toggleDensity,
  density,
}: ChatPanelProps) {
  const { toast } = useToast();

  return (
    <div className="flex-1 flex flex-col min-w-0 relative">
      <ChatInterface
        messages={messages}
        input={input}
        setInput={setInput}
        onSubmit={handleSubmit}
        onVoiceToggle={handleVoiceToggle}
        isRecording={isRecording}
        isStreaming={isStreaming}
        uiState={uiState}
        currentMode={currentMode}
        systemHealth={systemHealth}
        isAnalyzing={isAnalyzing}
        activeNodes={activeNodes}
      />
    </div>
  );
}