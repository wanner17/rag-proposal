# Agent Answer Quality Contract

This document records the current Agent answer-quality contract used by the roadmap in `.omx/plans/prd-next-ai-agent-roadmap-20260513.md`.

## Phase 1-2 Contract

Agent answer quality is metadata-first:

```text
metadata.answer_quality = {
  status,
  findings,
  coverage,
  evidence_sufficiency,
  revision_recommended,
  revision_triggered,
  revision_count
}
```

The current implementation may recommend revision but must not mutate the answer.

Required invariants:
- `revision_triggered` remains `false`.
- `revision_count` remains `0`.
- `status` must not be `revised`.
- `/api/agent/stream` may review the accumulated final answer only after token streaming completes.
- streamed content must not be retracted, replaced, or marked revised without an explicit replacement protocol.

## Coverage Metadata

Coverage entries describe requested items detected in the user query:

```text
{
  item,
  status,
  requested_aliases,
  answer_aliases,
  revision_recommended
}
```

Statuses:
- `covered`: the answer explicitly mentions a requested item alias.
- `missing`: the query requested the item, but the answer does not mention it.
- `unavailable`: the answer says the item was not found or not confirmed in the documents.

`revision_recommended` is true for `missing` entries only. It is a planning signal for a later revision phase, not permission to mutate the answer in the current stream contract.

## Evidence Attribution Metadata

`evidence_sufficiency` carries both retrieval critic output and a conservative claim-support review:

```text
evidence_sufficiency.claim_support = {
  reviewed_count,
  weak_count,
  weak_claims
}
```

The claim-support review splits the final answer into sentence-like claims and compares extracted terms with retrieved chunk text. Claims with no term overlap are reported as `evidence_attribution` findings. This is a lightweight quality signal, not a proof engine: it should flag suspicious unsupported claims without rewriting or suppressing the answer.

## Future Revision Protocol

One-pass answer revision can be introduced only after one of these semantics is implemented and tested:

1. Final-answer replacement:
   - stream tokens remain provisional,
   - backend emits a final answer replacement event,
   - frontend replaces the displayed answer once,
   - metadata records `revision_triggered=true` and `revision_count=1`.

2. Non-stream revision only:
   - `/api/agent/query` may return revised final text,
   - `/api/agent/stream` still reports recommendation metadata only,
   - UI labels the difference explicitly so Agent and Compare do not imply parity.

3. Pre-stream QA:
   - answer is generated and reviewed before any token is emitted,
   - streaming starts only after the final text is selected,
   - latency tradeoff is accepted explicitly.

Until one path is chosen, tested, and reflected in both query and stream contracts, revision remains recommendation-only.
