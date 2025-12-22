from ingest.models import RawSpan
from telemetry.models import Trace, Observation, Generation


def project_unprocessed_spans(limit=1000):
    spans = RawSpan.objects.filter(projected=False).order_by("ingested_at")[:limit]

    for raw in spans:
        project_raw_span(raw)

        raw.projected = True
        raw.save(update_fields=["projected"])


def project_raw_span(raw: RawSpan):
    # 1. Ensure Trace exists
    trace, _ = Trace.objects.get_or_create(trace_id=raw.trace_id)

    # 2. Create Observation (1:1 with RawSpan)
    observation, _ = Observation.objects.get_or_create(
        span_id=raw.span_id,
        defaults={
            "span_id": raw.span_id,
            "trace": trace,
            "parent_span_id": raw.parent_span_id,
            "name": raw.name,
            "kind": raw.kind,
            "start_time": raw.start_time,
            "end_time": raw.end_time,
            "attributes": raw.attributes,
        },
    )

    # 3. If this span represents an LLM call, create Generation
    if is_llm_span(raw):
        project_generation(observation, raw)


def is_llm_span(raw: RawSpan) -> bool:
    attrs = raw.attributes or {}
    return "gen_ai.provider.name" in attrs and "gen_ai.request.model" in attrs


def project_generation(observation: Observation, raw: RawSpan):
    attrs = raw.attributes or {}

    Generation.objects.get_or_create(
        observation=observation,
        defaults={
            "provider": attrs.get("gen_ai.provider.name"),
            "model": attrs.get("gen_ai.request.model"),
            "input": attrs.get("gen_ai.input.messages"),
            "output": attrs.get("gen_ai.output.messages"),
            "prompt_tokens": attrs.get("gen_ai.usage.input_tokens"),
            "completion_tokens": attrs.get("gen_ai.usage.output_tokens"),
        },
    )
