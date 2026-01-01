from celery import shared_task
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.trace.v1.trace_pb2 import TracesData

from traces.models import RawTrace


@shared_task
def process_trace(raw_trace_id):
    raw_trace = RawTrace.objects.get(id=raw_trace_id)

    # Parse the protobuf message
    traces_data = TracesData()
    traces_data.ParseFromString(raw_trace.payload_protobuf)

    # Convert protobuf message to dictionary (unmarshalling)
    traces_dict = MessageToDict(traces_data, preserving_proto_field_name=True)

    raw_trace.status = "processed"
    raw_trace.save()

    return traces_dict
