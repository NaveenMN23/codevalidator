import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { RefreshCcw } from 'lucide-react';
import { fetchChallenges } from '../../workspace/api';
import type { Challenge } from '../../workspace/workspace.types';

type DiffKey = 'EASY' | 'MEDIUM' | 'HARD';

const DIFF_ORDER: DiffKey[] = ['EASY', 'MEDIUM', 'HARD'];

const DIFF_META: Record<DiffKey, { label: string; color: string; bg: string; border: string }> = {
  EASY:   { label: 'Easy',   color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0' },
  MEDIUM: { label: 'Medium', color: '#f59e0b', bg: '#fffbeb', border: '#fde68a' },
  HARD:   { label: 'Hard',   color: '#ef4444', bg: '#fef2f2', border: '#fecaca' },
};

interface ChallengeGroup {
  baseName: string;
  displayTitle: string;
  difficulties: Partial<Record<DiffKey, Challenge[]>>;
  languages: string[];
  hardestDiff: DiffKey;
}

function toBaseSlug(slug: string): string {
  return slug
    .replace(/-scenario-\d+$/i, '')
    .replace(/-(easy|medium|hard)(-.+)?$/i, '');
}

function slugToTitle(slug: string): string {
  return slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function shuffleArray<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export function Dashboard() {
  const navigate = useNavigate();
  const [selectedBase, setSelectedBase] = useState<string | null>(null);
  const [diffFilters, setDiffFilters] = useState<Set<DiffKey>>(new Set());
  const [langFilter, setLangFilter] = useState('ALL');

  function toggleDiff(d: DiffKey) {
    setDiffFilters(prev => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });
    setShuffledList(null);
  }
  const [shuffledList, setShuffledList] = useState<Challenge[] | null>(null);

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ['challenges'],
    queryFn: fetchChallenges,
  });

  const languages = useMemo(() => {
    if (!challenges) return [];
    return [...new Set(challenges.map(c => c.language))].sort();
  }, [challenges]);

  const groups = useMemo((): ChallengeGroup[] => {
    if (!challenges) return [];
    const map = new Map<string, ChallengeGroup>();
    for (const c of challenges) {
      const rawSlug = c.slug ?? c.title.toLowerCase().replace(/\s+/g, '-');
      const base = toBaseSlug(rawSlug) || rawSlug;
      if (!map.has(base)) {
        map.set(base, {
          baseName: base,
          displayTitle: slugToTitle(base),
          difficulties: {},
          languages: [],
          hardestDiff: 'EASY',
        });
      }
      const g = map.get(base)!;
      const upper = c.difficulty.toUpperCase();
      const diff: DiffKey = DIFF_ORDER.includes(upper as DiffKey) ? (upper as DiffKey) : 'EASY';
      if (!g.difficulties[diff]) g.difficulties[diff] = [];
      g.difficulties[diff]!.push(c);
      if (!g.languages.includes(c.language)) g.languages.push(c.language);
      if (DIFF_ORDER.indexOf(diff) > DIFF_ORDER.indexOf(g.hardestDiff)) g.hardestDiff = diff;
    }
    return [...map.values()];
  }, [challenges]);

  const filteredGroups = useMemo(() => {
    let result = langFilter === 'ALL' ? groups : groups.filter(g => g.languages.includes(langFilter));
    if (diffFilters.size > 0) {
      result = result.filter(g =>
        [...diffFilters].some(d => g.difficulties[d] && g.difficulties[d]!.length > 0)
      );
    }
    return result;
  }, [groups, langFilter, diffFilters]);

  const baseFiltered = useMemo(() => {
    if (!challenges) return [];
    let list = langFilter === 'ALL' ? challenges : challenges.filter(c => c.language === langFilter);
    if (diffFilters.size > 0) {
      list = list.filter(c => diffFilters.has(c.difficulty.toUpperCase() as DiffKey));
    }
    return list;
  }, [challenges, diffFilters, langFilter]);

  const displayProblems = shuffledList ?? baseFiltered;
  const selectedGroup = groups.find(g => g.baseName === selectedBase) ?? null;

  if (isLoading) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', background: '#f4f4f6' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <RefreshCcw className="animate-spin" style={{ color: '#2563eb' }} size={36} />
          <p style={{ color: '#6b7280', fontSize: 14, margin: 0 }}>Loading challenges...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', background: '#f4f4f6' }}>
        <p style={{ color: '#ef4444', fontSize: 14 }}>Failed to load challenges. Make sure the backend is running.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

      {/* ── Left Sidebar ── */}
      <aside style={{
        width: 260,
        flexShrink: 0,
        background: '#ffffff',
        borderRight: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header + language filter */}
        <div style={{ padding: '20px 16px 12px', borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Challenges
            </span>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#2563eb', background: '#eff6ff', padding: '2px 8px', borderRadius: 12 }}>
              {filteredGroups.length}
            </span>
          </div>
          <select
            value={langFilter}
            onChange={e => { setLangFilter(e.target.value); setSelectedBase(null); setShuffledList(null); }}
            style={{ width: '100%', padding: '6px 10px', fontSize: 12, color: '#374151', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 6, cursor: 'pointer', outline: 'none' }}
          >
            <option value="ALL">All Languages</option>
            {languages.map(lang => (
              <option key={lang} value={lang}>{lang.charAt(0).toUpperCase() + lang.slice(1)}</option>
            ))}
          </select>
        </div>

        {/* Challenge name list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {filteredGroups.length === 0 ? (
            <p style={{ padding: 16, fontSize: 12, color: '#9ca3af', textAlign: 'center', margin: 0 }}>No challenges found</p>
          ) : (
            filteredGroups.map(g => {
              const isActive = selectedBase === g.baseName;
              return (
                <button
                  key={g.baseName}
                  onClick={() => setSelectedBase(isActive ? null : g.baseName)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '9px 16px',
                    background: isActive ? '#eff6ff' : 'transparent',
                    border: 'none',
                    borderLeft: isActive ? '2px solid #2563eb' : '2px solid transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: DIFF_META[g.hardestDiff].color,
                    flexShrink: 0, display: 'inline-block',
                  }} />
                  <span style={{ fontSize: 13, fontWeight: isActive ? 600 : 400, color: isActive ? '#1d4ed8' : '#111827' }}>
                    {g.displayTitle}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main style={{ flex: 1, background: '#f4f4f6', overflowY: 'auto', padding: 32 }}>
        {!selectedGroup ? (
          /* Default: all problems grid */
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
              {/* Difficulty filter pills — multi-select */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
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
                        border: active ? `1.5px solid ${meta.color}` : '1.5px solid #e5e7eb',
                        background: active ? meta.bg : '#ffffff',
                        color: active ? meta.color : '#6b7280',
                        cursor: 'pointer',
                      }}
                    >
                      {meta.label}
                    </button>
                  );
                })}
              </div>
              {/* Shuffle button */}
              <button
                onClick={() => setShuffledList(shuffleArray(baseFiltered))}
                style={{ padding: '6px 16px', fontSize: 13, fontWeight: 500, borderRadius: 20, border: '1.5px solid #111', background: '#fff', color: '#111', cursor: 'pointer' }}
              >
                ⇄ Shuffle
              </button>
            </div>

            {displayProblems.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                <p style={{ fontSize: 14, color: '#9ca3af', margin: 0 }}>No problems match your filters.</p>
                <button
                  onClick={() => { setDiffFilters(new Set()); setShuffledList(null); }}
                  style={{ marginTop: 12, fontSize: 13, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                {displayProblems.map(c => {
                  const upper = c.difficulty.toUpperCase() as DiffKey;
                  const meta = DIFF_META[upper] ?? DIFF_META.EASY;
                  return (
                    <div key={c.id} style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>{c.title}</h3>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: meta.color, background: meta.bg, border: `1px solid ${meta.border}`, padding: '2px 8px', borderRadius: 12 }}>
                          {meta.label}
                        </span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', background: '#f3f4f6', padding: '2px 8px', borderRadius: 12 }}>
                          {c.language}
                        </span>
                      </div>
                      {c.description && (
                        <p style={{ fontSize: 13, color: '#6b7280', margin: 0, lineHeight: 1.5 }}>
                          {c.description.length > 100 ? c.description.slice(0, 100) + '…' : c.description}
                        </p>
                      )}
                      <button
                        onClick={() => navigate(`/workspace/${c.id}`)}
                        style={{ marginTop: 'auto', padding: '8px 16px', background: '#000', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-start' }}
                      >
                        Start →
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          /* Challenge detail: tiers + scenarios */
          <>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>
              <button
                onClick={() => setSelectedBase(null)}
                style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontSize: 12, padding: 0, fontWeight: 500 }}
              >
                Challenges
              </button>
              <span style={{ margin: '0 6px', color: '#9ca3af' }}>›</span>
              <span>{selectedGroup.displayTitle}</span>
            </div>

            <h2 style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', margin: '0 0 28px' }}>
              {selectedGroup.displayTitle}
            </h2>

            {DIFF_ORDER.map(diff => {
              const items = selectedGroup.difficulties[diff];
              if (!items || items.length === 0) return null;
              const meta = DIFF_META[diff];
              return (
                <div key={diff} style={{ marginBottom: 32 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: meta.color, display: 'inline-block', flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: meta.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      {meta.label}
                    </span>
                    <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {items.map((c, idx) => (
                      <div key={c.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#111827', flex: 1 }}>Scenario {idx + 1}</span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', background: '#f3f4f6', padding: '3px 10px', borderRadius: 12 }}>
                          {c.language}
                        </span>
                        <button
                          onClick={() => navigate(`/workspace/${c.id}`)}
                          style={{ padding: '7px 18px', background: '#000', color: '#fff', border: 'none', borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
                        >
                          Start →
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            {DIFF_ORDER.every(d => !selectedGroup.difficulties[d]?.length) && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#9ca3af', fontSize: 14 }}>
                No scenarios available yet.
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
