from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from accounts.models import UserProfile

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
            "password1": "testpass123",
            "password2": "testpass123",
        }
        response = self.client.post(self.signup_url, data, follow=True)
        messages = list(get_messages(response.wsgi_request))
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Account created successfully! Please log in.")

    def test_signup_invalid_form_does_not_create_user(self):
        """Test that invalid form submission does not create a user"""
        user_count_before = User.objects.count()
        data = {
            "username": "testuser",
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
            "password1": "123",
            "password2": "123",
        }
        response = self.client.post(self.signup_url, data)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")


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
        response = self.client.get(self.logout_url)
        
        # Should redirect to login page (since @login_required redirects unauthenticated users)
        self.assertRedirects(
            response, f"{self.login_url}?next={self.logout_url}", status_code=302
        )

    def test_logout_get_request_works(self):
        """Test that GET request to logout works (Django allows both GET and POST)"""
        self.client.force_login(self.user)
        
        response = self.client.get(self.logout_url, follow=True)
        
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertRedirects(response, self.login_url)
