from celery import shared_task

from traces.models import RawTrace


@shared_task
def process_trace(raw_trace_id):
    raw_trace = RawTrace.objects.get(id=raw_trace_id)
    traces_dict = raw_trace.convert_to_dict()

    raw_trace.status = "processed"
    raw_trace.save()

    return traces_dict
