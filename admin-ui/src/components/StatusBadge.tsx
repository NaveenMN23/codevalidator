const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  DESIGNING:          { bg: '#dbeafe', text: '#1d4ed8' },
  AWAITING_APPROVAL:  { bg: '#fef3c7', text: '#92400e' },
  GENERATING:         { bg: '#e0e7ff', text: '#4338ca' },
  COMPLETED:          { bg: '#d1fae5', text: '#065f46' },
  FAILED:             { bg: '#fee2e2', text: '#991b1b' },
  CANCELLED:          { bg: '#f3f4f6', text: '#4b5563' },
}

const DARK_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  DESIGNING:          { bg: '#1e3a5f', text: '#93c5fd' },
  AWAITING_APPROVAL:  { bg: '#3d2c00', text: '#fcd34d' },
  GENERATING:         { bg: '#2d2d5e', text: '#a5b4fc' },
  COMPLETED:          { bg: '#064e3b', text: '#6ee7b7' },
  FAILED:             { bg: '#450a0a', text: '#fca5a5' },
  CANCELLED:          { bg: '#1f2937', text: '#9ca3af' },
}

export function StatusBadge({ status }: { status: string }) {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const colors = isDark ? DARK_STATUS_COLORS[status] : STATUS_COLORS[status]
  const fallback = { bg: '#f3f4f6', text: '#374151' }
  const c = colors || fallback
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.03em',
      background: c.bg,
      color: c.text,
    }}>
      {status}
    </span>
  )
}
