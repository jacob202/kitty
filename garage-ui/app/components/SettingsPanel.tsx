"use client";

import SettingsModal from './SettingsModal';
import { useToast } from './Toast';

interface SettingsPanelProps {
  settingsModalOpen: boolean;
  setSettingsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  toggleDensity: () => void;
  density: string;
  isLightMode: boolean;
  setIsLightMode: React.Dispatch<React.SetStateAction<boolean>>;
  currentMode: string;
  setCurrentMode: React.Dispatch<React.SetStateAction<string>>;
}

export function SettingsPanel({
  settingsModalOpen,
  setSettingsModalOpen,
  toggleDensity,
  density,
  isLightMode,
  setIsLightMode,
  currentMode,
  setCurrentMode,
}: SettingsPanelProps) {
  const { toast } = useToast();

  return (
    <>
      <SettingsModal 
        isOpen={settingsModalOpen} 
        onClose={() => setSettingsModalOpen(false)}
        currentMode={currentMode}
        onModeChange={setCurrentMode}
        isLightMode={isLightMode}
        onLightModeToggle={() => setIsLightMode(!isLightMode)}
      />
      <div className="hidden md:flex items-center gap-2 md:gap-3 text-[10px] font-mono opacity-50">
        <button 
          onClick={() => setIsLightMode(!isLightMode)} 
          className="hover:text-[var(--accent-color)] uppercase tracking-tighter transition-colors"
        >
          {isLightMode ? '🌙 DARK' : '☀️ LIGHT'}
        </button>
        <button 
          onClick={toggleDensity} 
          className="hidden sm:inline hover:text-[var(--accent-color)] uppercase tracking-tighter transition-colors"
        >
          [{density}]
        </button>
        <button 
          onClick={() => setSettingsModalOpen(true)} 
          className="hover:text-[var(--accent-color)] transition-colors"
        >
          ⚙ <span className="hidden sm:inline">SETTINGS</span>
        </button>
      </div>
    </>
  );
}