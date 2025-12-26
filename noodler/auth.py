import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from projects.models import ApiKey


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization")
        if not header or not header.startswith("Bearer "):
            return None

        raw_key = header.split(" ", 1)[1]
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            key = ApiKey.objects.select_related("project", "project__organization").get(
                hashed_key=hashed,
                revoked_at__isnull=True,
            )
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key")

        return (None, key)
