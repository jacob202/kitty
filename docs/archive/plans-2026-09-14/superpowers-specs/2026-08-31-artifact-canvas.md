# Artifact Canvas Design

## Goal
Turn Kitty artifacts into openable, reusable product objects instead of metadata rows or disposable chat output.

## First slice
- Library rows gain an Open action for safe previewable ready artifacts.
- Desktop opens a right-side Artifact Canvas; mobile opens the same canvas fullscreen.
- Images render visually, Markdown renders as Markdown, plain text renders readably, and PDFs render inline.
- Existing image "Use in chat" remains available from both the row and the canvas.
- Unsupported active content such as HTML/SVG is not rendered in this slice.

## Authority and safety
ArtifactStore remains canonical. The browser asks for bytes by artifact id only; it never receives or supplies an arbitrary local path. The Gateway resolves the registered storage URI server-side and serves only ready artifacts whose media type is on a preview allowlist. Missing files and unsupported types fail explicitly.

## Acceptance
1. GET `/artifacts/{id}/content` serves registered ready text/image/PDF bytes with the stored media type.
2. Missing files, non-ready artifacts, and unsupported active media fail closed.
3. Library can open a Markdown artifact and render its content in a canvas.
4. Image and PDF artifacts have direct inline previews through the same artifact-id content route.
5. Closing the canvas returns to the Library without changing durable state.
