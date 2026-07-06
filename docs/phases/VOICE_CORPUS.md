# Voice Corpus Builder

Kitty learns your speaking style from your own words. Run this to build your voice corpus:

## Quick Start (run once)

```bash
# Build from iMessage messages (requires Full Disk Access)
python3 scripts/build_voice_corpus.py --out data/voice_corpus/jacob_voice.txt

# Or include Gmail Sent from Takeout
python3 scripts/build_voice_corpus.py --mbox ~/Downloads/Takeout/Mail/Sent.mbox \
    --out data/voice_corpus/jacob_voice.txt
```

## What it does

- Extracts your outbound messages from iMessage/Gmail
- Cleans and normalizes to plain text
- Output: `data/voice_corpus/jacob_voice.txt`

## Requirements

- iMessage: System Settings → Privacy & Security → Full Disk Access (for chat.db)
- Gmail: Export from https://takeout.google.com (Mail only)

## After building

Edit `src/core/aura_loader.py` to point to your corpus file:

```python
"voice_corpus_path": "data/voice_corpus/jacob_voice.txt"
```

Then Kitty can analyze your speech patterns (word choice, phrases, tone) for more personalized responses.

## ⚠️ Never commit

`data/voice_corpus/` is in `.gitignore` — contains personal data.
