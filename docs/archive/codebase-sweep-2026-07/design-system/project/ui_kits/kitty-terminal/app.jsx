// kitty terminal — chat UI

const { useState, useRef, useEffect } = React;

function Sidebar({ active, onPick }) {
  const threads = [
    { id: 't1', icon: '♡', title: 'today\'s plan', when: 'now' },
    { id: 't2', icon: '◆', title: 'birthday gift for jamie', when: '2h' },
    { id: 't3', icon: '★', title: 'cancun trip — flights', when: 'wed' },
    { id: 't4', icon: '▓', title: 'rewrite my linkedin', when: 'mar 4' },
    { id: 't5', icon: '→', title: 'tax stuff (ugh)', when: 'feb 28' },
    { id: 't6', icon: '~', title: 'what to cook tonight', when: 'feb 27' },
  ];
  const projects = [
    { id: 'p1', icon: '◇', title: 'house renovation' },
    { id: 'p2', icon: '◇', title: 'novel draft' },
  ];
  return (
    <aside className="side">
      <div className="brand">
        <img src="../../assets/kitty-mark.svg" alt="" />
        <span className="word">kitty</span>
        <span className="v">v0.1</span>
      </div>

      <button className="new-btn">＋ &nbsp;new chat</button>

      <div className="section-label">recent</div>
      <div className="threads">
        {threads.map(t => (
          <div key={t.id}
               className={"thread" + (active === t.id ? ' active' : '')}
               onClick={() => onPick(t.id)}>
            <span className="ico">{t.icon}</span>
            <span style={{flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{t.title}</span>
            <span className="when">{t.when}</span>
          </div>
        ))}
      </div>

      <div className="section-label">projects</div>
      <div className="threads">
        {projects.map(t => (
          <div key={t.id} className="thread">
            <span className="ico" style={{color:'var(--grape)'}}>{t.icon}</span>
            <span style={{flex:1}}>{t.title}</span>
          </div>
        ))}
      </div>

      <div className="side-foot">
        <div className="avatar">m</div>
        <div className="who">
          <b>marc</b><br/>
          <span style={{color:'var(--cream-faint)'}}>signed in · pro</span>
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  return (
    <div className="topbar">
      <div className="title"><span className="accent">$</span> today's plan</div>
      <div className="breadcrumb">· chat · saved 2 min ago</div>
      <div className="right">
        <button className="icon-btn" title="search">⌕</button>
        <button className="icon-btn" title="pin">★</button>
        <button className="icon-btn" title="more">···</button>
      </div>
    </div>
  );
}

function KittyMsg({ children, time = '10:41' }) {
  return (
    <div className="msg">
      <div className="who-badge"><img src="../../assets/kitty-mascot.svg" alt="kitty"/></div>
      <div className="body">
        <div className="who"><b>kitty</b> · {time}</div>
        {children}
      </div>
    </div>
  );
}

function MeMsg({ children, time = '10:41' }) {
  return (
    <div className="msg me">
      <div className="who-badge">m</div>
      <div className="body">
        <div className="who"><b>you</b> · {time}</div>
        <div className="bubble">{children}</div>
      </div>
    </div>
  );
}

function ToolCard({ name, target, status = 'done' }) {
  return (
    <div className="tool-card">
      <div className="ico">✓</div>
      <div className="name">{name}<span>{target}</span></div>
      <div className="status">{status}</div>
    </div>
  );
}

function Feed() {
  return (
    <div className="feed">
      <div className="feed-inner">
        <div className="day-divider">monday · feb 26</div>

        <KittyMsg time="10:39">
          <div className="bubble">
            hey :3 you got 4 things on the list today. wanna start with the laundry or the email
          </div>
        </KittyMsg>

        <MeMsg time="10:40">laundry. i'm scared of the email</MeMsg>

        <KittyMsg time="10:40">
          <div className="bubble">
            understandable. timer set for <code>35 min</code>. i'll poke you when it buzzes
            <ToolCard name="timer.set" target="35 minutes — laundry" status="running"/>
          </div>
        </KittyMsg>

        <MeMsg time="10:42">also can you find me a cheap flight to halifax in march. 4ish days, midweek</MeMsg>

        <KittyMsg time="10:42">
          <div className="bubble">
            ok cool, looking. i'll prefer non-stop and aim under $400 cad
            <ToolCard name="flights.search" target="yyz → yhz · mar 11–14" status="3 results"/>
            <div style={{marginTop:'10px', display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:'8px'}}>
              <FlightOption airline="porter" price="$318" stops="non-stop" time="6:40 am"/>
              <FlightOption airline="air canada" price="$362" stops="non-stop" time="11:15 am" recommended/>
              <FlightOption airline="westjet" price="$291" stops="1 stop" time="2:05 pm"/>
            </div>
            <div className="quick-row">
              <button className="chip">book the air canada one</button>
              <button className="chip">show more times</button>
              <button className="chip">add to calendar</button>
            </div>
          </div>
        </KittyMsg>

        <MeMsg time="10:43">i love you</MeMsg>

        <KittyMsg time="10:43">
          <div className="bubble">don't get weird on me</div>
        </KittyMsg>
      </div>
    </div>
  );
}

function FlightOption({ airline, price, stops, time, recommended }) {
  return (
    <div style={{
      border: recommended ? '1px solid var(--tabby)' : '1px solid var(--ink-line)',
      background: 'var(--ink)',
      padding: '10px 12px',
      position: 'relative',
    }}>
      {recommended && (
        <div style={{
          position:'absolute', top:'-8px', left:'10px',
          fontSize:'9px', textTransform:'uppercase', letterSpacing:'0.12em',
          background:'var(--tabby)', color:'var(--ink-deep)', padding:'2px 6px',
          fontWeight:700,
        }}>kitty's pick</div>
      )}
      <div style={{fontFamily:'var(--font-display)', fontSize:'22px', color:'var(--cream)', lineHeight:1}}>{price}</div>
      <div style={{fontSize:'12px', color:'var(--cream)', marginTop:'4px'}}>{airline}</div>
      <div style={{fontSize:'10px', color:'var(--cream-faint)', textTransform:'uppercase', letterSpacing:'0.1em', marginTop:'2px'}}>{time} · {stops}</div>
    </div>
  );
}

function Composer() {
  const [val, setVal] = useState('');
  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="composer-input">
          <span className="pmt">$</span>
          <input
            value={val}
            onChange={e => setVal(e.target.value)}
            placeholder="say something to kitty…"
          />
          {val.length === 0 && <span className="caret"></span>}
        </div>
        <div className="composer-bar">
          <button className="tool-btn">＋ attach</button>
          <button className="tool-btn">/ commands</button>
          <button className="tool-btn">@ context</button>
          <span className="hint"><kbd>⌘</kbd><kbd>K</kbd> commands · <kbd>↵</kbd> send</span>
          <button className="send">send →</button>
        </div>
      </div>
    </div>
  );
}

function Rail() {
  return (
    <aside className="rail">
      <div>
        <h3>nudges</h3>
        <div className="sub">stuff kitty's keeping an eye on</div>
      </div>

      <div className="nudge">
        <div className="when"><span className="dot lemon"></span>in 28 min · timer</div>
        <div className="title">laundry will buzz at <b>11:15</b></div>
        <div className="row">
          <button className="chip">snooze 10</button>
          <button className="chip">cancel</button>
        </div>
      </div>

      <div className="nudge">
        <div className="when"><span className="dot"></span>tomorrow · 2:00pm</div>
        <div className="title">call mom — sunday like you said. i blocked the time.</div>
        <div className="row">
          <button className="chip">good</button>
          <button className="chip">move it</button>
        </div>
      </div>

      <div className="nudge">
        <div className="when"><span className="dot maple"></span>4 days late</div>
        <div className="title">that email to your landlord. you know the one.</div>
        <div className="row">
          <button className="chip" style={{borderColor:'var(--maple)', color:'var(--maple)', whiteSpace:'nowrap'}}>draft it for me</button>
        </div>
      </div>

      <div>
        <h3 style={{marginTop:'4px'}}>this week</h3>
      </div>
      <div className="stat-row">
        <div className="stat">
          <div className="num">12</div>
          <div className="lbl">tasks done</div>
        </div>
        <div className="stat">
          <div className="num mint">3.2h</div>
          <div className="lbl">deep work</div>
        </div>
        <div className="stat">
          <div className="num" style={{color:'var(--grape)'}}>4</div>
          <div className="lbl">chats</div>
        </div>
        <div className="stat">
          <div className="num" style={{color:'var(--lemon)'}}>1</div>
          <div className="lbl">overdue</div>
        </div>
      </div>

      <div className="now-playing">
        <img src="../../assets/kitty-mascot.svg" alt=""/>
        <div>
          <div className="what">kitty status</div>
          <div className="state">awake :3</div>
          <div className="meta">listening · 2 tools online</div>
        </div>
      </div>
    </aside>
  );
}

function App() {
  const [active, setActive] = useState('t1');
  return (
    <div className="app">
      <Sidebar active={active} onPick={setActive}/>
      <main className="main">
        <Topbar/>
        <Feed/>
        <Composer/>
      </main>
      <Rail/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
