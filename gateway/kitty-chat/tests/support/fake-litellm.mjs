import http from 'node:http'

const port = Number.parseInt(process.env.KITTY_FAKE_LITELLM_PORT ?? '48101', 10)
const reply = 'Hermetic Kitty reply persisted through the real Gateway.'

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && (req.url === '/health' || req.url === '/health/readiness')) {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ ok: true }))
    return
  }
  if (req.method === 'GET' && req.url === '/v1/models') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ data: [{ id: 'hermetic-model', object: 'model' }] }))
    return
  }
  if (req.method === 'POST' && req.url === '/v1/chat/completions') {
    req.resume()
    req.on('end', () => {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      })
      const chunk = {
        id: 'chatcmpl-hermetic',
        object: 'chat.completion.chunk',
        model: 'hermetic-model',
        choices: [{ index: 0, delta: { role: 'assistant', content: reply }, finish_reason: null }],
      }
      res.write(`data: ${JSON.stringify(chunk)}\n\n`)
      res.end('data: [DONE]\n\n')
    })
    return
  }
  res.writeHead(404, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ error: 'not found' }))
})

server.listen(port, '127.0.0.1')
