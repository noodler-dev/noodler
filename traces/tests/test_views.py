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
            trace_id="trace1",
            project=self.project1,
            started_at=now,
            ended_at=now,
            attributes={},
        )
        self.trace2 = Trace.objects.create(
            trace_id="trace2",
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

    def test_trace_list_shows_user_traces(self):
        """Test that trace list shows traces from user's projects when no project filter is set."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trace1")
        self.assertNotContains(response, "trace2")

    def test_trace_list_filters_by_current_project(self):
        """Test that trace list filters by current_project_id from session."""
        self.client.login(username="user1", password="testpass123")
        
        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()
        
        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trace1")
        self.assertNotContains(response, "trace2")
        self.assertContains(response, self.project1.name)

    def test_trace_list_clears_invalid_current_project(self):
        """Test that invalid current_project_id is cleared from session."""
        self.client.login(username="user1", password="testpass123")
        
        # Set invalid project ID in session
        session = self.client.session
        session["current_project_id"] = 99999
        session.save()
        
        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 200)
        # Should show all user traces since invalid project was cleared
        self.assertContains(response, "trace1")
        
        # Session should be cleared
        session = self.client.session
        self.assertNotIn("current_project_id", session)

    def test_trace_list_clear_filter(self):
        """Test that clear_filter view removes current_project_id from session."""
        self.client.login(username="user1", password="testpass123")
        
        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()
        
        # Clear filter
        response = self.client.get(reverse("traces:clear_filter"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("traces:list"))
        
        # Session should be cleared
        session = self.client.session
        self.assertNotIn("current_project_id", session)

    def test_trace_list_empty_for_user_with_no_traces(self):
        """Test that trace list shows empty message when user has no traces."""
        # Create user with no traces
        user3 = User.objects.create_user(username="user3", password="testpass123")
        user3_profile = UserProfile.objects.create(user=user3)
        org3 = Organization.objects.create(name="Org 3")
        Membership.objects.create(
            user_profile=user3_profile, organization=org3, role="admin"
        )

        self.client.login(username="user3", password="testpass123")
        response = self.client.get(reverse("traces:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No traces found")

    def test_trace_detail_requires_authentication(self):
        """Test that trace detail redirects unauthenticated users."""
        response = self.client.get(reverse("traces:detail", args=[self.trace1.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_trace_detail_access_control(self):
        """Test that users cannot view traces outside their projects."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:detail", args=[self.trace2.id]))
        self.assertEqual(response.status_code, 302)  # Redirects with error message
        self.assertEqual(response.url, reverse("traces:list"))

    def test_trace_detail_shows_trace_info(self):
        """Test that trace detail shows trace information."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:detail", args=[self.trace1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trace1")
        self.assertContains(response, "Project 1")

    def test_trace_detail_shows_spans(self):
        """Test that trace detail shows all associated spans."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:detail", args=[self.trace1.id]))
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
        response = self.client.get(reverse("traces:detail", args=[self.trace1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Span 1")
        self.assertContains(response, "Span 3")
        self.assertNotContains(response, "Span 2")  # Span from trace2

    def test_trace_detail_404_for_nonexistent_trace(self):
        """Test that trace detail returns 404 for nonexistent trace."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("traces:detail", args=[99999]))
        self.assertEqual(response.status_code, 404)
