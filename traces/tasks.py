from celery import shared_task

from traces.models import RawTrace


@shared_task
def process_trace(raw_trace_id):
    raw_trace = RawTrace.objects.get(id=raw_trace_id)
    trace = raw_trace.process()
    return trace
