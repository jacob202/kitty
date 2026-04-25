"use client";

import React, { useState, useEffect } from 'react';

interface JournalEntry {
  id: number;
  timestamp: string;
  type: string;
  content: string;
  mood?: string;
  energy?: number;
}

export default function JournalDashboard() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [content, setContent] = useState('');
  const [mood, setMood] = useState('Neutral');
  const [energy, setEnergy] = useState(5);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchEntries();
  }, []);

  const fetchEntries = async () => {
    try {
      const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
      const response = await fetch(`http://${backendHost}:5001/api/journal/entries`);
      if (response.ok) {
        const data = await response.json();
        setEntries(data);
      }
    } catch (error) {
      console.error('Failed to fetch journal entries:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setLoading(true);
    try {
      const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
      const response = await fetch(`http://${backendHost}:5001/api/journal/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, mood, energy, type: 'journal' })
      });

      if (response.ok) {
        setContent('');
        fetchEntries();
      }
    } catch (error) {
      console.error('Failed to add entry:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 h-full overflow-hidden">
      <div className="panel p-6 rounded-lg shadow-lg">
        <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--accent-color)' }}>DAILY REFLECTION</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="What's on your mind?..."
            className="w-full h-32 bg-white bg-opacity-5 border rounded p-3 text-sm outline-none focus:border-orange-500 transition-all"
            style={{ borderColor: 'var(--border-color)', color: 'var(--text-main)' }}
          />
          <div className="flex gap-4 items-center">
            <div className="flex-1">
              <label className="block text-[10px] opacity-50 uppercase mb-1">Mood</label>
              <select
                value={mood}
                onChange={(e) => setMood(e.target.value)}
                className="w-full bg-white bg-opacity-5 border rounded p-2 text-xs outline-none"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-main)' }}
              >
                <option value="High">High</option>
                <option value="Good">Good</option>
                <option value="Neutral">Neutral</option>
                <option value="Low">Low</option>
                <option value="Frustrated">Frustrated</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-[10px] opacity-50 uppercase mb-1">Energy ({energy})</label>
              <input
                type="range"
                min="1"
                max="10"
                value={energy}
                onChange={(e) => setEnergy(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !content.trim()}
              className="px-6 py-2 rounded font-bold self-end transition-all disabled:opacity-50"
              style={{ backgroundColor: 'var(--accent-color)', color: 'var(--bg-color)' }}
            >
              {loading ? 'SAVING...' : 'SAVE ENTRY'}
            </button>
          </div>
        </form>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar panel p-6 rounded-lg shadow-lg">
        <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--accent-color)' }}>HISTORY</h2>
        <div className="space-y-4">
          {entries.map((entry) => (
            <div key={entry.id} className="p-4 border rounded bg-white bg-opacity-5" style={{ borderColor: 'var(--border-color)' }}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-[10px] opacity-50 font-mono">{new Date(entry.timestamp).toLocaleString()}</span>
                <div className="flex gap-2">
                  <span className="px-2 py-0.5 rounded-full bg-orange-500 bg-opacity-20 text-[9px] uppercase tracking-tighter" style={{ color: 'var(--accent-color)' }}>
                    {entry.mood}
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-blue-500 bg-opacity-20 text-[9px] uppercase tracking-tighter text-blue-400">
                    E:{entry.energy}
                  </span>
                </div>
              </div>
              <p className="text-sm leading-relaxed opacity-90">{entry.content}</p>
            </div>
          ))}
          {entries.length === 0 && <p className="text-center opacity-30 italic py-10">No entries yet. Start reflecting...</p>}
        </div>
      </div>
    </div>
  );
}
