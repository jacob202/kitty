# Tailscale Access — Open WebUI from Phone

Tailscale creates a private WireGuard mesh between your Mac and iPhone so you can
reach Open WebUI on port 3000 without exposing it to the public internet.

## 1. Install Tailscale on Mac

Download from tailscale.com/download (GUI installer) or:

```bash
brew install tailscale
sudo tailscaled &
tailscale up
```

Sign in when prompted. The Mac will appear in your Tailscale network.

## 2. Install Tailscale on iPhone

Install the Tailscale app from the App Store. Sign in with the same account used
on your Mac.

## 3. Find your Mac's Tailscale IP

```bash
tailscale ip -4
```

Example output: `100.64.0.12`

You can also open the Tailscale menu bar icon on your Mac and look for your device
name — the IP is listed there.

## 4. Access Open WebUI from your phone

With Tailscale active on both devices, open Safari on your iPhone and navigate to:

```
http://<your-tailscale-ip>:3000
```

Example: `http://100.64.0.12:3000`

Open WebUI must be running on your Mac. Start it with:

```bash
bash kitty_gateway/start_openwebui.sh
```

or via autolaunch.sh for all services at once.

## 5. Verify connectivity (cellular-only test)

Turn off Wi-Fi on your iPhone (cellular only) and navigate to
`http://<tailscale-ip>:3000`. The Kitty login screen should appear.
This confirms traffic is routed through Tailscale, not local Wi-Fi.

## Troubleshooting

- Run `tailscale status` on the Mac — your iPhone should appear as a peer.
- Open WebUI's start script binds to `0.0.0.0` by default. If it only binds
  to `127.0.0.1`, edit `kitty_gateway/start_openwebui.sh` and add `--host 0.0.0.0`.
- Both devices must have Tailscale active simultaneously.
- If the iPhone shows "Key Expiry," re-authenticate in the Tailscale app.

## Nightly Backup

The launchd agent (`kitty_gateway/com.kitty.backup.plist`) runs `scripts/backup.py`
at 2am every night. It backs up `data/` to:

1. Local external drive at `$BACKUP_LOCAL_PATH` (default: `/Volumes/KittyBackup`)
2. Backblaze B2 at `b2:$BACKUP_B2_BUCKET`

### Load the launchd agent (one-time)

```bash
cp kitty_gateway/com.kitty.backup.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kitty.backup.plist
```

### Test it manually

```bash
launchctl start com.kitty.backup
tail -f logs/backup.log
```

### Initialize restic repositories (one-time, before first backup)

```bash
# Local drive
restic -r /Volumes/KittyBackup/restic-repo init

# Backblaze B2 (set env vars from .env first)
export RESTIC_PASSWORD="$(grep RESTIC_PASSWORD .env | cut -d= -f2)"
export B2_ACCOUNT_ID="$(grep B2_ACCOUNT_ID .env | cut -d= -f2)"
export B2_ACCOUNT_KEY="$(grep B2_ACCOUNT_KEY .env | cut -d= -f2)"
restic -r b2:kitty-backup init
```

### Simulate restore (verify backups work)

```bash
restic -r /Volumes/KittyBackup/restic-repo snapshots
restic -r /Volumes/KittyBackup/restic-repo restore latest --target /tmp/kitty-restore-test
ls /tmp/kitty-restore-test/data/
rm -rf /tmp/kitty-restore-test
```

### Required `.env` entries for backup

```
RESTIC_PASSWORD=<strong-passphrase>
B2_ACCOUNT_ID=<from Backblaze>
B2_ACCOUNT_KEY=<from Backblaze>
BACKUP_B2_BUCKET=kitty-backup
BACKUP_LOCAL_PATH=/Volumes/KittyBackup
```
