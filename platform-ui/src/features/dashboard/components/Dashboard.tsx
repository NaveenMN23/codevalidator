import { useCallback, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchChallenges } from '../../workspace/api';
import type { Challenge } from '../../workspace/workspace.types';
import { Code2, Trophy, Flame, Layers, Filter, RefreshCcw, Search, X } from 'lucide-react';
import { useAppStore } from '../../../store';

const DIFFICULTY_OPTIONS = [
  { value: 'ALL', label: 'All Levels' },
  { value: 'BEGINNER', label: 'Beginner' },
  { value: 'INTERMEDIATE', label: 'Intermediate' },
  { value: 'ADVANCED', label: 'Advanced' },
];

const DIFFICULTY_COLORS: Record<string, string> = {
  BEGINNER: 'text-green-600 border-green-300 dark:text-green-400 dark:border-green-800',
  INTERMEDIATE: 'text-primary border-primary/40',
  ADVANCED: 'text-red-500 border-red-300 dark:border-red-800',
};

export function Dashboard() {
  const navigate = useNavigate();
  const gamificationEnabled = useAppStore(state => state.features.enableGamification);

  const [difficultyFilter, setDifficultyFilter] = useState<string>('ALL');
  const [languageFilter, setLanguageFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ['challenges'],
    queryFn: fetchChallenges,
  });

  const languages = useMemo(() => {
    if (!challenges) return [];
    return Array.from(new Set(challenges.map((c: Challenge) => c.language))).sort() as string[];
  }, [challenges]);

  const filteredChallenges = useMemo(() => {
    if (!challenges) return [];
    return challenges.filter((c: Challenge) => {
      const difficultyMatch = difficultyFilter === 'ALL' || c.difficulty === difficultyFilter;
      const languageMatch = languageFilter === 'ALL' || c.language === languageFilter;
      const searchMatch = !search.trim() || c.title.toLowerCase().includes(search.toLowerCase());
      return difficultyMatch && languageMatch && searchMatch;
    });
  }, [challenges, difficultyFilter, languageFilter, search]);

  const difficultyCounts = useMemo(() => {
    if (!challenges) return {} as Record<string, number>;
    return challenges.reduce((acc: Record<string, number>, c: Challenge) => {
      acc[c.difficulty] = (acc[c.difficulty] || 0) + 1;
      return acc;
    }, {});
  }, [challenges]);

  const handleStartChallenge = useCallback((id: string) => {
    navigate(`/workspace/${id}`);
  }, [navigate]);

  const hasFilters = difficultyFilter !== 'ALL' || languageFilter !== 'ALL' || search.trim() !== '';

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
    <div className="flex h-full overflow-hidden">
      {/* Left Sidebar */}
      <aside className="w-56 shrink-0 border-r border-border-main bg-panel flex flex-col overflow-y-auto">
        <div className="px-5 py-5 border-b border-border-main shrink-0">
          <h2 className="text-sm font-bold text-text-main">Challenges</h2>
          <p className="text-xs text-text-muted mt-0.5">{challenges?.length ?? 0} available</p>
        </div>

        {/* Difficulty filter */}
        <div className="px-5 py-4 border-b border-border-main shrink-0">
          <div className="text-[10px] font-black uppercase tracking-widest text-text-muted mb-3">Difficulty</div>
          <div className="flex flex-col gap-0.5">
            {DIFFICULTY_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setDifficultyFilter(value)}
                className={`text-left text-xs font-medium px-3 py-1.5 rounded-md border-l-2 transition-all ${
                  difficultyFilter === value
                    ? 'border-primary text-primary bg-primary/5'
                    : 'border-transparent text-text-main/70 hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Language filter */}
        {languages.length > 0 && (
          <div className="px-5 py-4 border-b border-border-main shrink-0">
            <div className="text-[10px] font-black uppercase tracking-widest text-text-muted mb-3">Language</div>
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => setLanguageFilter('ALL')}
                className={`text-left text-xs font-medium px-3 py-1.5 rounded-md border-l-2 transition-all ${
                  languageFilter === 'ALL'
                    ? 'border-primary text-primary bg-primary/5'
                    : 'border-transparent text-text-main/70 hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                All Languages
              </button>
              {languages.map((lang: string) => (
                <button
                  key={lang}
                  onClick={() => setLanguageFilter(lang)}
                  className={`text-left text-xs font-medium px-3 py-1.5 rounded-md border-l-2 transition-all ${
                    languageFilter === lang
                      ? 'border-primary text-primary bg-primary/5'
                      : 'border-transparent text-text-main/70 hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                  }`}
                >
                  {lang.charAt(0).toUpperCase() + lang.slice(1)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Gamification stats */}
        {gamificationEnabled && (
          <div className="px-5 py-4 space-y-3">
            <div className="text-[10px] font-black uppercase tracking-widest text-text-muted mb-1">Your Progress</div>
            <div className="flex items-center gap-3 p-3 rounded-lg border border-border-main bg-background">
              <Flame className="text-orange-500 shrink-0" size={15} />
              <div>
                <div className="text-xs font-bold text-text-main">12 Days</div>
                <div className="text-[10px] text-text-muted">Daily Streak</div>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-lg border border-border-main bg-background">
              <Trophy className="text-primary shrink-0" size={15} />
              <div>
                <div className="text-xs font-bold text-text-main">#452</div>
                <div className="text-[10px] text-text-muted">Global Rank</div>
              </div>
            </div>
            <div className="p-3 rounded-lg border border-border-main bg-background">
              <div className="flex justify-between items-center mb-2">
                <div className="text-[10px] text-text-muted">Solved</div>
                <div className="text-[10px] font-bold text-primary">24 / 150</div>
              </div>
              <div className="w-full h-1 rounded-full overflow-hidden" style={{ backgroundColor: 'rgba(128,128,128,0.2)' }}>
                <div className="bg-primary h-full w-[16%] rounded-full" />
              </div>
              <div className="text-[10px] text-text-muted mt-1.5">4,850 XP total</div>
            </div>
          </div>
        )}
        <div className="flex-grow" />
      </aside>

      {/* Main content */}
      <main className="flex-grow overflow-y-auto bg-background flex flex-col">
        {/* Hero header — directly above the table */}
        <div className="px-8 pt-10 pb-7 border-b border-border-main shrink-0">
          {/* Title row */}
          <div className="flex items-end justify-between gap-4 mb-6">
            <div>
              <h1 className="text-4xl font-light text-text-main tracking-tight leading-none">
                Let's <span className="font-bold text-primary">Decode.</span>
              </h1>
              <p className="text-sm text-text-muted mt-2">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={filteredChallenges.length}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="inline-block"
                  >
                    {hasFilters
                      ? `${filteredChallenges.length} result${filteredChallenges.length !== 1 ? 's' : ''} found`
                      : `${challenges?.length ?? 0} challenges ready to crack`}
                  </motion.span>
                </AnimatePresence>
              </p>
            </div>

            {/* Difficulty quick-filter pills with live counts */}
            <div className="flex items-center gap-2 shrink-0">
              {(['BEGINNER', 'INTERMEDIATE', 'ADVANCED'] as const).map(d => (
                <button
                  key={d}
                  onClick={() => setDifficultyFilter(prev => prev === d ? 'ALL' : d)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                    difficultyFilter === d
                      ? 'bg-primary text-white border-primary shadow-sm'
                      : `${DIFFICULTY_COLORS[d]} bg-transparent hover:bg-primary/5`
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    d === 'BEGINNER' ? 'bg-green-500' : d === 'INTERMEDIATE' ? 'bg-primary' : 'bg-red-500'
                  }`} />
                  {difficultyCounts[d] ?? 0} {d.charAt(0) + d.slice(1).toLowerCase()}
                </button>
              ))}
              {hasFilters && (
                <button
                  onClick={() => { setDifficultyFilter('ALL'); setLanguageFilter('ALL'); setSearch(''); }}
                  className="ml-1 text-xs text-text-muted hover:text-text-main transition-colors flex items-center gap-1"
                >
                  <X size={12} /> Clear
                </button>
              )}
            </div>
          </div>

          {/* Search bar */}
          <div className="relative max-w-lg">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" size={15} />
            <input
              type="text"
              placeholder="Search challenges..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-10 py-2.5 rounded-full border border-border-main bg-panel text-text-main text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-main transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="px-6">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-main">
                <th className="py-3 text-left text-[10px] font-black uppercase tracking-widest text-text-muted w-10" />
                <th className="py-3 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Problem / Challenge</th>
                <th className="py-3 text-left text-[10px] font-black uppercase tracking-widest text-text-muted w-28">Language</th>
                <th className="py-3 text-right text-[10px] font-black uppercase tracking-widest text-text-muted w-32">Difficulty</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {filteredChallenges.map((challenge: Challenge) => (
                  <motion.tr
                    key={challenge.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    onClick={() => handleStartChallenge(challenge.id)}
                    className="group border-b border-border-main hover:bg-primary/[0.04] cursor-pointer transition-colors"
                  >
                    <td className="py-4 pl-1">
                      <div className="w-4 h-4 rounded-full border border-border-main group-hover:border-primary transition-colors" />
                    </td>
                    <td className="py-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-panel rounded-lg border border-border-main group-hover:border-primary group-hover:bg-primary/5 transition-all shrink-0">
                          <Layers size={14} className="text-primary" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-text-main group-hover:text-primary transition-colors">
                            {challenge.title}
                          </div>
                          <div className="h-0.5 w-40 rounded-full mt-1.5" style={{ backgroundColor: 'rgba(128,128,128,0.2)' }}>
                            <div className="h-0.5 bg-primary rounded-full w-0" />
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-4">
                      <span className="text-xs font-medium text-text-muted flex items-center gap-1.5">
                        <Code2 size={11} className="text-primary shrink-0" />
                        {challenge.language.charAt(0).toUpperCase() + challenge.language.slice(1)}
                      </span>
                    </td>
                    <td className="py-4 text-right">
                      <span className={`inline-block text-[10px] font-bold px-2.5 py-1 rounded-full border ${DIFFICULTY_COLORS[challenge.difficulty]}`}>
                        {challenge.difficulty.charAt(0) + challenge.difficulty.slice(1).toLowerCase()}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>

              {filteredChallenges.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={4} className="py-16 text-center">
                    <Filter className="mx-auto text-text-muted mb-3 opacity-20" size={32} />
                    <p className="text-sm font-bold text-text-main mb-1">No challenges found</p>
                    <p className="text-xs text-text-muted">Try a different search or clear the filters.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
