import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name: string;
  username: string;
  token: string;
}

type Theme = 'light' | 'dark';

interface AppState {
  user: User | null;
  isAuthenticated: boolean;
  theme: Theme;
  login: (user: User) => void;
  logout: () => void;
  setTheme: (theme: Theme) => void;
  features: {
    enableGamification: boolean;
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      theme: 'light',
      login: (user) => set({ user, isAuthenticated: true }),
      logout: () => set({ user: null, isAuthenticated: false }),
      setTheme: (theme) => {
        set({ theme });
        document.documentElement.setAttribute('data-theme', theme);
      },
      features: {
        enableGamification: false,
      },
    }),
    {
      name: 'platform-storage',
      onRehydrateStorage: () => (state) => {
        if (state) {
          document.documentElement.setAttribute('data-theme', state.theme);
        }
      },
    }
  )
);
