"""
Admin routes for managing dashboards, tasks, and countdowns.
"""
import os
import json
import uuid
from PIL import Image
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from flask_login import login_required

from dinkydash import db
from dinkydash.models import Dashboard, Task, Countdown
from dinkydash.forms.countdown import CountdownForm
from dinkydash.forms.dashboard import DashboardForm
from dinkydash.utils.countdown import calculate_days_remaining, format_countdown, get_target_date
import calendar


admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
def index():
    """Admin dashboard - show admin menu."""
    return render_template('admin/index.html')


@admin_bp.route('/admin/countdowns')
@login_required
def countdown_list():
    """List all countdowns for the current tenant."""
    countdowns = Countdown.query.filter_by(tenant_id=g.current_tenant_id).all()
    
    # Calculate days remaining and format dates
    for countdown in countdowns:
        countdown.days_remaining = calculate_days_remaining(countdown.date_month, countdown.date_day)
        countdown.days_text = format_countdown(countdown.days_remaining)
        target_date = get_target_date(countdown.date_month, countdown.date_day)
        countdown.date_text = target_date.strftime("%B %d")
    
    # Sort by days remaining (soonest first)
    countdowns.sort(key=lambda c: c.days_remaining)
    
    return render_template('admin/countdowns.html', countdowns=countdowns)


@admin_bp.route('/admin/countdowns/new', methods=['GET', 'POST'])
@login_required
def countdown_create():
    """Create a new countdown."""
    form = CountdownForm()
    
    # Populate dashboard choices
    dashboards = Dashboard.query.filter_by(tenant_id=g.current_tenant_id).all()
    form.dashboard_id.choices = [(d.id, d.name) for d in dashboards]
    
    if form.validate_on_submit():
        # Create countdown
        countdown = Countdown(
            tenant_id=g.current_tenant_id,
            dashboard_id=form.dashboard_id.data,
            name=form.name.data,
            date_month=form.date_month.data,
            date_day=form.date_day.data,
            icon_type=form.icon_type.data
        )
        
        # Handle icon
        if form.icon_type.data == 'emoji':
            countdown.icon_value = form.emoji.data
        elif form.icon_type.data == 'image' and form.image.data:
            # Save image
            countdown.icon_value = save_countdown_image(form.image.data, g.current_tenant_id, 'new')
        
        db.session.add(countdown)
        db.session.commit()
        
        # Update icon value with countdown ID if image was uploaded
        if form.icon_type.data == 'image' and countdown.icon_value:
            countdown.icon_value = save_countdown_image(form.image.data, g.current_tenant_id, countdown.id)
            db.session.commit()
        
        flash('Countdown created successfully!', 'success')
        return redirect(url_for('admin.countdown_list'))
    
    return render_template('admin/countdown_form.html', form=form, countdown=None)


@admin_bp.route('/admin/countdowns/<int:countdown_id>/edit', methods=['GET', 'POST'])
@login_required
def countdown_edit(countdown_id):
    """Edit an existing countdown."""
    countdown = Countdown.query.filter_by(id=countdown_id, tenant_id=g.current_tenant_id).first_or_404()
    
    form = CountdownForm()
    
    # Populate dashboard choices
    dashboards = Dashboard.query.filter_by(tenant_id=g.current_tenant_id).all()
    form.dashboard_id.choices = [(d.id, d.name) for d in dashboards]
    
    if form.validate_on_submit():
        # Update countdown
        countdown.name = form.name.data
        countdown.dashboard_id = form.dashboard_id.data
        countdown.date_month = form.date_month.data
        countdown.date_day = form.date_day.data
        countdown.icon_type = form.icon_type.data
        
        # Handle icon
        if form.icon_type.data == 'emoji':
            countdown.icon_value = form.emoji.data
        elif form.icon_type.data == 'image':
            if form.image.data:
                # Save new image
                countdown.icon_value = save_countdown_image(form.image.data, g.current_tenant_id, countdown.id)
            # else: keep existing image
        
        db.session.commit()
        flash('Countdown updated successfully!', 'success')
        return redirect(url_for('admin.countdown_list'))
    
    elif request.method == 'GET':
        # Populate form with countdown data
        form.name.data = countdown.name
        form.dashboard_id.data = countdown.dashboard_id
        form.date_month.data = countdown.date_month
        form.date_day.data = countdown.date_day
        form.icon_type.data = countdown.icon_type
        
        if countdown.icon_type == 'emoji':
            form.emoji.data = countdown.icon_value
    
    return render_template('admin/countdown_form.html', form=form, countdown=countdown)


@admin_bp.route('/admin/countdowns/<int:countdown_id>/delete', methods=['POST'])
@login_required
def countdown_delete(countdown_id):
    """Delete a countdown."""
    countdown = Countdown.query.filter_by(id=countdown_id, tenant_id=g.current_tenant_id).first_or_404()
    
    # Delete associated image file if exists
    if countdown.icon_type == 'image' and countdown.icon_value:
        try:
            image_path = os.path.join(current_app.static_folder, countdown.icon_value.lstrip('/static/'))
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception:
            pass  # Don't fail deletion if image cleanup fails
    
    db.session.delete(countdown)
    db.session.commit()
    
    flash('Countdown deleted successfully!', 'success')
    return redirect(url_for('admin.countdown_list'))


def save_countdown_image(file_obj, tenant_id, countdown_id):
    """Save uploaded countdown image with validation."""
    try:
        # Validate image
        img = Image.open(file_obj)
        img.verify()
        
        # Generate unique filename
        ext = os.path.splitext(file_obj.filename)[1]
        filename = f'countdown_{countdown_id}_{uuid.uuid4().hex}{ext}'
        
        # Create tenant directory
        upload_dir = os.path.join(current_app.static_folder, 'uploads', str(tenant_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        
        # Reset file pointer after verify
        file_obj.seek(0)
        file_obj.save(filepath)
        
        # Return relative path from static folder
        return f'uploads/{tenant_id}/{filename}'
        
    except Exception as e:
        current_app.logger.error(f"Failed to save countdown image: {e}")
        return None


# Dashboard Management Routes

@admin_bp.route('/admin/dashboards')
@login_required
def dashboard_list():
    """List all dashboards for the current tenant."""
    dashboards = Dashboard.query.filter_by(tenant_id=g.current_tenant_id).all()
    return render_template('admin/dashboards.html', dashboards=dashboards)


@admin_bp.route('/admin/dashboards/new', methods=['GET', 'POST'])
@login_required
def dashboard_create():
    """Create a new dashboard."""
    form = DashboardForm()
    
    if form.validate_on_submit():
        # Create dashboard
        dashboard = Dashboard(
            tenant_id=g.current_tenant_id,
            name=form.name.data,
            layout_size=form.layout_size.data,
            is_default=False  # New dashboards are not default
        )
        
        db.session.add(dashboard)
        db.session.commit()
        
        flash('Dashboard created successfully!', 'success')
        return redirect(url_for('admin.dashboard_list'))
    
    return render_template('admin/dashboard_form.html', form=form, dashboard=None)


@admin_bp.route('/admin/dashboards/<int:dashboard_id>/edit', methods=['GET', 'POST'])
@login_required
def dashboard_edit(dashboard_id):
    """Edit an existing dashboard."""
    dashboard = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.current_tenant_id).first_or_404()
    
    form = DashboardForm()
    
    if form.validate_on_submit():
        # Update dashboard
        dashboard.name = form.name.data
        dashboard.layout_size = form.layout_size.data
        
        db.session.commit()
        flash('Dashboard updated successfully!', 'success')
        return redirect(url_for('admin.dashboard_list'))
    
    elif request.method == 'GET':
        # Populate form with dashboard data
        form.name.data = dashboard.name
        form.layout_size.data = dashboard.layout_size
    
    return render_template('admin/dashboard_form.html', form=form, dashboard=dashboard)


@admin_bp.route('/admin/dashboards/<int:dashboard_id>/delete', methods=['POST'])
@login_required
def dashboard_delete(dashboard_id):
    """Delete a dashboard."""
    dashboard = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.current_tenant_id).first_or_404()
    
    # Prevent deletion of default dashboard
    if dashboard.is_default:
        flash('Cannot delete the default dashboard.', 'error')
        return redirect(url_for('admin.dashboard_list'))
    
    # Prevent deletion of last dashboard
    dashboard_count = Dashboard.query.filter_by(tenant_id=g.current_tenant_id).count()
    if dashboard_count <= 1:
        flash('Cannot delete the last dashboard. Every family needs at least one dashboard.', 'error')
        return redirect(url_for('admin.dashboard_list'))
    
    # Get default dashboard to reassign items
    default_dashboard = Dashboard.query.filter_by(
        tenant_id=g.current_tenant_id,
        is_default=True
    ).first()
    
    if not default_dashboard:
        # If no default, get any other dashboard
        default_dashboard = Dashboard.query.filter_by(tenant_id=g.current_tenant_id).filter(
            Dashboard.id != dashboard_id
        ).first()
    
    # Reassign all tasks to default dashboard
    Task.query.filter_by(dashboard_id=dashboard_id).update(
        {'dashboard_id': default_dashboard.id}
    )
    
    # Reassign all countdowns to default dashboard
    Countdown.query.filter_by(dashboard_id=dashboard_id).update(
        {'dashboard_id': default_dashboard.id}
    )
    
    db.session.delete(dashboard)
    db.session.commit()
    
    flash(f'Dashboard deleted. Tasks and countdowns have been moved to {default_dashboard.name}.', 'success')
    return redirect(url_for('admin.dashboard_list'))
