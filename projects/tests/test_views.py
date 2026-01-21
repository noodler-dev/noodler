from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import Organization, UserProfile, Membership
from projects.models import Project, ApiKey


class ProjectViewsTestCase(TestCase):
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

    def test_project_list_requires_authentication(self):
        """Test that project list redirects unauthenticated users."""
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_project_list_shows_user_projects(self):
        """Test that project list only shows projects from user's organizations."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project 1")
        self.assertNotContains(response, "Project 2")

    def test_project_create_requires_authentication(self):
        """Test that project create redirects unauthenticated users."""
        response = self.client.get(reverse("projects:create"))
        self.assertEqual(response.status_code, 302)

    def test_project_create_with_valid_data(self):
        """Test creating a project with valid data."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:create"),
            {"name": "New Project", "organization": self.org1.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Project.objects.filter(name="New Project", organization=self.org1).exists()
        )

    def test_project_create_rejects_invalid_organization(self):
        """Test that users cannot create projects in organizations they don't belong to."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:create"),
            {"name": "Unauthorized Project", "organization": self.org2.id},
        )
        self.assertEqual(response.status_code, 200)  # Returns form with error
        self.assertFalse(Project.objects.filter(name="Unauthorized Project").exists())

    def test_project_detail_requires_authentication(self):
        """Test that project detail redirects unauthenticated users."""
        response = self.client.get(reverse("projects:detail", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)

    def test_project_detail_access_control(self):
        """Test that users cannot view projects outside their organizations."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("projects:detail", args=[self.project2.id]))
        self.assertEqual(response.status_code, 302)  # Redirects with error message

    def test_project_edit_requires_authentication(self):
        """Test that project edit redirects unauthenticated users."""
        response = self.client.get(reverse("projects:edit", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)

    def test_project_edit_access_control(self):
        """Test that users cannot edit projects outside their organizations."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:edit", args=[self.project2.id]),
            {"name": "Hacked Project"},
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.project2.refresh_from_db()
        self.assertEqual(self.project2.name, "Project 2")

    def test_project_edit_updates_name(self):
        """Test that project edit updates the project name."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:edit", args=[self.project1.id]),
            {"name": "Updated Project 1"},
        )
        self.assertEqual(response.status_code, 302)
        self.project1.refresh_from_db()
        self.assertEqual(self.project1.name, "Updated Project 1")

    def test_project_delete_requires_post(self):
        """Test that project delete requires POST method."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("projects:delete", args=[self.project1.id]))
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_project_delete_requires_authentication(self):
        """Test that project delete redirects unauthenticated users."""
        response = self.client.post(reverse("projects:delete", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)

    def test_project_delete_access_control(self):
        """Test that users cannot delete projects outside their organizations."""
        self.client.login(username="user1", password="testpass123")
        project_id = self.project2.id
        response = self.client.post(reverse("projects:delete", args=[project_id]))
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertTrue(Project.objects.filter(id=project_id).exists())

    def test_project_delete_removes_project(self):
        """Test that project delete removes the project."""
        self.client.login(username="user1", password="testpass123")
        project_id = self.project1.id
        response = self.client.post(reverse("projects:delete", args=[project_id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(id=project_id).exists())

    def test_project_delete_clears_session(self):
        """Test that deleting current project clears session."""
        self.client.login(username="user1", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        response = self.client.post(reverse("projects:delete", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertNotIn("current_project_id", session)

    def test_project_delete_preserves_different_current_project(self):
        """Test that deleting a project different from current project preserves current project."""
        self.client.login(username="user1", password="testpass123")

        # Create another project for user1
        project3 = Project.objects.create(name="Project 3", organization=self.org1)

        # Set project1 as current project
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        # Delete project3 (different from current project)
        response = self.client.post(reverse("projects:delete", args=[project3.id]))
        self.assertEqual(response.status_code, 302)

        # Current project should still be project1 (not cleared)
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)

        # Project3 should be deleted
        self.assertFalse(Project.objects.filter(id=project3.id).exists())

    def test_project_switch_requires_post(self):
        """Test that project switch requires POST method."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(reverse("projects:switch", args=[self.project1.id]))
        self.assertEqual(response.status_code, 405)

    def test_project_switch_requires_authentication(self):
        """Test that project switch redirects unauthenticated users."""
        response = self.client.post(reverse("projects:switch", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)

    def test_project_switch_access_control(self):
        """Test that users cannot switch to projects outside their organizations."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(reverse("projects:switch", args=[self.project2.id]))
        self.assertEqual(response.status_code, 302)  # Redirects with error
        session = self.client.session
        self.assertNotIn("current_project_id", session)

    def test_project_switch_sets_session(self):
        """Test that project switch sets current_project_id in session."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(reverse("projects:switch", args=[self.project1.id]))
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)

    def test_project_detail_auto_updates_current_project(self):
        """Test that visiting a project detail page auto-updates current project."""
        self.client.login(username="user1", password="testpass123")

        # Set a different project as current
        session = self.client.session
        session["current_project_id"] = self.project1.id
        session.save()

        # Create another project for user1
        project3 = Project.objects.create(name="Project 3", organization=self.org1)

        # Visit project3 detail page
        response = self.client.get(reverse("projects:detail", args=[project3.id]))
        self.assertEqual(response.status_code, 200)

        # Current project should be updated to project3
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), project3.id)

    def test_project_detail_auto_selects_when_no_current_project(self):
        """Test that visiting a project detail page auto-selects it when no current project is set."""
        self.client.login(username="user1", password="testpass123")

        # Ensure no current project is set
        session = self.client.session
        if "current_project_id" in session:
            del session["current_project_id"]
        session.save()

        # Visit project detail page
        response = self.client.get(reverse("projects:detail", args=[self.project1.id]))
        self.assertEqual(response.status_code, 200)

        # Current project should be auto-selected
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)

    def test_project_detail_clears_invalid_current_project(self):
        """Test that visiting a project detail page clears invalid current project and sets new one."""
        self.client.login(username="user1", password="testpass123")

        # Set invalid project ID in session
        session = self.client.session
        session["current_project_id"] = 99999
        session.save()

        # Visit a valid project detail page
        response = self.client.get(reverse("projects:detail", args=[self.project1.id]))
        self.assertEqual(response.status_code, 200)

        # Invalid project should be cleared and replaced with valid one
        session = self.client.session
        self.assertEqual(session.get("current_project_id"), self.project1.id)


class ApiKeyViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create user
        self.user = User.objects.create_user(username="user1", password="testpass123")
        self.user_profile = UserProfile.objects.create(user=self.user)

        # Create organization
        self.org = Organization.objects.create(name="Org 1")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )

        # Create project
        self.project = Project.objects.create(name="Project 1", organization=self.org)

    def test_api_key_create_requires_authentication(self):
        """Test that API key create redirects unauthenticated users."""
        response = self.client.post(
            reverse("projects:key_create", args=[self.project.id]), {"name": "Test Key"}
        )
        self.assertEqual(response.status_code, 302)

    def test_api_key_create_access_control(self):
        """Test that users cannot create API keys for projects outside their organizations."""
        # Create another org and project
        org2 = Organization.objects.create(name="Org 2")
        project2 = Project.objects.create(name="Project 2", organization=org2)

        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:key_create", args=[project2.id]),
            {"name": "Unauthorized Key"},
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertFalse(ApiKey.objects.filter(name="Unauthorized Key").exists())

    def test_api_key_create_generates_hashed_key(self):
        """Test that API key create generates and stores hashed key."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:key_create", args=[self.project.id]), {"name": "Test Key"}
        )
        self.assertEqual(response.status_code, 302)

        api_key = ApiKey.objects.get(name="Test Key", project=self.project)
        self.assertIsNotNone(api_key.hashed_key)
        self.assertEqual(len(api_key.hashed_key), 64)  # SHA256 hex digest length

    def test_api_key_create_stores_raw_key_in_session(self):
        """Test that raw key is stored in session for one-time display."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:key_create", args=[self.project.id]), {"name": "Test Key"}
        )
        self.assertEqual(response.status_code, 302)

        api_key = ApiKey.objects.get(name="Test Key", project=self.project)
        session = self.client.session
        self.assertIn(f"api_key_{api_key.id}", session)

    def test_api_key_created_shows_raw_key_once(self):
        """Test that raw key is shown once and then removed from session."""
        self.client.login(username="user1", password="testpass123")

        # Create key
        response = self.client.post(
            reverse("projects:key_create", args=[self.project.id]), {"name": "Test Key"}
        )
        api_key = ApiKey.objects.get(name="Test Key", project=self.project)

        # First view - should show key
        response = self.client.get(
            reverse("projects:key_created", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API Key Created")

        # Check that raw key is in response (it should be)
        session = self.client.session
        self.assertNotIn(f"api_key_{api_key.id}", session)  # Removed after first view

        # Second view - should redirect
        response = self.client.get(
            reverse("projects:key_created", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_api_key_created_requires_authentication(self):
        """Test that API key created page redirects unauthenticated users."""
        api_key = ApiKey.objects.create(
            name="Test Key", project=self.project, hashed_key="test"
        )
        response = self.client.get(
            reverse("projects:key_created", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_api_key_revoke_requires_post(self):
        """Test that API key revoke requires POST method."""
        self.client.login(username="user1", password="testpass123")
        api_key = ApiKey.objects.create(
            name="Test Key", project=self.project, hashed_key="test"
        )
        response = self.client.get(
            reverse("projects:key_revoke", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_api_key_revoke_requires_authentication(self):
        """Test that API key revoke redirects unauthenticated users."""
        api_key = ApiKey.objects.create(
            name="Test Key", project=self.project, hashed_key="test"
        )
        response = self.client.post(
            reverse("projects:key_revoke", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_api_key_revoke_sets_revoked_at(self):
        """Test that API key revoke sets revoked_at timestamp."""
        self.client.login(username="user1", password="testpass123")
        api_key = ApiKey.objects.create(
            name="Test Key", project=self.project, hashed_key="test"
        )
        self.assertIsNone(api_key.revoked_at)

        response = self.client.post(
            reverse("projects:key_revoke", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)

        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)

    def test_api_key_revoke_does_not_hard_delete(self):
        """Test that API key revoke does not hard-delete the key."""
        self.client.login(username="user1", password="testpass123")
        api_key = ApiKey.objects.create(
            name="Test Key", project=self.project, hashed_key="test"
        )
        key_id = api_key.id

        response = self.client.post(
            reverse("projects:key_revoke", args=[self.project.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)

        self.assertTrue(ApiKey.objects.filter(id=key_id).exists())

    def test_api_key_revoke_access_control(self):
        """Test that users cannot revoke API keys for projects outside their organizations."""
        # Create another org and project
        org2 = Organization.objects.create(name="Org 2")
        project2 = Project.objects.create(name="Project 2", organization=org2)
        api_key = ApiKey.objects.create(
            name="Test Key", project=project2, hashed_key="test"
        )

        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("projects:key_revoke", args=[project2.id, api_key.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error

        api_key.refresh_from_db()
        self.assertIsNone(api_key.revoked_at)
