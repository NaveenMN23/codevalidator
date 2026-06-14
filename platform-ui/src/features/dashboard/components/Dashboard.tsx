import { useCallback, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { fetchChallenges } from '../../workspace/api';
import type { Challenge } from '../../workspace/workspace.types';
import { 
  Code2, 
  Trophy, 
  Flame, 
  BookOpen, 
  ChevronRight,
  Clock,
  Layers,
  Filter
} from 'lucide-react';
import { useAppStore } from '../../../store';

interface ChallengeCardProps {
  challenge: Challenge;
  onClick: (id: string) => void;
}

function ChallengeCard({ challenge, onClick }: ChallengeCardProps) {
  const handleClick = useCallback(() => {
    onClick(challenge.id);
  }, [challenge.id, onClick]);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      whileHover={{ scale: 1.01 }}
      onClick={handleClick}
      className="glass-panel p-5 cursor-pointer group hover:border-primary/50 transition-all"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-background/50 rounded-lg group-hover:bg-primary/10 transition-colors">
            <Layers className="text-slate-400 group-hover:text-primary" size={20} />
          </div>
          <div>
            <h3 className="text-lg font-medium text-white group-hover:text-primary transition-colors">
              {challenge.title}
            </h3>
            <div className="flex items-center gap-4 mt-1">
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                challenge.difficulty === 'BEGINNER' ? 'text-green-400 bg-green-400/10' :
                challenge.difficulty === 'INTERMEDIATE' ? 'text-yellow-400 bg-yellow-400/10' :
                'text-red-400 bg-red-400/10'
              }`}>
                {challenge.difficulty}
              </span>
              <span className="text-xs text-slate-500 flex items-center gap-1 uppercase">
                <Code2 size={12} /> {challenge.language}
              </span>
            </div>
          </div>
        </div>
        <ChevronRight size={20} className="text-slate-600 group-hover:text-primary group-hover:translate-x-1 transition-all" />
      </div>
    </motion.div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const gamificationEnabled = useAppStore(state => state.features.enableGamification);
  
  const [difficultyFilter, setDifficultyFilter] = useState<string>('ALL');
  const [languageFilter, setLanguageFilter] = useState<string>('ALL');

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ['challenges'],
    queryFn: fetchChallenges,
  });

  const languages = useMemo(() => {
    if (!challenges) return [];
    const uniqueLangs = Array.from(new Set(challenges.map(c => c.language)));
    return uniqueLangs.sort();
  }, [challenges]);

  const filteredChallenges = useMemo(() => {
    if (!challenges) return [];
    return challenges.filter(c => {
      const difficultyMatch = difficultyFilter === 'ALL' || c.difficulty === difficultyFilter;
      const languageMatch = languageFilter === 'ALL' || c.language === languageFilter;
      return difficultyMatch && languageMatch;
    });
  }, [challenges, difficultyFilter, languageFilter]);

  const handleStartChallenge = (id: string) => {
    navigate(`/workspace/${id}`);
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-slate-400">Loading challenges...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-red-400">Error loading challenges. Make sure the backend is running.</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 w-full space-y-12">
      {/* Welcome Header */}
      <section>
        <h1 className="text-3xl font-bold text-white mb-2">Ready for a challenge?</h1>
        <p className="text-slate-400">Choose a problem and start coding in your browser environment.</p>
      </section>

      {gamificationEnabled && (
        /* Daily Streak & Challenge section (Gamification V2) */
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div 
            whileHover={{ y: -4 }}
            className="glass-panel p-6 flex items-center space-x-4 border-l-4 border-l-orange-500"
          >
            <div className="p-3 bg-orange-500/10 rounded-xl">
              <Flame className="text-orange-500" size={24} />
            </div>
            <div>
              <div className="text-sm text-slate-400">Daily Streak</div>
              <div className="text-xl font-bold text-white">12 Days</div>
            </div>
          </motion.div>

          <motion.div 
            whileHover={{ y: -4 }}
            className="glass-panel p-6 flex items-center space-x-4 border-l-4 border-l-blue-500"
          >
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Trophy className="text-blue-500" size={24} />
            </div>
            <div>
              <div className="text-sm text-slate-400">Global Rank</div>
              <div className="text-xl font-bold text-white">#452</div>
            </div>
          </motion.div>

          <motion.div 
            whileHover={{ y: -4 }}
            className="glass-panel p-6 flex items-center space-x-4 border-l-4 border-l-purple-500"
          >
            <div className="p-3 bg-purple-500/10 rounded-xl">
              <BookOpen className="text-purple-500" size={24} />
            </div>
            <div>
              <div className="text-sm text-slate-400">Path Progress</div>
              <div className="text-xl font-bold text-white">65%</div>
            </div>
          </motion.div>
        </section>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Challenge List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <Code2 size={20} className="text-primary" />
              Available Challenges
            </h2>
            
            <div className="flex items-center gap-3">
              <div className="relative">
                <select
                  value={difficultyFilter}
                  onChange={(e) => setDifficultyFilter(e.target.value)}
                  className="appearance-none bg-white/5 border border-white/10 text-slate-300 text-xs rounded-lg focus:ring-primary focus:border-primary block w-full pl-3 pr-8 py-2 cursor-pointer hover:bg-white/10 transition-colors"
                >
                  <option value="ALL">All Levels</option>
                  <option value="BEGINNER">Beginner</option>
                  <option value="INTERMEDIATE">Intermediate</option>
                  <option value="ADVANCED">Advanced</option>
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none text-slate-500">
                  <Filter size={12} />
                </div>
              </div>

              <div className="relative">
                <select
                  value={languageFilter}
                  onChange={(e) => setLanguageFilter(e.target.value)}
                  className="appearance-none bg-white/5 border border-white/10 text-slate-300 text-xs rounded-lg focus:ring-primary focus:border-primary block w-full pl-3 pr-8 py-2 cursor-pointer hover:bg-white/10 transition-colors"
                >
                  <option value="ALL">All Languages</option>
                  {languages.map(lang => (
                    <option key={lang} value={lang}>{lang.charAt(0).toUpperCase() + lang.slice(1)}</option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none text-slate-500">
                  <Code2 size={12} />
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {filteredChallenges.length > 0 ? (
              filteredChallenges.map((challenge: Challenge) => (
                <ChallengeCard
                  key={challenge.id}
                  challenge={challenge}
                  onClick={handleStartChallenge}
                />
              ))
            ) : (
              <div className="glass-panel p-12 text-center border-dashed border-2 border-white/5 bg-transparent">
                <Filter className="mx-auto text-slate-700 mb-4 opacity-50" size={40} />
                <h3 className="text-white font-medium mb-1">No challenges found</h3>
                <p className="text-slate-500 text-sm">Try adjusting your filters to find more problems.</p>
                <button 
                  onClick={() => { setDifficultyFilter('ALL'); setLanguageFilter('ALL'); }}
                  className="mt-4 text-primary text-xs font-semibold hover:underline"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar / Stats / Quick Actions */}
        <div className="space-y-8">
          {gamificationEnabled && (
            <div className="glass-panel p-6">
              <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                <Clock size={18} className="text-primary" />
                Daily Challenge
              </h3>
              <div className="p-4 bg-primary/5 rounded-xl border border-primary/10">
                <div className="text-sm font-medium text-primary mb-1">Book My Show: Cache Stampede</div>
                <p className="text-xs text-slate-400 mb-3 line-clamp-2">Fix the thundering herd problem in the seat selection logic.</p>
                <button className="w-full bg-primary text-white text-sm font-medium py-2 rounded-lg hover:bg-primary/90 transition-colors">
                  Start Now
                </button>
              </div>
            </div>
          )}

          <div className="glass-panel p-6">
            <h3 className="text-lg font-medium text-white mb-4">Quick Stats</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-400">Solved</span>
                <span className="text-white font-medium">24 / 150</span>
              </div>
              <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden">
                <div className="bg-primary h-full w-[16%]" />
              </div>
              <div className="flex justify-between items-center text-sm pt-2 border-t border-white/5">
                <span className="text-slate-400">Total Score</span>
                <span className="text-primary font-bold">4,850 XP</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
