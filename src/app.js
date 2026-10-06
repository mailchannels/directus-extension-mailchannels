export default {
  id: 'mailchannels-send-email',
  name: 'MailChannels Email',
  icon: 'outgoing_mail',
  description: 'Send transactional email or validate a request without sending.',
  overview: ({ dryRun = true }) => [{ label: 'Mode', text: dryRun === false || dryRun === 'false' ? 'Send email' : 'Dry-run validation' }],
  options: [
    {
      field: 'apiKey', name: 'API key reference', type: 'string',
      schema: { default_value: '{{$env.MAILCHANNELS_API_KEY}}' },
      meta: {
        width: 'full', interface: 'input', required: true,
        note: 'Keep the environment reference. Set MAILCHANNELS_API_KEY and allow it with FLOWS_ENV_ALLOW_LIST on the server. Do not paste a key here.',
      },
    },
    {
      field: 'dryRun', name: 'Dry run (no email sent)', type: 'boolean',
      schema: { default_value: true },
      meta: { width: 'full', interface: 'boolean' },
    },
    {
      field: 'payload', name: 'Email API payload', type: 'json',
      meta: {
        width: 'full', interface: 'input-code', required: true,
        options: { language: 'json' },
        note: 'Use the MailChannels send request JSON, including from, personalizations, subject and content. Flow expressions are supported.',
      },
    },
  ],
};
