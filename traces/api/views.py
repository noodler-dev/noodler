from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from projects.auth import APIKeyAuthentication
from traces.models import RawTrace


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def ingest_trace(request):
    try:
        if request.content_type == "application/x-protobuf":
            body_bytes = request.body
        else:
            return Response({"error": "Unsupported content type"}, status=400)

        _ = RawTrace.objects.create(
            project=request.auth.project,
            received_at=timezone.now(),
            payload_protobuf=body_bytes,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=400)

    return Response({})
