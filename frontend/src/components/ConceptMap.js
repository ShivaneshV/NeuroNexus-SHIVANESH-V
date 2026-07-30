'use client';

import React, { useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Group style configurations for node appearance
const GROUP_STYLES = {
  background: {
    background: '#1e293b', // slate-800
    border: '2px solid #64748b', // slate-500
    color: '#e2e8f0', // slate-200
    boxShadow: '0 0 12px rgba(100, 116, 139, 0.2)'
  },
  architecture: {
    background: '#1e1b4b', // indigo-950
    border: '2px solid #6366f1', // indigo-500
    color: '#e0e7ff', // indigo-100
    boxShadow: '0 0 12px rgba(99, 102, 241, 0.3)'
  },
  model: {
    background: '#2e1065', // violet-950
    border: '2px solid #8b5cf6', // violet-500
    color: '#f5f3ff', // violet-100
    boxShadow: '0 0 12px rgba(139, 92, 246, 0.3)'
  },
  methodology: {
    background: '#064e3b', // emerald-950
    border: '2px solid #10b981', // emerald-500
    color: '#ecfdf5', // emerald-100
    boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)'
  },
  results: {
    background: '#7c2d12', // orange-950
    border: '2px solid #f97316', // orange-500
    color: '#fff7ed', // orange-50
    boxShadow: '0 0 12px rgba(249, 115, 22, 0.3)'
  },
  default: {
    background: '#18181b', // zinc-900
    border: '2px solid #71717a', // zinc-500
    color: '#f4f4f5', // zinc-100
    boxShadow: '0 0 12px rgba(113, 113, 122, 0.2)'
  }
};

export default function ConceptMap({ data }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!data || !data.nodes) return;

    // 1. Group nodes for semantic layout positioning
    const groupedNodes = {};
    data.nodes.forEach(node => {
      const g = (node.group || 'default').toLowerCase();
      if (!groupedNodes[g]) groupedNodes[g] = [];
      groupedNodes[g].push(node);
    });

    // 2. Map groups to columns to represent scientific workflow flow
    // Columns: Background (Left) -> Architecture/Core (Middle-Left) -> Methodology/Training (Middle-Right) -> Results (Right)
    const columnOrder = ['background', 'architecture', 'model', 'methodology', 'results'];
    
    // Position nodes using a left-to-right columns algorithm
    const computedNodes = [];
    const nodePaddingX = 280;
    const nodePaddingY = 90;

    // Identify and position orphan groups
    const allGroups = Object.keys(groupedNodes);
    allGroups.forEach(g => {
      if (!columnOrder.includes(g)) {
        columnOrder.push(g);
      }
    });

    columnOrder.forEach((groupName, colIdx) => {
      const groupNodesList = groupedNodes[groupName] || [];
      const totalInGroup = groupNodesList.length;
      
      groupNodesList.forEach((node, rowIdx) => {
        // Center the column vertically
        const yOffset = 300 - ((totalInGroup - 1) * nodePaddingY) / 2;
        
        const style = GROUP_STYLES[groupName] || GROUP_STYLES.default;
        
        computedNodes.push({
          id: node.id,
          data: { label: node.label },
          position: { 
            x: colIdx * nodePaddingX + 50, 
            y: yOffset + (rowIdx * nodePaddingY) 
          },
          style: {
            ...style,
            padding: '10px 14px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: '600',
            width: '180px',
            textAlign: 'center',
            cursor: 'grab',
            transition: 'box-shadow 0.2s ease',
          }
        });
      });
    });

    // 3. Format edges
    const computedEdges = (data.edges || []).map((edge, idx) => ({
      id: `edge-${idx}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#4f46e5', strokeWidth: 2 },
      labelStyle: { fill: '#c084fc', fontSize: 10, fontWeight: 500 },
      labelBgPadding: [4, 2],
      labelBgBorderRadius: 4,
      labelBgStyle: { fill: '#09090b', fillOpacity: 0.85, stroke: '#312e81', strokeWidth: 1 }
    }));

    setNodes(computedNodes);
    setEdges(computedEdges);
  }, [data, setNodes, setEdges]);

  return (
    <div className="w-full h-[550px] bg-zinc-950 border border-slate-900 rounded-2xl overflow-hidden relative shadow-inner">
      <div className="absolute top-4 left-4 z-10 bg-slate-900/90 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-300 pointer-events-none">
        <p className="font-semibold text-slate-200 mb-1.5">Map Legend</p>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-slate-500 inline-block" />
            <span>Background</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-indigo-500 inline-block" />
            <span>Architecture</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" />
            <span>Methodology</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-orange-500 inline-block" />
            <span>Results</span>
          </div>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        colorMode="dark"
      >
        <Background color="#1e293b" gap={16} size={1} />
        <Controls showInteractive={false} className="!bg-slate-900 !border-slate-800 !text-slate-100 fill-slate-100" />
        <MiniMap 
          nodeColor={(node) => {
            // Pick minicap node color based on border styling
            if (node.style?.border?.includes('#10b981')) return '#10b981';
            if (node.style?.border?.includes('#6366f1')) return '#6366f1';
            if (node.style?.border?.includes('#f97316')) return '#f97316';
            return '#64748b';
          }}
          maskColor="rgba(0, 0, 0, 0.6)"
          className="!bg-slate-950/80 !border-slate-800"
        />
      </ReactFlow>
    </div>
  );
}
