---
name: flashcard-study-system
description: Build a comprehensive flashcard study application with spaced repetition, confidence tracking, statistics, and multi-format card support. Use when asked to create a flashcard app, study tool, or learning system.
---

## Purpose

Build a production-ready flashcard study system with spaced repetition (SM-2 algorithm), card categorization, progress tracking, and import/export capabilities.

## When to Activate

Invoke this skill when the user asks to:
- "Build a flashcard app"
- "Create a study system"
- "Implement spaced repetition"
- "Make a quiz app"
- "Build a learning tool"
- "Create flashcards"

## Detection

Look for these indicators to auto-activate:
- Request involves spaced repetition terminology (SM-2, Leitner)
- User wants to study, memorize, or review concepts
- Project structure with decks/cards/categories

## Process

### Step 1: Architecture Design

```
flashcard-app/
├── index.html              # Entry point
├── style.css               # Global styles + themes
├── app.js                  # Main application logic
├── lib/
│   ├── sm2.js              # Spaced repetition algorithm
│   ├── storage.js          # localStorage/indexedDB persistence
│   ├── parser.js           # Import/export (CSV, JSON, APKG)
│   └── stats.js            # Study statistics engine
├── components/
│   ├── DeckList.js         # Deck overview
│   ├── StudySession.js     # Active review session
│   ├── CardEditor.js       # Card creation/editing
│   ├── StatsDashboard.js   # Progress visualization
│   └── ImportExport.js     # Data management
└── data/
    └── decks.json          # Default/sample decks
```

### Step 2: Implement SM-2 Spaced Repetition Algorithm

```javascript
// lib/sm2.js — The core learning algorithm
function sm2(quality, repetitions, easeFactor, interval) {
  // quality: 0-5 self-assessment (0=forgot, 5=perfect)
  // returns: { repetitions, easeFactor, interval, nextReview }

  if (quality < 3) {
    // Reset — user didn't remember
    return {
      repetitions: 0,
      easeFactor: Math.max(1.3, easeFactor - 0.2),
      interval: 1, // Review tomorrow
    };
  }

  const newEaseFactor = easeFactor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  const newRepetitions = repetitions + 1;

  let newInterval;
  if (newRepetitions === 1) {
    newInterval = 1;
  } else if (newRepetitions === 2) {
    newInterval = 6;
  } else {
    newInterval = Math.round(interval * newEaseFactor);
  }

  return {
    repetitions: newRepetitions,
    easeFactor: Math.max(1.3, newEaseFactor),
    interval: newInterval,
    nextReview: Date.now() + newInterval * 86400000,
  };
}
```

### Step 3: Implement Card Types

| Card Type | Front | Back | Use Case |
|-----------|-------|------|----------|
| Basic | Text | Text | Definitions, facts |
| Cloze | Text with `{...}` | Filled text | Fill-in-the-blank |
| Image | Image + prompt | Explanation | Diagrams, maps |
| Audio | Audio + prompt | Answer | Language learning |
| Reversed | Term | Definition | Bidirectional recall |
| Type-in | Question | Answer + typing | Spelling, formulas |

```html
<!-- Card templates example -->
<template id="card-basic">
  <div class="card" role="article">
    <div class="card-front">
      <p>{{front}}</p>
    </div>
    <div class="card-back" hidden>
      <p>{{back}}</p>
      <button onclick="this.rate(quality)">Rate</button>
    </div>
  </div>
</template>
```

### Step 4: Data Persistence

```javascript
// lib/storage.js
const DB_NAME = 'flashcard-studio';
const STORE = 'cards';

async function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      db.createObjectStore(STORE, { keyPath: 'id' });
      db.createObjectStore('decks', { keyPath: 'id' });
      db.createObjectStore('stats', { keyPath: 'date' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
```

### Step 5: Study Session Flow

```bash
# Build commands
# No build step — pure HTML/CSS/JS
# Or with Vite for TypeScript:
# npm create vite@latest . -- --template vanilla-ts

# Run locally
python3 -m http.server 8000
# or
npx serve .
```

**Session Logic:**

1. Load all cards due for review (`nextReview <= now`)
2. Shuffle due cards
3. Show front, wait for user to reveal back
4. User self-assesses (0-5)
5. Run SM-2 → update card schedule
6. Log result to stats
7. Repeat until all due cards reviewed
8. Show summary

### Step 6: Statistics Dashboard

Track these metrics:

| Metric | Calculation | Visualization |
|--------|------------|--------------|
| Cards due today | Count where `nextReview <= now` | Number badge |
| Retention rate | Cards with quality >= 3 / total reviews | Progress bar |
| Reviews today | Count of today's reviews | Line chart |
| Cards mastered | Cards with interval >= 21 days | Percentage |
| Study streak | Consecutive days with >= 1 review | Calendar heatmap |
| Average ease | Mean ease factor across all cards | Number |
| Deck breakdown | Cards per deck with due counts | Stacked bar |

```javascript
// lib/stats.js
function computeStats(cards, reviews) {
  const now = Date.now();
  const today = new Date().toISOString().split('T')[0];
  const todayReviews = reviews.filter(r => r.date === today);

  return {
    dueToday: cards.filter(c => c.nextReview <= now).length,
    retention: reviews.filter(r => r.quality >= 3).length / reviews.length || 0,
    reviewsToday: todayReviews.length,
    mastered: cards.filter(c => c.interval >= 21).length,
    avgEase: cards.reduce((s, c) => s + c.easeFactor, 0) / cards.length || 2.5,
  };
}
```

### Step 7: Import/Export Formats

| Format | Direction | Implementation |
|--------|-----------|---------------|
| JSON (full) | Both | `JSON.stringify(allData)` with schema version |
| CSV (basic) | Both | Front,Back,Deck,Tags per line |
| APKG (Anki) | Import | Parse `.apkg` zip with SQLite inside |

### Step 8: Present Results

```
## 📚 Flashcard Study System

### Features Implemented
- ✅ SM-2 spaced repetition algorithm
- ✅ [N] card types (basic, cloze, image, audio, reversed, type-in)
- ✅ [N] decks created
- ✅ Study session with self-assessment
- ✅ Statistics dashboard
- ✅ Import/export (JSON, CSV${apkg ? ', APKG' : ''})
- ✅ Dark mode
- ✅ Keyboard shortcuts (Space=reveal, 1-5=rate)

### Learning Statistics
- Total cards: [count]
- Due today: [count]
- Retention rate: [percent]%
- Study streak: [days] days

### Running
- Open `index.html` in browser
- Or: `python3 -m http.server 8000`

### Next Steps
1. [Suggested enhancement]
2. [Suggested enhancement]
```

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md`
- **Code cleanup**: `skills/code-cleanup/SKILL.md` — run after implementation
- **Code optimization**: `skills/code-optimization/SKILL.md` — profile bundle size, optimize rendering
- **Documentation**: `skills/technical-documentation/SKILL.md` — document the flashcard system

## Principles

- **Offline-first**: All data stored locally (no backend required)
- **Keyboard-first**: Study sessions should never require a mouse
- **Algorithm fidelity**: SM-2 implementation must match the original paper
- **Data portability**: User owns their data — always support export
- **Performance**: Render 1000+ cards without jank (virtual scrolling if needed)
