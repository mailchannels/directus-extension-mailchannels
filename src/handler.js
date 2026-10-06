const endpoint = 'https://api.mailchannels.net/tx/v1/send';

// Only the platform's scoped request function crosses the sandbox boundary.
export function createHandler(request) {
  return async function handler({ apiKey, payload, dryRun = true } = {}) {
    if (typeof apiKey !== 'string' || !apiKey.trim() || /[\r\n]/.test(apiKey) || apiKey.includes('{{')) {
      throw new Error('Configure MAILCHANNELS_API_KEY and FLOWS_ENV_ALLOW_LIST on the Directus server.');
    }
    // Flow expressions can produce a boolean or an interpolated string.
    if (![true, false, 'true', 'false'].includes(dryRun)) {
      throw new Error('Dry run must be true or false.');
    }
    const validate = dryRun === true || dryRun === 'true';
    let body = payload;
    if (typeof body === 'string') {
      try { body = JSON.parse(body); } catch { throw new Error('Email payload must be valid JSON.'); }
    }
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw new Error('Email payload must be a JSON object.');
    }
    // Preserve the full API payload, including personalization, attachments and
    // tracking options. The API performs schema and account/domain validation.
    let response;
    try {
      response = await request(endpoint + (validate ? '?dry-run=true' : ''), {
        method: 'POST',
        headers: { 'X-Api-Key': apiKey, 'Content-Type': 'application/json' },
        body,
      });
    } catch {
      // Platform errors may contain headers, payloads and response bodies.
      // Never attach the original exception or return its message to Flow logs.
      throw new Error('MailChannels request failed. Check account and delivery records before retrying; the outcome may be unknown.');
    }
    const expected = validate ? 200 : 202;
    if (response?.status !== expected) {
      throw new Error('MailChannels returned an unexpected response. Check account and delivery records before retrying.');
    }
    return { status: response.status, validated: validate, accepted: !validate };
  };
}
