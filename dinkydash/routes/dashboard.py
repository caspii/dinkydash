"""
Dashboard routes for viewing family dashboards.
"""
from flask import Blueprint, render_template, abort, request, g
from flask_login import login_required
from dinkydash.models import db, Dashboard, Task, Countdown
from dinkydash.utils.rotation import get_current_person
from dinkydash.utils.countdown import calculate_days_remaining, format_countdown, get_target_date
from dinkydash.utils.tenant import require_tenant

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.before_request
@login_required
def require_login():
    """Ensure user is logged in for all dashboard routes."""
    require_tenant()


@dashboard_bp.route('/dashboard')
@dashboard_bp.route('/dashboard/')
def view():
    """View the default dashboard for the family."""
    tenant_id = g.current_tenant_id

    # Get default dashboard
    dashboard = Dashboard.query.filter_by(
        tenant_id=tenant_id,
        is_default=True
    ).first()

    if not dashboard:
        # No default dashboard, try to get any dashboard
        dashboard = Dashboard.query.filter_by(tenant_id=tenant_id).first()

    if not dashboard:
        # No dashboards at all, redirect to dashboard list
        return render_template(
            'dashboard/list.html',
            dashboards=[],
            message="You don't have any dashboards yet. Create one to get started!"
        )

    return view_dashboard(dashboard.id)


@dashboard_bp.route('/dashboard/<int:dashboard_id>')
def view_dashboard(dashboard_id):
    """View a specific dashboard by ID."""
    tenant_id = g.current_tenant_id

    # Get dashboard (tenant filtering happens automatically)
    dashboard = Dashboard.query.filter_by(
        id=dashboard_id,
        tenant_id=tenant_id
    ).first_or_404()

    # Get tasks for this dashboard
    tasks = Task.query.filter_by(dashboard_id=dashboard.id).all()

    # Calculate current person for each task
    for task in tasks:
        try:
            task.current_person = get_current_person(task.rotation_json)
        except (ValueError, Exception) as e:
            task.current_person = "Error"

    # Get countdowns for this dashboard
    countdowns = Countdown.query.filter_by(dashboard_id=dashboard.id).all()

    # Calculate days remaining for each countdown
    for countdown in countdowns:
        try:
            days = calculate_days_remaining(countdown.date_month, countdown.date_day)
            countdown.days_remaining = days
            countdown.days_text = format_countdown(days)

            # Get target date for display
            target = get_target_date(countdown.date_month, countdown.date_day)
            countdown.date_text = target.strftime("%B %d")
        except (ValueError, Exception) as e:
            countdown.days_remaining = -1
            countdown.days_text = "Invalid date"
            countdown.date_text = ""

    # Sort countdowns by days remaining (soonest first)
    countdowns.sort(key=lambda c: c.days_remaining if c.days_remaining >= 0 else 999)

    # Check if this is an HTMX request for partial refresh
    is_htmx = request.headers.get('HX-Request') == 'true'

    if is_htmx:
        # Return only the dashboard content (partial)
        return render_template(
            'dashboard/_content.html',
            dashboard=dashboard,
            tasks=tasks,
            countdowns=countdowns
        )

    # Return full page
    return render_template(
        'dashboard/view.html',
        dashboard=dashboard,
        tasks=tasks,
        countdowns=countdowns
    )


@dashboard_bp.route('/dashboards')
def list():
    """List all dashboards for the family."""
    tenant_id = g.current_tenant_id

    # Get all dashboards for this family
    dashboards = Dashboard.query.filter_by(tenant_id=tenant_id).all()

    return render_template(
        'dashboard/list.html',
        dashboards=dashboards
    )
