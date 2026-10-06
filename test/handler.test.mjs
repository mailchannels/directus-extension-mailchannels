import test from 'node:test';
import assert from 'node:assert/strict';
import { createHandler } from '../src/handler.js';
import app from '../src/app.js';

const apiKey = 'fixture-key-never-a-real-credential';
const payload = {
  from: { email: 'sender@example.com' }, subject: 'Fixture only',
  personalizations: [{ to: [{ email: 'recipient@example.com' }], cc: [{ email: 'cc@example.com' }], bcc: [{ email: 'bcc@example.com' }] }],
  content: [{ type: 'text/plain', value: 'Hello' }, { type: 'text/html', value: '<p>Hello</p>' }],
  attachments: [{ filename: 'hello.txt', type: 'text/plain', content: 'SGVsbG8=' }],
  reply_to: { email: 'reply@example.com' }, headers: { 'X-Custom': 'test' },
  tracking_settings: { open_tracking: { enable: false } },
};

test('default dry-run preserves full payload and returns only status fields', async () => {
  const handler = createHandler(async (url, options) => {
    assert.equal(url, 'https://api.mailchannels.net/tx/v1/send?dry-run=true');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['X-Api-Key'], apiKey);
    assert.deepEqual(options.body, payload);
    return { status: 200, data: { secret: apiKey } };
  });
  assert.deepEqual(await handler({ apiKey, payload: JSON.stringify(payload) }), { status: 200, validated: true, accepted: false });
});

test('explicit send supports boolean and interpolated string false', async () => {
  for (const dryRun of [false, 'false']) {
    const handler = createHandler(async (url, options) => {
      assert.equal(url, 'https://api.mailchannels.net/tx/v1/send');
      assert.deepEqual(options.body, payload);
      return { status: 202 };
    });
    assert.deepEqual(await handler({ apiKey, payload, dryRun }), { status: 202, validated: false, accepted: true });
  }
});

test('true string uses dry-run and unexpected responses reject', async () => {
  const handler = createHandler(async url => { assert.match(url, /dry-run=true$/); return { status: 202, data: apiKey }; });
  await assert.rejects(handler({ apiKey, payload, dryRun: 'true' }), error => !String(error).includes(apiKey));
});

test('missing or unresolved key and invalid inputs never make network requests', async () => {
  const handler = createHandler(() => { assert.fail('network must not be called'); });
  for (const key of [undefined, '', ' ', '{{ $env.MAILCHANNELS_API_KEY }}', 'bad\nkey']) await assert.rejects(handler({ apiKey: key, payload }));
  for (const body of [null, [], 1, '{broken']) await assert.rejects(handler({ apiKey, payload: body }));
  for (const dryRun of [null, 'FALSE', 0, {}, '']) await assert.rejects(handler({ apiKey, payload, dryRun }));
});

test('network errors never leak original messages, causes or response data and do not retry', async () => {
  let calls = 0;
  const handler = createHandler(async () => { calls++; throw new Error(`header=${apiKey}`, { cause: { body: payload } }); });
  await assert.rejects(handler({ apiKey, payload, dryRun: false }), error => {
    assert.equal(error.cause, undefined);
    assert.ok(!String(error).includes(apiKey));
    assert.match(error.message, /outcome may be unknown/);
    return true;
  });
  assert.equal(calls, 1);
});

test('UI defaults to environment reference and dry-run; overview reveals no email content', () => {
  assert.equal(app.options.find(x => x.field === 'apiKey').schema.default_value, '{{$env.MAILCHANNELS_API_KEY}}');
  assert.equal(app.options.find(x => x.field === 'dryRun').schema.default_value, true);
  assert.ok(!JSON.stringify(app.overview({ apiKey, payload })).includes(apiKey));
});
