import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, deleteUser } from '../lib/api'
import { Trash2, Shield, ChevronLeft, ChevronRight } from 'lucide-react'

type User = { id: string; email: string; displayName?: string; isAdmin: boolean; createdAt: string }

export default function UsersPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const { data } = useQuery({ queryKey: ['users', page], queryFn: () => listUsers(page) })
  const users: User[] = data?.content || []
  const totalPages: number = data?.totalPages || 1

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: '0 0 4px', color: 'var(--text-primary)' }}>Users</h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 14 }}>{data?.totalElements || 0} total users</p>
      </div>

      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 10, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              {['User', 'Email', 'Role', 'Joined', 'Actions'].map((h) => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600, color: '#374151' }}>
                      {(u.displayName || u.email)[0].toUpperCase()}
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{u.displayName || '—'}</span>
                  </div>
                </td>
                <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>{u.email}</td>
                <td style={{ padding: '12px 16px' }}>
                  {u.isAdmin ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', background: '#ede9fe', color: '#5b21b6', borderRadius: 999, fontSize: 11, fontWeight: 600 }}>
                      <Shield size={10} /> Admin
                    </span>
                  ) : (
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Candidate</span>
                  )}
                </td>
                <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)' }}>
                  {new Date(u.createdAt).toLocaleDateString()}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {!u.isAdmin && (
                    <button
                      onClick={() => { if (confirm(`Delete ${u.email}?`)) deleteMut.mutate(u.id) }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', padding: 4, display: 'flex' }}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>No users found</td></tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
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
