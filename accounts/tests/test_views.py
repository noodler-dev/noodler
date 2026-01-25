from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from accounts.models import UserProfile, Organization, Membership
from projects.models import Project

User = get_user_model()


class SignUpViewTests(TestCase):
    def setUp(self):
        self.signup_url = reverse("accounts:signup")

    def test_signup_get_request_shows_form(self):
        """Test that GET request to signup shows the form"""
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, "Sign Up")
        self.assertContains(response, "form")

    def test_signup_valid_form_creates_user(self):
        """Test that valid form submission creates a new user"""
        user_count_before = User.objects.count()
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)
        user_count_after = User.objects.count()

        self.assertEqual(user_count_after, user_count_before + 1)
        self.assertTrue(User.objects.filter(username="testuser").exists())

    def test_signup_valid_form_creates_userprofile(self):
        """Test that valid form submission creates a UserProfile"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)

        user = User.objects.get(username="testuser")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_signup_redirects_to_login_on_success(self):
        """Test that successful signup redirects to login page"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data, follow=True)

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)

    def test_signup_shows_success_message(self):
        """Test that success message is displayed after signup"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data, follow=True)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]), "Account created successfully! Please log in."
        )

    def test_signup_invalid_form_does_not_create_user(self):
        """Test that invalid form submission does not create a user"""
        user_count_before = User.objects.count()
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "differentpass",
        }
        response = self.client.post(self.signup_url, data)
        user_count_after = User.objects.count()

        self.assertEqual(user_count_after, user_count_before)
        self.assertFalse(User.objects.filter(username="testuser").exists())

    def test_signup_invalid_form_shows_errors(self):
        """Test that invalid form shows error messages"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "differentpass",
        }
        response = self.client.post(self.signup_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_signup_duplicate_username_shows_error(self):
        """Test that duplicate username shows error"""
        User.objects.create_user(username="existinguser", password="testpass123")
        data = {
            "username": "existinguser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_signup_redirects_authenticated_user(self):
        """Test that authenticated users are redirected away from signup"""
        user = User.objects.create_user(username="testuser", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_signup_weak_password_shows_error(self):
        """Test that weak password shows validation error"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "123",
            "password2": "123",
        }
        response = self.client.post(self.signup_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_signup_creates_default_organization(self):
        """Test that signup creates a default organization for the user"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)

        user = User.objects.get(username="testuser")
        user_profile = user.userprofile
        organizations = Organization.objects.filter(
            membership__user_profile=user_profile
        )

        self.assertEqual(organizations.count(), 1)
        default_org = organizations.first()
        self.assertEqual(default_org.name, "testuser")
        self.assertTrue(default_org.is_default)

    def test_signup_default_organization_has_admin_membership(self):
        """Test that user is an admin member of the default organization"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)

        user = User.objects.get(username="testuser")
        user_profile = user.userprofile
        default_org = Organization.objects.get(
            membership__user_profile=user_profile, is_default=True
        )
        membership = Membership.objects.get(
            user_profile=user_profile, organization=default_org
        )

        self.assertEqual(membership.role, "admin")

    def test_signup_requires_first_name(self):
        """Test that first name is required"""
        data = {
            "username": "testuser",
            "first_name": "",
            "last_name": "User",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertFalse(User.objects.filter(username="testuser").exists())

    def test_signup_requires_last_name(self):
        """Test that last name is required"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "",
            "email": "test@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertFalse(User.objects.filter(username="testuser").exists())

    def test_signup_requires_email(self):
        """Test that email is required"""
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertFalse(User.objects.filter(username="testuser").exists())

    def test_signup_saves_user_fields(self):
        """Test that first name, last name, and email are saved to user"""
        data = {
            "username": "testuser",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data)

        user = User.objects.get(username="testuser")
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.email, "john.doe@example.com")


class LoginViewTests(TestCase):
    def setUp(self):
        self.login_url = reverse("accounts:login")
        self.username = "testuser"
        self.password = "testpass123"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )

    def test_login_get_request_shows_form(self):
        """Test that GET request to login shows the form"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, "Log In")
        self.assertContains(response, "form")

    def test_login_valid_credentials_logs_in_user(self):
        """Test that valid credentials successfully log in the user"""
        data = {
            "username": self.username,
            "password": self.password,
        }
        self.client.post(self.login_url, data)

        # Check that user is authenticated by checking session
        from django.contrib.auth import get_user

        user = get_user(self.client)
        self.assertTrue(user.is_authenticated)
        self.assertEqual(user, self.user)

    def test_login_valid_credentials_redirects_to_home(self):
        """Test that successful login redirects to home page"""
        data = {
            "username": self.username,
            "password": self.password,
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_invalid_username_shows_error(self):
        """Test that invalid username shows error"""
        data = {
            "username": "nonexistent",
            "password": self.password,
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_login_invalid_password_shows_error(self):
        """Test that invalid password shows error"""
        data = {
            "username": self.username,
            "password": "wrongpassword",
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_login_empty_credentials_shows_error(self):
        """Test that empty credentials show error"""
        data = {
            "username": "",
            "password": "",
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_login_redirects_authenticated_user(self):
        """Test that authenticated users are redirected away from login"""
        self.client.force_login(self.user)

        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_redirects_to_next_parameter(self):
        """Test that login redirects to 'next' parameter if provided"""
        next_url = "/some/protected/page/"
        data = {
            "username": self.username,
            "password": self.password,
            "next": next_url,
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)

    def test_login_uses_next_from_query_string(self):
        """Test that login uses 'next' from query string"""
        next_url = "/another/page/"
        login_url_with_next = f"{self.login_url}?next={next_url}"
        data = {
            "username": self.username,
            "password": self.password,
        }
        response = self.client.post(login_url_with_next, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.logout_url = reverse("accounts:logout")
        self.login_url = reverse("accounts:login")
        self.username = "testuser"
        self.password = "testpass123"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )

    def test_logout_logs_out_user(self):
        """Test that logout successfully logs out the user"""
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url, follow=True)

        self.assertFalse(response.context["user"].is_authenticated)

    def test_logout_redirects_to_login(self):
        """Test that logout redirects to login page"""
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url)

        self.assertRedirects(response, self.login_url)

    def test_logout_shows_success_message(self):
        """Test that success message is displayed after logout"""
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url, follow=True)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You have been logged out successfully.")

    def test_logout_requires_authentication(self):
        """Test that logout requires authentication (redirects to login)"""
        response = self.client.post(self.logout_url)

        # Should redirect to login page (since @login_required redirects unauthenticated users)
        self.assertRedirects(
            response, f"{self.login_url}?next={self.logout_url}", status_code=302
        )

    def test_logout_get_request_not_allowed(self):
        """Test that GET request to logout returns 405 Method Not Allowed"""
        self.client.force_login(self.user)

        response = self.client.get(self.logout_url)

        self.assertEqual(response.status_code, 405)  # Method Not Allowed


class OrganizationListViewTests(TestCase):
    def setUp(self):
        self.list_url = reverse("accounts:organization_list")
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")
        self.user1_profile = UserProfile.objects.create(user=self.user1)
        self.user2_profile = UserProfile.objects.create(user=self.user2)

        # Create organizations
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # Create memberships
        Membership.objects.create(
            user_profile=self.user1_profile, organization=self.org1, role="admin"
        )
        Membership.objects.create(
            user_profile=self.user2_profile, organization=self.org2, role="admin"
        )

    def test_organization_list_requires_authentication(self):
        """Test that organization list redirects unauthenticated users."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_organization_list_shows_user_organizations(self):
        """Test that organization list only shows organizations user belongs to."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/organization_list.html")
        self.assertContains(response, "Org 1")
        self.assertNotContains(response, "Org 2")

    def test_organization_list_empty_shows_message(self):
        """Test that empty organization list shows helpful message."""
        user3 = User.objects.create_user(username="user3", password="testpass123")
        UserProfile.objects.create(user=user3)
        self.client.login(username="user3", password="testpass123")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No organizations found")


class OrganizationCreateViewTests(TestCase):
    def setUp(self):
        self.create_url = reverse("accounts:organization_create")
        self.user = User.objects.create_user(username="user1", password="testpass123")
        self.user_profile = UserProfile.objects.create(user=self.user)

    def test_organization_create_requires_authentication(self):
        """Test that organization create redirects unauthenticated users."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)

    def test_organization_create_get_shows_form(self):
        """Test that GET request shows the create form."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/organization_new.html")
        self.assertContains(response, "form")

    def test_organization_create_with_valid_name(self):
        """Test creating an organization with valid name."""
        self.client.login(username="user1", password="testpass123")
        org_count_before = Organization.objects.count()
        membership_count_before = Membership.objects.count()

        response = self.client.post(self.create_url, {"name": "New Org"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Organization.objects.count(), org_count_before + 1)
        self.assertEqual(Membership.objects.count(), membership_count_before + 1)

        org = Organization.objects.get(name="New Org")
        membership = Membership.objects.get(
            user_profile=self.user_profile, organization=org
        )
        self.assertEqual(membership.role, "admin")

    def test_organization_create_creates_admin_membership(self):
        """Test that creating an organization creates admin membership for creator."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(self.create_url, {"name": "New Org"})

        self.assertEqual(response.status_code, 302)
        org = Organization.objects.get(name="New Org")
        membership = Membership.objects.get(
            user_profile=self.user_profile, organization=org
        )
        self.assertEqual(membership.role, "admin")

    def test_organization_create_redirects_to_detail(self):
        """Test that successful creation redirects to organization detail."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(self.create_url, {"name": "New Org"})

        org = Organization.objects.get(name="New Org")
        self.assertRedirects(
            response, reverse("accounts:organization_detail", args=[org.uid])
        )

    def test_organization_create_shows_success_message(self):
        """Test that success message is displayed after creation."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(self.create_url, {"name": "New Org"}, follow=True)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertIn("created successfully", str(messages[0]))

    def test_organization_create_empty_name_shows_error(self):
        """Test that empty name shows error message."""
        self.client.login(username="user1", password="testpass123")
        org_count_before = Organization.objects.count()

        response = self.client.post(self.create_url, {"name": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Organization.objects.count(), org_count_before)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("required", str(messages[0]).lower())

    def test_organization_create_whitespace_only_name_shows_error(self):
        """Test that whitespace-only name shows error."""
        self.client.login(username="user1", password="testpass123")
        org_count_before = Organization.objects.count()

        response = self.client.post(self.create_url, {"name": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Organization.objects.count(), org_count_before)


class OrganizationDetailViewTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")
        self.user1_profile = UserProfile.objects.create(user=self.user1)
        self.user2_profile = UserProfile.objects.create(user=self.user2)

        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        Membership.objects.create(
            user_profile=self.user1_profile, organization=self.org1, role="admin"
        )
        Membership.objects.create(
            user_profile=self.user2_profile, organization=self.org2, role="member"
        )

    def test_organization_detail_requires_authentication(self):
        """Test that organization detail redirects unauthenticated users."""
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 302)

    def test_organization_detail_access_control(self):
        """Test that users cannot view organizations they don't belong to."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org2.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error

    def test_organization_detail_shows_organization_info(self):
        """Test that detail view shows organization information."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/organization_detail.html")
        self.assertContains(response, "Org 1")

    def test_organization_detail_shows_projects(self):
        """Test that detail view shows organization's projects."""
        self.client.login(username="user1", password="testpass123")
        project1 = Project.objects.create(name="Project 1", organization=self.org1)
        project2 = Project.objects.create(name="Project 2", organization=self.org1)

        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project 1")
        self.assertContains(response, "Project 2")

    def test_organization_detail_shows_admin_actions_for_admin(self):
        """Test that admin users see edit/delete actions."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit")
        self.assertContains(response, "Delete Organization")

    def test_organization_detail_hides_admin_actions_for_member(self):
        """Test that non-admin members don't see edit/delete actions."""
        self.client.login(username="user2", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org2.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Edit")
        self.assertNotContains(response, "Delete Organization")


class OrganizationEditViewTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")
        self.user1_profile = UserProfile.objects.create(user=self.user1)
        self.user2_profile = UserProfile.objects.create(user=self.user2)

        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        Membership.objects.create(
            user_profile=self.user1_profile, organization=self.org1, role="admin"
        )
        Membership.objects.create(
            user_profile=self.user2_profile, organization=self.org2, role="member"
        )

    def test_organization_edit_requires_authentication(self):
        """Test that organization edit redirects unauthenticated users."""
        response = self.client.get(
            reverse("accounts:organization_edit", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 302)

    def test_organization_edit_requires_admin(self):
        """Test that only admins can edit organizations."""
        self.client.login(username="user2", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_edit", args=[self.org2.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error

    def test_organization_edit_access_control(self):
        """Test that users cannot edit organizations they don't belong to."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_edit", args=[self.org2.uid]),
            {"name": "Hacked Org"},
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.org2.refresh_from_db()
        self.assertEqual(self.org2.name, "Org 2")

    def test_organization_edit_get_shows_form(self):
        """Test that GET request shows edit form."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_edit", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/organization_edit.html")
        self.assertContains(response, self.org1.name)

    def test_organization_edit_updates_name(self):
        """Test that organization edit updates the organization name."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_edit", args=[self.org1.uid]),
            {"name": "Updated Org 1"},
        )
        self.assertEqual(response.status_code, 302)
        self.org1.refresh_from_db()
        self.assertEqual(self.org1.name, "Updated Org 1")

    def test_organization_edit_redirects_to_detail(self):
        """Test that successful edit redirects to organization detail."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_edit", args=[self.org1.uid]),
            {"name": "Updated Org 1"},
        )
        self.assertRedirects(
            response, reverse("accounts:organization_detail", args=[self.org1.uid])
        )

    def test_organization_edit_shows_success_message(self):
        """Test that success message is displayed after edit."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_edit", args=[self.org1.uid]),
            {"name": "Updated Org 1"},
            follow=True,
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("updated successfully", str(messages[0]).lower())

    def test_organization_edit_empty_name_shows_error(self):
        """Test that empty name shows error message."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_edit", args=[self.org1.uid]), {"name": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.org1.refresh_from_db()
        self.assertEqual(self.org1.name, "Org 1")  # Unchanged
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("required", str(messages[0]).lower())


class OrganizationDeleteViewTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")
        self.user1_profile = UserProfile.objects.create(user=self.user1)
        self.user2_profile = UserProfile.objects.create(user=self.user2)

        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        Membership.objects.create(
            user_profile=self.user1_profile, organization=self.org1, role="admin"
        )
        Membership.objects.create(
            user_profile=self.user2_profile, organization=self.org2, role="member"
        )

    def test_organization_delete_requires_authentication(self):
        """Test that organization delete redirects unauthenticated users."""
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 302)

    def test_organization_delete_requires_post(self):
        """Test that organization delete requires POST method."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_delete", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_organization_delete_requires_admin(self):
        """Test that only admins can delete organizations."""
        self.client.login(username="user2", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org2.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertTrue(Organization.objects.filter(id=self.org2.id).exists())

    def test_organization_delete_access_control(self):
        """Test that users cannot delete organizations they don't belong to."""
        self.client.login(username="user1", password="testpass123")
        org_id = self.org2.id
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org2.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertTrue(Organization.objects.filter(id=org_id).exists())

    def test_organization_delete_removes_organization(self):
        """Test that organization delete removes the organization."""
        self.client.login(username="user1", password="testpass123")
        org_id = self.org1.id
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Organization.objects.filter(id=org_id).exists())

    def test_organization_delete_redirects_to_list(self):
        """Test that successful delete redirects to organization list."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid])
        )
        self.assertRedirects(response, reverse("accounts:organization_list"))

    def test_organization_delete_shows_success_message(self):
        """Test that success message is displayed after delete."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("deleted successfully", str(messages[0]).lower())

    def test_organization_delete_prevents_deletion_with_projects(self):
        """Test that organization cannot be deleted if it has projects."""
        self.client.login(username="user1", password="testpass123")
        Project.objects.create(name="Project 1", organization=self.org1)

        org_id = self.org1.id
        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertTrue(Organization.objects.filter(id=org_id).exists())

    def test_organization_delete_with_projects_shows_error(self):
        """Test that error message is shown when trying to delete org with projects."""
        self.client.login(username="user1", password="testpass123")
        Project.objects.create(name="Project 1", organization=self.org1)

        response = self.client.post(
            reverse("accounts:organization_delete", args=[self.org1.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("cannot delete", str(messages[0]).lower())
        self.assertIn("project", str(messages[0]).lower())

    def test_organization_delete_prevents_deletion_of_default_org(self):
        """Test that default organizations cannot be deleted."""
        self.client.login(username="user1", password="testpass123")
        default_org = Organization.objects.create(name="Default Org", is_default=True)
        Membership.objects.create(
            user_profile=self.user1_profile, organization=default_org, role="admin"
        )

        org_id = default_org.id
        response = self.client.post(
            reverse("accounts:organization_delete", args=[default_org.uid])
        )
        self.assertEqual(response.status_code, 302)  # Redirects with error
        self.assertTrue(Organization.objects.filter(id=org_id).exists())

    def test_organization_delete_default_org_shows_error(self):
        """Test that error message is shown when trying to delete default org."""
        self.client.login(username="user1", password="testpass123")
        default_org = Organization.objects.create(name="Default Org", is_default=True)
        Membership.objects.create(
            user_profile=self.user1_profile, organization=default_org, role="admin"
        )

        response = self.client.post(
            reverse("accounts:organization_delete", args=[default_org.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("cannot delete", str(messages[0]).lower())
        self.assertIn("default", str(messages[0]).lower())

    def test_organization_detail_hides_delete_button_for_default_org(self):
        """Test that delete button is hidden for default organizations."""
        self.client.login(username="user1", password="testpass123")
        default_org = Organization.objects.create(name="Default Org", is_default=True)
        Membership.objects.create(
            user_profile=self.user1_profile, organization=default_org, role="admin"
        )

        response = self.client.get(
            reverse("accounts:organization_detail", args=[default_org.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Delete Organization")

    def test_organization_detail_shows_delete_button_for_non_default_org(self):
        """Test that delete button is shown for non-default organizations."""
        self.client.login(username="user1", password="testpass123")
        response = self.client.get(
            reverse("accounts:organization_detail", args=[self.org1.uid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Organization")
