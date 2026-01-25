from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from accounts.models import Organization, UserProfile, Membership
from projects.models import Project
from traces.models import Trace, Span


class TraceViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create users
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")

        # Create user profiles
        self.user1_profile = UserProfile.objects.create(user=self.user1)
        self.user2_profile = UserProfile.objects.create(user=self.user2)

        # Create organizations
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # Create memberships
        self.membership1 = Membership.objects.create(
            user_profile=self.user1_profile, organization=self.org1, role="admin"
        )
        self.membership2 = Membership.objects.create(
            user_profile=self.user2_profile, organization=self.org2, role="admin"
        )

        # Create projects
        self.project1 = Project.objects.create(name="Project 1", organization=self.org1)
        self.project2 = Project.objects.create(name="Project 2", organization=self.org2)

        # Create traces
        now = timezone.now()
        self.trace1 = Trace.objects.create(
            otel_trace_id="trace1",
            project=self.project1,
            started_at=now,
            ended_at=now,
            attributes={},
        )
        self.trace2 = Trace.objects.create(
            otel_trace_id="trace2",
            project=self.project2,
            started_at=now,
            ended_at=now,
            attributes={},
        )

        # Create spans
        self.span1 = Span.objects.create(
            name="Span 1",
            trace=self.trace1,
            span_id="span1",
            start_time=now,
            end_time=now,
        )
        self.span2 = Span.objects.create(
            name="Span 2",
            trace=self.trace2,
            span_id="span2",
            start_time=now,
            end_time=now,
        )

    def test_trace_list_requires_authentication(self):
        """Test that trace list redirects unauthenticated users."""
        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_trace_list_clears_invalid_current_project(self):
        """Test that invalid current_project_id is cleared and first project is auto-selected."""
        self.client.login(username="user1", password="testpass123")

        # Set invalid project ID in session
        session = self.client.session
        session["current_project_id"] = 99999
        session.save()

        response = self.client.get(reverse("traces:list"))
        # With auto-select, invalid project is cleared and first valid project is selected
        self.assertEqual(response.status_code, 200)

        # Session should be updated to first valid project
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)

    def test_trace_list_empty_for_user_with_no_traces(self):
        """Test that trace list shows empty message when user has no traces for current project."""
        # Create user with no traces
        user3 = User.objects.create_user(username="user3", password="testpass123")
        user3_profile = UserProfile.objects.create(user=user3)
        org3 = Organization.objects.create(name="Org 3")
        Membership.objects.create(
            user_profile=user3_profile, organization=org3, role="admin"
        )
        project3 = Project.objects.create(name="Project 3", organization=org3)

        self.client.login(username="user3", password="testpass123")

        # Set current project in session
        session = self.client.session
        session["current_project_id"] = project3.id
        session.save()

        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No traces found")

    def test_trace_detail_requires_authentication(self):
        """Test that trace detail redirects unauthenticated users."""
        response = self.client.get(reverse("traces:detail", args=[self.trace1.uid]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_trace_detail_requires_current_project(self):
        """Test that trace detail auto-selects first project when none is set."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:detail", args=[self.trace1.uid]))
        # With auto-select, first project is automatically selected and view succeeds
        self.assertEqual(response.status_code, 200)

        # Verify current project was set in session
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)

    def test_trace_detail_access_control(self):
        """Test that users cannot view traces outside their projects."""
        self.client.login(username="user1", password="testpass123")

        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        response = self.client.get(reverse("traces:detail", args=[self.trace2.uid]))
        self.assertEqual(response.status_code, 302)  # Redirects with error message
        self.assertEqual(response.url, reverse("projects:list"))

    def test_trace_detail_shows_trace_info(self):
        """Test that trace detail shows trace information."""
        self.client.login(username="user1", password="testpass123")

        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        response = self.client.get(reverse("traces:detail", args=[self.trace1.uid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trace1")
        self.assertContains(response, "Project 1")

    def test_trace_detail_shows_spans(self):
        """Test that trace detail shows all associated spans."""
        self.client.login(username="user1", password="testpass123")

        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        response = self.client.get(reverse("traces:detail", args=[self.trace1.uid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Span 1")
        self.assertContains(response, "span1")

    def test_trace_detail_only_shows_spans_for_that_trace(self):
        """Test that spans from other traces are not shown."""
        # Create another span for trace1
        now = timezone.now()
        span3 = Span.objects.create(
            name="Span 3",
            trace=self.trace1,
            span_id="span3",
            start_time=now,
            end_time=now,
        )

        self.client.login(username="user1", password="testpass123")

        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        response = self.client.get(reverse("traces:detail", args=[self.trace1.uid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Span 1")
        self.assertContains(response, "Span 3")
        self.assertNotContains(response, "Span 2")  # Span from trace2

    def test_trace_detail_404_for_nonexistent_trace(self):
        """Test that trace detail returns 404 for nonexistent trace."""
        self.client.login(username="user1", password="testpass123")
        # Use a UUID that doesn't exist
        import uuid

        fake_uid = uuid.uuid4()
        response = self.client.get(reverse("traces:detail", args=[fake_uid]))
        self.assertEqual(response.status_code, 404)
