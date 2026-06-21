import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { previewDesign, refineDesign, approveGeneration, cancelJob, retryJob, getJobStatus, getGenerationHistory } from '../lib/api'
import { useAdminStore } from '../store'
import { StatusBadge } from '../components/StatusBadge'
import { CheckCircle2, RefreshCw, ChevronDown, ChevronUp, Loader2, XCircle, ArrowRight, X, AlertTriangle, RotateCcw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const LABEL: React.CSSProperties = { fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8, display: 'block' }
const INPUT: React.CSSProperties = { width: '100%', padding: '9px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 14, color: 'var(--text-primary)', outline: 'none', boxSizing: 'border-box' }
const BTN = (variant: 'primary' | 'secondary' | 'ghost' | 'danger' | 'amber'): React.CSSProperties => ({
  padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer',
  background: variant === 'primary' ? '#000' : variant === 'danger' ? '#fee2e2' : variant === 'amber' ? '#fffbeb' : variant === 'secondary' ? 'var(--bg-elevated)' : 'transparent',
  color: variant === 'primary' ? '#fff' : variant === 'danger' ? '#b91c1c' : variant === 'amber' ? '#92400e' : 'var(--text-primary)',
  border: variant !== 'primary' && variant !== 'ghost' ? `1px solid ${variant === 'danger' ? '#fca5a5' : variant === 'amber' ? '#fcd34d' : 'var(--border-color)'}` : 'none',
} as React.CSSProperties)

type Job = {
  id: string; status: string; prompt: string; languages: string[]; tiers: string[]
  scenariosPerTier: number; debugScenariosPerTier: number
  designJson?: string; resultJson?: string; error?: string; problemId?: string
  createdAt: string; updatedAt: string
}

function elapsedMs(updatedAt: string): number {
  return Date.now() - new Date(updatedAt).getTime()
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`
}

function ScenarioCard({ scenario, tag }: { scenario: Record<string, unknown>; tag: string }) {
  return (
    <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-color)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{tag}</span>
        <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: scenario.type === 'debug' ? '#fee2e2' : '#dbeafe', color: scenario.type === 'debug' ? '#991b1b' : '#1d4ed8' }}>
          {String(scenario.type || 'implement')}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {String(scenario.description || '')}
      </p>
    </div>
  )
}

function DesignReview({ job, onRefine, onApprove, onReject, refining, approving, rejecting }: {
  job: Job; onRefine: (f: string) => void; onApprove: () => void; onReject: (reason: string) => void
  refining: boolean; approving: boolean; rejecting: boolean
}) {
  const [feedback, setFeedback] = useState('')
  const [expandedTier, setExpandedTier] = useState<string | null>('easy')
  const [showReject, setShowReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  let design: Record<string, unknown> | null = null
  try { design = job.designJson ? JSON.parse(job.designJson) : null } catch { design = null }
  const tiers: Record<string, unknown> = (design?.difficulty_tiers as Record<string, unknown>) || {}

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>Design Preview</h3>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
            {job.prompt} · {job.languages?.join(', ')} · {job.tiers?.join(', ')}
          </p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {Object.entries(tiers).map(([tier, tierData]) => {
          const td = tierData as Record<string, unknown>
          const scenarios = (td.scenarios as unknown[]) || []
          const isOpen = expandedTier === tier
          return (
            <div key={tier} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, overflow: 'hidden' }}>
              <button
                onClick={() => setExpandedTier(isOpen ? null : tier)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{tier}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{scenarios.length} scenarios</span>
                </div>
                {isOpen ? <ChevronUp size={16} color="var(--text-secondary)" /> : <ChevronDown size={16} color="var(--text-secondary)" />}
              </button>
              {isOpen && (
                <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {!!td.description && (
                    <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{String(td.description)}</p>
                  )}
                  {scenarios.map((s) => {
                    const sc = s as Record<string, unknown>
                    return <ScenarioCard key={String(sc.scenario_tag || sc.tag)} scenario={sc} tag={String(sc.scenario_tag || sc.tag || '')} />
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Refinement */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 20, marginBottom: 16 }}>
        <span style={LABEL}>Refinement feedback (optional)</span>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="e.g. Make the hard tier use event-driven architecture, add more debug scenarios..."
          rows={3}
          style={{ ...INPUT, resize: 'vertical', lineHeight: 1.5 }}
        />
        <button
          onClick={() => { onRefine(feedback); setFeedback('') }}
          disabled={refining}
          style={{ ...BTN('secondary'), marginTop: 12, display: 'flex', alignItems: 'center', gap: 6, opacity: refining ? 0.7 : 1 }}
        >
          {refining ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          {refining ? 'Regenerating…' : 'Regenerate design'}
        </button>
      </div>

      {/* Approve + Reject row */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <button
          onClick={onApprove}
          disabled={approving}
          style={{ ...BTN('primary'), flex: 1, padding: '12px 0', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: approving ? 0.7 : 1 }}
        >
          {approving ? <Loader2 size={16} /> : <CheckCircle2 size={16} />}
          {approving ? 'Submitting…' : 'Approve & Generate Full Challenge'}
        </button>
        <button
          onClick={() => setShowReject(!showReject)}
          disabled={rejecting}
          style={{ ...BTN('danger'), display: 'flex', alignItems: 'center', gap: 6, padding: '12px 16px', opacity: rejecting ? 0.7 : 1 }}
        >
          <X size={14} /> Reject
        </button>
      </div>

      {/* Reject reason inline panel */}
      {showReject && (
        <div style={{ marginTop: 12, padding: 16, background: '#fff7f7', border: '1px solid #fca5a5', borderRadius: 10 }}>
          <span style={{ ...LABEL, color: '#b91c1c' }}>Rejection reason (optional)</span>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Explain what was wrong with this design…"
            rows={2}
            style={{ ...INPUT, resize: 'vertical', lineHeight: 1.5, borderColor: '#fca5a5' }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              onClick={() => onReject(rejectReason)}
              disabled={rejecting}
              style={{ ...BTN('danger'), display: 'flex', alignItems: 'center', gap: 6, opacity: rejecting ? 0.7 : 1 }}
            >
              {rejecting ? <Loader2 size={13} /> : <X size={13} />}
              Confirm Reject
            </button>
            <button onClick={() => setShowReject(false)} style={{ ...BTN('secondary') }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function GenerationPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { activeJobId, setActiveJobId } = useAdminStore()
  const [form, setForm] = useState({ prompt: '', languages: ['node'], tiers: ['easy', 'medium', 'hard'], implementScenariosPerTier: 2, debugScenariosPerTier: 1 })
  const [activeTab, setActiveTab] = useState<'new' | 'history'>('new')
  const [now, setNow] = useState(() => Date.now())

  const { data: currentJob } = useQuery<Job>({
    queryKey: ['active-job', activeJobId],
    queryFn: () => getJobStatus(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED' ? false : 10_000
    },
  })

  useEffect(() => {
    if (currentJob?.status === 'COMPLETED' || currentJob?.status === 'FAILED' || currentJob?.status === 'CANCELLED') {
      qc.invalidateQueries({ queryKey: ['history'] })
    }
  }, [currentJob?.status, qc])

  // Tick every second while a job is in-flight so elapsed time updates live
  useEffect(() => {
    const s = currentJob?.status
    if (s !== 'DESIGNING' && s !== 'GENERATING') return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [currentJob?.status])

  const { data: history = [] } = useQuery<Job[]>({
    queryKey: ['history'],
    queryFn: getGenerationHistory,
    enabled: activeTab === 'history',
  })

  const previewMutation = useMutation({
    mutationFn: () => previewDesign({
      prompt: form.prompt,
      languages: form.languages,
      tiers: form.tiers,
      scenariosPerTier: form.implementScenariosPerTier + form.debugScenariosPerTier,
      debugScenariosPerTier: form.debugScenariosPerTier,
    }),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const refineMutation = useMutation({
    mutationFn: (feedback: string) => refineDesign(activeJobId!, feedback),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['active-job', activeJobId] }),
  })

  const approveMutation = useMutation({
    mutationFn: () => approveGeneration(activeJobId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['active-job', activeJobId] }),
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelJob(activeJobId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['active-job', activeJobId] }),
  })

  const rejectMutation = useMutation({
    mutationFn: (_reason: string) => cancelJob(activeJobId!),
    onSuccess: () => {
      const prompt = currentJob?.prompt || ''
      setActiveJobId(null)
      qc.removeQueries({ queryKey: ['active-job'] })
      if (prompt) setForm((f) => ({ ...f, prompt }))
    },
  })

  const retryMutation = useMutation({
    mutationFn: (jobId: string) => retryJob(jobId),
    onSuccess: (_, jobId) => {
      setActiveJobId(jobId)
      setActiveTab('new')
      qc.invalidateQueries({ queryKey: ['active-job', jobId] })
    },
  })

  const handleNewJob = () => {
    setActiveJobId(null)
    qc.removeQueries({ queryKey: ['active-job'] })
  }

  const handleResumeJob = (job: Job) => {
    setActiveJobId(job.id)
    setActiveTab('new')
  }

  const LANG_OPTIONS = ['node', 'java', 'python']
  const TIER_OPTIONS = ['easy', 'medium', 'hard']
  const toggleArr = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]

  const status = currentJob?.status
  const isDesigning = status === 'DESIGNING'
  const canShowDesign = status === 'AWAITING_APPROVAL' && !!currentJob?.designJson
  const isGenerating = status === 'GENERATING'
  const isCompleted = status === 'COMPLETED'
  const isFailed = status === 'FAILED'
  const isCancelled = status === 'CANCELLED'
  const hasActiveJob = !!activeJobId

  // Elapsed time driven by `now` which ticks every second (see useEffect above)
  const elapsed = currentJob?.updatedAt ? now - new Date(currentJob.updatedAt).getTime() : 0
  const isDesigningStuck = isDesigning && elapsed > 2 * 60 * 1000
  const isGeneratingStuck = isGenerating && elapsed > 10 * 60 * 1000

  const isHistoryStuck = (job: Job) => {
    const e = job.updatedAt ? elapsedMs(job.updatedAt) : 0
    return (job.status === 'DESIGNING' && e > 2 * 60 * 1000) || (job.status === 'GENERATING' && e > 10 * 60 * 1000)
  }

  return (
    <div style={{ maxWidth: 820 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, margin: '0 0 4px', color: 'var(--text-primary)' }}>Challenge Generation</h1>
      <p style={{ color: 'var(--text-secondary)', margin: '0 0 28px', fontSize: 14 }}>AI-powered challenge creation with review before generation</p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 24, background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 4, width: 'fit-content' }}>
        {(['new', 'history'] as const).map((t) => (
          <button key={t} onClick={() => setActiveTab(t)}
            style={{ padding: '6px 16px', borderRadius: 6, fontSize: 13, fontWeight: 500, border: 'none', cursor: 'pointer', background: activeTab === t ? '#000' : 'transparent', color: activeTab === t ? '#fff' : 'var(--text-secondary)' }}>
            {t === 'new' ? 'New Challenge' : 'History'}
          </button>
        ))}
      </div>

      {activeTab === 'new' && (
        <>
          {/* New challenge form — only when no active job */}
          {!hasActiveJob && (
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 24 }}>
              <div style={{ marginBottom: 20 }}>
                <span style={LABEL}>Challenge prompt</span>
                <textarea
                  value={form.prompt}
                  onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                  placeholder="Describe the challenge… e.g. Build a ticket booking system like BookMyShow with seat selection, payment flow, and overbooking prevention"
                  rows={4}
                  style={{ ...INPUT, resize: 'vertical', lineHeight: 1.6 }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20 }}>
                <div>
                  <span style={LABEL}>Languages</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {LANG_OPTIONS.map((l) => (
                      <label key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                        <input type="checkbox" checked={form.languages.includes(l)} onChange={() => setForm({ ...form, languages: toggleArr(form.languages, l) })} />
                        {l}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <span style={LABEL}>Tiers</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {TIER_OPTIONS.map((t) => (
                      <label key={t} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                        <input type="checkbox" checked={form.tiers.includes(t)} onChange={() => setForm({ ...form, tiers: toggleArr(form.tiers, t) })} />
                        {t}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <span style={LABEL}>Scenarios per tier</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Feature (implement)</label>
                      <select value={form.implementScenariosPerTier} onChange={(e) => setForm({ ...form, implementScenariosPerTier: Number(e.target.value) })} style={{ ...INPUT, width: '100%' }}>
                        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Bug (debug)</label>
                      <select value={form.debugScenariosPerTier} onChange={(e) => setForm({ ...form, debugScenariosPerTier: Number(e.target.value) })} style={{ ...INPUT, width: '100%' }}>
                        {[0, 1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </div>
                    <p style={{ margin: 0, fontSize: 11, color: 'var(--text-secondary)' }}>
                      Total: {form.implementScenariosPerTier + form.debugScenariosPerTier} per tier
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={() => previewMutation.mutate()}
                disabled={!form.prompt.trim() || form.languages.length === 0 || previewMutation.isPending}
                style={{ ...BTN('primary'), padding: '10px 24px', opacity: previewMutation.isPending ? 0.7 : 1 }}
              >
                {previewMutation.isPending ? 'Submitting…' : 'Preview Design'}
              </button>
            </div>
          )}

          {/* Designing */}
          {isDesigning && currentJob && (
            <div style={{ marginTop: 24, padding: 24, background: 'var(--bg-surface)', border: `1px solid ${isDesigningStuck ? '#fcd34d' : 'var(--border-color)'}`, borderRadius: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: isDesigningStuck ? 16 : 0 }}>
                <Loader2 size={22} color="var(--accent-color)" style={{ flexShrink: 0 }} className="spin" />
                <div style={{ flex: 1 }}>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>Generating design…</p>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
                    <em>{currentJob.prompt}</em> · elapsed: {formatElapsed(elapsed)}
                  </p>
                </div>
              </div>
              {isDesigningStuck && (
                <div style={{ padding: '12px 14px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={15} color="#92400e" />
                    <span style={{ fontSize: 13, color: '#92400e' }}>Taking longer than usual — codegen may be stuck or restarting.</span>
                  </div>
                  <button
                    onClick={() => retryMutation.mutate(currentJob.id)}
                    disabled={retryMutation.isPending}
                    style={{ ...BTN('amber'), display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, whiteSpace: 'nowrap', opacity: retryMutation.isPending ? 0.7 : 1 }}
                  >
                    {retryMutation.isPending ? <Loader2 size={12} /> : <RotateCcw size={12} />} Force Retry
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Design ready */}
          {canShowDesign && currentJob && (
            <DesignReview
              job={currentJob}
              onRefine={(f) => refineMutation.mutate(f)}
              onApprove={() => approveMutation.mutate()}
              onReject={(reason) => rejectMutation.mutate(reason)}
              refining={refineMutation.isPending}
              approving={approveMutation.isPending}
              rejecting={rejectMutation.isPending}
            />
          )}

          {/* Generating full challenge */}
          {isGenerating && currentJob && (
            <div style={{ marginTop: 24, padding: 24, background: 'var(--bg-surface)', border: `1px solid ${isGeneratingStuck ? '#fcd34d' : 'var(--border-color)'}`, borderRadius: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                <Loader2 size={22} color="var(--accent-color)" style={{ flexShrink: 0 }} className="spin" />
                <div style={{ flex: 1 }}>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>Full generation in progress</p>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
                    Building skeletons, tests, and blueprints for <em>{currentJob.prompt}</em> · elapsed: {formatElapsed(elapsed)}
                  </p>
                </div>
              </div>
              {isGeneratingStuck && (
                <div style={{ padding: '12px 14px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={15} color="#92400e" />
                    <span style={{ fontSize: 13, color: '#92400e' }}>Taking longer than expected — codegen may be stuck or have crashed.</span>
                  </div>
                  <button
                    onClick={() => retryMutation.mutate(currentJob.id)}
                    disabled={retryMutation.isPending}
                    style={{ ...BTN('amber'), display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, whiteSpace: 'nowrap', opacity: retryMutation.isPending ? 0.7 : 1 }}
                  >
                    {retryMutation.isPending ? <Loader2 size={12} /> : <RotateCcw size={12} />} Force Retry
                  </button>
                </div>
              )}
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                style={{ ...BTN('danger'), display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, opacity: cancelMutation.isPending ? 0.7 : 1 }}
              >
                {cancelMutation.isPending ? <Loader2 size={12} /> : <X size={12} />}
                Cancel generation
              </button>
            </div>
          )}

          {/* Completed */}
          {isCompleted && (
            <div style={{ marginTop: 24, padding: 24, background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <CheckCircle2 size={20} color="#065f46" />
                <span style={{ fontWeight: 700, color: '#065f46', fontSize: 15 }}>Generation complete!</span>
              </div>
              <p style={{ margin: '0 0 16px', fontSize: 13, color: '#047857' }}>
                Challenge assets uploaded. The problem has been created as a draft — go to Problems to review and publish it for students.
              </p>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => navigate('/problems')}
                  style={{ ...BTN('primary'), display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}
                >
                  Go to Problems <ArrowRight size={14} />
                </button>
                <button onClick={handleNewJob} style={{ ...BTN('secondary'), fontSize: 13 }}>
                  Generate another
                </button>
              </div>
            </div>
          )}

          {/* Cancelled */}
          {isCancelled && (
            <div style={{ marginTop: 24, padding: 24, background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <XCircle size={20} color="#6b7280" />
                <span style={{ fontWeight: 700, color: '#374151', fontSize: 15 }}>Generation cancelled</span>
              </div>
              <button onClick={handleNewJob} style={{ ...BTN('secondary'), fontSize: 13 }}>Start a new challenge</button>
            </div>
          )}

          {/* Failed */}
          {isFailed && currentJob && (
            <div style={{ marginTop: 24, padding: 24, background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <XCircle size={20} color="#dc2626" />
                <span style={{ fontWeight: 700, color: '#dc2626', fontSize: 15 }}>Generation failed</span>
              </div>
              {currentJob.error && (
                <pre style={{ margin: '0 0 16px', fontSize: 12, color: '#b91c1c', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#fff1f1', borderRadius: 6, padding: '10px 12px' }}>
                  {currentJob.error}
                </pre>
              )}
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => retryMutation.mutate(currentJob.id)}
                  disabled={retryMutation.isPending}
                  style={{ ...BTN('secondary'), display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, opacity: retryMutation.isPending ? 0.7 : 1 }}
                >
                  {retryMutation.isPending ? <Loader2 size={14} /> : <RotateCcw size={14} />}
                  Retry (same job)
                </button>
                <button onClick={handleNewJob} style={{ ...BTN('ghost'), fontSize: 13, border: '1px solid var(--border-color)' }}>Start fresh</button>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === 'history' && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                {['Prompt', 'Languages', 'Status', 'Created', ''].map((h) => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(history as Job[]).map((job) => (
                <tr key={job.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-primary)', maxWidth: 260 }}>
                    <span style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{job.prompt}</span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>{job.languages?.join(', ')}</td>
                  <td style={{ padding: '12px 16px' }}><StatusBadge status={job.status} /></td>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)' }}>{new Date(job.createdAt).toLocaleDateString()}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {job.status === 'AWAITING_APPROVAL' && (
                        <button
                          onClick={() => handleResumeJob(job)}
                          style={{ ...BTN('primary'), fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          Review <ArrowRight size={12} />
                        </button>
                      )}
                      {job.status === 'GENERATING' && (
                        <button
                          onClick={() => handleResumeJob(job)}
                          style={{ ...BTN('secondary'), fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          <Loader2 size={11} /> Monitor
                        </button>
                      )}
                      {(job.status === 'FAILED' || isHistoryStuck(job)) && (
                        <button
                          onClick={() => retryMutation.mutate(job.id)}
                          disabled={retryMutation.isPending}
                          style={{ ...BTN('secondary'), fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4, opacity: retryMutation.isPending ? 0.6 : 1 }}
                          title={isHistoryStuck(job) ? 'Job appears stuck — click to retry' : 'Re-run this job'}
                        >
                          <RotateCcw size={11} /> Retry
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {(history as Job[]).length === 0 && (
                <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', fontSize: 14 }}>No generation jobs yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
