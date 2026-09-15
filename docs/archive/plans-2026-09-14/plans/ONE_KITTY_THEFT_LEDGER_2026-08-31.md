# ONE KITTY — Theft Ledger

The rule: steal proven interaction behavior, not another product's architecture or visual identity.

## 1. Raycast — actions belong to the selected object

### Proven behavior
Raycast gives essentially every selected item an Action Panel. The first action is the primary action, additional actions are grouped semantically, actions can be searched, and shortcuts are shown so mouse discovery teaches keyboard speed over time.

Raycast AI Extensions apply the same idea to Chat: extensions expose tools, the user can `@`-mention an extension, the AI chooses the relevant tool, and tool calls can require approval.

### Why it works
The product does not force users to memorize where functionality lives. Selection establishes context; the available actions follow the object.

### Kitty equivalent
Kitty already owns:
- ActionQueue and approval/execution truth;
- Projects;
- Artifacts;
- Work/Builder;
- Automations;
- Deadlines;
- Image jobs/results;
- durable context references in the WOW stack.

### Steal specifically
- every canonical Kitty object can declare a primary action and contextual secondary actions;
- `Enter`/tap invokes the obvious primary action where safe;
- a discoverable action menu exposes the rest;
- actions are grouped by user purpose, not backend route;
- keyboard shortcuts can be taught through the visible menus;
- Chat can operate against the same object/action definitions rather than inventing prose instructions;
- consequential Chat tool use keeps explicit approval boundaries.

### Do not steal
- Raycast's extension registry;
- a new tool/plugin model;
- global command semantics where Kitty already has domain-specific authorities;
- extension-owned state.

### ONE KITTY destination
Wave 1 Action Grammar, Wave 2 Chat Concierge, later contextual menus in the Precision/Sophistication pass.

---

## 2. Linear — contextual actions and invisible precision

### Proven behavior
Linear's command menu prioritizes commands based on the current view/focus. Contextual menus expose actions applicable to a selected issue, and Linear explicitly treats tiny interaction details — such as pointer-safe submenu movement — as worth engineering because repeated friction accumulates.

Linear's Inbox is also action-oriented: notifications are not merely read; the user can update the underlying issue, snooze, mark read/unread, and use shortcuts directly from the attention surface.

### Why it works
The interface feels fast because actions live where the user's attention already is. Precision is not ornamental; it reduces interaction cost.

### Kitty equivalent
- Home/Attention has approvals, deadlines, running work, project next steps, repairs/signals, and intelligence.
- Work/Builder already has durable underlying state.
- Existing design-system guidance already prefers calm hierarchy and truthful states.

### Steal specifically
- contextual menus should act on the underlying object, not only the notification/card wrapper;
- Home attention items should expose the underlying object's meaningful action;
- current surface/selection affects action ranking;
- visible shortcut hints progressively teach faster operation;
- engineer micro-interactions when they remove repeated friction: menu placement, focus restore, stable geometry, click targets, keyboard continuity;
- attention items can be snoozed/deferred only when Kitty has a truthful model for doing so.

### Do not steal
- issue-tracker information architecture;
- dense enterprise tables everywhere;
- dark visual styling as identity;
- arbitrary hotkey proliferation before actions are coherent.

### ONE KITTY destination
Wave 3 Home Action Board, Wave 5 Precision System, Wave 7 Everything Responds.

---

## 3. Anthropic / Claude — brand character as punctuation

### Proven behavior
Anthropic's public visual identity uses simple editorial illustrations and recognizable organic/hand-drawn visual motifs around Claude rather than turning the main interface into a mascot theme. Claude Design also emphasizes applying a design system consistently so outputs feel on-brand rather than individually decorated.

### Why it works
The character is memorable because it is selective. The core product stays calm; expressive visuals appear at moments that can carry personality.

### Kitty equivalent
Kitty already has a `KidCatDoodle`/cat asset idea and an explicit design rule that mascot personality should be sparse and functional.

### Steal specifically
- define a canonical illustration language rather than one-off doodles;
- create a small state family: hello, thinking, working, waiting, found something, success, empty, offline/sleeping, creative, Builder;
- use illustration in high-salience emotional/state moments;
- keep working surfaces mostly typographic and structural;
- use the same spacing/type/color system around illustrations so brand and UI feel related.

### Do not steal
- Claude's character, logo, palette, exact line style, compositions, or copy voice;
- mascot beside every card;
- animation for decoration;
- replacing status copy with ambiguous character poses.

### ONE KITTY destination
Wave 6 Kitty Brand Character after Wave 5 Precision System.

---

## 4. Raycast AI — Chat as an action-capable connective layer

### Proven behavior
Raycast AI Chat can pull live context and take actions through existing extensions/tools without forcing each tool to become a new Chat-specific application. Explicit mentions can scope the assistant, multiple sources can be combined in one request, and approvals can remain enabled.

### Why it works
Chat becomes connective tissue over real capabilities instead of a silo. The tool remains the authority; Chat chooses and coordinates it.

### Kitty equivalent
Kitty already has domain authorities and the WOW stack adds Project/Artifact/Conversation context references, action cards, capability discovery, and activity projection.

### Steal specifically
- Chat gets a bounded catalog/projection of available Kitty context and actions;
- explicit user references outrank inferred relevance;
- active Project/context influences ranking;
- Chat may combine multiple domains in one answer/action plan;
- tool/action execution stays visible and approval-aware;
- Chat references canonical objects that the user can open elsewhere.

### Do not steal
- exposing every backend endpoint to the model;
- automatic global context dumping;
- granting Chat direct store writes;
- separate Chat-only tool definitions for capabilities already registered elsewhere.

### ONE KITTY destination
Wave 2 Chat Concierge.

---

## 5. Linear Inbox — attention should terminate in action

### Proven behavior
Linear's Inbox surfaces work that needs attention and allows the user to manipulate the underlying issue from the same context. It supports explicit clearing/snoozing/read state and fast keyboard traversal.

### Why it works
Attention is treated as a workflow, not a feed.

### Kitty equivalent
Home currently composes many sources: Actions, Needs Jacob, deadlines, projects, repairs, signals, Builder glance, insights, state changes, and more. The risk is section accumulation instead of prioritization.

### Steal specifically
- `Needs you` is a first-class queue, not one card among many;
- each item owns a next action;
- resolving the underlying object updates/removes the attention item automatically;
- allow deferral only where there is an authoritative schedule/reminder model;
- fast next/previous traversal can come later if the queue becomes dense;
- passive context belongs below the fold or behind disclosure.

### Do not steal
- notification count as engagement mechanic;
- separate read/unread state where the underlying object already provides completion/resolution truth;
- storing duplicate attention objects just to drive Home.

### ONE KITTY destination
Wave 3 Home Action Board.

---

## 6. Linear's product lesson — sophistication hides in repeated small costs

### Proven behavior
Linear publicly documents spending engineering effort on details users may never consciously notice, because fractions of seconds and small pointer errors compound across hundreds of interactions.

### Why it works
“Polished” is not a visual adjective. It is the accumulated absence of friction.

### Kitty equivalent
Kitty has already passed earlier token/coherence audits while still retaining bespoke inline styles and uneven component composition. Token compliance alone is insufficient.

### Steal specifically
Audit and fix:
- baseline alignment;
- row height consistency;
- text hierarchy;
- icon optical alignment;
- predictable primary action placement;
- stable loading geometry;
- focus restore;
- menus/sheets anchored where invoked;
- keyboard continuity;
- deliberate truncation/wrapping;
- touch target consistency;
- zero accidental horizontal scroll;
- no layout jump when state changes.

### Do not steal
- complexity for invisible-details bragging rights;
- bespoke interaction physics before ordinary alignment is correct.

### ONE KITTY destination
Wave 5 Precision System and Wave 8 Ruthless Product Pass.

---

# Synthesis

The references point to one architecture/product rule:

**Object -> context -> available action -> truthful lifecycle -> canonical result.**

Home, Chat, Work, Projects, Library, Automations, and Image Lab should be different lenses over that chain, not separate mini-products.

Raycast contributes the object/action grammar.
Linear contributes contextuality, attention workflow, and micro-precision.
Anthropic contributes restrained brand character and coherence through a design system.
Kitty contributes the actual authorities, durable state, personal intelligence, project context, and cross-domain assistant.

That combination should feel recognizably Kitty rather than like any one reference product.
