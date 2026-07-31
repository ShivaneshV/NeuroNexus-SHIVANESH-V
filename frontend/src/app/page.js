'use client';

import React, { useState, useEffect } from 'react';
import { 
  Upload, FileText, Brain, RefreshCw, BarChart2, CheckCircle, AlertTriangle, FileUp, MessageSquare, Send 
} from 'lucide-react';

import CostTracker from '../components/CostTracker';
import Flashcards from '../components/Flashcards';
import ConceptMap from '../components/ConceptMap';
import PdfViewer from '../components/PdfViewer';

export default function Home() {
  // App states
  const [file, setFile] = useState(null);
  const [fileHash, setFileHash] = useState('');
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [briefData, setBriefData] = useState(null);
  const [stats, setStats] = useState({});
  const [statusMessage, setStatusMessage] = useState('');
  const [eli5, setEli5] = useState(false);
  
  // Citation navigation state
  const [highlightedPage, setHighlightedPage] = useState(0);
  const [citationContext, setCitationContext] = useState(null);
  
  // UI States
  const [activeTab, setActiveTab] = useState('brief');
  const [speaking, setSpeaking] = useState(false);

  const speakText = (text, languageCode = 'hi-IN') => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      
      if (speaking) {
        setSpeaking(false);
        return;
      }
      
      const cleanedText = text
        .replace(/\[\d+\]/g, '')
        .replace(/###/g, '')
        .replace(/\*\*/g, '')
        .replace(/-\s+/g, '');

      const utterance = new SpeechSynthesisUtterance(cleanedText);
      utterance.lang = languageCode;
      utterance.rate = 0.9;
      
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      
      setSpeaking(true);
      window.speechSynthesis.speak(utterance);
    } else {
      alert("Sorry, your browser doesn't support text to speech!");
    }
  };

  // Copilot Chat States & Functions
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { 
      role: 'assistant', 
      text: "Hello! I am your Research Copilot. Ask me any custom question about this paper, and I'll find the exact pages and quote sections to answer it." 
    }
  ]);
  const [chatLoading, setChatLoading] = useState(false);

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading || !fileHash) return;

    const userQuestion = chatInput.trim();
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', text: userQuestion }]);
    setChatLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_hash: fileHash, question: userQuestion }),
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, { 
          role: 'assistant', 
          text: data.answer_data.answer,
          citations: data.answer_data.citations_map 
        }]);
        // Refresh efficiency tracker stats immediately
        fetchStats();
      } else {
        const err = await res.json();
        setChatHistory(prev => [...prev, { 
          role: 'assistant', 
          text: `Error: ${err.detail || 'Unable to retrieve answer.'}` 
        }]);
      }
    } catch (err) {
      console.error('Chat error:', err);
      setChatHistory(prev => [...prev, { 
        role: 'assistant', 
        text: 'Connection failed. Ensure the FastAPI backend is running.' 
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Load API tracking stats on mount
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Error fetching statistics:', err);
    }
  };

  const handleResetStats = async () => {
    if (!confirm('Are you sure you want to reset the API tracking statistics?')) return;
    try {
      const res = await fetch('http://localhost:8000/api/stats/reset', { method: 'POST' });
      if (res.ok) {
        fetchStats();
      }
    } catch (err) {
      console.error('Error resetting statistics:', err);
    }
  };

  // Upload handler (Ingestion phase)
  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile || !selectedFile.name.endsWith('.pdf')) {
      alert('Please upload a valid PDF file.');
      return;
    }

    setFile(selectedFile);
    setUploading(true);
    setBriefData(null);
    setFileHash('');
    setHighlightedPage(0);
    setCitationContext(null);
    setChatHistory([
      { 
        role: 'assistant', 
        text: "Hello! I am your Research Copilot. Ask me any custom question about this paper, and I'll find the exact pages and quote sections to answer it." 
      }
    ]);
    setStatusMessage('Uploading, parsing text, and generating local vector embeddings...');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();
      
      setFileHash(data.file_hash);
      
      if (data.cached) {
        setStatusMessage('Document found in semantic cache! Loading briefing outputs instantly.');
        await generateBrief(data.file_hash, eli5);
      } else {
        setStatusMessage(`Ingestion successful. Generated ${data.num_chunks} vector chunks locally using sentence-transformers (0 API calls).`);
        await generateBrief(data.file_hash, eli5);
      }
    } catch (err) {
      console.error(err);
      setStatusMessage('Ingestion failed. Ensure FastAPI backend is running on port 8000.');
    } finally {
      setUploading(false);
    }
  };

  // Structured Brief Generation Handler (Retrieval + Synthesis)
  const generateBrief = async (hash, eli5Mode = false) => {
    setGenerating(true);
    setStatusMessage(`Executing local vector search & calling single-pass LLM agent (ELI5=${eli5Mode})...`);
    
    try {
      const res = await fetch('http://localhost:8000/api/brief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_hash: hash, eli5: eli5Mode }),
      });

      if (!res.ok) throw new Error('Briefing failed');
      const data = await res.json();
      
      setBriefData(data.brief);
      setStatusMessage(data.source === 'cache' 
        ? 'Brief successfully retrieved from local cache (0 API calls).' 
        : 'Brief successfully generated in single-pass JSON call (1 API call).'
      );
      
      // Update statistics
      fetchStats();
    } catch (err) {
      console.error(err);
      setStatusMessage('Synthesis failed. Ensure API keys are configured correctly.');
    } finally {
      setGenerating(false);
    }
  };

  const handleEli5Toggle = async () => {
    const newEli5 = !eli5;
    setEli5(newEli5);
    if (fileHash) {
      await generateBrief(fileHash, newEli5);
    }
  };

  // Jump to specific citation block inside PDF
  const handleCitationClick = (chunkId, pageNum, citation) => {
    setHighlightedPage(pageNum);
    setCitationContext(citation);
  };

  // Custom renderer to convert markdown-like sections and link bracketed numbers e.g. [1]
  const renderBriefMarkdown = (text, citationsMap) => {
    if (!text) return null;
    
    // Split text by citations e.g. [1] or [2]
    const parts = text.split(/(\[\d+\])/g);
    
    return (
      <p className="mb-4 text-slate-300 leading-relaxed text-sm">
        {parts.map((part, index) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const citationId = match[1];
            const citation = citationsMap?.find(c => String(c.citation_id) === String(citationId));
            
            if (citation) {
              return (
                <button
                  key={index}
                  onClick={() => handleCitationClick(citation.chunk_id, citation.page_number, citation)}
                  className="inline-flex items-center justify-center w-4 h-4 bg-violet-950/70 hover:bg-violet-900 border border-violet-850 rounded text-[10px] font-bold text-violet-300 cursor-pointer align-super select-none transition-colors mx-0.5"
                  title={`Page ${citation.page_number}: ${citation.snippet}`}
                >
                  {citationId}
                </button>
              );
            }
            return <span key={index} className="align-super text-[10px] text-slate-500 font-semibold">{part}</span>;
          }
          
          // Render basic linebreaks
          if (part.includes('\n')) {
            return part.split('\n').map((line, lIdx) => (
              <React.Fragment key={`${index}-${lIdx}`}>
                {line}
                {lIdx < part.split('\n').length - 1 && <br />}
              </React.Fragment>
            ));
          }
          
          return part;
        })}
      </p>
    );
  };

  return (
    <main className="min-h-screen bg-[#030712] text-slate-100 flex flex-col font-sans select-none">
      {/* Background radial glow */}
      <div className="absolute top-0 left-0 w-full h-[600px] bg-gradient-to-b from-indigo-950/20 to-transparent pointer-events-none z-0" />
      
      {/* Top Navigation */}
      <header className="relative z-10 border-b border-slate-900 bg-slate-950/60 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-violet-600 to-indigo-500 rounded-xl shadow-lg shadow-indigo-900/30">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-slate-100 via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-2">
              PaperPilot
            </h1>
            <p className="text-[10px] font-medium text-indigo-400 uppercase tracking-widest">
              AntigravityAcademIQ
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <span className="text-xs px-3 py-1 bg-indigo-950/50 border border-indigo-900/50 rounded-full text-indigo-300 font-semibold shadow-inner">
            Agentic AI Track
          </span>
          <span className="text-xs text-slate-400">SOCF 2.0 Hackathon Entry</span>
        </div>
      </header>

      {/* Main Workspace Wrapper */}
      <div className="flex-1 p-6 relative z-10 max-w-7xl mx-auto w-full flex flex-col gap-6">
        
        {/* Document Ingest & Status Bar */}
        <section className="flex flex-col md:flex-row gap-5 items-stretch justify-between bg-slate-950/40 border border-slate-900 rounded-2xl p-5 shadow-xl">
          {/* File input controls */}
          <div className="flex-1 flex flex-col justify-center">
            <div className="flex items-center gap-3 mb-2">
              <label 
                className={`flex items-center gap-2 px-4 py-2.5 bg-gradient-to-tr from-violet-600 to-indigo-500 hover:from-violet-500 hover:to-indigo-400 text-white rounded-xl text-xs font-semibold cursor-pointer shadow-lg shadow-indigo-950/20 transition-all ${
                  uploading || generating ? 'opacity-50 pointer-events-none' : ''
                }`}
              >
                <Upload className="w-4 h-4" />
                Upload PDF
                <input 
                  type="file" 
                  accept=".pdf" 
                  onChange={handleFileUpload} 
                  className="hidden" 
                />
              </label>
              
              {file && (
                <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-900 border border-slate-850 px-3 py-2 rounded-xl">
                  <FileText className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="max-w-[180px] truncate font-medium">{file.name}</span>
                </div>
              )}

              <button
                onClick={handleEli5Toggle}
                disabled={uploading || generating || !fileHash}
                className={`px-4 py-2 text-xs font-bold border rounded-xl shadow-md transition-all flex items-center gap-1.5 ${
                  eli5 
                    ? 'bg-amber-950/40 text-amber-300 border-amber-600/50 hover:bg-amber-900/40' 
                    : 'bg-slate-900 text-slate-300 border-slate-850 hover:border-slate-750'
                } ${!fileHash ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <Brain className={`w-3.5 h-3.5 ${eli5 ? 'text-amber-400 animate-pulse' : 'text-slate-400'}`} />
                {eli5 ? 'ELI5 Mode Active' : 'Switch to ELI5'}
              </button>
            </div>
            
            {/* Realtime Action Logs */}
            <div className="text-xs text-slate-400 flex items-center gap-2 min-h-[1.5rem]">
              {(uploading || generating) && (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-violet-400" />
              )}
              <span className={statusMessage.includes('failed') ? 'text-rose-400' : 'text-slate-300'}>
                {statusMessage || 'Awaiting document upload...'}
              </span>
            </div>
          </div>

          {/* Efficiency tracker integration */}
          <div className="flex justify-end items-center">
            <CostTracker stats={stats} onReset={handleResetStats} />
          </div>
        </section>

        {/* Dynamic Workspace Layout Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* PDF Viewer - Left 6 Columns */}
          <div className="lg:col-span-6 h-full">
            <PdfViewer 
              fileHash={fileHash} 
              highlightedPage={highlightedPage} 
              citationContext={citationContext}
            />
          </div>

          {/* Synthesis Workspace - Right 6 Columns */}
          <div className="lg:col-span-6 flex flex-col gap-5 h-full">
            
            {/* View Selection Tabs */}
            <div className="flex bg-slate-950/80 p-1.5 border border-slate-900 rounded-xl shadow-inner">
              <button
                onClick={() => setActiveTab('brief')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'brief' 
                    ? 'bg-slate-900 text-violet-300 border border-slate-800 shadow-md' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-4 h-4" />
                Study Brief
              </button>
              <button
                onClick={() => setActiveTab('flashcards')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'flashcards' 
                    ? 'bg-slate-900 text-violet-300 border border-slate-800 shadow-md' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                disabled={!briefData}
              >
                <Brain className="w-4 h-4" />
                Flashcards
              </button>
              <button
                onClick={() => setActiveTab('concept_map')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'concept_map' 
                    ? 'bg-slate-900 text-violet-300 border border-slate-800 shadow-md' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                disabled={!briefData}
              >
                <BarChart2 className="w-4 h-4" />
                Concept Map
              </button>
              <button
                onClick={() => setActiveTab('copilot')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'copilot' 
                    ? 'bg-slate-900 text-violet-300 border border-slate-800 shadow-md' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                disabled={!briefData}
              >
                <MessageSquare className="w-4 h-4" />
                Copilot Q&A
              </button>
            </div>

            {/* Tab Workspace Panel */}
            <div className="bg-slate-950/40 border border-slate-900 rounded-2xl p-6 min-h-[500px] flex flex-col shadow-xl">
              {!briefData ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 p-8">
                  {generating ? (
                    <>
                      <RefreshCw className="w-12 h-12 mb-3 stroke-1 text-violet-400 animate-spin" />
                      <p className="font-semibold text-slate-200">Analyzing Document Structure...</p>
                      <p className="text-xs text-slate-500 mt-1 max-w-xs">
                        Local embeddings mapped. Retrieving sections and synthesizing resources in a single pass.
                      </p>
                    </>
                  ) : (
                    <>
                      <FileUp className="w-12 h-12 mb-3 stroke-1 text-slate-650" />
                      <p className="font-medium text-slate-300">Workspace Empty</p>
                      <p className="text-xs text-slate-500 mt-1 max-w-xs">
                        Upload an academic paper to unlock the Study Brief, Flashcards, and Concept Map.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <div className="flex-grow">
                  
                  {/* Tab 1: Brief */}
                  {activeTab === 'brief' && (
                    <div className="space-y-6 animate-fade-in">
                      <div>
                        <h2 className="text-xl font-bold text-slate-100 mb-1">{briefData.title}</h2>
                        
                        {/* Agentic Skeptic Critique Panel */}
                        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 border border-rose-950/40 bg-rose-950/5 rounded-xl p-4 mt-3 shadow-sm hover:border-rose-500/20 transition-all duration-300">
                          <div className="md:col-span-3 flex flex-col justify-center items-center bg-rose-950/25 border border-rose-900/50 rounded-xl p-2.5 text-center">
                            <span className="text-[9px] uppercase tracking-wider font-extrabold text-rose-400 mb-0.5">
                              Skeptic Score
                            </span>
                            <span className="text-2xl font-black text-rose-500">
                              {briefData.methodology_score || 7}/10
                            </span>
                          </div>
                          <div className="md:col-span-9 flex flex-col justify-center">
                            <span className="text-[9px] uppercase tracking-wider font-extrabold text-rose-400 mb-1 flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                              Critical Methodology Flaw
                            </span>
                            <p className="text-xs text-rose-200 leading-relaxed font-semibold italic">
                              "{briefData.critical_flaw || 'No flaw identified by the reviewer.'}"
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 bg-violet-950/20 border border-violet-900/50 rounded-xl p-3.5">
                          <div className="flex items-center justify-between mb-1.5 border-b border-violet-950/40 pb-1">
                            <p className="text-xs text-violet-400 font-bold uppercase tracking-wider">Abstract Highlights</p>
                            <div className="flex items-center gap-1.5 text-[9px] text-slate-400">
                              <span className="font-semibold text-slate-500">🔊 LISTEN:</span>
                              <button 
                                onClick={() => speakText(`${briefData.title}. Abstract highlights: ${briefData.abstract_summary}`, 'en-US')}
                                className="hover:text-violet-300 font-bold uppercase cursor-pointer"
                              >
                                English
                              </button>
                              <span>|</span>
                              <button 
                                onClick={() => speakText(`${briefData.title}. ${briefData.abstract_summary}`, 'hi-IN')}
                                className="hover:text-violet-300 font-bold uppercase cursor-pointer"
                              >
                                Hindi
                              </button>
                              <span>|</span>
                              <button 
                                onClick={() => speakText(`${briefData.title}. ${briefData.abstract_summary}`, 'ta-IN')}
                                className="hover:text-violet-300 font-bold uppercase cursor-pointer"
                              >
                                Tamil
                              </button>
                              <span>|</span>
                              <button 
                                onClick={() => speakText(`${briefData.title}. ${briefData.abstract_summary}`, 'te-IN')}
                                className="hover:text-violet-300 font-bold uppercase cursor-pointer"
                              >
                                Telugu
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed font-medium italic">
                            "{briefData.abstract_summary}"
                          </p>
                        </div>
                      </div>

                      <div className="space-y-5 border-t border-slate-900 pt-5">
                        <div>
                          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-3.5 rounded bg-violet-500 inline-block" />
                            Methodology & Pipeline
                          </h3>
                          {renderBriefMarkdown(briefData.methodology, briefData.citations_map)}
                        </div>

                        <div>
                          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-3.5 rounded bg-emerald-500 inline-block" />
                            Results & Benchmarks
                          </h3>
                          {renderBriefMarkdown(briefData.results, briefData.citations_map)}
                        </div>

                        <div>
                          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-3.5 rounded bg-orange-500 inline-block" />
                            Limitations & Assumptions
                          </h3>
                          {renderBriefMarkdown(briefData.limitations, briefData.citations_map)}
                        </div>
                      </div>

                      {/* Paper-to-Podcast Dialogue Script Section */}
                      {briefData.podcast_script && briefData.podcast_script.length > 0 && (
                        <div className="border border-slate-900 bg-slate-950/70 rounded-xl p-4.5 shadow-sm mt-4.5">
                          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-900">
                            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                              <span className="w-1.5 h-3.5 rounded bg-indigo-500 inline-block animate-pulse" />
                              🎙️ Narrated Podcast Script (ELI5)
                            </h3>
                            <button
                              onClick={() => {
                                const fullScriptText = briefData.podcast_script.map(d => `${d.speaker} says: ${d.text}`).join(". ");
                                speakText(fullScriptText, 'en-US');
                              }}
                              className={`px-3 py-1 border rounded text-[10px] font-bold transition-all cursor-pointer ${
                                speaking 
                                  ? 'bg-rose-950/40 text-rose-300 border-rose-800 hover:bg-rose-900/40' 
                                  : 'bg-indigo-950/50 text-indigo-300 border-indigo-850 hover:bg-indigo-900/40'
                              }`}
                            >
                              🔊 {speaking ? 'Stop Broadcast' : 'Play Broadcast Audio'}
                            </button>
                          </div>
                          
                          <div className="space-y-3.5 max-h-[250px] overflow-y-auto pr-2 scrollbar-thin">
                            {briefData.podcast_script.map((turn, idx) => (
                              <div key={idx} className="flex items-start gap-2.5">
                                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                                  turn.speaker === 'Host' ? 'bg-indigo-950 text-indigo-300 border border-indigo-900' : 'bg-emerald-950 text-emerald-300 border border-emerald-900'
                                }`}>
                                  {turn.speaker === 'Host' ? '🎙️' : '🎓'}
                                </div>
                                <div className={`p-3 rounded-xl text-xs flex-1 ${
                                  turn.speaker === 'Host' ? 'bg-slate-900/40 text-slate-350' : 'bg-slate-900 text-slate-200 border border-slate-850'
                                }`}>
                                  <span className="block font-bold text-[9px] text-slate-450 mb-0.5 uppercase tracking-wide">
                                    {turn.speaker === 'Host' ? 'Host' : 'Researcher'}
                                  </span>
                                  {turn.text}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Replication Agent GitHub/Kaggle Hub */}
                      {briefData.replicate_tools && briefData.replicate_tools.length > 0 && (
                        <div className="border border-slate-900 bg-slate-950/70 rounded-xl p-4.5 shadow-sm mt-4.5">
                          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                            <span className="w-1.5 h-3.5 rounded bg-emerald-500 inline-block" />
                            🚀 Replicate this Study (GitHub & Kaggle Queries)
                          </h3>
                          <p className="text-[10px] text-slate-450 mb-3.5">
                            Our Replication Agent identified these packages, models, or datasets in the paper. Click to search codebases:
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {briefData.replicate_tools.map((tool, idx) => (
                              <div key={idx} className="bg-slate-900/60 border border-slate-850 rounded-xl p-3 flex flex-col justify-between gap-2.5">
                                <span className="text-xs font-semibold text-slate-200 block truncate">{tool.tool_or_dataset}</span>
                                <div className="flex gap-2">
                                  <a
                                    href={tool.github_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex-1 py-1 px-2.5 bg-slate-950 hover:bg-slate-850 border border-slate-800 rounded text-[9px] font-bold text-slate-300 hover:text-slate-100 transition-colors text-center"
                                  >
                                    🔍 GitHub Code
                                  </a>
                                  <a
                                    href={tool.kaggle_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex-1 py-1 px-2.5 bg-slate-950 hover:bg-slate-850 border border-slate-800 rounded text-[9px] font-bold text-slate-300 hover:text-slate-100 transition-colors text-center"
                                  >
                                    📊 Kaggle Data
                                  </a>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 2: Flashcards */}
                  {activeTab === 'flashcards' && (
                    <div className="animate-fade-in">
                      <Flashcards 
                        cards={briefData.flashcards} 
                        onCitationClick={handleCitationClick} 
                      />
                    </div>
                  )}

                  {/* Tab 3: Concept Map */}
                  {activeTab === 'concept_map' && (
                    <div className="animate-fade-in">
                      <ConceptMap data={briefData.concept_map} />
                    </div>
                  )}

                  {/* Tab 4: Research Copilot */}
                  {activeTab === 'copilot' && (
                    <div className="flex flex-col h-[520px] border border-slate-900 bg-slate-950/40 rounded-xl p-4.5 shadow-sm animate-fade-in justify-between">
                      {/* Messages scroll area */}
                      <div className="flex-1 overflow-y-auto space-y-3.5 pr-1.5 scrollbar-thin">
                        {chatHistory.map((msg, idx) => (
                          <div key={idx} className={`flex items-start gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            {msg.role === 'assistant' && (
                              <div className="w-6 h-6 rounded-full bg-violet-950 text-violet-300 border border-violet-900 flex items-center justify-center text-[10px] font-bold shrink-0">
                                🤖
                              </div>
                            )}
                            <div className={`p-3 rounded-xl text-xs max-w-[85%] ${
                              msg.role === 'user' 
                                ? 'bg-indigo-650 text-white font-medium rounded-tr-none' 
                                : 'bg-slate-900 text-slate-100 border border-slate-850 rounded-tl-none'
                            }`}>
                              {msg.role === 'assistant' ? (
                                <>
                                  {renderBriefMarkdown(msg.text, msg.citations || [])}
                                </>
                              ) : (
                                msg.text
                              )}
                            </div>
                          </div>
                        ))}
                        {chatLoading && (
                          <div className="flex items-start gap-2.5 justify-start">
                            <div className="w-6 h-6 rounded-full bg-violet-950 text-violet-300 border border-violet-900 flex items-center justify-center text-[10px] font-bold shrink-0 animate-spin">
                              ⚙️
                            </div>
                            <div className="p-3 bg-slate-900 text-slate-450 border border-slate-850 rounded-xl rounded-tl-none text-xs flex items-center gap-1.5">
                              <RefreshCw className="w-3.5 h-3.5 animate-spin text-violet-400" />
                              Research Copilot is searching local index and consulting LLM...
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Chat Input form */}
                      <form onSubmit={handleSendChat} className="flex gap-2 mt-4 pt-3.5 border-t border-slate-900">
                        <input
                          type="text"
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          placeholder="Ask a custom question (e.g., 'What training configuration was used?')..."
                          className="flex-1 bg-slate-900 border border-slate-850 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 outline-none transition-all"
                          disabled={chatLoading}
                        />
                        <button
                          type="submit"
                          disabled={chatLoading || !chatInput.trim()}
                          className="px-3.5 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-900 disabled:opacity-40 text-white border border-violet-500 disabled:border-slate-850 rounded-xl transition-all flex items-center justify-center cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5" />
                        </button>
                      </form>
                    </div>
                  )}
                  
                </div>
              )}
            </div>
            
          </div>
        </section>
        
      </div>
    </main>
  );
}
