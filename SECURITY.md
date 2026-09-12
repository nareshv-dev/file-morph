# FileMorph Security

## Implemented Controls

- bcrypt hashes, bounded password bytes, normalized email uniqueness, uniform login errors and dummy-hash timing work.
- Separate short-lived access/rotating refresh JWTs, fixed HS256 verification, hashed refresh sessions, atomic single-use consumption, logout revocation.
- HTTP-only authentication cookies, SameSite=Lax, Secure/HSTS in production, double-submit CSRF for authenticated mutations, no localStorage tokens.
- Account-owned job lookups/updates/downloads/history; cross-account IDs return 404.
- Explicit credentialed CORS, request IDs, no-store API responses, nosniff/frame/referrer headers.
- Extension/MIME/signature checks, valid DOCX package inspection, expansion/ratio ZIP-bomb limits, empty/size limits, protected PDF rejection, page/rendering/image dimensions, UTF-8 validation.
- Sanitized bounded filenames, random storage keys, resolved local-path containment, atomic local writes and temporary-file cleanup.
- HTML scripts/styles/embedded objects removed; external resources are not fetched or executed.
- Private authenticated downloads; no document bytes in MongoDB, no internal storage URLs in public job metadata.
- Configured retention, scheduled cleanup entry point, immediate deletion, password-change access invalidation and account cleanup.

## Deployment Requirements and Remaining Risks

Production startup requires MongoDB, private S3 storage, and strong environment secrets. Use TLS and explicit trusted origins. Use an unversioned bucket or independently delete every retained object version. Disable public bucket access. Set proxy/platform body limits, including chunked requests; the application also checks declared request length and per-file content.

Rate limits are per-process memory, not a distributed anti-abuse guarantee. Put a distributed limiter/WAF at the gateway for multi-instance deployment. Legacy anonymous conversion routes remain intentionally compatible and should be restricted if the product policy requires authentication for all conversions.

Synchronous converters run in separate child processes with hard timeouts, output-size limits, and two execution slots per API process. OS/container memory limits, durable queue delivery, job leases, and distributed concurrency controls remain necessary for large/hostile workloads. Vercel request execution is rejected until a process-capable worker is integrated. Retry/delete/retention concurrency requires worker-safe locking before asynchronous multi-instance processing.

Live MongoDB/S3 integration, browser console/mobile/keyboard QA, dependency security review, password reset/email verification, and a production penetration/security review are not represented as completed. No password-reset or email-verification feature is advertised.

Deleted jobs are hidden tombstones until account deletion; file objects are removed immediately. Do not log uploaded document contents or secrets. Restrict operational log access and audit filenames as potentially sensitive metadata.

## Reporting

Report vulnerabilities privately to the project owner. Include a minimal reproduction, affected endpoint, and request ID. Do not include document contents, passwords, cookies, or production secrets in public issues.
