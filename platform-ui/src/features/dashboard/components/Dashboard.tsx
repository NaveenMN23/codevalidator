import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { RefreshCcw, ChevronDown, ChevronRight, ChevronLeft, Flame, Sparkles } from 'lucide-react';
import { fetchChallenges } from '../../workspace/api';
import { useAppStore } from '../../../store';
import type { Challenge } from '../../workspace/workspace.types';

type DiffKey = 'EASY' | 'MEDIUM' | 'HARD';

const DIFF_ORDER: DiffKey[] = ['EASY', 'MEDIUM', 'HARD'];

const DIFF_META: Record<DiffKey, { label: string; color: string; bg: string }> = {
  EASY:   { label: 'Easy',   color: 'var(--color-easy)',   bg: 'var(--color-easy-bg)' },
  MEDIUM: { label: 'Medium', color: 'var(--color-medium)', bg: 'var(--color-medium-bg)' },
  HARD:   { label: 'Hard',   color: 'var(--color-hard)',   bg: 'var(--color-hard-bg)' },
};

// Mock taxonomy — no topic/tag field exists on Challenge yet. Replaced by a real
// codegen-generated taxonomy later (see PLATFORM_UI_RESTYLE_PLAN.md Part 3). Filtering is a
// best-effort keyword match against title/description until then, so it may show zero results
// for challenges that don't happen to mention the topic by name.
const TOPICS: { name: string; blurb: string }[] = [
  { name: 'Concurrency', blurb: 'Problems that exercise threads, locks, and race conditions.' },
  { name: 'Databases', blurb: 'Schema design, queries, and transactional correctness.' },
  { name: 'Caching', blurb: 'Cache invalidation, eviction policies, and consistency tradeoffs.' },
  { name: 'Distributed Systems', blurb: 'Consensus, replication, and failure handling across nodes.' },
  { name: 'API Design', blurb: 'Designing clean, versionable, and predictable interfaces.' },
  { name: 'Data Structures', blurb: 'Core structures and the operations built on top of them.' },
];

function shuffleArray<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export function Dashboard() {
  const navigate = useNavigate();
  const user = useAppStore(state => state.user);
  const [diffFilters, setDiffFilters] = useState<Set<DiffKey>>(new Set());
  const [langFilter, setLangFilter] = useState('ALL');
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [shuffledList, setShuffledList] = useState<Challenge[] | null>(null);

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ['challenges'],
    queryFn: fetchChallenges,
  });

  const languages = useMemo(() => {
    if (!challenges) return [];
    return [...new Set(challenges.map(c => c.language))].sort();
  }, [challenges]);

  function toggleDiff(d: DiffKey) {
    setDiffFilters(prev => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });
    setShuffledList(null);
  }

  function toggleExpanded(id: string) {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleTopic(name: string) {
    setSelectedTopic(prev => (prev === name ? null : name));
    setShuffledList(null);
  }

  const baseFiltered = useMemo(() => {
    if (!challenges) return [];
    let list = langFilter === 'ALL' ? challenges : challenges.filter(c => c.language === langFilter);
    if (diffFilters.size > 0) {
      list = list.filter(c => diffFilters.has(c.difficulty.toUpperCase() as DiffKey));
    }
    if (selectedTopic) {
      const needle = selectedTopic.toLowerCase();
      list = list.filter(c =>
        c.title.toLowerCase().includes(needle) || (c.description ?? '').toLowerCase().includes(needle)
      );
    }
    return list;
  }, [challenges, diffFilters, langFilter, selectedTopic]);

  const displayProblems = shuffledList ?? baseFiltered;
  const newlyReleased = useMemo(() => (challenges ?? []).slice(0, 3), [challenges]);
  const activeTopic = TOPICS.find(t => t.name === selectedTopic) ?? null;

  if (isLoading) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-main)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <RefreshCcw className="animate-spin" style={{ color: 'var(--accent-color)' }} size={36} />
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>Loading challenges...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-main)' }}>
        <p style={{ color: 'var(--color-danger)', fontSize: 14 }}>Failed to load challenges. Make sure the backend is running.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

      {/* ── Left Sidebar — Topics ── */}
      <aside style={{
        width: sidebarCollapsed ? 44 : 240,
        flexShrink: 0,
        background: 'var(--bg-panel)',
        borderRight: '1px solid var(--border-main)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'width 0.18s ease',
      }}>
        <div style={{ padding: sidebarCollapsed ? '16px 0' : '20px 16px 12px', borderBottom: '1px solid var(--border-main)', display: 'flex', alignItems: 'center', justifyContent: sidebarCollapsed ? 'center' : 'space-between' }}>
          {!sidebarCollapsed && (
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Topics
            </span>
          )}
          <button
            onClick={() => setSidebarCollapsed(v => !v)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2 }}
          >
            <ChevronLeft size={14} style={{ transform: sidebarCollapsed ? 'rotate(180deg)' : 'none', transition: 'transform 0.18s ease' }} />
          </button>
        </div>

        {!sidebarCollapsed && (
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
            {TOPICS.map(topic => {
              const isActive = selectedTopic === topic.name;
              return (
                <button
                  key={topic.name}
                  onClick={() => toggleTopic(topic.name)}
                  style={{
                    width: '100%',
                    display: 'block',
                    padding: '9px 16px',
                    background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    border: 'none',
                    borderLeft: isActive ? '2px solid var(--accent-color)' : '2px solid transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'var(--accent-color)' : 'var(--text-main)',
                  }}
                >
                  {topic.name}
                </button>
              );
            })}
          </div>
        )}
      </aside>

      {/* ── Main Content ── */}
      <main style={{ flex: 1, background: 'var(--bg-main)', overflowY: 'auto', padding: 32 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 24px' }}>
          {greeting()}{user?.name ? `, ${user.name}` : ''}
        </h1>

        <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start' }}>
          {/* Problem list column */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {activeTopic && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, padding: '10px 14px', background: 'var(--accent-soft)', border: '1px solid var(--accent-color)', borderRadius: 8 }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>{activeTopic.name}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>{activeTopic.blurb}</span>
                </div>
                <button
                  onClick={() => setSelectedTopic(null)}
                  style={{ background: 'none', border: 'none', color: 'var(--accent-color)', cursor: 'pointer', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}
                >
                  Clear
                </button>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, gap: 16, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {DIFF_ORDER.map(d => {
                  const active = diffFilters.has(d);
                  const meta = DIFF_META[d];
                  return (
                    <button
                      key={d}
                      onClick={() => toggleDiff(d)}
                      style={{
                        padding: '6px 16px',
                        fontSize: 13,
                        fontWeight: 500,
                        borderRadius: 20,
                        border: active ? `1.5px solid ${meta.color}` : '1.5px solid var(--border-main)',
                        background: active ? meta.bg : 'var(--bg-panel)',
                        color: active ? meta.color : 'var(--text-muted)',
                        cursor: 'pointer',
                      }}
                    >
                      {meta.label}
                    </button>
                  );
                })}
                <select
                  value={langFilter}
                  onChange={e => setLangFilter(e.target.value)}
                  style={{ padding: '6px 10px', fontSize: 12, color: 'var(--text-main)', background: 'var(--bg-elevated)', border: '1px solid var(--border-main)', borderRadius: 6, cursor: 'pointer', outline: 'none' }}
                >
                  <option value="ALL">All Languages</option>
                  {languages.map(lang => (
                    <option key={lang} value={lang}>{lang.charAt(0).toUpperCase() + lang.slice(1)}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => setShuffledList(shuffleArray(baseFiltered))}
                style={{ padding: '6px 16px', fontSize: 13, fontWeight: 500, borderRadius: 20, border: '1.5px solid var(--border-main)', background: 'var(--bg-panel)', color: 'var(--text-main)', cursor: 'pointer' }}
              >
                ⇄ Shuffle
              </button>
            </div>

            {displayProblems.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: 0 }}>
                  {selectedTopic ? `No problems tagged "${selectedTopic}" yet.` : 'No problems match your filters.'}
                </p>
                <button
                  onClick={() => { setDiffFilters(new Set()); setSelectedTopic(null); setShuffledList(null); }}
                  style={{ marginTop: 12, fontSize: 13, color: 'var(--accent-color)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {displayProblems.map(c => {
                  const upper = c.difficulty.toUpperCase() as DiffKey;
                  const meta = DIFF_META[upper] ?? DIFF_META.EASY;
                  const isExpanded = expandedIds.has(c.id);
                  return (
                    <div
                      key={c.id}
                      onClick={() => navigate(`/workspace/${c.id}`)}
                      style={{ background: 'var(--bg-panel)', borderRadius: 8, border: '1px solid var(--border-main)', cursor: 'pointer', transition: 'border-color 0.15s' }}
                      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent-color)')}
                      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-main)')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px' }}>
                        {c.description && (
                          <button
                            onClick={e => { e.stopPropagation(); toggleExpanded(c.id); }}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0, flexShrink: 0 }}
                            title={isExpanded ? 'Collapse' : 'Expand'}
                          >
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          </button>
                        )}
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: meta.color, flexShrink: 0 }} />
                        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-main)', flex: 1 }}>{c.title}</span>
                        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: meta.color, background: meta.bg, padding: '2px 8px', borderRadius: 12 }}>
                          {meta.label}
                        </span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '2px 8px', borderRadius: 12 }}>
                          {c.language}
                        </span>
                      </div>
                      {isExpanded && c.description && (
                        <div style={{ padding: '0 16px 16px 44px' }}>
                          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>{c.description}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Right Rail ── */}
          <aside style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-main)', borderRadius: 10, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <Flame size={18} color="#f59e0b" />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>Streak</span>
              </div>
              <p style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-main)', margin: '4px 0 0' }}>4 days</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>Keep it going — solve one today.</p>
            </div>

            <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-main)', borderRadius: 10, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Sparkles size={16} className="text-[var(--accent-color)]" />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>Newly released</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {newlyReleased.map(c => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/workspace/${c.id}`)}
                    style={{ cursor: 'pointer', padding: '8px 10px', borderRadius: 6, background: 'var(--bg-elevated)' }}
                  >
                    <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>{c.title}</p>
                    <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0', textTransform: 'uppercase' }}>{c.language}</p>
                  </div>
                ))}
                {newlyReleased.length === 0 && (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>Nothing new yet.</p>
                )}
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
