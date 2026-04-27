"use client";

import React from 'react';

interface ActiveNodesProps {
  nodes: Record<string, any>;
}

const ActiveNodes = React.memo(({ nodes }: ActiveNodesProps) => {
  const nodeValues = Object.values(nodes);
  
  if (nodeValues.length === 0) {
    return <span className="text-[9px] opacity-30 italic">IDLE_TASK_WAIT</span>;
  }

  return (
    <div className="flex gap-2 overflow-x-auto no-scrollbar max-w-md">
      {nodeValues.map((node: any) => (
        <div 
          key={node.node} 
          className="flex-shrink-0 flex items-center gap-1 bg-white bg-opacity-5 px-2 py-0.5 rounded text-[8px] border border-white border-opacity-10 active-node"
        >
          <span className="opacity-70 uppercase font-bold">{node.node}</span>
          {node.status === 'processing' && (
            <span className="w-1 h-1 rounded-full bg-orange-500 animate-pulse"></span>
          )}
        </div>
      ))}
    </div>
  );
});

ActiveNodes.displayName = 'ActiveNodes';

export default ActiveNodes;
