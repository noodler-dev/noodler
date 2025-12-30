from datetime import datetime
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from projects.auth import APIKeyAuthentication
from traces.models import RawTrace

@api_view(['GET'])
def hello_world(request):
    return Response({"message": "hello world"})


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def ingest_trace(request):
    try:
        _ = RawTrace.objects.create(
            project=request.auth.project,
            received_at=datetime.now(),
            payload=request.data,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=400)

    return Response({"message": "trace ingested"})