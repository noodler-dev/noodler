import hashlib
import uuid
from django.db import models
from accounts.models import Organization


class Project(models.Model):
    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_available_trace_count(self):
        """Get the count of available traces for this project."""
        from traces.models import Trace

        return Trace.objects.filter(project=self).count()

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    hashed_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    create_dummy_key = models.BooleanField(
        default=False,
        help_text="Create a dummy key for testing purposes. Key is `dummy-key`.",
    )

    def save(self, *args, **kwargs):
        if self.create_dummy_key and not self.hashed_key:
            # TODO: Turn this into a function
            self.hashed_key = hashlib.sha256("dummy-key".encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
