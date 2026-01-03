from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.auth import APIKeyAuthentication
from traces.models import RawTrace
from traces.tasks import process_trace


class TraceListView(APIView):
    authentication_classes = [APIKeyAuthentication]

    def post(self, request):
        try:
            if request.content_type == "application/x-protobuf":
                body_bytes = request.body
            else:
                return Response({"error": "Unsupported content type"}, status=400)

            raw_trace = RawTrace.objects.create(
                project=request.auth.project,
                received_at=timezone.now(),
                payload_protobuf=body_bytes,
            )
            process_trace.delay(raw_trace.id)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({}, status=201)
