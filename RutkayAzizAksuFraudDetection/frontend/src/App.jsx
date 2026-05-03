import React, { useState, useEffect, useRef, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AlertCircle, Activity, ShieldCheck, User, X, LogOut, Sun, Moon, Terminal, Send, Lock, Bell, Search, MapPin, GripHorizontal } from 'lucide-react';

const API_BASE = 'http://localhost:8080';

export default function App() {
  const [isAuthenticated, setIsAuth] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetails, setUserDetails] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [blockedUsers, setBlockedUsers] = useState(new Set());
  const [searchUser, setSearchUser] = useState('');
  const [searchCity, setSearchCity] = useState('');
  const [feedHeight, setFeedHeight] = useState(400);
  const isDragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartH = useRef(0);
  const [notifications, setNotifications] = useState([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef(null);
  const [isWarRoomOpen, setIsWarRoomOpen] = useState(false);
  const [warRoomHistory, setWarRoomHistory] = useState([
    { type: 'system', text: 'Cortex XSOAR War Room initialized. Ready for analyst commands.' },
    { type: 'system', text: 'Type /help to see available commands.' }
  ]);
  const [commandInput, setCommandInput] = useState('');
  const chatEndRef = useRef(null);
  const [warRoomSize, setWarRoomSize] = useState('standard');
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark);
  }, [isDark]);

  const addToStats = useCallback((tx) => {

    const time = new Date(tx.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    setStats(prev => {
      const last = prev[prev.length - 1];
      if (last && last.time === time) {
        return prev.map((s, i) => i === prev.length - 1 ? { ...s, approved: s.approved + (tx.status === 'APPROVED' ? 1 : 0), rejected: s.rejected + (tx.status === 'REJECTED' ? 1 : 0) } : s);
      }
      return [...prev, { time, approved: tx.status === 'APPROVED' ? 1 : 0, rejected: tx.status === 'REJECTED' ? 1 : 0 }].slice(-30);
    });
  }, []);

  const triggerFraudAlert = useCallback((tx) => {

    const id = Date.now() + Math.random();
    setToasts(t => [...t, { id, msg: `🚨 Fraud Detected: $${tx.amount} by ${tx.user_id}` }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000);
    setWarRoomHistory(h => [...h, { type: 'alert', text: `Automated Alert: High risk transaction $${tx.amount} from ${tx.user_id}. Reason: ${tx.reason || 'Multiple rules violated'}.` }]);
    setNotifications(prev => [{ id, userId: tx.user_id, amount: tx.amount, reason: tx.reason || 'Multiple rules violated', time: new Date().toLocaleTimeString() }, ...prev].slice(0, 50));
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;

    fetch(`${API_BASE}/dashboard`).then(r => r.json()).then(data => { setTransactions(data.transactions || []); setStats(data.stats || []); });
    const evtSource = new EventSource(`${API_BASE}/events`);
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type !== 'transaction') return;
      setTransactions(prev => [data, ...prev].slice(0, 50));
      addToStats(data);
      if (data.status === 'REJECTED') triggerFraudAlert(data);
    };
    return () => evtSource.close();
  }, [isAuthenticated, addToStats, triggerFraudAlert]);

  useEffect(() => {
    const onMove = (e) => {
      if (!isDragging.current) return;
      const dy = dragStartY.current - e.clientY;
      const next = Math.min(window.innerHeight * 0.8, Math.max(120, dragStartH.current + dy));
      setFeedHeight(next);
    };
    const onUp = () => { isDragging.current = false; setIsResizing(false); document.body.style.cursor = 'default'; document.body.style.userSelect = 'auto'; };
    if (isResizing) {
      window.addEventListener('mousemove', onMove, { passive: true });
      window.addEventListener('mouseup', onUp);
      document.body.style.userSelect = 'none';
    }
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [isResizing]);

  const startDrag = (e) => {

    isDragging.current = true;
    setIsResizing(true);
    dragStartY.current = e.clientY;
    dragStartH.current = feedHeight;
    document.body.style.cursor = 'row-resize';
    e.preventDefault();
  };

  const handleUserClick = async (userId, openWarRoom = false, isFraud = false) => {
    setSelectedUser(userId);
    try {
      const res = await fetch(`${API_BASE}/users/${userId}`);
      setUserDetails(await res.json());
    } catch (e) { console.error(e); }
    if (openWarRoom) {
      setIsWarRoomOpen(true);
      const isAlreadyBlocked = blockedUsers.has(userId);
      setWarRoomHistory(prev => [...prev,
        { type: 'system', text: `🎯 Target acquired: ${userId}` },
      ]);

      if (isFraud && !isAlreadyBlocked) {
        setTimeout(() => setWarRoomHistory(prev => [...prev,
          { type: 'bot', text: `▶ AUTO-PLAYBOOK: Fraud Response\n  Target: ${userId}\n  ──────────────────────────────\n  ✓ Transaction flagged as FRAUD\n  ✓ Risk signals cross-referenced\n  ✓ Initiating block sequence...` }
        ]), 500);
        setTimeout(() => {
          setBlockedUsers(prev => new Set([...prev, userId]));
          setWarRoomHistory(prev => [...prev,
            { type: 'alert', text: `🚫 AUTO-BLOCK EXECUTED\n  User: ${userId}\n  ──────────────────────────────\n  ✓ Blocklist updated\n  ✓ Real-time sync pushed\n  ✓ Webhook: fraud_block triggered\n  Status: USER IS NOW BLOCKED` }
          ]);
        }, 1800);
      } else if (isAlreadyBlocked) {
        setTimeout(() => setWarRoomHistory(prev => [...prev,
          { type: 'bot', text: `ℹ ${userId} is already on the blocklist.\nUse /unblock ${userId} to remove.` }
        ]), 400);
      } else {
        setTimeout(() => setWarRoomHistory(prev => [...prev,
          { type: 'bot', text: `▶ Deep Scan: ${userId}\n  Transaction history loaded.\n  No automatic fraud flag.\n  ──────────────────────────────\n  Use /analyze ${userId} for full report\n  Use /block ${userId} to block manually` }
        ]), 600);
      }
    }
  };


  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [warRoomHistory]);

  const handleCommandSubmit = (e) => {
    e.preventDefault();
    if (!commandInput.trim()) return;
    const cmd = commandInput.trim();
    setWarRoomHistory(prev => [...prev, { type: 'user', text: cmd }]);
    setCommandInput('');
    setTimeout(() => {
      let response = '';
      if (cmd.startsWith('/help')) {
        response = `╔══════════════════════════════════════╗
║     CORTEX XSOAR — Available Commands     ║
╚══════════════════════════════════════╝

/analyze <user_id>   — Deep threat scan
/block <user_id>     — Block user network-wide
/unblock <user_id>   — Remove user from blocklist
/status <user_id>    — Check user block status
/clear               — Clear terminal
/help                — Show this message`;
      } else if (cmd.startsWith('/analyze ')) {
        const uid = cmd.split(' ').slice(1).join(' ') || 'unknown';
        response = `▶ Running playbook: Deep_Scan_User\n  Target: ${uid}\n  ──────────────────────────────\n  ✓ Transaction history: loaded\n  ✓ Velocity check: passed\n  ✓ Geo-anomaly scan: complete\n  ──────────────────────────────\n  ⚠ Confidence Score: 89%\n  Status: SUSPICIOUS — recommend /block ${uid}`;
      } else if (cmd.startsWith('/block ')) {
        const uid = cmd.split(' ').slice(1).join(' ');
        if (!uid) { response = '✗ Usage: /block <user_id>'; }
        else {
          setBlockedUsers(prev => new Set([...prev, uid]));
          response = `✓ EXECUTED: Block User\n  Target: ${uid}\n  ──────────────────────────────\n  ✓ Blocklist updated\n  ✓ Real-time sync: active\n  ✓ Webhook triggered\n  Status: 🚫 ${uid} is now BLOCKED`;
        }
      } else if (cmd.startsWith('/unblock ')) {
        const uid = cmd.split(' ').slice(1).join(' ');
        if (!uid) { response = '✗ Usage: /unblock <user_id>'; }
        else {
          setBlockedUsers(prev => { const n = new Set(prev); n.delete(uid); return n; });
          response = `✓ EXECUTED: Unblock User\n  Target: ${uid}\n  Status: ✅ ${uid} removed from blocklist`;
        }
      } else if (cmd.startsWith('/status ')) {
        const uid = cmd.split(' ').slice(1).join(' ');
        const isBlocked = blockedUsers.has(uid);
        response = `▶ Status Check: ${uid}\n  Blocklist: ${isBlocked ? '🚫 BLOCKED' : '✅ CLEAR'}\n  Risk Level: ${isBlocked ? 'HIGH' : 'NORMAL'}`;
      } else if (cmd === '/clear') {
        setWarRoomHistory([{ type: 'system', text: 'Terminal cleared. Session active.' }]);
        return;
      } else {
        response = `✗ Unknown command: "${cmd}"\n  Type /help to see available commands.`;
      }
      setWarRoomHistory(prev => [...prev, { type: 'bot', text: response }]);
    }, 400);
  };

  if (!isAuthenticated) return (
    <div className="min-h-screen flex flex-col justify-center items-center p-4 relative">
      <div className="absolute inset-0 z-0 bg-cover bg-center" style={{ backgroundImage: `url('https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&q=80&w=2560')` }} />
      <div className={`absolute inset-0 z-0 transition-colors duration-700 ${isDark ? 'bg-slate-950/80 backdrop-blur-sm' : 'bg-slate-900/40 backdrop-blur-md'}`} />
      <div className="absolute top-6 right-6 z-10"><button onClick={() => setIsDark(!isDark)} className="p-3 bg-white/80 dark:bg-slate-900/80 rounded-full shadow-2xl text-slate-800 dark:text-slate-200">{isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}</button></div>
      <div className="max-w-md w-full bg-white/90 dark:bg-slate-900/85 rounded-3xl shadow-2xl p-8 border border-white/40 z-10">
        <div className="flex justify-center mb-6"><div className="p-4 bg-emerald-500/10 rounded-2xl border border-emerald-500/20"><Lock className="w-10 h-10 text-emerald-600" /></div></div>
        <h2 className="text-3xl font-bold text-center text-slate-900 dark:text-white mb-8 tracking-tight">Fraud Detection Center</h2>
        <form onSubmit={(e) => { e.preventDefault(); setIsAuth(true); }} className="space-y-5">
          <input type="text" required className="w-full px-4 py-3.5 rounded-xl bg-white/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white" placeholder="Analyst ID" />
          <input type="password" required className="w-full px-4 py-3.5 rounded-xl bg-white/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white" placeholder="Password" />
          <div className="flex justify-end"><button type="button" onClick={() => setForgotOpen(true)} className="text-xs font-semibold text-emerald-600">Forgot password?</button></div>
          <button type="submit" className="w-full mt-4 py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg transition-all">Secure Login</button>
        </form>
      </div>
      <div className="absolute bottom-5 right-7 z-10 text-white/50" style={{ fontFamily: "'Dancing Script', cursive", fontSize: '1.05rem' }}>developed by Rutkay Aziz Aksu</div>
      {forgotOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setForgotOpen(false)} />
          <div className="relative w-full max-w-sm mx-4 bg-white dark:bg-slate-900 rounded-3xl p-8 animate-in zoom-in-95">
            <h3 className="text-xl font-bold text-center mb-6">Reset Password</h3>
            <form onSubmit={(e) => { e.preventDefault(); setForgotOpen(false); setForgotSuccess(true); setTimeout(() => setForgotSuccess(false), 5000); }} className="space-y-4">
              <input type="email" required value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} placeholder="Email" className="w-full px-4 py-3 rounded-xl bg-white/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800" />
              <button type="submit" className="w-full py-3.5 bg-emerald-600 text-white font-bold rounded-xl shadow-lg">Send Code</button>
            </form>
          </div>
        </div>
      )}
      {forgotSuccess && <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 bg-emerald-600 text-white px-6 py-4 rounded-2xl shadow-2xl font-semibold text-sm animate-in slide-in-from-bottom-4">Mail adresinize kod gönderildi.</div>}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-6 flex flex-col h-screen text-slate-900 dark:text-slate-200 transition-colors">
      <div className="fixed top-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        {toasts.filter(t => !searchUser || t.msg.toLowerCase().includes(searchUser.toLowerCase())).map(t => (
          <div key={t.id} className="relative bg-red-500 text-white px-4 py-4 rounded-2xl shadow-2xl flex items-center gap-3 animate-in slide-in-from-right-8 pointer-events-auto">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span className="font-bold text-sm leading-snug">{t.msg}</span>
            <button onClick={() => setToasts(p => p.filter(x => x.id !== t.id))} className="absolute top-3 right-3 text-white/50 hover:text-white"><X className="w-4 h-4" /></button>
          </div>
        ))}
      </div>

      <header className="mb-6 flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4 shrink-0">
        <h1 className="text-3xl font-extrabold bg-gradient-to-r from-blue-600 to-emerald-500 dark:from-blue-400 dark:to-teal-400 bg-clip-text text-transparent flex items-center gap-3"><Activity className="w-8 h-8" /> Fraud Detection Center</h1>
        <div className="flex gap-3 items-center">
          <button onClick={() => setIsWarRoomOpen(!isWarRoomOpen)} className={`px-4 py-2 rounded-xl border flex items-center gap-2 font-bold transition-all ${isWarRoomOpen ? 'bg-indigo-100 border-indigo-300 text-indigo-700 dark:bg-indigo-950 dark:border-indigo-700 dark:text-indigo-400' : 'bg-white border-slate-200 dark:bg-slate-900 dark:border-slate-800'}`}><Terminal className="w-4 h-4" /> XSOAR War Room</button>
          <div className="relative" ref={notifRef}>
            <button onClick={() => setNotifOpen(!notifOpen)} className="relative p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm"><Bell className={`w-5 h-5 ${notifications.length > 0 ? 'text-red-500' : ''}`} />{notifications.length > 0 && <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[10px] w-[18px] h-[18px] rounded-full flex items-center justify-center animate-pulse">{notifications.length}</span>}</button>
            {notifOpen && <div className="absolute right-0 top-12 w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl z-50 overflow-hidden animate-in slide-in-from-top-2"><div className="flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-950 border-b border-slate-100 dark:border-slate-800"><span className="font-bold text-sm flex items-center gap-2"><Bell className="w-4 h-4 text-red-500" /> Fraud Alerts</span><button onClick={() => setNotifications([])} className="text-xs text-slate-400 hover:text-red-500 font-semibold">Clear all</button></div><div className="max-h-80 overflow-y-auto">{notifications.length === 0 ? <div className="py-10 text-center text-slate-400 text-sm">No alerts yet</div> : notifications.map(n => (<div key={n.id} className="flex items-start gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-800 hover:bg-red-50 dark:hover:bg-red-950/20 group"><div className="mt-0.5 p-1.5 bg-red-100 dark:bg-red-900/40 rounded-lg"><AlertCircle className="w-3.5 h-3.5 text-red-600" /></div><div className="flex-1 min-w-0"><p className="text-xs font-bold text-red-600 truncate">🚨 {n.userId}</p><p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">${n.amount} — {n.reason.split(' AND ')[0]}</p><p className="text-[10px] text-slate-400 mt-0.5">{n.time}</p></div><button onClick={() => setNotifications(p => p.filter(x => x.id !== n.id))} className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500"><X className="w-3.5 h-3.5" /></button></div>))}</div></div>}
          </div>
          <button onClick={() => setIsDark(!isDark)} className="p-2 bg-white dark:bg-slate-900 border border-slate-200 rounded-xl">{isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}</button>
          <button onClick={() => setIsAuth(false)} className="p-2 bg-red-50 dark:bg-red-950 border border-red-200 rounded-xl text-red-600"><LogOut className="w-5 h-5" /></button>
        </div>
      </header>

      <div className="flex-1 flex gap-6 min-h-0">
        <div className={`flex flex-col gap-6 h-full ${isResizing ? '' : 'transition-all duration-500'} ${!isWarRoomOpen ? 'w-full' : warRoomSize === 'maximized' ? 'w-0 overflow-hidden opacity-0' : warRoomSize === 'minimized' ? 'w-[calc(100%-80px)]' : 'w-2/3'}`}>
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 shadow-xl flex-1 min-h-[150px] flex flex-col">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2 shrink-0">Live Transaction Volume</h2>
            <div className="flex-1 w-full min-h-0"><ResponsiveContainer width="100%" height="100%"><LineChart data={stats}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="time" fontSize={12} tickMargin={8} /><YAxis fontSize={12} /><Tooltip contentStyle={{ borderRadius: '12px' }} /><Line type="monotone" dataKey="approved" stroke="#10b981" strokeWidth={3} dot={{ r: 3 }} /><Line type="monotone" dataKey="rejected" stroke="#ef4444" strokeWidth={3} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div>
          </div>

          <div className={`bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-xl flex flex-col overflow-hidden ${isResizing ? '' : 'transition-all duration-500'}`} style={{ height: feedHeight }}>
            <div onMouseDown={startDrag} className="group/handle flex items-center justify-center py-2 cursor-row-resize border-b border-slate-100 dark:border-slate-800 hover:bg-emerald-500/10 transition-all shrink-0 relative z-10"><div className="w-12 h-1 bg-slate-200 dark:bg-slate-700 rounded-full group-hover/handle:bg-emerald-500 group-hover/handle:w-20 transition-all duration-300"></div><GripHorizontal className="absolute right-4 w-4 h-4 text-slate-300 opacity-0 group-hover/handle:opacity-100 transition-opacity" /></div>
            <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 shrink-0"><div className="flex items-center justify-between mb-4"><h2 className="text-xl font-bold flex items-center gap-2">Live Feed <span className="flex h-2.5 w-2.5 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span></span></h2>{ (searchUser || searchCity) && <button onClick={() => { setSearchUser(''); setSearchCity(''); }} className="text-xs font-bold text-slate-400 hover:text-red-500">Clear filters</button> }</div><div className="flex gap-3"><input type="text" value={searchUser} onChange={e => setSearchUser(e.target.value)} placeholder="User ID..." className="flex-[1.2] px-4 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-emerald-500 transition-all outline-none" /><input type="text" value={searchCity} onChange={e => setSearchCity(e.target.value)} placeholder="City..." className="flex-1 px-4 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-blue-500 transition-all outline-none" /></div></div>
            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-3 custom-scrollbar">
              {transactions.filter(tx => (!searchUser || tx.user_id.toLowerCase().includes(searchUser.toLowerCase())) && (!searchCity || (tx.location || '').toLowerCase().includes(searchCity.toLowerCase()))).map(tx => {
                const isFraud = tx.status === 'REJECTED'; const isBlocked = blockedUsers.has(tx.user_id);
                return (
                  <div key={tx.id} className={`p-4 rounded-2xl border-2 transition-all duration-200 group ${isBlocked ? 'bg-slate-100 dark:bg-slate-800/60 border-slate-300 dark:border-slate-700 opacity-60' : isFraud ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/60' : 'bg-slate-50 dark:bg-slate-800/40 border-transparent hover:border-slate-200 dark:hover:border-slate-700'}`}>
                    <div className="flex justify-between items-start mb-2"><span className="font-mono text-sm font-semibold cursor-pointer hover:text-emerald-600" onClick={() => handleUserClick(tx.user_id)}>👤 {tx.user_id} {isBlocked && <span className="ml-2 text-[10px] bg-slate-400 text-white px-1.5 py-0.5 rounded uppercase">Blocked</span>}</span><span className={`font-bold text-base ${isFraud ? 'text-red-600' : 'text-emerald-600'}`}>${tx.amount}</span></div>
                    <div className="flex justify-between items-center text-xs font-medium"><div className="flex items-center gap-2 text-slate-400"><span>{new Date(tx.timestamp).toLocaleTimeString()}</span>{tx.location && <span className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded"><MapPin className="w-2.5 h-2.5" /> {tx.location}</span>}</div><div className="flex items-center gap-2">{!isBlocked && <button onClick={() => handleUserClick(tx.user_id, true, isFraud)} className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-bold transition-all opacity-0 group-hover:opacity-100 ${isFraud ? 'bg-indigo-600 text-white' : 'bg-slate-200 dark:bg-slate-700'}`}><Terminal className="w-3 h-3" /> XSOAR</button>}{isFraud ? <span className="flex items-center gap-1 text-red-700 bg-red-100 px-2 py-1 rounded-md font-bold">FRAUD</span> : <span className="text-emerald-700 bg-emerald-100 px-2 py-1 rounded-md font-bold">APPROVED</span>}</div></div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {isWarRoomOpen && (
          <div className={`bg-slate-900 dark:bg-[#0f172a] rounded-3xl border border-slate-700 shadow-2xl flex flex-col overflow-hidden transition-all duration-500 ${warRoomSize === 'maximized' ? 'flex-1' : warRoomSize === 'minimized' ? 'w-20' : 'w-1/3'}`}>
            <div className="p-4 border-b border-slate-800 bg-[#0a0f1d] flex items-center justify-between shrink-0"><div className="flex items-center gap-3"><Terminal className="w-5 h-5 text-indigo-400" />{warRoomSize !== 'minimized' && <h3 className="text-lg font-bold text-white">Cortex XSOAR</h3>}</div><div className="flex gap-2"><button onClick={() => { setIsWarRoomOpen(false); setWarRoomSize('standard'); }} className="w-3.5 h-3.5 rounded-full bg-[#ff5f56] border border-[#e0443e] hover:bg-[#ff5f56]/80 transition-colors flex items-center justify-center group"><X className="w-2 h-2 text-black/40 opacity-0 group-hover:opacity-100" /></button><button onClick={() => setWarRoomSize(warRoomSize === 'minimized' ? 'standard' : 'minimized')} className="w-3.5 h-3.5 rounded-full bg-[#ffbd2e] border border-[#dea123] hover:bg-[#ffbd2e]/80 transition-colors"></button><button onClick={() => setWarRoomSize(warRoomSize === 'maximized' ? 'standard' : 'maximized')} className="w-3.5 h-3.5 rounded-full bg-[#27c93f] border border-[#1aab29] hover:bg-[#27c93f]/80 transition-colors"></button></div></div>
            {warRoomSize !== 'minimized' && <div className="flex flex-col flex-1 min-h-0"><div className="flex-1 overflow-y-auto p-5 font-mono text-sm space-y-4 custom-scrollbar">{warRoomHistory.map((msg, i) => (<div key={i} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[90%] rounded-lg p-3 whitespace-pre-wrap ${msg.type === 'user' ? 'bg-indigo-600 text-white' : msg.type === 'alert' ? 'bg-red-950/80 border border-red-800/80 text-red-200' : 'bg-slate-800/80 border border-slate-700/50 text-slate-300'}`}>{msg.type === 'bot' && <span className="text-emerald-400 font-bold block mb-1">» System Response</span>}{msg.type === 'alert' && <span className="text-red-400 font-bold block mb-1">» Alert</span>}{msg.text}</div></div>))}<div ref={chatEndRef} /></div><div className="p-4 bg-[#0a0f1d] border-t border-slate-800"><form onSubmit={handleCommandSubmit} className="flex gap-2"><input type="text" value={commandInput} onChange={e => setCommandInput(e.target.value)} placeholder="Enter command..." className="flex-1 bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 outline-none focus:border-indigo-500 font-mono text-sm" /><button type="submit" className="bg-indigo-600 text-white p-3 rounded-xl"><Send className="w-5 h-5" /></button></form></div></div>}
          </div>
        )}
      </div>

      {selectedUser && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedUser(null)}></div>
          <div className="relative w-full max-w-lg bg-white dark:bg-slate-900 h-full border-l border-slate-200 p-8 overflow-y-auto transform transition-transform animate-in slide-in-from-right-full duration-300">
            <button onClick={() => setSelectedUser(null)} className="absolute top-6 right-6 text-slate-400 hover:text-slate-800 p-2 rounded-full transition-colors"><X className="w-5 h-5" /></button>
            <div className="flex items-center gap-5 mb-10 mt-4 border-b pb-8"><div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center"><User className="w-8 h-8 text-slate-500" /></div><div><h3 className="text-3xl font-bold mb-1">{selectedUser}</h3><p className="text-slate-500 text-sm tracking-wide uppercase font-semibold">User Risk Profile</p></div></div>
            {userDetails ? (
              <div className="space-y-8">
                <div><h4 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Anomalies & Risk History</h4>{userDetails.frauds.length === 0 ? <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5 text-emerald-700 flex gap-4 items-center"><ShieldCheck className="w-8 h-8 text-emerald-500" /><p className="text-sm font-medium">Clean history. No suspicious activities detected.</p></div> : <div className="space-y-4">{userDetails.frauds.map((f, i) => (<div key={i} className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 rounded-2xl p-5 relative overflow-hidden"><div className="absolute top-0 left-0 w-1 h-full bg-red-500"></div><div className="flex justify-between items-center mb-3"><span className="text-red-600 font-extrabold text-lg">Risk Score: {f.risk_score}</span><span className="text-slate-500 text-sm">{new Date(f.detected_at).toLocaleString()}</span></div><p className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed font-medium bg-white/50 dark:bg-black/20 p-3 rounded-xl border border-red-100 dark:border-red-900/30">{f.reason}</p></div>))}</div>}</div>
                <div><h4 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Recent Transactions</h4><div className="bg-white dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">{userDetails.transactions.map((t, i) => (<div key={i} className="p-4 border-b last:border-0 flex justify-between items-center hover:bg-slate-50 transition-colors"><div className="flex flex-col gap-1"><div className="flex items-center gap-2"><span className="text-slate-800 dark:text-slate-200 font-mono text-base font-semibold">${t.amount}</span>{t.location && <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded font-bold uppercase tracking-tight">{t.location}</span>}</div><span className="text-slate-500 text-xs">{new Date(t.timestamp).toLocaleString()}</span></div><span className={`text-xs px-3 py-1.5 rounded-md font-bold uppercase ${t.status === 'REJECTED' ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-700'}`}>{t.status}</span></div>))}</div></div>
              </div>
            ) : <div className="flex justify-center py-20 animate-pulse text-slate-400">Loading user profile data...</div>}
          </div>
        </div>
      )}
    </div>
  );
}
