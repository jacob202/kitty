// app.jsx — kitty: rail + left sidebar (content swaps) + chat + right brief
// dark ink palette, all DS colors visible, both sidebars collapsible

const { useState, useEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "screen": "empty",
  "leftOpen": true,
  "rightOpen": true,
  "railActive": "chats",
  "activeThread": "t1"
}/*EDITMODE-END*/;

const KITTY = '../../assets/mascot/kitty.svg';

// ============ rail icons ============
function IconChats() { return (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 5 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v7 a2 2 0 0 1 -2 2 h-6 l-3 3 v-3 h-1 a2 2 0 0 1 -2 -2 z"/>
  </svg>); }
function IconMem() { return (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3 c-3 0 -5 2 -5 4 c0 1 0 1 -1 2 c-1 1 -1 3 0 4 c1 1 1 1 1 2 c0 2 2 4 5 4 c3 0 5 -2 5 -4 c0 -1 0 -1 1 -2 c1 -1 1 -3 0 -4 c-1 -1 -1 -1 -1 -2 c0 -2 -2 -4 -5 -4 z"/>
    <path d="M10 3 v14 M5 9 h10"/>
  </svg>); }
function IconKnow() { return (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 3 v14 l6 -2 l6 2 v-14 l-6 2 z"/>
    <path d="M10 5 v12"/>
  </svg>); }
function IconAgent() { return (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 2 L4 11 h5 l-2 7 l8 -10 h-5 z" fill="currentColor"/>
  </svg>); }
function IconSettings() { return (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="10" cy="10" r="2.5"/>
    <path d="M10 1.5 v2.5 M10 16 v2.5 M1.5 10 h2.5 M16 10 h2.5 M3.5 3.5 l1.7 1.7 M14.8 14.8 l1.7 1.7 M3.5 16.5 l1.7 -1.7 M14.8 5.2 l1.7 -1.7"/>
  </svg>); }

const RAIL_ITEMS = [
  { id: 'chats', label: 'chats',     Icon: IconChats },
  { id: 'mem',   label: 'memory',    Icon: IconMem },
  { id: 'know',  label: 'knowledge', Icon: IconKnow },
  { id: 'agent', label: 'agents',    Icon: IconAgent },
];

// ============ Rail ============
function Rail({ active, onPick, onSettings }) {
  return (
    <aside className="rail">
      <div className="rail-mark"><img src={KITTY} alt=""/></div>
      {RAIL_ITEMS.map(it => {
        const Icon = it.Icon;
        return (
          <button
            key={it.id}
            className={"rail-btn" + (active === it.id ? ' active' : '')}
            onClick={() => onPick(it.id)}
          >
            <Icon/>
            <span className="tip">{it.label}</span>
          </button>
        );
      })}
      <div className="rail-spacer"/>
      <button
        className={"rail-btn" + (active === 'set' ? ' active' : '')}
        onClick={onSettings}
      >
        <IconSettings/>
        <span className="tip">settings</span>
      </button>
    </aside>
  );
}

// ============ LEFT SIDEBAR — content swaps based on rail active ============
function SideLeftChats({ active, onPick }) {
  const today = [
    { id: 't1', g: '★', t: "today's brief",            when: 'now' },
    { id: 't2', g: '◆', t: 'halifax flights research', when: '9:12' },
  ];
  const yesterday = [
    { id: 't3', g: '→', t: 'rewrite landing copy',     when: '4:21' },
    { id: 't4', g: '▓', t: 'q1 doc outline',           when: '11am' },
    { id: 't5', g: '~', t: 'tax docs sorted',          when: '9am' },
  ];
  const lastweek = [
    { id: 't6', g: '◇', t: 'gift ideas for jamie',     when: 'wed' },
    { id: 't7', g: '♡', t: 'rent the plateau place',   when: 'tue' },
    { id: 't8', g: '★', t: 'what to cook tonight',     when: 'mon' },
  ];
  const projects = [
    { id: 'p1', g: '◇', t: 'house reno' },
    { id: 'p2', g: '◇', t: 'novel draft' },
  ];

  return (
    <>
      <div className="side-left-head">
        <h2>chats</h2>
        <span className="count">38</span>
      </div>
      <button className="new-chat-btn">
        <span className="plus">＋</span>
        new chat
        <span className="kbd">⌘N</span>
      </button>
      <div className="threads-scroll">
        <div className="side-section">today</div>
        {today.map(it => (
          <div key={it.id}
               className={"thread" + (active === it.id ? ' active' : '')}
               onClick={() => onPick(it.id)}>
            <span className="g">{it.g}</span>
            <span className="t">{it.t}</span>
            <span className="when">{it.when}</span>
          </div>
        ))}

        <div className="side-section">yesterday</div>
        {yesterday.map(it => (
          <div key={it.id} className="thread" onClick={() => onPick(it.id)}>
            <span className="g">{it.g}</span>
            <span className="t">{it.t}</span>
            <span className="when">{it.when}</span>
          </div>
        ))}

        <div className="side-section">last week</div>
        {lastweek.map(it => (
          <div key={it.id} className="thread" onClick={() => onPick(it.id)}>
            <span className="g">{it.g}</span>
            <span className="t">{it.t}</span>
            <span className="when">{it.when}</span>
          </div>
        ))}

        <div className="side-section">projects</div>
        {projects.map(it => (
          <div key={it.id} className="thread k-proj">
            <span className="g">{it.g}</span>
            <span className="t">{it.t}</span>
          </div>
        ))}
      </div>
      <div className="side-foot">
        <div className="avatar">m</div>
        <div className="who">
          <b>marc</b>
          <span className="status">signed in · pro</span>
        </div>
      </div>
    </>
  );
}

function SideLeftMemory() {
  const items = [
    { k: 'name',      v: <>you go by <em>marc</em></> },
    { k: 'location',  v: <>montreal · plateau-mont-royal</> },
    { k: 'work',      v: <>staff designer @ <em>anthropic</em></> },
    { k: 'allergies', v: <>shellfish — don't suggest seafood</> },
    { k: 'partner',   v: <>jamie · birthday <em>mar 14</em></> },
    { k: 'wants',     v: <>halifax in march, non-stop, ≤ $400</> },
    { k: 'voice',     v: <>i talk casual & lowercase. don't be perky.</> },
  ];
  return (
    <>
      <div className="side-left-head">
        <h2>memory</h2>
        <span className="count">124</span>
      </div>
      <div className="side-search">
        <input placeholder="search memory…"/>
      </div>
      <div className="threads-scroll">
        {items.map(it => (
          <div key={it.k} className="mem">
            <div className="k">{it.k}</div>
            <div className="v">{it.v}</div>
          </div>
        ))}
      </div>
      <div className="side-foot-mini">
        <span style={{color:'var(--cream-faint)', fontSize:10.5}}>+ add</span>
        <span style={{marginLeft:'auto', color:'var(--grape)', fontSize:10.5}}>kitty wrote 84</span>
      </div>
    </>
  );
}

function SideLeftKnow() {
  const docs = [
    { ext: 'pdf', name: 'apartment lease 2024.pdf',     meta: 'feb 1',   size: '1.2mb' },
    { ext: 'md',  name: 'q1-2026 design notes.md',      meta: '3d ago',  size: '14kb' },
    { ext: 'pdf', name: 'halifax-trip.pdf',             meta: 'feb 18',  size: '420kb' },
    { ext: 'txt', name: 'jamie gift ideas.txt',         meta: 'last wk', size: '2kb' },
    { ext: 'url', name: 'porter air faq',               meta: 'pinned',  size: 'web' },
    { ext: 'md',  name: 'mom recipe.md',                meta: 'jan 12',  size: '6kb' },
  ];
  return (
    <>
      <div className="side-left-head">
        <h2>knowledge</h2>
        <span className="count">38</span>
      </div>
      <div className="side-search">
        <input placeholder="search docs & urls…"/>
      </div>
      <div className="threads-scroll">
        {docs.map(d => (
          <div key={d.name} className="doc">
            <div className={"ext " + d.ext}>{d.ext}</div>
            <div>
              <div className="doc-name">{d.name}</div>
              <div className="doc-meta">{d.meta}</div>
            </div>
            <div className="doc-size">{d.size}</div>
          </div>
        ))}
      </div>
      <div className="side-foot-mini">
        <span style={{color:'var(--cream-faint)', fontSize:10.5}}>+ upload</span>
        <span style={{marginLeft:'auto', color:'var(--cream-faint)', fontSize:10.5}}>4.3 mb · ▓▓▓░ 76%</span>
      </div>
    </>
  );
}

function SideLeftAgents() {
  return (
    <>
      <div className="side-left-head">
        <h2>agents</h2>
        <span className="count">2 live</span>
      </div>
      <div className="threads-scroll">
        <div className="side-section">running</div>
        <div className="agent running">
          <div className="head"><span className="pulse"/><span className="name">flight-watcher</span><span className="when">2m</span></div>
          <div className="desc">yul→yhz · mar 11-14 · ≤$400</div>
          <div className="bar"><span style={{width:'64%'}}/></div>
        </div>
        <div className="agent running">
          <div className="head"><span className="pulse"/><span className="name">inbox-triage</span><span className="when">9m</span></div>
          <div className="desc">3 new threads · drafting replies</div>
          <div className="bar"><span style={{width:'30%'}}/></div>
        </div>
        <div className="side-section">recent</div>
        <div className="agent done">
          <div className="head"><span className="pulse"/><span className="name">q1-summarize</span><span className="when">22m</span></div>
          <div className="desc">done · 4 sections</div>
        </div>
        <div className="agent done">
          <div className="head"><span className="pulse"/><span className="name">cal-conflict</span><span className="when">1h</span></div>
          <div className="desc">moved standup to 10:30</div>
        </div>
        <div className="agent fail">
          <div className="head"><span className="pulse"/><span className="name">spotify-bridge</span><span className="when">3h</span></div>
          <div className="desc" style={{color:'var(--maple)'}}>token expired</div>
        </div>
      </div>
      <div className="side-foot-mini">
        <span style={{color:'var(--cream-faint)', fontSize:10.5}}>+ new agent</span>
        <span style={{marginLeft:'auto', color:'var(--mint)', fontSize:10.5}}>● 2 running</span>
      </div>
    </>
  );
}

function SideLeftSettings() {
  return (
    <>
      <div className="side-left-head">
        <h2>settings</h2>
      </div>
      <div className="threads-scroll" style={{padding:'4px 0'}}>
        <div className="field">
          <div className="field-label">model</div>
          <select defaultValue="kitty-3.1-mini">
            <option>kitty-3.1-mini</option>
            <option>kitty-3.1-pro</option>
            <option>kitty-3.1-fast</option>
          </select>
        </div>
        <div className="field">
          <div className="field-label">gateway</div>
          <input type="text" defaultValue="http://localhost:5001"/>
        </div>
        <div className="field">
          <div className="field-row">
            <div className="desc"><b>personality</b>casual, lowercase, dry</div>
            <div className="toggle on"/>
          </div>
        </div>
        <div className="field">
          <div className="field-row">
            <div className="desc"><b>auto-brief @ 8am</b>build brief on launch</div>
            <div className="toggle on"/>
          </div>
        </div>
        <div className="field">
          <div className="field-row">
            <div className="desc"><b>send on ↵</b>shift+↵ for newline</div>
            <div className="toggle on"/>
          </div>
        </div>
      </div>
      <div className="side-foot-mini">
        <span style={{color:'var(--cream-faint)', fontSize:10.5}}>kitty v0.1.4</span>
        <span style={{marginLeft:'auto', color:'var(--mint)', fontSize:10.5}}>● connected</span>
      </div>
    </>
  );
}

const SIDE_LEFT = {
  chats: SideLeftChats,
  mem:   SideLeftMemory,
  know:  SideLeftKnow,
  agent: SideLeftAgents,
  set:   SideLeftSettings,
};

// ============ Calendar widget ============
function Calendar() {
  // feb 26 2026 — a wednesday
  const today = 26;
  const events = new Set([10, 14, 17, 20, 24, 26, 28]);
  // feb 2026: 1st is sun, 28 days
  const cells = [];
  for (let i = 0; i < 28; i++) cells.push({ day: i + 1, muted: false });
  // pad start: feb 1 2026 is a sunday, so no leading pad needed (sun=0)
  // pad trail to fill grid: 28 days + 0 pad = 28 = 4 weeks exactly. add one trailing row to feel calendar-y.
  for (let i = 1; i <= 7; i++) cells.push({ day: i, muted: true });
  return (
    <div className="cal">
      <div className="cal-head">
        <button>‹</button>
        <span className="m">february 2026</span>
        <button>›</button>
      </div>
      <div className="cal-grid">
        {['S','M','T','W','T','F','S'].map((d, i) => <div key={i} className="cal-dow">{d}</div>)}
        {cells.map((c, i) => {
          const cls = ['cal-day'];
          if (c.muted) cls.push('muted');
          if (!c.muted && c.day === today) cls.push('today');
          if (!c.muted && events.has(c.day)) cls.push('has-event');
          return <div key={i} className={cls.join(' ')}>{c.day}</div>;
        })}
      </div>
    </div>
  );
}

// ============ RIGHT SIDEBAR — calendar + restrained cards ============
function SideRight({ onCollapse }) {
  return (
    <aside className="side-right">
      <div className="side-head">
        <h2>today</h2>
        <span className="date">wed feb 26</span>
        <button onClick={onCollapse} title="hide"
                style={{background:'transparent', border:0, color:'var(--cream-faint)', padding:'3px 6px', borderRadius:3, cursor:'pointer'}}>→|</button>
      </div>
      <div className="side-body">

        <Calendar/>

        <div className="scard">
          <h4>schedule <span className="badge">3 events</span></h4>
          <div className="row-s"><span className="when">10:30</span><span className="what" style={{color:'var(--tabby)', fontWeight:700}}>standup</span></div>
          <div className="row-s"><span className="when">12:30</span><span className="what">lunch w/ jamie</span></div>
          <div className="row-s"><span className="when">3:00</span><span className="what">deep work · q1 doc</span></div>
        </div>

        <div className="scard danger">
          <h4>overdue <span className="badge maple">4d</span></h4>
          <div className="what-title">landlord email</div>
          <div className="desc">heat's been out 4 nights. you keep saying you'll send it.</div>
          <div className="actions">
            <button className="primary">draft it</button>
            <button>snooze</button>
          </div>
        </div>

        <div className="scard">
          <h4>watching <span className="badge">4</span></h4>
          <div className="row-s"><span className="what">halifax flight</span><span className="num-s">$291</span><span className="delta">↓$27</span></div>
          <div className="row-s"><span className="what">vinyl reissue</span><span className="num-s">$38</span><span className="delta flat">—</span></div>
          <div className="row-s"><span className="what">inbox unread</span><span className="num-s">3</span><span className="delta up">+2</span></div>
          <div className="row-s"><span className="what">apt temp · 24h</span><span className="num-s">17°c</span><span className="delta up">cold</span></div>
        </div>

        <div className="scard">
          <h4>memory · pinned <span className="badge">8</span></h4>
          <div className="row-s"><span className="what">jamie b-day · <span style={{color:'var(--tabby)'}}>mar 14</span></span></div>
          <div className="row-s"><span className="what">no shellfish</span></div>
          <div className="row-s"><span className="what">non-stop, ≤$400 cad</span></div>
        </div>

        <div className="scard">
          <h4>agents <span className="badge">2 live</span></h4>
          <div className="row-s"><span className="what"><span style={{color:'var(--mint)'}}>●</span> flight-watcher</span><span className="when">2m</span></div>
          <div className="row-s"><span className="what"><span style={{color:'var(--mint)'}}>●</span> inbox-triage</span><span className="when">9m</span></div>
          <div className="row-s"><span className="what"><span style={{color:'var(--maple)'}}>●</span> spotify · expired</span><span className="when">3h</span></div>
        </div>

      </div>
      <div className="side-foot">
        <div className="pet-mini">
          <img src={KITTY} alt=""/>
          <div>
            <div className="state">awake :3</div>
            <div className="meta">listening · 2 tools</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

// ============ topbar ============
function TopBar({ title, breadcrumb, leftOpen, rightOpen, onToggleLeft, onToggleRight }) {
  return (
    <div className="topbar">
      <button className="sb-toggle" onClick={onToggleLeft} title={leftOpen ? 'hide sidebar' : 'show sidebar'}>
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <rect x="2" y="3" width="12" height="10" rx="1"/>
          <path d="M6 3 v10" stroke={leftOpen ? 'currentColor' : 'var(--tabby)'}/>
        </svg>
      </button>
      <h1>{title}{breadcrumb && <span className="breadcrumb">{breadcrumb}</span>}</h1>
      <button className="model-pill"><span className="dot"/>kitty-3.1-mini<span style={{color:'var(--cream-faint)', fontSize:10}}>▾</span></button>
      <button className="top-btn">↗ share</button>
      <button className="sb-toggle" onClick={onToggleRight} title={rightOpen ? 'hide brief' : 'show brief'}>
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <rect x="2" y="3" width="12" height="10" rx="1"/>
          <path d="M10 3 v10" stroke={rightOpen ? 'currentColor' : 'var(--tabby)'}/>
        </svg>
      </button>
    </div>
  );
}

// ============ empty state = morning brief (data-rich) ============
function MorningBrief() {
  return (
    <div className="brief">
      <div className="brief-inner">

        <div className="brief-hero">
          <img src={KITTY} alt=""/>
          <div>
            <h1>morning, marc <span className="accent">:3</span></h1>
            <div className="meta">mon · feb 26 · 9:31am · awake</div>
          </div>
        </div>

        <div className="tiles">
          <div className="tile primary">
            <h3>weather <span className="badge">snow 2pm</span></h3>
            <div className="big">-4°c</div>
            <div className="desc">cold front. snow rolling in. wear the boots.</div>
          </div>
          <div className="tile">
            <h3>next up <span className="badge">59m</span></h3>
            <div className="big">standup</div>
            <div className="desc">10:30 · w/ team · notes pinned</div>
          </div>
          <div className="tile danger">
            <h3>overdue <span className="badge maple">4d</span></h3>
            <div className="big">landlord</div>
            <div className="desc">heat thing. you've been ducking it.</div>
          </div>
        </div>

        <div className="tile tile-sched">
          <h3>today's schedule <span className="badge">3 events · 3h 30m</span></h3>
          <div className="rows">
            <div className="r"><span className="when">10:30</span><span className="what now">standup w/ team <em>· prep notes pinned</em></span><span className="dur">30m</span></div>
            <div className="r"><span className="when">12:30</span><span className="what">lunch w/ jamie <em>· café st-henri</em></span><span className="dur">1h</span></div>
            <div className="r"><span className="when">3:00</span><span className="what">deep work · finish q1 doc</span><span className="dur">2h</span></div>
          </div>
        </div>

        <div className="tiles" style={{gridTemplateColumns:'1.4fr 1fr'}}>
          <div className="tile tile-watch">
            <h3>watching <span className="badge">4</span></h3>
            <div className="rows">
              <div className="r"><span className="what">halifax flight · porter non-stop</span><span className="num">$291</span><span className="delta">↓$27</span></div>
              <div className="r"><span className="what">that vinyl reissue</span><span className="num">$38</span><span className="delta flat">—</span></div>
              <div className="r"><span className="what">inbox unread</span><span className="num">3</span><span className="delta up">+2</span></div>
              <div className="r"><span className="what">apartment temp · last 24h</span><span className="num">17°c</span><span className="delta up">cold</span></div>
            </div>
          </div>
          <div className="tile tile-overdue">
            <h3>side-eyeing <span className="badge maple">4d</span></h3>
            <div className="what">landlord email</div>
            <div className="why">heat's been out 4 nights. you keep saying you'll send it.</div>
            <div className="actions">
              <button className="primary">draft for me</button>
              <button>snooze 1d</button>
              <button>not today</button>
            </div>
          </div>
        </div>

        <div className="prompts">
          <div className="label">quick start</div>
          <button className="chip"><span className="g">→</span>summarize yesterday's standup<span className="ar">↵</span></button>
          <button className="chip"><span className="g">→</span>book the porter flight at $318<span className="ar">↵</span></button>
          <button className="chip"><span className="g">→</span>what should i eat tonight<span className="ar">↵</span></button>
        </div>

      </div>
    </div>
  );
}

// ============ chat feed ============
function ChatFeed() {
  return (
    <div className="feed">
      <div className="feed-inner">
        <div className="day-marker">today · feb 26</div>

        <article className="msg-k first">
          <div className="peek"/>
          <div>
            <div>
              morning. prices on the halifax thing moved overnight — porter dropped to <code>$318</code> non-stop. westjet has a 1-stop at <code>$291</code> if you want to save the $27.
              <ToolCall name="flights.watch" arg="yul → yhz · mar 11–14" status="3 results"/>
            </div>
            <span className="ts">9:42am</span>
          </div>
        </article>

        <article className="msg-m">
          <div className="body">
            non-stop. book porter.
            <span className="ts">9:43am</span>
          </div>
          <div className="marker"/>
        </article>

        <article className="msg-k">
          <div className="peek"/>
          <div>
            <div>
              done. confirmation hitting your inbox in ~2 min. blocked tuesday afternoon for packing because you always forget the charger.
              <ToolCall name="flights.book" arg="porter · mar 11 06:40" status="confirmed"/>
            </div>
            <span className="ts">9:43am</span>
          </div>
        </article>

        <article className="msg-m">
          <div className="body">
            also — the landlord email. just rip it.
            <span className="ts">9:45am</span>
          </div>
          <div className="marker"/>
        </article>

        <article className="msg-k">
          <div className="peek"/>
          <div>
            <div>
              on it. tone: firm but cool, mentions the heat being out 4 nights, asks for a specific date. <em>do not</em> forward your previous threads — too much fuel.
              <div className="typing"><span/><span/><span/></div>
            </div>
          </div>
        </article>
      </div>
    </div>
  );
}

function ToolCall({ name, arg, status }) {
  return (
    <div className="tool">
      <span className="nm">▸ {name}</span>
      <span className="ar">{arg}</span>
      <span className="st">{status}</span>
    </div>
  );
}

// ============ composer ============
function Composer({ placeholder }) {
  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="composer-input">
          <textarea placeholder={placeholder} rows={1}/>
        </div>
        <div className="composer-bar">
          <button className="b">＋ attach</button>
          <button className="b">/ commands</button>
          <button className="b has">@ context · 2</button>
          <span className="spacer"/>
          <span className="hint"><kbd>⌘K</kbd></span>
          <button className="send" disabled>send →</button>
        </div>
      </div>
    </div>
  );
}

// ============ app ============
function App() {
  const [t, setT] = useTweaks(TWEAK_DEFAULTS);
  const [activeThread, setActiveThread] = useState(t.activeThread || 't1');
  const isEmpty = t.screen === 'empty';
  const leftOpen = t.leftOpen !== false;
  const rightOpen = t.rightOpen !== false;
  const railActive = t.railActive || 'chats';
  const SideContent = SIDE_LEFT[railActive] || SideLeftChats;

  const cls = ['kf', !leftOpen && 'no-left', !rightOpen && 'no-right'].filter(Boolean).join(' ');

  return (
    <>
      <div className={cls}>
        <Rail
          active={railActive}
          onPick={(id) => { setT('railActive', id); if (!leftOpen) setT('leftOpen', true); }}
          onSettings={() => { setT('railActive', 'set'); if (!leftOpen) setT('leftOpen', true); }}
        />
        <aside className="side-left">
          <SideContent active={activeThread} onPick={(id) => { setActiveThread(id); setT('activeThread', id); }}/>
        </aside>
        <div className="main">
          <TopBar
            title={isEmpty ? 'new chat' : "today's brief"}
            breadcrumb={isEmpty ? '· empty' : '· active'}
            leftOpen={leftOpen}
            rightOpen={rightOpen}
            onToggleLeft={() => setT('leftOpen', !leftOpen)}
            onToggleRight={() => setT('rightOpen', !rightOpen)}
          />
          {isEmpty ? <MorningBrief/> : <ChatFeed/>}
          <Composer placeholder={isEmpty ? 'message kitty…' : 'reply…'}/>
        </div>
        <SideRight onCollapse={() => setT('rightOpen', false)}/>

        {!leftOpen && (
          <button className="peek-btn l" onClick={() => setT('leftOpen', true)}>
            ▶ {railActive}
          </button>
        )}
        {!rightOpen && (
          <button className="peek-btn r" onClick={() => setT('rightOpen', true)}>
            ◀ today
          </button>
        )}
      </div>

      <TweaksPanel title="kitty">
        <TweakSection label="state">
          <TweakRadio
            label="screen"
            value={t.screen}
            options={[{value:'empty', label:'brief'}, {value:'chat', label:'chat'}]}
            onChange={(v) => setT('screen', v)}
          />
          <TweakToggle label="left sidebar"  value={leftOpen}  onChange={(v) => setT('leftOpen', v)}/>
          <TweakToggle label="right sidebar" value={rightOpen} onChange={(v) => setT('rightOpen', v)}/>
        </TweakSection>
        <TweakSection label="rail">
          <TweakSelect
            label="active"
            value={railActive}
            options={[
              {value:'chats', label:'chats'},
              {value:'mem',   label:'memory'},
              {value:'know',  label:'knowledge'},
              {value:'agent', label:'agents'},
              {value:'set',   label:'settings'},
            ]}
            onChange={(v) => setT('railActive', v)}
          />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
