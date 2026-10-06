# MailChannels Email for Directus Flows

Unreleased extension candidate for Directus 12.4.1. **Not published to npm or the Directus
Marketplace; no live MailChannels API test has been performed.**

Send transactional email or validate a request without sending it. The operation
accepts the complete [MailChannels send payload](https://docs.mailchannels.com/email-api/overview),
including personalizations, attachments, reply-to, custom headers and tracking
settings. It does not replace Directus' built-in system email transport.

## Setup

A MailChannels account, API key and authorized sending domain are required.
Use an allowed sender and recipient for initial validation.

1. Install the built package into your self-hosted Directus extensions directory
   and restart Directus. After publication, search for **MailChannels** in the
   Directus Marketplace. Marketplace installation is not available yet.
2. Set `MAILCHANNELS_API_KEY` in your server's secret/environment configuration.
   Add `MAILCHANNELS_API_KEY` to `FLOWS_ENV_ALLOW_LIST`, preserving any existing
   entries. Restart Directus. Enterprise Cloud environment settings require
   Directus Customer Success; this is not a client-side credential.
3. Add **MailChannels Email** to a Flow triggered by authorized events or users.
   Authenticate and validate incoming webhook triggers before this operation;
   do not expose an unrestricted send-email webhook. Keep the API key reference as
   `{{$env.MAILCHANNELS_API_KEY}}`. Never replace it with the literal key.
4. Leave **Dry run** enabled and provide the email payload, for example:

   ```json
   {
     "from": {"email": "sender@your-verified-domain.example"},
     "personalizations": [{"to": [{"email": "allowed-recipient@example.com"}]}],
     "subject": "Directus validation",
     "content": [{"type": "text/plain", "value": "Hello from Directus"}]
   }
   ```

   Replace both addresses with authorized values. Directus Flow expressions may
   populate payload fields. The API validates the resulting request.
5. Trigger the Flow and confirm `{"status":200,"validated":true,"accepted":false}`.
   This mode sends no email. Disable Dry run only when actual sending is intended.
   A send returns `{"status":202,"validated":false,"accepted":true}` on acceptance;
   acceptance does not establish inbox delivery.

## Credentials, logs and failures

The sandbox scope allows initial POST requests only to the fixed MailChannels
send URL and its dry-run variant. The extension never returns the key, payload or API response
body, and sanitizes errors without retaining the original exception. It does not
retry failed requests. An ambiguous failure may follow acceptance: inspect
MailChannels delivery records before manually retrying a send.

Directus resolves the environment reference before invoking this sandboxed
operation. Directus 12.4.1 redacts allowed environment values from stored Flow
revisions. The operation cannot access the host environment directly. Restrict
Flow creation/editing to trusted administrators: Flow authors can use allowed
environment variables in other operations. Avoid returning `$all` from webhooks;
return this operation's result. Flow revisions can still contain email content
and recipient addresses, so choose Flow logging settings accordingly.

The platform's `directus:api` request function controls HTTP redirects and
network timeouts; it exposes no per-operation settings for either. The extension
does not claim to enforce a timeout or prevent redirect following. Review this
host behavior before production deployment. This package does not bundle or
patch the Directus server's HTTP client.

## Development and release

```sh
npm ci
npm test
npm run build
npm run validate
python test/docker-smoke.py
```

The Docker smoke test requires Linux Docker networking, Python 3 and OpenSSL.
It starts Directus 12.4.1 and a local HTTPS fixture on an internal Docker network,
trusts a temporary test certificate, and uses generated fixture credentials.
It does not reach MailChannels or send email. Test-only private-IP access is
confined to this isolated network. Containers and network are removed afterward.

The build SDK's `@directus/composables` dependency pins an affected Axios version.
A scoped development override selects Axios 1.20.0; `npm audit` reports zero
vulnerabilities for this package at preparation time. The API bundle imports the
host `directus:api` function, so this build-time override does not alter the host.

Before release: review the Data Studio form in a real project, perform an
explicitly authorized live dry-run, confirm the npm name,
and publish through a MailChannels npm maintainer.
Public [source and issues](https://github.com/mailchannels/directus-extension-mailchannels)
are available for review.
The package contains required Marketplace metadata and built app/API entrypoints.
Directus mirrors qualifying npm packages every few hours; verify actual search
and install after publication instead of treating npm publication as completion.

## Support

Support owner: [dev@mailchannels.com](mailto:dev@mailchannels.com).

## References

- [Operation extensions](https://directus.com/docs/guides/extensions/api-extensions/operations)
- [Sandbox scopes](https://directus.com/docs/guides/extensions/api-extensions/sandbox)
- [Flow environment configuration](https://directus.com/docs/configuration/flows)
- [Marketplace publication](https://directus.com/docs/guides/extensions/marketplace/publishing)

## Disposable Data Studio review

After building the extension, run `python test/docker-smoke.py --studio-port 18055`.
The usual six sandbox checks run first. The script then leaves the local fixture alive,
restores dry-run mode, and prints its Flow URL. Open that URL in a browser on the same
machine. The synthetic login is `fixture@example.com` with password
`Local-fixture-only-password-2026`. These credentials belong only to this disposable
fixture; do not reuse them in a real project. The MailChannels key is independently
random and belongs only to the mock HTTPS service, not a real account.

The listener binds127.0.0.1 only. It tunnels TCP over `docker exec` so Directus and its
HTTPS fixture stay on an internal Docker network with no internet egress. No extra
bridge network or public port is opened. Studio mode is for a trusted local reviewer,
not a shared hosting environment. Ctrl-C the script to stop the listener, remove its
containers/network and discard the temporary credentials/database. Normal smoke-test
mode still exits and cleans up automatically.

Inspect the operation's API-key environment reference, dry-run default, JSON editor,
dynamic Flow expressions, and success/rejection branches. This mode makes that review
reproducible; serving the page alone is not proof of correct rendering or interaction.
No live MailChannels traffic or npm publication is part of this fixture.
