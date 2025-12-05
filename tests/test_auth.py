"""
Tests for authentication functionality (registration, login, logout).
"""
import pytest
from dinkydash.models import db, User, Family, Dashboard


class TestRegistration:
    """Test cases for user registration."""

    def test_registration_page_loads(self, client):
        """Test that registration page loads successfully."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Create Your Family Dashboard' in response.data

    def test_successful_registration(self, client, app):
        """Test successful user registration."""
        response = client.post('/register', data={
            'family_name': 'Test Family',
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'csrf_token': 'dummy'  # CSRF disabled in test config
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Welcome to DinkyDash' in response.data

        # Verify user was created
        with app.app_context():
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.email == 'newuser@example.com'

            # Verify family was created
            family = Family.query.get(user.tenant_id)
            assert family is not None
            assert family.name == 'Test Family'

            # Verify default dashboard was created
            dashboard = Dashboard.query.filter_by(tenant_id=family.id, is_default=True).first()
            assert dashboard is not None
            assert dashboard.name == 'Test Family Dashboard'

    def test_registration_duplicate_email(self, client, user):
        """Test that registration fails with duplicate email."""
        response = client.post('/register', data={
            'family_name': 'Another Family',
            'email': 'test@example.com',  # Email already exists from fixture
            'password': 'password123',
            'confirm_password': 'password123'
        })

        assert response.status_code == 200
        assert b'already registered' in response.data

    def test_registration_password_mismatch(self, client):
        """Test that registration fails when passwords don't match."""
        response = client.post('/register', data={
            'family_name': 'Test Family',
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })

        assert response.status_code == 200
        assert b'Passwords must match' in response.data

    def test_registration_short_password(self, client):
        """Test that registration fails with short password."""
        response = client.post('/register', data={
            'family_name': 'Test Family',
            'email': 'newuser@example.com',
            'password': 'short',
            'confirm_password': 'short'
        })

        assert response.status_code == 200
        assert b'at least 8 characters' in response.data

    def test_registration_invalid_email(self, client):
        """Test that registration fails with invalid email."""
        response = client.post('/register', data={
            'family_name': 'Test Family',
            'email': 'not-an-email',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        assert response.status_code == 200
        assert b'Invalid email' in response.data

    def test_registration_redirects_if_logged_in(self, auth_client):
        """Test that logged-in users are redirected from registration."""
        response = auth_client.get('/register', follow_redirects=False)
        assert response.status_code == 302
        assert '/dashboard' in response.location


class TestLogin:
    """Test cases for user login."""

    def test_login_page_loads(self, client):
        """Test that login page loads successfully."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Welcome Back' in response.data

    def test_successful_login(self, client, app, user):
        """Test successful login with valid credentials."""
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Welcome back!' in response.data
        # Should be redirected to dashboard
        assert b'Dashboard' in response.data or b'dashboard' in response.data

    def test_login_invalid_email(self, client):
        """Test login with non-existent email."""
        response = client.post('/login', data={
            'email': 'nonexistent@example.com',
            'password': 'password123'
        })

        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_invalid_password(self, client, user):
        """Test login with incorrect password."""
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_redirects_if_logged_in(self, auth_client):
        """Test that logged-in users are redirected from login."""
        response = auth_client.get('/login', follow_redirects=False)
        assert response.status_code == 302
        assert '/dashboard' in response.location

    def test_login_with_next_parameter(self, client, user):
        """Test login redirects to 'next' parameter."""
        response = client.post('/login?next=/dashboards', data={
            'email': 'test@example.com',
            'password': 'testpassword123'
        }, follow_redirects=False)

        assert response.status_code == 302
        assert response.location == '/dashboards'


class TestLogout:
    """Test cases for user logout."""

    def test_logout_when_logged_in(self, auth_client):
        """Test logout when user is logged in."""
        response = auth_client.get('/logout', follow_redirects=True)

        assert response.status_code == 200
        assert b'logged out successfully' in response.data
        # Should be redirected to home page
        assert b'DinkyDash' in response.data

    def test_logout_when_not_logged_in(self, client):
        """Test logout when user is not logged in."""
        response = client.get('/logout', follow_redirects=True)

        assert response.status_code == 200
        # Should still redirect to home without error

    def test_logout_clears_session(self, auth_client):
        """Test that logout clears the user session."""
        # First verify we're logged in
        response = auth_client.get('/dashboard')
        assert response.status_code == 200

        # Logout
        auth_client.get('/logout')

        # Try to access dashboard (should redirect to login)
        response = auth_client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location


class TestAuthIntegration:
    """Integration tests for complete auth workflows."""

    def test_complete_registration_and_login_flow(self, client, app):
        """Test complete flow: register, logout, login."""
        # Step 1: Register
        client.post('/register', data={
            'family_name': 'Integration Test Family',
            'email': 'integration@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123'
        }, follow_redirects=True)

        # Verify user can access dashboard after registration
        response = client.get('/dashboard')
        assert response.status_code == 200

        # Step 2: Logout
        client.get('/logout')

        # Verify user can't access dashboard after logout
        response = client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302

        # Step 3: Login again
        response = client.post('/login', data={
            'email': 'integration@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Welcome back!' in response.data

        # Verify user can access dashboard after login
        response = client.get('/dashboard')
        assert response.status_code == 200

    def test_email_case_insensitivity(self, client, app):
        """Test that email login is case-insensitive."""
        # Register with lowercase email
        client.post('/register', data={
            'family_name': 'Test Family',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        client.get('/logout')

        # Login with uppercase email
        response = client.post('/login', data={
            'email': 'TEST@EXAMPLE.COM',
            'password': 'password123'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Welcome back!' in response.data
