import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listProblems, createProblem, updateProblem, deleteProblem, setPublished } from '../lib/api'
import { Plus, Edit2, Trash2, Globe, EyeOff } from 'lucide-react'

type Problem = { id: string; slug: string; title: string; difficulty: string; tiers?: string[]; isPublished: boolean; tags: string[]; description?: string; problemLink?: string }

const INPUT: React.CSSProperties = { width: '100%', padding: '9px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 14, color: 'var(--text-primary)', outline: 'none', boxSizing: 'border-box' }
const LABEL: React.CSSProperties = { fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }

function ProblemForm({ initial, onSave, onCancel }: { initial?: Problem; onSave: (d: object) => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    slug: initial?.slug || '',
    title: initial?.title || '',
    description: initial?.description || '',
    difficulty: initial?.difficulty || 'EASY',
    problemLink: initial?.problemLink || '',
    tags: initial?.tags?.join(', ') || '',
  })
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ background: 'var(--bg-surface)', borderRadius: 12, padding: 28, width: 480, border: '1px solid var(--border-color)', maxHeight: '80vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>{initial ? 'Edit Problem' : 'New Problem'}</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {['slug', 'title', 'description', 'problemLink'].map((field) => (
            <div key={field}>
              <span style={LABEL}>{field}</span>
              {field === 'description' ? (
                <textarea value={(form as Record<string, string>)[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} rows={3} style={{ ...INPUT, resize: 'vertical' }} />
              ) : (
                <input value={(form as Record<string, string>)[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} style={INPUT} />
              )}
            </div>
          ))}
          <div>
            <span style={LABEL}>Difficulty</span>
            <select value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })} style={INPUT}>
              {['EASY', 'MEDIUM', 'HARD'].map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <span style={LABEL}>Tags (comma-separated)</span>
            <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="e.g. system-design, concurrency" style={INPUT} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={{ padding: '8px 16px', borderRadius: 8, background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>Cancel</button>
          <button onClick={() => onSave({ ...form, tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean) })}
            style={{ padding: '8px 16px', borderRadius: 8, background: '#000', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ProblemsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Problem | undefined>()

  const { data } = useQuery({ queryKey: ['problems'], queryFn: () => listProblems() })
  const problems: Problem[] = data?.content || []

  const createMut = useMutation({ mutationFn: createProblem, onSuccess: () => { qc.invalidateQueries({ queryKey: ['problems'] }); setShowForm(false) } })
  const updateMut = useMutation({ mutationFn: ({ id, d }: { id: string; d: object }) => updateProblem(id, d), onSuccess: () => { qc.invalidateQueries({ queryKey: ['problems'] }); setEditing(undefined) } })
  const deleteMut = useMutation({ mutationFn: deleteProblem, onSuccess: () => qc.invalidateQueries({ queryKey: ['problems'] }) })
  const publishMut = useMutation({ mutationFn: ({ id, v }: { id: string; v: boolean }) => setPublished(id, v), onSuccess: () => qc.invalidateQueries({ queryKey: ['problems'] }) })

  const DIFF_COLOR: Record<string, string> = { EASY: '#059669', MEDIUM: '#d97706', HARD: '#dc2626' }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: '0 0 4px', color: 'var(--text-primary)' }}>Problems</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 14 }}>{problems.length} problems total</p>
        </div>
        <button onClick={() => setShowForm(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px', background: '#000', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>
          <Plus size={14} /> New Problem
        </button>
      </div>

      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              {['Title', 'Difficulty', 'Tags', 'Visibility', 'Actions'].map((h) => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {problems.map((p) => (
              <tr key={p.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text-primary)' }}>{p.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{p.slug}</div>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: DIFF_COLOR[p.difficulty?.toUpperCase()] || 'var(--text-secondary)' }}>
                    {p.difficulty?.toUpperCase() ?? '—'}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {(p.tags || []).slice(0, 3).map((t) => (
                      <span key={t} style={{ padding: '2px 6px', background: 'var(--bg-elevated)', borderRadius: 4, fontSize: 11, color: 'var(--text-secondary)' }}>{t}</span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <button
                    onClick={() => publishMut.mutate({ id: p.id, v: !p.isPublished })}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, border: '1px solid var(--border-color)', background: p.isPublished ? '#d1fae5' : 'var(--bg-elevated)', color: p.isPublished ? '#065f46' : 'var(--text-secondary)', cursor: 'pointer' }}
                  >
                    {p.isPublished ? <><Globe size={12} /> Published</> : <><EyeOff size={12} /> Draft</>}
                  </button>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => setEditing(p)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 4, display: 'flex' }}><Edit2 size={14} /></button>
                    <button onClick={() => { if (confirm('Delete?')) deleteMut.mutate(p.id) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', padding: 4, display: 'flex' }}><Trash2 size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
            {problems.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', fontSize: 14 }}>No problems yet. Generate one to get started.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && <ProblemForm onSave={(d) => createMut.mutate(d)} onCancel={() => setShowForm(false)} />}
      {editing && <ProblemForm initial={editing} onSave={(d) => updateMut.mutate({ id: editing.id, d })} onCancel={() => setEditing(undefined)} />}
    </div>
  )
}
