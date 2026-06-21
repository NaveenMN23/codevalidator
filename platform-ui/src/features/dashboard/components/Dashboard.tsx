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
  Filter,
  RefreshCcw
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
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      onClick={handleClick}
      className="glass-panel p-5 cursor-pointer group hover:border-primary transition-all duration-200"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-background rounded-lg border border-border-main group-hover:border-primary group-hover:bg-primary/5 transition-colors">
            <Layers className="text-primary" size={20} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-text-main group-hover:text-primary transition-colors">
              {challenge.title}
            </h3>
            <div className="flex items-center gap-4 mt-1">
              <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded border ${
                challenge.difficulty === 'BEGINNER' ? 'text-green-600 bg-panel border-green-200 dark:border-green-900/50 dark:text-green-400' :
                challenge.difficulty === 'INTERMEDIATE' ? 'text-blue-600 bg-panel border-blue-200 dark:border-blue-900/50 dark:text-blue-400' :
                'text-red-600 bg-panel border-red-200 dark:border-red-900/50 dark:text-red-400'
              }`}>
                {challenge.difficulty}
              </span>
              <span className="text-xs text-text-muted flex items-center gap-1 uppercase font-bold tracking-tighter">
                <Code2 size={12} className="text-primary" /> {challenge.language}
              </span>
            </div>
          </div>
        </div>
        <ChevronRight size={20} className="text-text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
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
      <div className="flex h-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <RefreshCcw className="animate-spin text-primary" size={40} />
          <p className="text-text-muted animate-pulse font-medium">Fetching challenges...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-background">
        <div className="text-red-500 font-medium">Error loading challenges. Make sure the backend is running.</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 w-full space-y-12">
      {/* Welcome Header */}
      <section className="bg-panel p-8 rounded-lg border border-border-main hover:border-primary transition-colors">
        <h1 className="text-4xl font-black text-text-main mb-2 tracking-tight">Ready for a challenge?</h1>
        <p className="text-text-muted text-lg">Choose a problem and start coding in your browser-native IDE.</p>
      </section>

      {gamificationEnabled && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div 
            whileHover={{ y: -4 }}
            className="glass-panel p-6 flex items-center space-x-4 border-l-4 border-l-orange-500"
          >
            <div className="p-3 bg-orange-500/10 rounded-xl">
              <Flame className="text-orange-500" size={24} />
            </div>
            <div>
              <div className="text-sm text-text-muted">Daily Streak</div>
              <div className="text-xl font-bold text-text-main">12 Days</div>
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
              <div className="text-sm text-text-muted">Global Rank</div>
              <div className="text-xl font-bold text-text-main">#452</div>
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
              <div className="text-sm text-text-muted">Path Progress</div>
              <div className="text-xl font-bold text-text-main">65%</div>
            </div>
          </motion.div>
        </section>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Challenge List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h2 className="text-xl font-black text-text-main flex items-center gap-2">
              <Code2 size={24} className="text-primary" />
              Available Challenges
            </h2>
            
            <div className="flex items-center gap-3">
              <div className="relative">
                <select
                  value={difficultyFilter}
                  onChange={(e) => setDifficultyFilter(e.target.value)}
                  className="appearance-none bg-panel border border-border-main text-text-main text-xs font-bold rounded-lg focus:ring-primary focus:border-primary block w-full pl-3 pr-8 py-2 cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                >
                  <option value="ALL">All Levels</option>
                  <option value="BEGINNER">Beginner</option>
                  <option value="INTERMEDIATE">Intermediate</option>
                  <option value="ADVANCED">Advanced</option>
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none text-text-muted">
                  <Filter size={12} />
                </div>
              </div>

              <div className="relative">
                <select
                  value={languageFilter}
                  onChange={(e) => setLanguageFilter(e.target.value)}
                  className="appearance-none bg-panel border border-border-main text-text-main text-xs font-bold rounded-lg focus:ring-primary focus:border-primary block w-full pl-3 pr-8 py-2 cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                >
                  <option value="ALL">All Languages</option>
                  {languages.map(lang => (
                    <option key={lang} value={lang}>{lang.charAt(0).toUpperCase() + lang.slice(1)}</option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none text-text-muted">
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
              <div className="glass-panel p-12 text-center border-dashed border-2 bg-transparent shadow-none">
                <Filter className="mx-auto text-text-muted mb-4 opacity-30" size={48} />
                <h3 className="text-text-main font-bold text-lg mb-1">No challenges found</h3>
                <p className="text-text-muted">Try adjusting your filters to find more problems.</p>
                <button 
                  onClick={() => { setDifficultyFilter('ALL'); setLanguageFilter('ALL'); }}
                  className="mt-4 bg-primary text-white px-4 py-2 rounded-lg text-xs font-bold hover:bg-primary/90 transition-all shadow-lg shadow-primary/20"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar / Stats / Quick Actions */}
        <div className="space-y-8">
          <div className="glass-panel p-6 border-primary shadow-sm shadow-primary/10">
            <h3 className="text-lg font-black text-text-main mb-4 flex items-center gap-2">
              <Clock size={18} className="text-primary" />
              Quick Progress
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-xs font-bold uppercase tracking-widest">
                <span className="text-text-muted">Challenges Solved</span>
                <span className="text-primary">24 / 150</span>
              </div>
              <div className="w-full bg-black/5 dark:bg-white/5 h-3 rounded-full overflow-hidden border border-border-main">
                <div className="bg-primary h-full w-[16%] shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
              </div>
              <div className="flex justify-between items-center text-sm pt-2 border-t border-border-main">
                <span className="text-text-muted font-medium">Total Rating</span>
                <span className="text-text-main font-black tracking-tight">4,850 XP</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
