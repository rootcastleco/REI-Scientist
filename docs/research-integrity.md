# Research integrity and publication gate

A REI Scientist PASS is a **local, falsifiable engineering experiment gate**. It is not acceptance into a conference, proof that a newly proposed method is original, or authority to make industrial/medical decisions.

Every result must preserve:

1. An explicit study hypothesis, limits, baseline and verification rule before running.
2. Development and holdout seed separation; holdout data not fed back into search.
3. Original objective/benchmark definition and independent recomputation.
4. Complete results including failed or unpromising candidate nodes.
5. Source hashes, run environment, evaluation counts and deterministic traces.
6. Distinction between bibliographic **metadata**, read full-text papers and verified factual claims.
7. Model assistance disclosure if ideation, proposals or writing used remote LLMs.
8. Human editorial review, independent experimental replication and journal policy checks before dissemination.

Do not claim literature novelty without a documented search protocol, full-text evidence and careful prior-work comparison. The current Crossref adapter returns only metadata and therefore **cannot** establish novelty.

For machinery-health or telematics workloads, specify sensor calibration, timestamps, sampling rates, uncertainty, ground truth and safety boundaries before a plugin is admitted to the registry. For medical workloads, require domain-specific governance and human oversight; v0.1 is not a medical system.
