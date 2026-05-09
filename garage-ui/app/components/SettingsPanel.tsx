"use client";

import SettingsModal from './components/SettingsModal';
import { useToast } from './components/Toast';

interface SettingsPanelProps {
  settingsModalOpen: boolean;
  setSettingsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  toggleDensity: () => void;
  density: string;
  isLightMode: boolean;
  setIsLightMode: React.Dispatch<React.SetStateAction<boolean>>;
}

export function SettingsPanel({
  settingsModalOpen,
  setSettingsModalOpen,
  toggleDensity,
  density,
  isLightMode,
  setIsLightMode,
}: SettingsPanelProps) {
  const { toast } = useToast();

  return (
    <>
      <SettingsModal 
        open={settingsModalOpen} 
        onOpenChange={setSettingsModalOpen} 
      />
      <div className="hidden md:flex items-center gap-2 md:gap-3 text-[10px] font-mono opacity-50">
        <button 
          onClick={() => setIsLightMode(!isLightMode)} 
          className="hover:text-white uppercase tracking-tighter"
        >
          {isLightMode ? '🌙 DARK' : '☀️ LIGHT'}
        </button>
        <button 
          onClick={toggleDensity} 
          className="hidden sm:inline hover:text-white uppercase tracking-tighter"
        >
          [{density}]
        </button>
        <button 
          onClick={() => setSettingsModalOpen(true)} 
          className="hover:text-white"
        >
          ⚙ <span className="hidden sm:inline">SETTINGS</span>
        </button>
      </div>
    </>
  );
}