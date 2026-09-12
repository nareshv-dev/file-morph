# FileMorph Deployment

This source upgrade was not pushed or deployed and did not modify production infrastructure. The existing Vercel domain still represents its earlier deployed version.

## Required Configuration

1. Provision MongoDB and a private S3-compatible bucket through an approved infrastructure workflow.
2. Configure `ENVIRONMENT=production`, `MONGODB_URI`, database name, separate JWT access/refresh secrets (32+ random characters), explicit CORS origins, token lifetimes, file/page/retention/timeout limits.
3. Set `STORAGE_PROVIDER=s3`, bucket, endpoint if needed, region, and environment credentials or a scoped IAM role. Grant only required object operations. Do not put credentials in source.
4. Use an unversioned bucket or a verified all-version deletion policy. Configure a retention lifecycle and schedule `python -m backend.cleanup` at least every few minutes. A serverless lifespan task is not a durable scheduler.
5. Install backend requirements, run tests, run frontend tests/build, and repeat live-provider/user-isolation/deletion checks.

## Runtime Choice

The existing repository has Docker, Render, and Vercel Services configuration. Preserve those files until a deployment is explicitly requested. A container deployment is the safer initial target for bounded synchronous document processing.

Large/CPU-heavy jobs need a durable queue and external worker before serverless production use. The execution boundary already uses separate child processes with hard timeouts and bounded concurrency, but a Redis-backed durable worker is not implemented. Vercel request execution is rejected until that worker is integrated. Add container memory limits, distributed rate limiting, upload gateway body limits, and worker/job leases before multi-instance load.

## Release Checklist

- Backend tests, frontend tests, production build, and `git diff --check` pass.
- Every advertised source/target mode works on representative real files; inspect output content and visual fidelity, not just signatures.
- Live MongoDB records survive restart; indexes are present and each history query is account-scoped.
- Private storage denies public access; authenticated downloads work and cross-account IDs fail.
- Deleted and expired source/output objects are actually removed, including any historical storage versions.
- Refresh replay fails; cookies are Secure/HTTP-only/SameSite in TLS production; logout/password changes behave correctly.
- Browser console, responsive desktop/mobile layouts, keyboard navigation, screen-reader names, focus visibility, reduced motion, and 200% zoom are checked.
- Secret/dependency scans and operational security review are completed.
- A worker/scheduler/gateway architecture appropriate to actual load is approved.

Only then deploy through an explicitly authorized workflow, verify the complete live flow, and assign a domain. No deployment command is part of this document's local implementation steps.
