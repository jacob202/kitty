# Kitty Siri Shortcut Setup

## Prerequisites

- Tailscale running on Mac and iPhone
- Gateway running on Mac (`./kitty up`)
- iOS Shortcuts app

> Tailscale IP and the legacy `kitty_gateway/start_all.sh` launcher are
> retired. Use `./kitty status` to confirm the gateway is up, then use
> the Mac's Tailscale hostname or MagicDNS name (not a hardcoded IP) in
> the URL below.

## Build the Shortcut

Open Shortcuts app, create a new shortcut, and name it `Ask Kitty`.

Add these actions in order:

1. `Dictate Text`

- Prompt: `What do you want to ask Kitty?`
- Language: English

2. `Get Contents of URL`

- URL: `http://<mac-tailscale-hostname>:8000/ask`
- Method: `POST`
- Request Body: `JSON`
- JSON field: key `message`, value `Dictated Text`

3. `Get Dictionary Value`

- Dictionary: `Contents of URL`
- Key: `reply`

4. `Speak Text`

- Text: `Dictionary Value`

Replace `<mac-tailscale-hostname>` with the name shown by
`./kitty status` (e.g. `mac.local`, `kitty.tailnet-name.ts.net`).

## Add to Siri

- Open shortcut settings
- Tap `Add to Siri`
- Record phrase: `Ask Kitty`

## Test

Say: `Hey Siri, Ask Kitty`, then dictate a question and verify Kitty speaks the response.

## Troubleshooting

- No response: open `http://<mac-tailscale-hostname>:8000/health` from your phone
- Connection refused: run `./kitty up` and `./kitty doctor --json` on Mac
- Timeout: make sure the Mac is awake and reachable on Tailscale
