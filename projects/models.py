import secrets
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from accounts.models import Organization


class Project(models.Model):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    hashed_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.hashed_key:
            plain_key = "sk_" + secrets.token_urlsafe(32)
            print(f"Plain Key: {plain_key}")
            self.hashed_key = make_password(plain_key)
        super().save(*args, **kwargs)

    def verify(self, plain_key):
        return check_password(plain_key, self.hashed_key)

    def __str__(self):
        return self.name
