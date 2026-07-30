'use client';

import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, HelpCircle, FileText } from 'lucide-react';

export default function Flashcards({ cards = [], onCitationClick }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  if (!cards || cards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400">
        <HelpCircle className="w-12 h-12 mb-2 stroke-1" />
        <p>No study flashcards available.</p>
      </div>
    );
  }

  const handleNext = () => {
    setIsFlipped(false);
    setTimeout(() => {
      setCurrentIndex((prev) => (prev + 1) % cards.length);
    }, 150);
  };

  const handlePrev = () => {
    setIsFlipped(false);
    setTimeout(() => {
      setCurrentIndex((prev) => (prev - 1 + cards.length) % cards.length);
    }, 150);
  };

  const card = cards[currentIndex];

  return (
    <div className="flex flex-col items-center justify-center gap-6 max-w-xl mx-auto py-6">
      {/* 3D Flippable Card Container */}
      <div 
        className="w-full h-80 cursor-pointer perspective-[1000px]"
        onClick={() => setIsFlipped(!isFlipped)}
      >
        <div 
          className={`relative w-full h-full duration-500 transform-style-3d transition-transform ${
            isFlipped ? 'rotate-y-180' : ''
          }`}
        >
          {/* FRONT Side */}
          <div className="absolute w-full h-full backface-hidden bg-slate-900 border border-slate-800 rounded-2xl p-8 flex flex-col justify-between shadow-xl">
            <div className="flex items-center justify-between text-violet-400 text-xs font-semibold tracking-wider uppercase">
              <span>Question {currentIndex + 1} of {cards.length}</span>
              <HelpCircle className="w-4 h-4" />
            </div>
            <div className="flex-1 flex items-center justify-center my-4">
              <p className="text-xl font-medium text-slate-100 text-center leading-relaxed">
                {card.question}
              </p>
            </div>
            <div className="text-center text-xs text-slate-500 italic">
              Click to flip and reveal answer
            </div>
          </div>

          {/* BACK Side */}
          <div className="absolute w-full h-full backface-hidden rotate-y-180 bg-slate-950 border border-violet-850/40 rounded-2xl p-8 flex flex-col justify-between shadow-2xl">
            <div className="flex items-center justify-between text-emerald-400 text-xs font-semibold tracking-wider uppercase">
              <div className="flex gap-2">
                <span className="bg-slate-900 text-slate-400 border border-slate-800 px-2 py-0.5 rounded text-[9px] font-bold uppercase">
                  {card.difficulty || 'Medium'}
                </span>
                <span className="bg-violet-950/60 text-violet-300 border border-violet-900/60 px-2 py-0.5 rounded text-[9px] font-bold uppercase">
                  Review: {card.next_review || 'In 3 days'}
                </span>
              </div>
              <span className="flex items-center gap-1">Page {card.page_number}</span>
            </div>
            <div className="flex-grow flex flex-col justify-center my-4 overflow-y-auto">
              <p className="text-lg text-slate-200 text-center leading-relaxed mb-4">
                {card.answer}
              </p>
              {card.chunk_id && (
                <button
                  onClick={(e) => {
                    e.stopPropagation(); // Avoid flipping the card
                    onCitationClick(card.chunk_id, card.page_number);
                  }}
                  className="mx-auto flex items-center gap-1.5 px-3 py-1.5 bg-violet-950/40 hover:bg-violet-900/50 border border-violet-850/50 rounded-lg text-xs text-violet-300 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Jump to source page
                </button>
              )}
            </div>
            <div className="text-center text-xs text-slate-600">
              Click to flip back
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center gap-4">
        <button
          onClick={handlePrev}
          className="p-3 bg-slate-900 border border-slate-800 hover:border-violet-500/50 hover:bg-slate-850 rounded-xl text-slate-300 hover:text-slate-100 transition-all shadow-md"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <span className="text-slate-400 text-sm font-medium">
          {currentIndex + 1} / {cards.length}
        </span>
        <button
          onClick={handleNext}
          className="p-3 bg-slate-900 border border-slate-800 hover:border-violet-500/50 hover:bg-slate-850 rounded-xl text-slate-300 hover:text-slate-100 transition-all shadow-md"
        >
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>

      {/* Tailwind helper styles for 3D card rotation */}
      <style jsx global>{`
        .perspective-\\[1000px\\] {
          perspective: 1000px;
        }
        .transform-style-3d {
          transform-style: preserve-3d;
        }
        .backface-hidden {
          backface-visibility: hidden;
        }
        .rotate-y-180 {
          transform: rotateY(180deg);
        }
      `}</style>
    </div>
  );
}
