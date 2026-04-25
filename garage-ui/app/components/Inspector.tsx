"use client";

import React from 'react';

interface InspectorProps {
  schematicData: { image_url: string; svg_overlay: string } | null;
  onSchematicUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClearSchematic: () => void;
  isAnalyzing: boolean;
  memoryEntries: { key: string; value: string }[];
}

const Inspector = React.memo(({
  schematicData,
  onSchematicUpload,
  onClearSchematic,
  isAnalyzing,
  memoryEntries
}: InspectorProps) => {
  return (
    <div className="flex flex-col gap-4 p-4 h-full">
      {/* THE OPTIC */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--accent-color)' }}>THE OPTIC</h2>
        
        <div className="flex-1 border border-dashed border-opacity-30 rounded p-2 flex flex-col gap-2 overflow-hidden">
          {!schematicData ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 opacity-50">
              <span className="text-center text-[10px] px-2">Upload schematic for autonomous mapping</span>
              <input 
                type="file" 
                id="schematic-upload-inspector" 
                className="hidden" 
                accept="image/*,application/pdf"
                onChange={onSchematicUpload}
              />
              <label 
                htmlFor="schematic-upload-inspector"
                className="px-4 py-2 border rounded cursor-pointer hover:bg-white hover:bg-opacity-10 transition-all font-bold text-[10px]"
                style={{ borderColor: 'var(--accent-color)', color: 'var(--accent-color)' }}
              >
                SELECT FILE
              </label>
            </div>
          ) : (
            <div className="relative flex-1 bg-black rounded overflow-hidden">
              <img 
                src={schematicData.image_url} 
                className="w-full h-full object-contain"
                alt="Schematic Base"
              />
              <div 
                className="absolute inset-0 pointer-events-none"
                dangerouslySetInnerHTML={{ __html: schematicData.svg_overlay }}
              />
              <button 
                onClick={onClearSchematic}
                className="absolute top-2 right-2 p-1 bg-black bg-opacity-50 rounded text-[10px] hover:text-red-500"
              >
                CLOSE
              </button>
            </div>
          )}
        </div>

        {isAnalyzing && (
          <div className="mt-2 text-[10px] animate-pulse text-center" style={{ color: 'var(--accent-color)' }}>
            [ ANALYZING HARDWARE DOMAIN... ]
          </div>
        )}
      </div>

      {/* THE ARCHIVE */}
      <div className="panel-sub p-3 rounded-lg overflow-hidden flex flex-col max-h-64 border border-color">
        <h2 className="text-lg font-bold mb-3" style={{ color: 'var(--accent-color)' }}>THE ARCHIVE</h2>
        {memoryEntries.length === 0 ? (
          <p className="text-[10px] opacity-40 italic">Memory engine active — no entries yet.</p>
        ) : (
          <div className="flex flex-col gap-1 overflow-y-auto no-scrollbar">
            {memoryEntries.map((entry, i) => (
              <div key={i} className="text-[10px] font-mono opacity-60 border-b border-white border-opacity-5 pb-1 truncate">
                <span style={{ color: 'var(--accent-color)' }}>{entry.key}</span>
                <span className="opacity-50 ml-2">{String(entry.value).slice(0, 40)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .panel-sub {
          background-color: rgba(255, 255, 255, 0.02);
        }
        .border-color {
          border-color: var(--border-color);
        }
      `}</style>
    </div>
  );
});

Inspector.displayName = 'Inspector';

export default Inspector;
