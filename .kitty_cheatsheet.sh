#!/usr/bin/env bash
# Kitty command cheatsheet — printed at terminal launch

cat <<'SHEET'

  ╔═══════════════════════════════════════════════════════════════════════════╗
  ║                         🐱  KITTY CHEAT SHEET                           ║
  ╚═══════════════════════════════════════════════════════════════════════════╝

  LAUNCH & STOP            STATUS & HEALTH          TUTOR (RAG learning)
    kitty        launch+browser  kitty status           kitty tutor learn <path>
    kitty up     start daemons   kitty doctor --json    kitty tutor ask "<q>"
    kitty down   stop all        kitty resume           kitty tutor review
    kitty logs   tail logs       kitty verify-home      kitty tutor rate <t> <1-3>
    kitty run-fg debug mode      kitty context --agent
                                                    BUILDER & PROJECTS
  DASHBOARD & ALIASES           TOOLS I INSTALLED       kitty builder <cmd>
    k       cd → kitty repo     brew    package mgr     kitty project list
    kg      git status          gh      GitHub CLI      kitty project refresh <id>
    ktest   pytest short        tmux    multiplexer     kitty sweep
    ai-fast chat default        lazygit git TUI
    ai-free chat fallback       yazi/y  file TUI       UTILITIES
    kanban  🗂️ view board       bat     cat w/ syntax   kitty install   launchd on boot
    standup print standup       eza     ls replacement  kitty push "msg"  iMessage
    refine🌟  mods→clipboard    fzf     fuzzy find      kitty backup    backup data
    review🌟  mods→stdout       zoxide  z foo→jump      make agent-wrap  session wrap
    litellm-start  start LM     btop    resource monitor
    kitty-hub  start hub        starship prompt theme  SHORTCUTS
    owui    open localhost:3000 aider    AI coding        ctrl+r   history search
    ghostty-reload  reload      ast-grep AST search      ctrl+t   fzf files
    kstatus quick status        node/npm JS runtime      pbpaste  clipboard
    kba --add  add kanban card  python3.12 Python        !! !$    repeat / last arg
                                rustc/cargo Rust         alias    list all aliases
  GIT                           ngrok/cloudflared        which X  find command path
    git push                       tunnel localhost      type X   alias or executable
    git log --oneline -5       emacs text editor
    git diff --stat            dotnet .NET              k  →  cd ~/Projects/kitty
    lg / lazygit   git TUI     ffmpeg media convert     .  →  current dir
    gh pr create / view        cloc   count lines       .. →  parent dir
                                                          cd -  →  last dir
  brew update -> update everything

SHEET
