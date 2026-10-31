import React, { useEffect, useId, useRef } from 'react';
import { LayoutGrid, CalendarDays, UsersRound, ChartNoAxesCombined, Sparkles, Bell, Plus, Search, ChevronLeft, ChevronRight, ChevronDown, ArrowUpRight, ArrowDownLeft, ArrowRight, ArrowLeft, ArrowUp, X, Check, CheckCheck, Clock3, MapPin, Heart, Sun, Moon, Monitor, LogIn, LogOut, UserRound, UserPlus, CalendarPlus, FileText, CircleAlert, ScanText, LockKeyhole, Settings2, Gift, Flower2, Cake, MoreHorizontal, Download, Copy, Send, Mail, Menu, SlidersHorizontal, Wallet, NotebookPen, MessageCircle, Star, Pencil, History, CheckCircle2, Circle, Info, ExternalLink, CalendarCheck, HandHeart, ShieldCheck, ArrowDown, Trash2, Filter, RefreshCw, Bookmark, HeartHandshake } from 'lucide-react';

const icons = { LayoutGrid, CalendarDays, UsersRound, ChartNoAxesCombined, Sparkles, Bell, Plus, Search, ChevronLeft, ChevronRight, ChevronDown, ArrowUpRight, ArrowDownLeft, ArrowRight, ArrowLeft, ArrowUp, X, Check, CheckCheck, Clock3, MapPin, Heart, Sun, Moon, Monitor, LogIn, LogOut, UserRound, UserPlus, CalendarPlus, FileText, CircleAlert, ScanText, LockKeyhole, Settings2, Gift, Flower2, Cake, MoreHorizontal, Download, Copy, Send, Mail, Menu, SlidersHorizontal, Wallet, NotebookPen, MessageCircle, Star, Pencil, History, CheckCircle2, Circle, Info, ExternalLink, CalendarCheck, HandHeart, ShieldCheck, ArrowDown, Trash2, Filter, RefreshCw, Bookmark, HeartHandshake };
const aliases = { home: 'LayoutGrid', calendar: 'CalendarDays', users: 'UsersRound', user: 'UserRound', 'bar-chart-3': 'ChartNoAxesCombined', 'chart-column': 'ChartNoAxesCombined', clock: 'Clock3', edit: 'Pencil', 'edit-3': 'NotebookPen', 'calendar-days': 'CalendarDays', 'circle-check': 'CheckCircle2', 'check-circle': 'CheckCircle2', 'user-round': 'UserRound', 'message-square': 'MessageCircle', 'notebook-pen': 'NotebookPen' };
export function Icon({ name, size = 20, strokeWidth = 1.7, ...props }) {
  const key = aliases[name] || name?.replace(/(^|-)([a-z])/g, (_, dash, letter) => letter.toUpperCase());
  const Component = icons[key] || icons[name] || Circle;
  return <Component size={size} strokeWidth={strokeWidth} aria-hidden="true" {...props} />;
}

export function Modal({ title, subtitle, onClose, children, wide = false }) {
  const dialog = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement;
    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusables = () => [...dialog.current.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]')].filter(el => el.getClientRects().length);
    const timer = setTimeout(() => (focusables().find(el => el.tagName === 'INPUT') || focusables()[0] || dialog.current)?.focus(), 30);
    const handler = (e) => {
      if (e.key === 'Escape') closeRef.current?.();
      if (e.key === 'Tab') {
        const list = focusables();
        const first = list[0], last = list.at(-1);
        if (!first) { e.preventDefault(); return; }
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handler);
    return () => { clearTimeout(timer); document.body.style.overflow = bodyOverflow; document.removeEventListener('keydown', handler); previous?.isConnected && previous.focus(); };
  }, []);
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose?.(); }}><section className={`modal ${wide ? 'modal-wide' : ''}`} ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
    <header className="modal-header"><div><h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button type="button" className="icon-button" aria-label="닫기" onClick={onClose}><Icon name="X" /></button></header>
    <div className="modal-body">{children}</div>
  </section></div>;
}

export function EmptyState({ icon = 'Heart', title = '아직 기록이 없어요', description, children }) {
  return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={28} /></span><h3>{title}</h3>{description && <p>{description}</p>}{children}</div>;
}

export function FlowerIllustration() {
  return <svg className="flower-illustration" viewBox="0 0 420 270" fill="none" aria-hidden="true">
    <ellipse cx="226" cy="249" rx="143" ry="11" fill="#b6a085" opacity=".1" />
    <path d="M255 229c-3-56 11-90 48-132M256 195c-36-8-45-34-50-53M269 165c27-5 43-19 51-39" stroke="#7b916d" strokeWidth="3" strokeLinecap="round" />
    <path d="M258 188c-39 1-63-24-61-48 30-3 54 14 61 48Z" fill="#9caa85" />
    <path d="M275 158c2-30 21-44 47-43-1 26-16 43-47 43Z" fill="#6f8967" />
    <path d="M291 113c-16-5-25-19-18-29 5-8 16-4 20 2-1-14 7-23 17-18 8 4 8 15 1 24 15-3 25 4 21 14-5 13-22 13-31 5-4 17-16 23-24 14-6-7 0-17 14-12Z" fill="#e8b67c" />
    <circle cx="300" cy="100" r="8" fill="#a87946" />
    <path d="M168 187c-16-35-36-53-58-66M153 161c8-22 5-40-6-55" stroke="#7b916d" strokeWidth="3" strokeLinecap="round" />
    <path d="M142 152c-26 9-46-5-50-26 22-7 43 4 50 26Z" fill="#7f9979" />
    <path d="M149 137c-17-17-18-40-3-54 19 18 20 35 3 54Z" fill="#a8b493" />
    <path d="M103 128c-15 3-30-6-27-17 2-9 12-9 19-4-7-12-3-24 8-24 10 0 15 11 12 22 12-9 24-7 25 4 1 13-14 20-26 16 3 16-6 26-17 21-8-4-6-14 6-18Z" fill="#efc0a9" />
    <circle cx="108" cy="119" r="8" fill="#bd866b" />
    <g transform="rotate(-8 205 196)">
      <rect x="113" y="151" width="191" height="105" rx="9" fill="#d4c4a4" />
      <path d="m113 158 87 59a10 10 0 0 0 12 0l92-60v90a9 9 0 0 1-9 9H122a9 9 0 0 1-9-9v-89Z" fill="#ece2ca" />
      <rect x="139" y="119" width="141" height="97" rx="5" fill="#fffdf7" />
      <path d="M180 146h58M191 158h37" stroke="#d1c9b4" strokeWidth="3" strokeLinecap="round" />
      <path d="m114 250 75-56 13 9a10 10 0 0 0 12 0l15-10 74 58" fill="#f1e9d8" />
      <path d="M208 185c-10-12-23 1 0 15 23-14 10-27 0-15Z" fill="#bc7f62" />
    </g>
    <path d="m341 162 3 8 8 3-8 3-3 8-3-8-8-3 8-3 3-8ZM78 178l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z" fill="#bba67a" />
    <circle cx="333" cy="66" r="3" fill="#c4b594" /><circle cx="77" cy="74" r="3" fill="#d5c0a7" />
  </svg>;
}
