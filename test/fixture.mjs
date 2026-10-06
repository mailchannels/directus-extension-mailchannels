import https from 'node:https';
import fs from 'node:fs';
const calls = [];
https.createServer({ key: fs.readFileSync('/certs/key.pem'), cert: fs.readFileSync('/certs/cert.pem') }, async (req, res) => {
  if (req.url === '/stats') { res.end(JSON.stringify(calls)); return; }
  let raw = '';
  for await (const chunk of req) raw += chunk;
  const payload = JSON.parse(raw);
  const authorized = req.headers['x-api-key'] === process.env.FIXTURE_KEY;
  calls.push({ url: req.url, authorized, payload });
  if (!authorized || payload.subject === 'Reject fixture') {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    // Intentional sentinel echo tests extension error sanitization.
    res.end(JSON.stringify({ error: process.env.FIXTURE_KEY }));
    return;
  }
  res.writeHead(req.url.endsWith('?dry-run=true') ? 200 : 202, { 'Content-Type': 'application/json' });
  res.end('{}');
}).listen(443, '0.0.0.0');
