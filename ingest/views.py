import json
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from .models import RawSpan
from .validators import validate_span


@csrf_exempt
def ingest_spans(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body)
        spans = payload.get("spans", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    accepted = 0
    rejected = 0

    for span in spans:
        try:
            validate_span(span)

            RawSpan.objects.create(
                trace_id=span["trace_id"],
                span_id=span["span_id"],
                parent_span_id=span.get("parent_span_id"),
                name=span["name"],
                kind=span["kind"],
                start_time=parse_datetime(span["start_time"]),
                end_time=parse_datetime(span.get("end_time"))
                if span.get("end_time")
                else None,
                attributes=span["attributes"],
            )
            accepted += 1

        except IntegrityError:
            # duplicate span → idempotent accept
            accepted += 1

        except Exception:
            rejected += 1

    return JsonResponse({"accepted": accepted, "rejected": rejected}, status=202)
