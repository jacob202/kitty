# Third-Party Notices

Kitty's frontend uses the following open-source libraries under permissive
licenses. No source code was copied from any prohibited repository.

## @assistant-ui/react

- **Version**: 0.14.28
- **License**: MIT
- **Source**: https://github.com/assistant-ui/assistant-ui
- **Usage**: `KittyRuntimeProvider` wraps `AssistantRuntimeProvider` via an
  `ExternalStoreAdapter<Message>` so Kitty owns message state and the adapter
  bridges to assistant-ui's runtime contract. `KittyThread` uses
  `ThreadPrimitive.Root`, `ThreadPrimitive.Viewport`,
  `ThreadPrimitive.Messages`, `ThreadPrimitive.Empty`, and
  `ThreadPrimitive.ScrollToBottom` — assistant-ui owns the viewport/scroll
  and smooth-completion-animation primitives; Kitty owns the message rendering.

## react-photo-album

- **License**: MIT
- **Source**: https://github.com/igordanchenko/react-photo-album
- **Usage**: Image Lab gallery layout (responsive row-based photo grid).

## yet-another-react-lightbox

- **License**: MIT
- **Source**: https://github.com/igordanchenko/yet-another-react-lightbox
- **Usage**: Full-screen image viewer overlay for Image Lab gallery.

## cmdk

- **Version**: 1.1.1
- **License**: MIT
- **Source**: https://github.com/pacocoursey/cmdk
- **Usage**: Model selector searchable command menu and global command palette.

## Pre-existing dependencies (not added in this wave)

- **react** / **react-dom** (MIT) — UI framework
- **next** (MIT) — application framework
- **@tanstack/react-query** (MIT) — data fetching
- **lucide-react** (ISC) — icon set
- **react-markdown** (MIT) — markdown rendering
- **remark-gfm** (MIT) — GFM table/task-list support
- **rehype-highlight** (MIT) — code syntax highlighting
- **highlight.js** (BSD-3-Clause) — syntax grammar engine
