"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';
import CommandPalette from './components/CommandPalette';
import SettingsModal from './components/SettingsModal';
import JournalDashboard from './components/JournalDashboard';
import Sidebar from './components/Sidebar';
import Inspector from './components/Inspector';
import ChatInterface from './components/ChatInterface';
import ActiveNodes from './components/ActiveNodes';
import CollapsiblePanel from './components/CollapsiblePanel';
import { useDensity } from './components/DensityContext';
import { Thought } from './components/ThinkingMonologue';

export default function GarageDashboard() {
  const { density, toggleDensity } = useDensity();
  const [messages, setMessages] = useState<{role: string, text: string}[]>([]);
  const [input, setInput] = useState('');
  const [uiState, setUiState] = useState('calm'); // 'calm' or 'unhinged'
  const [schematicData, setSchematicData] = useState<{image_url: string, svg_overlay: string} | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeNodes, setActiveNodes] = useState<Record<string, any>>({});
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [currentMode, setCurrentMode] = useState('hardware');
  const [activeView, setActiveView] = useState<'chat' | 'journal'>('chat');
  const [systemHealth, setSystemHealth] = useState({
    mlx_engine: 'active',
    memory_engine: 'active',
    websocket: 'connected'
  });
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [memoryEntries, setMemoryEntries] = useState<{key: string, value: string}[]>([]);
  
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);

  const socketRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const briefFiredRef = useRef(false);

  useEffect(() => {
    const backendHost = window.location.hostname;
    const socket = io(`http://${backendHost}:5001`);
    socketRef.current = socket;

    socket.on('node_status', (data: any) => {
      setActiveNodes(prev => {
        const next = { ...prev };
        if (data.status === 'completed' || data.status === 'error') {
          delete next[data.node];
        } else {
          next[data.node] = data;
        }
        return next;
      });
    });

    socket.on('thinking_bubble', (data: any) => {
      const id = Math.random().toString(36).substring(7);
      const newThought: Thought = {
        id,
        message: data.thought || data.message || '',
        status: 'thinking',
      };
      setThoughts(prev => [newThought, ...prev].slice(0, 5));
      setTimeout(() => setThoughts(prev => prev.filter(t => t.id !== id)), 5000);
    });

    socket.on('theme_change', (data: any) => {
      setCurrentMode(data.theme);
      document.body.classList.remove('theme-hardware', 'theme-investigative', 'theme-self-improvement');
      document.body.classList.add(`theme-${data.theme}`);
      document.body.setAttribute('data-mode', data.theme);
    });

    socket.on('system_health', (data: any) => {
      setSystemHealth(data);
    });

    socket.on('sync_state', (data: any) => {
      if (data.active_nodes) setActiveNodes(data.active_nodes);
      if (data.recent_logs && data.recent_logs.length > 0) {
        const formattedLogs = data.recent_logs.map((log: any) => {
          let text = log.message || log.details?.message || JSON.stringify(log);
          return { role: 'kitty', text: `[SYNC] ${text}` };
        });
        setMessages(formattedLogs);
      }
    });

    socket.on('connect', () => {
      setSystemHealth(prev => ({ ...prev, websocket: 'connected' }));
      if (!briefFiredRef.current) {
        briefFiredRef.current = true;
        // Stream brief into chat exactly like a user command
        setTimeout(() => executeCommand('/brief'), 300);
      }
    });

    socket.on('disconnect', () => {
      setSystemHealth(prev => ({ ...prev, websocket: 'disconnected' }));
    });

    return () => { socket.disconnect(); };
  }, []);

  const handleSchematicUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsAnalyzing(true);
    const formData = new FormData();
    formData.append('image', file);

    try {
      const backendHost = window.location.hostname;
      const response = await fetch(`http://${backendHost}:5001/api/schematic/analyze`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      
      if (data.svg_overlay) {
        const reader = new FileReader();
        reader.onload = (event) => {
          setSchematicData({
            image_url: event.target?.result as string,
            svg_overlay: data.svg_overlay
          });
        };
        reader.readAsDataURL(file);
      }
    } catch (error) {
      console.error("Schematic analysis failed:", error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    const backendHost = window.location.hostname;
    fetch(`http://${backendHost}:5001/api/memory/library`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.documents) {
          setMemoryEntries(
            (data.documents as string[]).slice(0, 12).map(doc => ({
              key: doc.split('/').pop() || doc,
              value: doc,
            }))
          );
        }
      })
      .catch(() => {});
  }, []);

  const handleVoiceToggle = useCallback(async () => {
    const backendHost = window.location.hostname;
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const form = new FormData();
        form.append('audio', blob, 'recording.webm');
        try {
          const res = await fetch(`http://${backendHost}:5001/api/transcribe`, { method: 'POST', body: form });
          const data = await res.json();
          if (data.ok && data.text) setInput(data.text);
        } catch { }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch { }
  }, [isRecording]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault();
        setSettingsModalOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'd') {
        e.preventDefault();
        toggleDensity();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [toggleDensity]);

  const executeCommand = useCallback((command: string) => {
    const backendHost = window.location.hostname;
    const eventSource = new EventSource(`http://${backendHost}:5001/stream?query=${encodeURIComponent(command)}`);
    let aiResponse = "";
    setIsStreaming(true);
    setMessages(prev => [...prev, { role: 'kitty', text: '' }]);

    eventSource.onmessage = (event) => {
      try {
        let data: string;
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === 'done') {
            eventSource.close();
            setIsStreaming(false);
            return;
          }
          if (parsed.type === 'error') {
            eventSource.close();
            setIsStreaming(false);
            return;
          }
          // Route thinking tokens to ThinkingMonologue, not the chat bubble
          if (parsed.type === 'thinking') {
            if (parsed.text?.trim()) {
              const id = Math.random().toString(36).substring(7);
              const thought: Thought = { id, message: (parsed.text as string).slice(0, 140), status: 'thinking' };
              setThoughts(prev => [thought, ...prev].slice(0, 5));
              setTimeout(() => setThoughts(prev => prev.filter(t => t.id !== id)), 4000);
            }
            return;
          }
          data = parsed.text || parsed.data || event.data;
        } catch { data = event.data; }

        if (data === '[DONE]') { eventSource.close(); setIsStreaming(false); return; }
        if (data.includes('[STATE:UNHINGED]')) { setUiState('unhinged'); return; }
        if (data.includes('[STATE:CALM]')) { setUiState('calm'); return; }
        if (!data || !data.trim()) return;

        aiResponse += data;
        setMessages(prev => {
          if (prev.length > 0 && prev[prev.length - 1].role === 'kitty') {
            if (prev[prev.length - 1].text === aiResponse) return prev;
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], text: aiResponse };
            return next;
          }
          return [...prev, { role: 'kitty', text: aiResponse }];
        });
      } catch { /* ignore malformed frames */ }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setIsStreaming(false);
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'kitty' && !last.text) {
          const next = [...prev];
          next[next.length - 1] = { ...last, text: '⚠ Connection lost. Is the backend running on :5001?' };
          return next;
        }
        return prev;
      });
    };
  }, []); // stable: only refs stable setState fns + window.location

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages(prev => [...prev, { role: 'user', text: input }]);
    const currentInput = input;
    setInput('');
    executeCommand(currentInput);
  }, [input, executeCommand]);

  return (
    <main 
      className={`h-screen flex flex-col mode-transition overflow-hidden ${uiState === 'unhinged' ? 'theme-unhinged' : `theme-${currentMode}`}`}
      style={{
        '--sidebar-width': sidebarCollapsed ? '48px' : '240px',
        '--inspector-width': inspectorCollapsed ? '48px' : '320px',
      } as React.CSSProperties}
    >
      {/* TOP HEADER */}
      <header className="h-12 flex items-center justify-between px-4 border-b border-color bg-panel-bg flex-shrink-0 z-10">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${systemHealth.websocket === 'connected' ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}></div>
            <span className="text-[10px] font-bold tracking-tighter opacity-70">KITTY_CORE v0.4</span>
          </div>
          <div className="flex bg-white bg-opacity-5 rounded p-0.5 border border-white border-opacity-10 scale-90">
            <button 
              onClick={() => setActiveView('chat')}
              className={`px-3 py-1 rounded text-[9px] font-bold transition-all ${activeView === 'chat' ? 'bg-orange-500 text-black' : 'opacity-50 hover:opacity-100'}`}
              style={{ backgroundColor: activeView === 'chat' ? 'var(--accent-color)' : '' }}
            >
              THE VOID
            </button>
            <button 
              onClick={() => setActiveView('journal')}
              className={`px-3 py-1 rounded text-[9px] font-bold transition-all ${activeView === 'journal' ? 'bg-orange-500 text-black' : 'opacity-50 hover:opacity-100'}`}
              style={{ backgroundColor: activeView === 'journal' ? 'var(--accent-color)' : '' }}
            >
              REFLECTIONS
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <ActiveNodes nodes={activeNodes} />
          <div className="flex items-center gap-3 text-[10px] font-mono opacity-50 mr-2">
            <button onClick={toggleDensity} className="hover:text-white uppercase tracking-tighter">[{density}]</button>
            <button onClick={() => setSettingsModalOpen(true)} className="hover:text-white">⚙ SETTINGS</button>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT GRID */}
      <div className="flex-1 flex overflow-hidden">
        <CollapsiblePanel
          id="sidebar"
          isCollapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          widthVar="--sidebar-width"
          expandedWidth="240px"
          side="left"
          title="The Bench"
        >
          <Sidebar 
            currentMode={currentMode} 
            systemHealth={systemHealth} 
            thoughts={thoughts} 
            onAction={(action) => {
              const cmd = action.startsWith('/') ? action : `/${action}`;
              setMessages(prev => [...prev, { role: 'user', text: cmd }]);
              executeCommand(cmd);
            }} 
          />
        </CollapsiblePanel>

        <section className="flex-1 flex flex-col min-w-0 relative">
          {/* Main workspace with persistent views */}
          <div className={`flex-1 ${activeView === 'chat' ? 'block' : 'hidden'}`}>
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
          <div className={`flex-1 ${activeView === 'journal' ? 'block' : 'hidden'}`}>
            <JournalDashboard />
          </div>
        </section>

        <CollapsiblePanel
          id="inspector"
          isCollapsed={inspectorCollapsed}
          onToggle={() => setInspectorCollapsed(!inspectorCollapsed)}
          widthVar="--inspector-width"
          expandedWidth="320px"
          side="right"
          title="The Optic"
        >
          <Inspector 
            schematicData={schematicData}
            onSchematicUpload={handleSchematicUpload}
            onClearSchematic={() => setSchematicData(null)}
            isAnalyzing={isAnalyzing}
            memoryEntries={memoryEntries}
          />
        </CollapsiblePanel>
      </div>

      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onExecuteCommand={(command) => {
          setMessages(prev => [...prev, { role: 'user', text: command }]);
          executeCommand(command);
          setCommandPaletteOpen(false);
        }}
        onViewChange={(view) => {
          setActiveView(view);
          setCommandPaletteOpen(false);
        }}
        currentMode={currentMode}
      />

      <SettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        currentMode={currentMode}
        onModeChange={(mode) => {
          executeCommand(`/bench ${mode}`);
          setSettingsModalOpen(false);
        }}
      />
      
      <style jsx>{`
        .border-color { border-color: var(--border-color); }
        .bg-panel-bg { background-color: var(--panel-bg); }
      `}</style>
    </main>
  );
}
