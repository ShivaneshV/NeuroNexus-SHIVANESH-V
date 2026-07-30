import React from 'react';
import { Shield, Sparkles, Database, BadgeDollarSign, RefreshCw } from 'lucide-react';

export default function CostTracker({ stats, onReset }) {
  // Extract and default metrics
  const apiCalls = stats.total_api_calls || 0;
  const tokens = stats.total_tokens_used || 0;
  const cost = stats.total_cost || 0.0;
  const savedCalls = stats.saved_api_calls || 0;
  const savedCost = stats.saved_cost || 0.0;
  
  // Calculate efficiency percentage
  const totalTheoreticalCalls = apiCalls + savedCalls;
  const efficiency = totalTheoreticalCalls > 0 
    ? Math.round((savedCalls / totalTheoreticalCalls) * 100) 
    : 100;

  return (
    <div className="bg-slate-900/85 backdrop-blur-xl border border-slate-800/80 rounded-2xl shadow-2xl p-5 text-slate-100 max-w-sm w-full transition-all duration-300 hover:border-violet-500/50 hover:shadow-violet-950/20 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-violet-400 animate-pulse" />
          <h2 className="text-sm font-semibold tracking-wide uppercase bg-gradient-to-r from-violet-400 to-indigo-300 bg-clip-text text-transparent">
            RAG Efficiency Hub
          </h2>
        </div>
        <button 
          onClick={onReset}
          className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-rose-400 transition-colors"
          title="Reset Metrics"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-slate-950/40 border border-slate-800/50 rounded-xl p-3">
          <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1">
            <Database className="w-3.5 h-3.5 text-indigo-400" />
            Local Compute
          </div>
          <p className="text-xl font-bold text-slate-100">0 API</p>
          <p className="text-[10px] text-indigo-300 mt-0.5">Embeddings & Retrieval</p>
        </div>

        <div className="bg-slate-950/40 border border-slate-800/50 rounded-xl p-3">
          <div className="text-slate-400 text-xs flex items-center gap-1.5 mb-1">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            Redundant Saved
          </div>
          <p className="text-xl font-bold text-emerald-400">{savedCalls}</p>
          <p className="text-[10px] text-emerald-500/70 mt-0.5">LLM Calls Bypassed</p>
        </div>
      </div>

      <div className="space-y-3 bg-slate-950/50 border border-slate-800/80 rounded-xl p-4 mb-3">
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-400">Total API calls made</span>
          <span className="font-semibold text-violet-300">{apiCalls}</span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-400">Tokens consumed</span>
          <span className="font-semibold text-slate-300">{tokens.toLocaleString()}</span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-400">Direct LLM cost</span>
          <span className="font-mono font-semibold text-rose-300">${cost.toFixed(5)}</span>
        </div>
        <div className="border-t border-slate-800/80 pt-2 flex justify-between items-center text-xs font-medium">
          <span className="text-slate-300 flex items-center gap-1">
            <BadgeDollarSign className="w-3.5 h-3.5 text-emerald-400" />
            Net Dollars Saved
          </span>
          <span className="font-mono text-emerald-400">+${savedCost.toFixed(3)}</span>
        </div>
      </div>

      <div className="bg-gradient-to-r from-violet-600/10 to-indigo-600/10 border border-violet-500/10 rounded-xl p-3 text-center">
        <div className="text-xs text-violet-300 font-medium">
          API Efficiency Score: <span className="text-slate-100 font-bold">{efficiency}%</span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
          <div 
            className="bg-gradient-to-r from-violet-500 to-indigo-400 h-1.5 rounded-full transition-all duration-500" 
            style={{ width: `${efficiency}%` }}
          />
        </div>
      </div>
    </div>
  );
}
