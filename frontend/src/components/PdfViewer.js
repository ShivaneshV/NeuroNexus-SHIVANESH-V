'use client';

import React from 'react';
import { BookOpen, AlertCircle, FileText } from 'lucide-react';

export default function PdfViewer({ fileHash, highlightedPage, citationContext }) {
  if (!fileHash) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[500px] border-2 border-dashed border-slate-800 rounded-2xl text-slate-400 bg-slate-950/20 p-8">
        <BookOpen className="w-12 h-12 mb-3 stroke-1 text-slate-600 animate-pulse" />
        <p className="font-medium text-slate-300">No Document Loaded</p>
        <p className="text-xs text-slate-500 mt-1 max-w-xs text-center">
          Upload an academic paper to preview and examine verified sources.
        </p>
      </div>
    );
  }

  // Construct PDF URL with target page number hash fragment
  // E.g., http://localhost:8000/api/pdfs/12345.pdf#page=2
  const baseUrl = `http://localhost:8000/api/pdfs/${fileHash}`;
  const pdfUrl = highlightedPage ? `${baseUrl}#page=${highlightedPage}` : baseUrl;

  return (
    <div className="flex flex-col h-full min-h-[600px] border border-slate-900 rounded-2xl overflow-hidden bg-slate-950/40">
      {/* Top Banner indicating PDF page status */}
      <div className="bg-slate-900 border-b border-slate-850 px-4 py-3 flex items-center justify-between text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" />
          <span className="font-semibold text-slate-200">Interactive PDF Viewer</span>
        </div>
        {highlightedPage ? (
          <span className="bg-violet-950 text-violet-300 px-2 py-1 rounded border border-violet-800 font-medium">
            Jumped to Page {highlightedPage}
          </span>
        ) : (
          <span className="text-slate-500">No page target selected</span>
        )}
      </div>

      {/* Main PDF Embed Container */}
      <div className="flex-1 bg-slate-900 relative">
        <iframe
          key={`${fileHash}-${highlightedPage}`} // Force iframe reload when page changes
          src={pdfUrl}
          className="w-full h-full border-0 bg-slate-900"
          title="Academic Paper PDF"
        />
      </div>

      {/* Citation context preview box */}
      {citationContext && (
        <div className="bg-slate-950 border-t border-slate-850 p-4 transition-all duration-300 animate-fade-in">
          <div className="flex items-center gap-1.5 text-xs text-violet-400 font-bold uppercase mb-1.5 tracking-wider">
            <FileText className="w-3.5 h-3.5" />
            Verified Source Context (Page {highlightedPage})
          </div>
          <div className="bg-slate-900/80 border border-violet-950/60 rounded-lg p-3 text-sm text-slate-300 italic leading-relaxed shadow-inner">
            "{citationContext.snippet || citationContext.text}"
          </div>
          <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-slate-500" />
            Source snippet retrieved locally from ChromaDB to ensure zero-hallucination.
          </div>
        </div>
      )}
    </div>
  );
}
