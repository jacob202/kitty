# Kitty Siri Shortcut Setup

## Prerequisites
- Tailscale running on Mac (Kitty at `100.84.78.1`)
- Gateway running on Mac (`bash kitty_gateway/start_all.sh`)
- iOS Shortcuts app

## Build the Shortcut

Open Shortcuts app, create a new shortcut, and name it `Ask Kitty`.

Add these actions in order:

1. `Dictate Text`
- Prompt: `What do you want to ask Kitty?`
- Language: English

2. `Get Contents of URL`
- URL: `http://100.84.78.1:8000/ask`
- Method: `POST`
- Request Body: `JSON`
- JSON field: key `message`, value `Dictated Text`

3. `Get Dictionary Value`
- Dictionary: `Contents of URL`
- Key: `reply`

4. `Speak Text`
- Text: `Dictionary Value`

## Add to Siri
- Open shortcut settings
- Tap `Add to Siri`
- Record phrase: `Ask Kitty`

## Test
Say: `Hey Siri, Ask Kitty`, then dictate a question and verify Kitty speaks the response.

## Troubleshooting
- No response: open `http://100.84.78.1:8000/health` from your phone
- Connection refused: run `bash kitty_gateway/start_all.sh` on Mac
- Timeout: make sure the Mac is awake and reachable on Tailscale
