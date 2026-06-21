import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AdminUser {
  id: string
  email: string
}

type Theme = 'light' | 'dark'

interface AdminStore {
  user: AdminUser | null
  token: string | null
  theme: Theme
  isAuthenticated: boolean
  activeJobId: string | null
  login: (user: AdminUser, token: string) => void
  logout: () => void
  setTheme: (theme: Theme) => void
  setActiveJobId: (id: string | null) => void
}

export const useAdminStore = create<AdminStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      theme: 'light',
      isAuthenticated: false,
      activeJobId: null,
      login: (user, token) => set({ user, token, isAuthenticated: true }),
      logout: () => set({ user: null, token: null, isAuthenticated: false, activeJobId: null }),
      setActiveJobId: (id) => set({ activeJobId: id }),
      setTheme: (theme) => {
        set({ theme })
        document.documentElement.setAttribute('data-theme', theme)
      },
    }),
    {
      name: 'admin-storage',
      onRehydrateStorage: () => (state) => {
        if (state) {
          document.documentElement.setAttribute('data-theme', state.theme)
        }
      },
    }
  )
)
