import { Link } from 'react-router-dom';
import { useAppStore } from '../../store';
import { LogOut, User as UserIcon, Trophy, Code2, Sun, Moon } from 'lucide-react';

export function Navbar() {
  const { isAuthenticated, user, logout, theme, setTheme } = useAppStore();

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  return (
    <nav className="fixed top-0 left-0 right-0 h-[72px] z-50 bg-background border-b border-border-main px-6 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight transition-colors">
          <div className="w-8 h-8 rounded bg-primary flex items-center justify-center">
            <Code2 size={18} className="text-white" />
          </div>
          <span className="text-text-main">Code<span className="text-primary font-black">Forge</span></span>
        </Link>

        {isAuthenticated && (
          <div className="flex items-center gap-4 ml-4">
            <Link to="/" className="text-sm font-medium text-text-muted hover:text-text-main transition-colors">Problems</Link>
            <Link to="/leaderboard" className="text-sm font-medium text-text-muted hover:text-text-main flex items-center gap-1.5 transition-colors">
              <Trophy size={14} className="text-yellow-500" /> Leaderboard
            </Link>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
          {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
        </button>

        {isAuthenticated ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/5 dark:bg-white/5 border border-border-main">
               <UserIcon size={16} className="text-text-muted" />
               <span className="text-sm font-medium text-text-main">{user?.username || 'User'}</span>
            </div>
            <button 
              onClick={logout}
              className="text-sm font-medium text-text-muted hover:text-text-main flex items-center gap-1.5 transition-colors"
            >
              <LogOut size={16} /> Logout
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-text-muted hover:text-text-main px-4 py-2 transition-colors">
              Log in
            </Link>
            <Link to="/signup" className="text-sm font-medium bg-primary text-white hover:bg-primary/90 px-4 py-2 rounded-lg transition-colors shadow-lg shadow-primary/20">
              Sign up
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}