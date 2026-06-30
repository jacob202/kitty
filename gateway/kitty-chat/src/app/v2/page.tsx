'use client';
// Kitty v2 — foundation surface, ported 1:1 from the Claude Design prototype
// (design-system/v2-reference/Kitty UI v2.dc.html) to match screenshot-day.png
// and screenshot-night.png exactly. Lives inside the live app at /v2, fully
// scoped via .v2-root so it can't touch today's UI. Spec: design-system/KITTY.md.
// The crayon cat is rendered exactly as the prototype draws her — ginger fills
// spilling past a wobbly outline (#wob2), green eye, pink nose. Not redrawn.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './kitty-v2.css';

type Theme = 'day' | 'night';
type CatState = 'idle' | 'working' | 'done' | 'broke';
interface Msg { id: number; isKitty: boolean; text: string; isTyping?: boolean }

const FACES: Record<CatState, string> = { idle: '._.', working: 'o_o', done: '^_^', broke: ':[' };
const STATE_DOT: Record<CatState, string> = {
  idle: 'var(--cat-green)', working: 'var(--c-yellow)', done: 'var(--c-green)', broke: 'var(--c-red)',
};
const PLACEHOLDER: Record<CatState, string> = {
  idle: 'ask kitty anything', working: 'kitty is on it…', done: 'nice. what next', broke: 'that broke. try again?',
};
const REPLIES = ['on it →', 'pulling that up now', 'got it. give me a sec', 'sure, i can do that', 'ok. here you go', 'done. want me to keep going'];

const NAV = [
  { id: 'home', label: 'home', d: 'M3 11 L12 3 L21 11 M6 9 V20 H18 V9' },
  { id: 'chats', label: 'chats', d: 'M4 5 H20 V15 H10 L5 19 V15 H4 Z' },
  { id: 'tasks', label: 'tasks', d: 'M5 5 H19 V19 H5 Z M8 12 l3 3 l5 -6' },
  { id: 'files', label: 'files', d: 'M4 7 H10 L12 5 H20 V18 H4 Z' },
  { id: 'about', label: 'about', d: 'M12 4 V20 M4 12 H20 M7 7 L17 17 M17 7 L7 17' },
];
const GROUPS = [
  { key: 'pinned', label: 'pinned', color: 'var(--c-red)', dot: 'var(--c-red)', items: [
    { id: 'p1', title: 'weekly planning', preview: 'every monday, on it', ago: '★' },
    { id: 'p2', title: 'reply templates', preview: 'the three you reuse', ago: '★' },
  ] },
  { key: 'today', label: 'today', color: 'var(--c-blue)', dot: 'var(--c-blue)', items: [
    { id: 't1', title: 'pulled my week together', preview: 'ok, mon → fri, sorted', ago: '2h' },
    { id: 't2', title: 'drafted reply to sarah', preview: 'sent. want a follow-up', ago: '4h' },
    { id: 't3', title: 'renamed three files', preview: 'done. all lowercase', ago: '5h' },
  ] },
  { key: 'yest', label: 'yesterday', color: 'var(--c-green)', dot: 'var(--c-green)', items: [
    { id: 'y1', title: 'summarised the design doc', preview: '3 takeaways, saved', ago: '1d' },
    { id: 'y2', title: 'checked calendar conflicts', preview: 'found one. moved it', ago: '1d' },
  ] },
  { key: 'earlier', label: 'earlier', color: 'var(--c-purple)', dot: 'var(--c-purple)', items: [
    { id: 'e1', title: 'facts on crayon pigment', preview: 'the waxy ones, briefly', ago: '4d' },
    { id: 'e2', title: 'tidied the downloads pile', preview: '42 files, sorted', ago: '6d' },
  ] },
];
const CHIP_LABELS = ['plan my week', 'draft a reply', 'what’s on today', 'summarise a doc'];
const CHIP_ROT = [-2, 1.5, -1, 2];

// crayon cat — drawn exactly as the prototype. ginger fills (#wob2) under a
// wobbly outline (#wob). geometry is kid-cat.svg; do not clean her up.
const CAT_BODY =
  '<g filter="url(#wob2)" opacity="0.9">' +
    '<ellipse cx="170" cy="129" rx="67" ry="51" fill="var(--cat-ginger)"></ellipse>' +
    '<circle cx="80" cy="102" r="49" fill="var(--cat-ginger)"></circle>' +
    '<path d="M55 64 L44 24 L86 57 Z" fill="var(--cat-ginger)"></path>' +
    '<path d="M99 57 L118 24 L121 63 Z" fill="var(--cat-ginger)"></path>' +
    '<path d="M58 56 L50 34 L74 53 Z" fill="var(--cat-pink)"></path>' +
    '<path d="M102 54 L115 36 L116 60 Z" fill="var(--cat-pink)"></path>' +
    '<circle cx="64" cy="95" r="8" fill="var(--cat-green)"></circle>' +
    '<path d="M38 104 L52 100 L49 112 Z" fill="var(--cat-pink)"></path>' +
    '<circle cx="44" cy="114" r="6" fill="var(--cat-pink)" opacity="0.5"></circle>' +
  '</g>' +
  '<g filter="url(#wob)" stroke="var(--cat-outline)" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
    '<ellipse cx="168" cy="128" rx="62" ry="46"></ellipse>' +
    '<circle cx="80" cy="102" r="44"></circle>' +
    '<path d="M54 66 L44 24 L88 58"></path>' +
    '<path d="M98 58 L118 24 L122 64"></path>' +
    '<circle cx="64" cy="96" r="4.5" fill="var(--cat-outline)" stroke="none"></circle>' +
    '<path d="M38 104 L52 100 L49 112 Z"></path>' +
    '<path d="M44 113 Q58 126 74 116"></path>' +
    '<path d="M36 100 Q20 96 8 102 M38 114 Q22 116 10 124"></path>' +
    '<path d="M120 168 q-4 18 6 20 M152 172 q-2 18 7 20 M188 170 q0 18 8 19 M214 160 q5 16 12 17"></path>' +
    '<path d="M226 122 Q262 112 256 70 Q254 48 236 58"></path>' +
  '</g>';
const CAT_MARK =
  '<g filter="url(#wob2)" opacity="0.9">' +
    '<circle cx="80" cy="92" r="50" fill="var(--cat-ginger)"></circle>' +
    '<path d="M52 52 L40 14 L84 46 Z" fill="var(--cat-ginger)"></path>' +
    '<path d="M108 46 L122 14 L128 54 Z" fill="var(--cat-ginger)"></path>' +
    '<circle cx="64" cy="88" r="7" fill="var(--cat-green)"></circle>' +
    '<circle cx="96" cy="88" r="7" fill="var(--cat-green)"></circle>' +
  '</g>' +
  '<g filter="url(#wob)" stroke="var(--cat-outline)" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="80" cy="92" r="46"></circle>' +
    '<path d="M52 54 L40 16 L82 48"></path>' +
    '<path d="M104 48 L122 16 L126 56"></path>' +
    '<circle cx="64" cy="89" r="4" fill="var(--cat-outline)" stroke="none"></circle>' +
    '<circle cx="96" cy="89" r="4" fill="var(--cat-outline)" stroke="none"></circle>' +
    '<path d="M74 100 Q80 106 86 100"></path>' +
  '</g>';

function Cat({ size, viewBox, html }: { size: number; viewBox: string; html: string }) {
  return <svg viewBox={viewBox} style={{ width: size, height: 'auto', display: 'block' }} dangerouslySetInnerHTML={{ __html: html }} />;
}

const STAR = 'M12 1 L14 9 L22 12 L14 15 L12 23 L10 15 L2 12 L10 9 Z';

export default function KittyV2() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<Theme>('day');
  const [catState, setCatState] = useState<CatState>('idle');
  const [showGreeting, setShowGreeting] = useState(true);
  const [inputVal, setInputVal] = useState('');
  const [searchVal, setSearchVal] = useState('');
  const [activeNav, setActiveNav] = useState('home');
  const [activeHistory, setActiveHistory] = useState<string | null>('t1');
  const [showSparkle, setShowSparkle] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([{ id: 0, isKitty: true, text: 'hey. what are we doing today' }]);

  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sparkTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    try { if (window.localStorage.getItem('kitty_v2_greeted')) setShowGreeting(false); } catch { /* ignore */ }
  }, []);

  const scroll = useCallback(() => {
    requestAnimationFrame(() => { if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight; });
  }, []);
  const sparkle = useCallback(() => {
    setShowSparkle(false);
    if (sparkTimer.current) clearTimeout(sparkTimer.current);
    requestAnimationFrame(() => {
      setShowSparkle(true);
      sparkTimer.current = setTimeout(() => setShowSparkle(false), 1400);
    });
  }, []);
  const resetState = useCallback((ms = 2200) => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
    resetTimer.current = setTimeout(() => setCatState('idle'), ms);
  }, []);

  const send = useCallback((textArg?: string) => {
    const text = (textArg ?? inputVal).trim();
    if (!text) return;
    const now = Date.now();
    setMessages((m) => [...m, { id: now, isKitty: false, text }, { id: now + 1, isKitty: true, text: '', isTyping: true }]);
    setInputVal('');
    setCatState('working');
    scroll();
    if (typingTimer.current) clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => {
      const reply = REPLIES[Math.floor(Math.random() * REPLIES.length)];
      setMessages((m) => [...m.filter((x) => !x.isTyping), { id: Date.now(), isKitty: true, text: reply }]);
      setCatState('done');
      sparkle();
      resetState();
      scroll();
    }, 1500);
  }, [inputVal, scroll, sparkle, resetState]);

  const addKitty = useCallback((text: string) => {
    setMessages((m) => [...m, { id: Date.now(), isKitty: true, text }]);
    scroll();
  }, [scroll]);

  const T = theme; // tokens resolve from CSS via data-theme
  const groups = useMemo(() => {
    const q = searchVal.trim().toLowerCase();
    if (!q) return GROUPS;
    const hits = GROUPS.flatMap((g) => g.items.filter((it) => (it.title + ' ' + it.preview).toLowerCase().includes(q)).map((it) => ({ ...it, dot: g.dot })));
    return [{ key: 'results', label: hits.length ? 'results' : 'nothing here', color: 'var(--c-blue)', dot: 'var(--c-blue)', items: hits }];
  }, [searchVal]);

  const showChips = messages.length <= 1 && !showGreeting;
  const hasInput = inputVal.trim().length > 0;
  const grainStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, width: '100%', height: '100%', pointerEvents: 'none',
    zIndex: 40, opacity: 'var(--grain-opacity)' as unknown as number, mixBlendMode: 'var(--grain-blend)' as React.CSSProperties['mixBlendMode'],
  };

  if (!mounted) return <div style={{ height: '100vh', background: '#F3EAD6' }} />;

  return (
    <div className="v2-root" data-theme={T} style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--ink)' }}>
      {/* shared hand-drawn filters */}
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden>
        <filter id="wob" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.015 0.02" numOctaves={2} seed={7} result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale={4.5} />
        </filter>
        <filter id="wob2" x="-30%" y="-30%" width="160%" height="160%">
          <feTurbulence type="fractalNoise" baseFrequency="0.02 0.028" numOctaves={2} seed={3} result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale={8} />
        </filter>
        <filter id="paper"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} stitchTiles="stitch" /></filter>
      </svg>

      {/* greeting */}
      {showGreeting && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 30, maxWidth: 420, textAlign: 'center', padding: 40 }}>
            <div style={{ position: 'relative' }}>
              <div className="cat-idle"><Cat size={150} viewBox="0 0 280 210" html={CAT_BODY} /></div>
              <svg viewBox="0 0 24 24" style={{ position: 'absolute', top: -6, right: -14, width: 30, height: 30, color: 'var(--c-yellow)' }}><path d={STAR} fill="currentColor" filter="url(#wob)" /></svg>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
              <h1 style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontWeight: 800, fontSize: 64, letterSpacing: '-.035em', color: 'var(--ink)', lineHeight: .86 }}>hey.</h1>
              <p style={{ fontSize: 16, lineHeight: 1.6, color: 'var(--ink2)', maxWidth: 300 }}>i&rsquo;m kitty. drawn by a six-year-old, allegedly. here when you need me — let&rsquo;s get things done.</p>
            </div>
            <button onClick={() => { try { window.localStorage.setItem('kitty_v2_greeted', '1'); } catch { /* ignore */ } setShowGreeting(false); sparkle(); }} style={{ background: 'var(--primary)', color: 'var(--on-primary)', border: 'none', borderRadius: 14, padding: '14px 40px', fontFamily: "'Hanken Grotesk',sans-serif", fontWeight: 600, fontSize: 16, cursor: 'pointer', boxShadow: 'var(--btn-shadow)', letterSpacing: '-.01em' }}>let&rsquo;s go →</button>
          </div>
        </div>
      )}

      {/* app shell */}
      <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', position: 'relative', zIndex: 2 }}>

        {/* rail */}
        <nav style={{ width: 94, background: 'var(--surface2)', borderRight: '1.5px solid var(--line)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '18px 0 14px', flexShrink: 0 }}>
          <div style={{ marginBottom: 22, color: 'var(--cat-ginger)' }}><Cat size={42} viewBox="0 0 160 150" html={CAT_MARK} /></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '100%', alignItems: 'center', flex: 1 }}>
            {NAV.map((n) => {
              const active = activeNav === n.id;
              return (
                <button key={n.id} onClick={() => setActiveNav(n.id)} style={{ width: 62, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, padding: '9px 0', border: 'none', borderRadius: 14, cursor: 'pointer', background: active ? 'var(--ginger-fade)' : 'transparent', color: active ? 'var(--cat-ginger)' : 'var(--ink2)' }}>
                  <svg viewBox="0 0 24 24" style={{ width: 23, height: 23 }}><path d={n.d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#wob)" /></svg>
                  <span style={{ fontSize: 10, letterSpacing: '.02em', fontWeight: 600 }}>{n.label}</span>
                </button>
              );
            })}
          </div>
          <button onClick={() => setTheme((t) => (t === 'day' ? 'night' : 'day'))} title="day / night" style={{ width: 46, height: 46, borderRadius: 12, border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink2)' }}>
            <svg viewBox="0 0 24 24" style={{ width: 21, height: 21 }}><path d={theme === 'night' ? 'M12 3 V5 M12 19 V21 M3 12 H5 M19 12 H21 M5.5 5.5 L7 7 M17 17 L18.5 18.5 M18.5 5.5 L17 7 M7 17 L5.5 18.5 M12 8 a4 4 0 1 0 0 8 a4 4 0 0 0 0 -8' : 'M19 13 a8 8 0 1 1 -8 -10 a6 6 0 0 0 8 10 Z'} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#wob)" /></svg>
          </button>
          <div style={{ width: 38, height: 38, borderRadius: 99, background: 'var(--c-purple)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 6, color: '#fff', fontFamily: "'Bricolage Grotesque',sans-serif", fontWeight: 800, fontSize: 16, boxShadow: 'var(--btn-shadow)' }}>d</div>
        </nav>

        {/* sidebar */}
        <aside style={{ width: 268, background: 'var(--surface)', borderRight: '1.5px solid var(--line)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <div style={{ padding: '16px 14px 10px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button onClick={() => { setMessages([{ id: 0, isKitty: true, text: 'hey. what are we doing today' }]); setCatState('idle'); setInputVal(''); setActiveHistory(null); }} style={{ width: '100%', border: 'none', borderRadius: 12, background: 'var(--primary)', color: 'var(--on-primary)', padding: 11, fontFamily: "'Hanken Grotesk',sans-serif", fontWeight: 600, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, boxShadow: 'var(--btn-shadow)' }}>
              <span style={{ fontSize: 18, lineHeight: 1 }}>+</span> new chat
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface2)', border: '1.5px solid var(--line)', borderRadius: 11, padding: '8px 11px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, color: 'var(--ink2)', flexShrink: 0 }}><path d="M11 4 a7 7 0 1 0 0 14 a7 7 0 0 0 0 -14 M16 16 L21 21" stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" filter="url(#wob)" /></svg>
              <input type="text" placeholder="search chats" value={searchVal} onChange={(e) => setSearchVal(e.target.value)} style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: "'Hanken Grotesk',sans-serif", fontSize: 13, color: 'var(--ink)', outline: 'none' }} />
            </div>
          </div>
          <div style={{ overflowY: 'auto', flex: 1, padding: '2px 10px 12px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {groups.map((g) => (
              <div key={g.key} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, padding: '0 4px', marginBottom: 2 }}>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--ink2)' }}>{g.label}</span>
                  <svg viewBox="0 0 80 7" preserveAspectRatio="none" style={{ width: 46, height: 6 }}><path d="M2 5 Q22 1 40 4 T78 3.5" stroke={g.color} strokeWidth={2.4} fill="none" strokeLinecap="round" filter="url(#wob)" /></svg>
                </div>
                {g.items.map((it) => {
                  const active = activeHistory === it.id;
                  const dot = (it as { dot?: string }).dot || g.dot;
                  return (
                    <button key={it.id} onClick={() => setActiveHistory(it.id)} style={{ width: '100%', display: 'flex', alignItems: 'flex-start', gap: 9, border: 'none', borderRadius: 10, padding: '8px 9px', cursor: 'pointer', background: active ? 'var(--ginger-fade)' : 'transparent' }}>
                      <span style={{ width: 9, height: 9, borderRadius: 3, background: dot, flexShrink: 0, marginTop: 4 }} />
                      <span style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0, flex: 1, textAlign: 'left' }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.title}</span>
                        <span style={{ fontSize: 11.5, color: 'var(--ink2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.preview}</span>
                      </span>
                      <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: 'var(--ink2)', flexShrink: 0, marginTop: 3 }}>{it.ago}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          <div style={{ padding: '11px 14px', borderTop: '1.5px solid var(--line)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--c-green)' }} />
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--ink2)' }}>all synced · audience of one</span>
          </div>
        </aside>

        {/* main */}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 26px', height: 58, borderBottom: '1.5px solid var(--line)', background: 'var(--surface)', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
              <span style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontWeight: 800, fontSize: 23, letterSpacing: '-.02em', color: 'var(--ink)' }}>kitty</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--ink2)', border: '1.5px solid var(--line)', borderRadius: 99, padding: '3px 10px' }}>
                <span style={{ width: 7, height: 7, borderRadius: 99, background: STATE_DOT[catState] }} />{catState}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--ink2)', border: '1.5px solid var(--line)', borderRadius: 8, padding: '4px 9px' }}>⌘K</span>
              <button onClick={() => { addKitty('^_^ done. anything else'); setCatState('done'); sparkle(); resetState(); }} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--c-green)', border: '1.5px solid var(--line)', borderRadius: 8, padding: '4px 9px', background: 'transparent', cursor: 'pointer' }}>^_^ done</button>
              <button onClick={() => { addKitty(':[ something went sideways. want me to try again'); setCatState('broke'); resetState(3200); }} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--c-red)', border: '1.5px solid var(--line)', borderRadius: 8, padding: '4px 9px', background: 'transparent', cursor: 'pointer' }}>:[ broke</button>
            </div>
          </div>

          <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '30px 44px 16px', display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: .7 }}>
              <span style={{ flex: 1, height: 1.5, background: 'var(--line)' }} />
              <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--ink2)' }}>today</span>
              <span style={{ flex: 1, height: 1.5, background: 'var(--line)' }} />
            </div>
            {messages.map((m) => (
              <div key={m.id} className="msg-in" style={{ display: 'flex', alignItems: 'flex-end', gap: 10, flexDirection: m.isKitty ? 'row' : 'row-reverse' }}>
                {m.isKitty && (
                  <span style={{ width: 30, height: 30, borderRadius: 99, background: 'var(--ginger-fade)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: 'var(--cat-ginger)', flexShrink: 0, border: '1.5px solid var(--line)' }}>{FACES[catState]}</span>
                )}
                <span style={{ maxWidth: 560, borderRadius: m.isKitty ? '5px 17px 17px 17px' : '17px 5px 17px 17px', padding: '11px 16px', background: m.isKitty ? 'var(--surface)' : 'var(--primary)', border: m.isKitty ? '1.5px solid var(--line)' : 'none', boxShadow: '0 2px 8px rgba(0,0,0,.06)' }}>
                  {m.isTyping ? (
                    <span style={{ display: 'flex', gap: 5, alignItems: 'center', height: 16 }}>
                      <span className="dot1" style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink2)' }} />
                      <span className="dot2" style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink2)' }} />
                      <span className="dot3" style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink2)' }} />
                    </span>
                  ) : (
                    <span style={{ fontSize: 14.5, lineHeight: 1.5, color: m.isKitty ? 'var(--ink)' : 'var(--on-primary)' }}>{m.text}</span>
                  )}
                </span>
              </div>
            ))}
            {showChips && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, paddingLeft: 42, paddingTop: 2 }}>
                {CHIP_LABELS.map((label, i) => (
                  <button key={label} onClick={() => send(label)} style={{ background: 'var(--surface)', border: '1.5px solid var(--line)', borderRadius: 99, padding: '8px 15px', fontFamily: "'Hanken Grotesk',sans-serif", fontSize: 13, fontWeight: 500, color: 'var(--ink)', cursor: 'pointer', transform: `rotate(${CHIP_ROT[i % 4]}deg)`, boxShadow: '0 2px 6px rgba(0,0,0,.05)' }}>{label}</button>
                ))}
              </div>
            )}
          </div>

          <div style={{ padding: '14px 26px 20px', flexShrink: 0, background: 'var(--bg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11, background: 'var(--surface)', border: '2px solid var(--primary)', borderRadius: 16, padding: '12px 16px', boxShadow: 'var(--input-glow)' }}>
              <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 15, color: 'var(--primary)', flexShrink: 0 }}>→</span>
              <input type="text" placeholder={PLACEHOLDER[catState]} value={inputVal} onChange={(e) => setInputVal(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') send(); }} style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: "'Hanken Grotesk',sans-serif", fontSize: 15, color: 'var(--ink)', outline: 'none' }} />
              <button onClick={() => send()} style={{ width: 32, height: 32, borderRadius: 9, border: 'none', background: hasInput ? 'var(--primary)' : 'var(--line)', color: hasInput ? 'var(--on-primary)' : 'var(--ink2)', cursor: hasInput ? 'pointer' : 'default', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>↑</button>
            </div>
          </div>
        </main>
      </div>

      {/* corner cat */}
      <div style={{ position: 'fixed', bottom: 92, right: 26, zIndex: 30, pointerEvents: 'none' }}>
        <div className={`cat-${catState}`}><Cat size={66} viewBox="0 0 280 210" html={CAT_BODY} /></div>
      </div>

      {/* sparkles */}
      {showSparkle && (
        <div style={{ position: 'fixed', bottom: 150, right: 34, zIndex: 31, pointerEvents: 'none', width: 80, height: 80 }}>
          {[{ color: 'var(--c-yellow)', size: 26, l: 6, t: 8, d: 0 }, { color: 'var(--cat-ginger)', size: 18, l: 42, t: 0, d: 0.12 }, { color: 'var(--c-blue)', size: 15, l: 30, t: 34, d: 0.22 }].map((c, i) => (
            <svg key={i} viewBox="0 0 24 24" style={{ position: 'absolute', left: c.l, top: c.t, width: c.size, height: c.size, animation: `v2-pop 1.3s ease ${c.d}s forwards` }}><path d={STAR} fill={c.color} filter="url(#wob)" /></svg>
          ))}
        </div>
      )}

      {/* paper grain */}
      <svg style={grainStyle} aria-hidden><rect width="100%" height="100%" filter="url(#paper)" /></svg>
    </div>
  );
}
