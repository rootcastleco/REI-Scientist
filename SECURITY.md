# Security and research integrity policy

## Trust boundaries

1. **Trusted code:** only reviewed in-package benchmark and algorithm functions execute.
2. **Untrusted input:** study JSON, prompt topic, external Crossref metadata, remote LLM replies.
3. **Credentials:** process environment only; never placed in study JSON, results or logs.
4. **Network:** no requests in the default offline path. `--llm-proposals`, `ideate`, or `--literature` are explicit operator actions. Network helper restricts to allowlisted HTTPS hosts, no redirects, response byte limits, and a fixed timeout. Application-level allowlisting is not a substitute for network isolation.
5. **Output:** local user-chosen folder; refuses to overwrite a pre-existing directory. SHA-256 detects accidental changes but is **not a cryptographic signature** against an attacker who can edit the manifest too.

## Threat model and controls

| Threat | Control | Residual risk |
|---|---|---|
| Model-generated RCE or package installation | LLM output is JSON validated against registered algorithm and parameter names; no subprocess or eval | Approved Python adapters require code review |
| Prompt injection from topic/model output | Topic treated as data; strict JSON schema; never executed | May generate misleading hypotheses or bad numeric proposals |
| Secret disclosure / unexpected spend | Opt-in network, environment keys, limited requests, payload/response ceilings | Third-party provider receives study metadata and can charge; use capped API keys |
| SSRF | Hardcoded approved external HTTPS hostnames, port 443, no redirects | DNS-level attacks not fully mitigated; enforce host egress policy outside app |
| CPU/memory denial of service | Hard bounds for algorithm count, search depth, dimensions, seeds, evaluation count | Local run has no OS resource limits unless launched in a constrained worker/container |
| Overfitting / result laundering | Locked development/test seed partition and one-time holdout, preregistered improvement gate | Benchmark choice bias and small holdout sample remain |
| Tampered evidence | Hashes, source fingerprints and deterministic experiment replay | Hashes are not signed / remote timestamped; host compromise can rewrite all files |
| Malicious bibliographic metadata | Metadata only; report states full text NOT VERIFIED | Text may be misleading; never treat it as instructions |
| Unsafe domain usage | No clinical decision-making; analytic synthetic benchmarks only | Domain extensions require specialist review |

## Deployment and rollback

Default to offline container execution as a non-root user with network disabled and narrow read/write mounts. Store API keys in a secret manager for any later remote mode. New external adapters must be feature-flagged, with a failure budget and rollback to the offline reference implementation. No current production integration or schema migration is required.

## Reporting security issues

Use a private Rootcastle security channel rather than disclosing credentials or an unpatched exploit in a public issue. This repository contains no automated vulnerability submission workflow.
