# 010 — Initial operator API authentication

Date: 2026-09-18  
Status: Accepted under delegated authority to implement NEM-030.

## Context and decision

Operational controls are required before the optional Admin UI. Enable them explicitly in the
existing API using one securely generated, configured operator token and a configured actor ID.
Spring Security's opaque bearer-token support performs authentication locally. Compare token
hashes with constant-time digest comparison; derive audit identity from the verified principal.
Use no browser cookies, sessions, Basic authentication or remote introspection service.

All operator paths require the operator authority. Disabled controls are unavailable; public
health remains accessible. Request DTOs expose no actor field or claim token. Audit mutation
records remain in the same transactions as queue changes. New manual submissions use the same
queue as scheduled submissions. Retire direct CLI execution to prevent a normal bypass path.

## Alternatives and consequences

A full OIDC identity provider or browser session flow adds deployment/UI choices before the
Admin feature decision. Those remain options for multi-user administration. This initial token
is suitable for a single operator/tool; sharing it cannot identify individual humans. Generate
at least 32 random bytes, store it server-side, and rotate by replacing configuration and restarting.
Remote access requires HTTPS. A UI must not embed this token in a public frontend bundle.

The current job list is bounded recent history, while per-job events support an ID cursor.
Shared OpenAPI/client generation and public coverage/series resources remain NEM-014.

## References and verification

- [Spring Security opaque-token support](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/opaque-token.html)
- [Operator guide](../../../api/README.md)
- [HTTP and database evidence](../evidence/jobs/admin-findings.md)
