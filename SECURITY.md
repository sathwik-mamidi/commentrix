# Security policy

## Project status

Commentrix is a sunset product published as an archival snapshot. The hosted
archive does not run the Python MVP, and the repository does not have maintained
release lines or guaranteed security updates.

## Reporting a vulnerability

Please report vulnerabilities that affect the published source or archive site
through GitHub's [private vulnerability reporting](https://github.com/sathwik-mamidi/commentrix/security/advisories/new)
instead of a public issue. Use synthetic video and credentials.

## Security boundaries

The local MVP processes untrusted media with several native and third-party
tools. Run it in an isolated environment, keep FFmpeg and dependencies patched,
apply file-size and resource limits, and never commit Gemini or ElevenLabs keys.
