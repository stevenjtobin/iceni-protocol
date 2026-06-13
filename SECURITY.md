# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report privately via GitHub instead:

1. Go to the [Security tab](https://github.com/stevenjtobin/iceni-protocol/security)
2. Click **"Report a vulnerability"**
3. Describe the issue, the affected version, and steps to reproduce

You'll get an acknowledgement within 72 hours. Once the issue is confirmed and a
fix is released, we'll credit you in the advisory (unless you'd prefer to remain
anonymous).

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅         |

## Security-relevant areas

ICENI cryptographically signs prompt aliases (Ed25519) and parses `.iceni` files
shared between machines. The areas most worth scrutiny:

- **Signature verification** (`src/iceni/trust/`) — forging or bypassing an alias signature
- **Import gates** (`iceni import`) — accepting a tampered or malicious `.iceni` file
- **MCP server** (`iceni mcp`) — anything exposed to Claude Desktop
- **Local-first by design** — ICENI makes no network calls unless you set an API key and pass `--execute`

## Out of scope

- The intentionally-vulnerable demo code in `examples/` — it exists so you can test the `security-audit` workflow
- Issues that require filesystem or OS access the attacker would already have on your machine
