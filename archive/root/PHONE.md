# Kitty — Phone Access

## Tailscale IPs
- Mac: `100.84.78.1`
- iPhone: `100.109.135.66`

## Open WebUI (chat in Safari)
http://100.84.78.1:3000

## Kitty Gateway (API)
http://100.84.78.1:8000/health

## Start everything on Mac
```bash
cd ~/Projects/kitty
bash kitty_gateway/start_all.sh
```

## SSH from Terminus
Host: `100.84.78.1`
User: `jacobbrizinski`
Port: `22`

## Quick checks from Terminus
```bash
curl http://localhost:8000/health      # gateway alive?
curl http://localhost:3000             # webui alive?
bash kitty_gateway/status_all.sh      # full status
```
