import { Link } from 'react-router-dom';
import { useAppStore } from '../../store';
import { LogOut, User as UserIcon, Trophy, Code2 } from 'lucide-react';

export function Navbar() {
  const { isAuthenticated, user, logout } = useAppStore();

  return (
    <nav className="fixed top-0 left-0 right-0 h-[72px] z-50 glass-panel border-b-0 border-x-0 rounded-none px-6 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-white tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
            <Code2 size={20} className="text-white" />
          </div>
          Code<span className="text-primary/90">Forge</span>
        </Link>
        
        {isAuthenticated && (
          <div className="flex items-center gap-4 ml-4">
            <Link to="/" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">Problems</Link>
            <Link to="/leaderboard" className="text-sm font-medium text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors">
              <Trophy size={14} className="text-yellow-500" /> Leaderboard
            </Link>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {isAuthenticated ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
               <UserIcon size={16} className="text-slate-400" />
               <span className="text-sm font-medium">{user?.username || 'User'}</span>
            </div>
            <button 
              onClick={logout}
              className="text-sm font-medium text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <LogOut size={16} /> Logout
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-slate-300 hover:text-white px-4 py-2 transition-colors">
              Log in
            </Link>
            <Link to="/signup" className="text-sm font-medium bg-white text-black hover:bg-slate-200 px-4 py-2 rounded-lg transition-colors shadow-lg shadow-white/10">
              Sign up
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}