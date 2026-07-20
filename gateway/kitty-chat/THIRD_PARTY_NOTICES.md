# Third-Party Notices

Kitty's frontend uses the following open-source libraries under permissive
licenses. No source code was copied from any prohibited repository.

## @assistant-ui/react

- **Version**: 0.14.27
- **License**: MIT
- **Source**: https://github.com/assistant-ui/assistant-ui
- **Usage**: External-store runtime adapter bridging Kitty's SSE chat to
  Assistant UI primitives. Currently used for the KittyRuntimeProvider
  foundation; chat thread rendering remains Kitty's own implementation.

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
