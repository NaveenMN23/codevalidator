import { useQuery } from '@tanstack/react-query'
import { listSubmissions, getQueueDepth } from '../lib/api'
import { useState } from 'react'
import { ChevronLeft, ChevronRight, Activity } from 'lucide-react'

type Submission = { id: string; userId: string; problemId: string; submissionLink: string; score?: number | null; submittedAt: string }

export default function MonitoringPage() {
  const [page, setPage] = useState(0)

  const { data } = useQuery({
    queryKey: ['submissions', page],
    queryFn: () => listSubmissions(page),
    refetchInterval: 30_000,
  })

  const { data: queueData } = useQuery({
    queryKey: ['queue-depth'],
    queryFn: getQueueDepth,
    refetchInterval: 30_000,
  })

  const submissions: Submission[] = data?.content || []
  const totalPages: number = data?.totalPages || 1
  const totalElements: number = data?.totalElements || 0
  const queueDepth: number = queueData?.depth ?? 0

  const gradedCount = submissions.filter((s) => s.score != null).length
  const pendingCount = submissions.filter((s) => s.score == null).length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: '0 0 4px', color: 'var(--text-primary)' }}>Monitoring</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 14 }}>Live submission queue · refreshes every 30s</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10 }}>
          <Activity size={14} color={queueDepth > 0 ? '#2563eb' : 'var(--text-secondary)'} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{queueDepth}</span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>in grading queue</span>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Total', value: totalElements, color: 'var(--text-primary)' },
          { label: 'Graded', value: gradedCount, color: '#059669' },
          { label: 'Pending', value: pendingCount, color: '#d97706' },
          { label: 'Queue Depth', value: queueDepth, color: '#2563eb' },
        ].map((stat) => (
          <div key={stat.label} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: stat.color, marginBottom: 2 }}>{stat.value}</div>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              {['User', 'Problem', 'Status', 'Score', 'Submitted'].map((h) => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {submissions.map((s) => {
              const isGraded = s.score != null
              return (
                <tr key={s.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{s.userId.slice(0, 8)}…</td>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{s.problemId.slice(0, 8)}…</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                      background: isGraded ? '#d1fae5' : '#fef9c3',
                      color: isGraded ? '#065f46' : '#854d0e',
                    }}>
                      {isGraded ? 'Graded' : 'Pending'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 13, fontWeight: 600, color: isGraded ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {isGraded ? `${s.score}%` : '—'}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {new Date(s.submittedAt).toLocaleString()}
                  </td>
                </tr>
              )
            })}
            {submissions.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>No submissions yet</td></tr>
            )}
          </tbody>
        </table>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Page {page + 1} of {totalPages}</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
              style={{ padding: '5px 8px', borderRadius: 6, border: '1px solid var(--border-color)', background: 'none', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.5 : 1, display: 'flex', color: 'var(--text-primary)' }}>
              <ChevronLeft size={14} />
            </button>
            <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              style={{ padding: '5px 8px', borderRadius: 6, border: '1px solid var(--border-color)', background: 'none', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', opacity: page >= totalPages - 1 ? 0.5 : 1, display: 'flex', color: 'var(--text-primary)' }}>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
