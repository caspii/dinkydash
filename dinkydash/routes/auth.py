"""
Authentication routes for registration, login, and logout.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from flask_login import login_user, logout_user, current_user
from dinkydash.models import db, Family, User, Dashboard
from dinkydash.forms import RegistrationForm, LoginForm
from dinkydash.utils.auth import hash_password, verify_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.view'))

    form = RegistrationForm()

    if form.validate_on_submit():
        try:
            # Create family
            family = Family(name=form.family_name.data.strip())
            db.session.add(family)
            db.session.flush()  # Get family ID without committing

            # Create user
            user = User(
                email=form.email.data.lower().strip(),
                password_hash=hash_password(form.password.data),
                tenant_id=family.id
            )
            db.session.add(user)
            db.session.flush()  # Get user ID without committing

            # Create default dashboard for the family
            dashboard = Dashboard(
                tenant_id=family.id,
                name=f"{family.name} Dashboard",
                layout_size="medium",
                is_default=True
            )
            db.session.add(dashboard)

            # Commit all changes
            db.session.commit()

            # Log the user in
            login_user(user)
            g.current_tenant_id = user.tenant_id

            flash(f'Welcome to DinkyDash, {family.name}! Your account has been created.', 'success')
            return redirect(url_for('dashboard.view'))

        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            # Log error for debugging
            print(f"Registration error: {str(e)}")

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.view'))

    form = LoginForm()

    if form.validate_on_submit():
        # Find user by email
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        # Verify user exists and password is correct
        if user and verify_password(user.password_hash, form.password.data):
            # Log the user in
            login_user(user)
            g.current_tenant_id = user.tenant_id

            flash('Welcome back!', 'success')

            # Redirect to next page if specified, otherwise dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.view'))
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
def logout():
    """Log out the current user."""
    if current_user.is_authenticated:
        logout_user()
        flash('You have been logged out successfully.', 'info')

    return redirect(url_for('index'))
