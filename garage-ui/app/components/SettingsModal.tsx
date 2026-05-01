"use client";

import React, { useState, useEffect } from 'react';
import { useToast } from './Toast';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentMode: string;
  onModeChange: (mode: string) => void;
  isLightMode: boolean;
  onLightModeToggle: () => void;
}

interface Settings {
  features: {
    auto_pagination: { enabled: boolean; description: string };
    chat_history_profiling: { enabled: boolean; description: string };
    unhinged_mode: { enabled: boolean; description: string };
    voice_input: { enabled: boolean; description: string };
    screen_watcher: { enabled: boolean; description: string };
  };
  models: {
    primary: string;
    fallback: string;
    vision: string;
  };
}

export default function SettingsModal({ isOpen, onClose, currentMode, onModeChange, isLightMode, onLightModeToggle }: SettingsModalProps) {
  const { toast } = useToast();
  const [settings, setSettings] = useState<Settings>({
    features: {
      auto_pagination: { enabled: true, description: "Automatically paginate long responses" },
      chat_history_profiling: { enabled: false, description: "Learn from conversation patterns" },
      unhinged_mode: { enabled: false, description: "Allow chaotic personality shifts" },
      voice_input: { enabled: true, description: "SuperWhisper voice integration" },
      screen_watcher: { enabled: false, description: "Continuous screen monitoring" }
    },
    models: {
      primary: "claude-3-5-sonnet",
      fallback: "deepseek-chat",
      vision: "claude-3-5-sonnet"
    }
  });

  const [loading, setLoading] = useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
      const response = await fetch(`http://${backendHost}:5001/api/settings`);
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast('Failed to load settings', 'error');
    }
  };

  const updateSetting = async (key: string, value: any, isModel = false) => {
    setLoading(true);
    try {
      const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
      const response = await fetch(`http://${backendHost}:5001/api/settings/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value })
      });
      
      if (response.ok) {
        if (isModel) {
          setSettings(prev => ({
            ...prev,
            models: { ...prev.models, [key]: value }
          }));
        } else {
          setSettings(prev => ({
            ...prev,
            features: {
              ...prev.features,
              [key]: { ...prev.features[key as keyof typeof prev.features], enabled: value }
            }
          }));
        }
        toast(`${key.replace(/_/g, ' ')} updated`, 'success');
      } else {
        toast('Failed to update setting', 'error');
      }
    } catch (error) {
      console.error('Failed to update setting:', error);
      toast('Failed to update setting', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={(e) => {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
          onClose();
        }
      }}
    >
      <div ref={containerRef} className="rounded-lg shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-y-auto" style={{
        backgroundColor: 'var(--panel-bg)',
        borderColor: 'var(--accent-color)',
        border: '1px solid var(--accent-color)'
      }}>
        <div className="p-6 border-b" style={{borderColor: 'var(--border-color)'}}>
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold" style={{color: 'var(--accent-color)'}}>
              KITTY CONTROL PANEL
            </h2>
            <button
              onClick={onClose}
              className="text-2xl opacity-50 hover:opacity-100 transition-opacity"
            >
              ×
            </button>
          </div>
          <p className="text-sm opacity-70 mt-2">Configure system behavior and preferences</p>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Mode Selection */}
          <div>
            <h3 className="text-lg font-semibold mb-4" style={{color: 'var(--accent-color)'}}>
              Operating Mode
            </h3>
            <div className="space-y-3">
              {[
                { id: 'hardware', label: 'Hardware Mode', description: 'Electronics repair and analysis' },
                { id: 'investigative', label: 'Investigative Mode', description: 'Research and fact-finding' },
                { id: 'self-improvement', label: 'Self-Improvement Mode', description: 'Personal development and reflection' }
              ].map(mode => (
                <div
                  key={mode.id}
                  className={`p-3 rounded border cursor-pointer transition-all ${
                    currentMode === mode.id ? 'bg-white bg-opacity-10' : 'hover:bg-white hover:bg-opacity-5'
                  }`}
                  style={{
                    borderColor: currentMode === mode.id ? 'var(--accent-color)' : 'var(--border-color)'
                  }}
                  onClick={() => onModeChange(mode.id)}
                >
                  <div className="font-medium">{mode.label}</div>
                  <div className="text-xs opacity-70 mt-1">{mode.description}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Feature Toggles */}
          <div>
            <h3 className="text-lg font-semibold mb-4" style={{color: 'var(--accent-color)'}}>
              Appearance
            </h3>
            <div className="space-y-4 mb-8">
              <div className="flex items-center justify-between p-3 rounded border" style={{borderColor: 'var(--border-color)'}}>
                <div className="flex-1">
                  <div className="font-medium">Light Mode</div>
                  <div className="text-xs opacity-70 mt-1">Use the cream palette</div>
                </div>
                <button
                  onClick={onLightModeToggle}
                  className={`w-12 h-6 rounded-full transition-all ${
                    isLightMode ? 'bg-accent-color' : 'bg-gray-600'
                  }`}
                  style={{
                    backgroundColor: isLightMode ? 'var(--accent-color)' : '#666'
                  }}
                >
                  <div
                    className={`w-5 h-5 bg-white rounded-full transition-transform ${
                      isLightMode ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>

            <h3 className="text-lg font-semibold mb-4" style={{color: 'var(--accent-color)'}}>
              Features
            </h3>
            <div className="space-y-4">
              {Object.entries(settings.features).map(([key, feature]) => (
                <div key={key} className="flex items-center justify-between p-3 rounded border" style={{borderColor: 'var(--border-color)'}}>
                  <div className="flex-1">
                    <div className="font-medium capitalize">
                      {key.replace(/_/g, ' ')}
                    </div>
                    <div className="text-xs opacity-70 mt-1">
                      {feature.description}
                    </div>
                  </div>
                  <button
                    onClick={() => updateSetting(key, !feature.enabled)}
                    disabled={loading}
                    className={`w-12 h-6 rounded-full transition-all ${
                      feature.enabled ? 'bg-accent-color' : 'bg-gray-600'
                    }`}
                    style={{
                      backgroundColor: feature.enabled ? 'var(--accent-color)' : '#666'
                    }}
                  >
                    <div
                      className={`w-5 h-5 bg-white rounded-full transition-transform ${
                        feature.enabled ? 'translate-x-6' : 'translate-x-0.5'
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Model Configuration */}
          <div className="md:col-span-2">
            <h3 className="text-lg font-semibold mb-4" style={{color: 'var(--accent-color)'}}>
              Model Configuration
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(settings.models).map(([key, model]) => (
                <div key={key} className="p-3 rounded border" style={{borderColor: 'var(--border-color)'}}>
                  <label className="block text-sm font-medium mb-2 capitalize">
                    {key} Model
                  </label>
                  <select
                    value={model}
                    onChange={(e) => updateSetting(key, e.target.value, true)}
                    disabled={loading}
                    className="w-full bg-transparent border rounded px-3 py-2 text-sm"
                    style={{
                      borderColor: 'var(--border-color)',
                      color: 'var(--text-main)'
                    }}
                  >
                    <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                    <option value="deepseek-chat">DeepSeek Chat</option>
                    <option value="gemini-pro">Gemini Pro</option>
                    <option value="gpt-4">GPT-4</option>
                    <option value="openrouter/free">OpenRouter Free</option>
                    <option value="google/gemini-2.0-flash-001">Gemini 2.0 Flash</option>
                  </select>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="p-6 border-t flex justify-between items-center" style={{borderColor: 'var(--border-color)'}}>
          <div className="text-xs opacity-50">
            Changes are saved automatically
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2 rounded font-bold transition-all"
            style={{
              backgroundColor: 'var(--accent-color)',
              color: 'var(--bg-color)'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
