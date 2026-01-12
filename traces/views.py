import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from projects.views import get_user_projects
from projects.models import Project
from .models import Trace, Span


def format_duration(start, end):
    """Format duration between two datetimes as a human-readable string."""
    if not start or not end:
        return None
    delta = end - start
    total_seconds = int(delta.total_seconds())
    if total_seconds < 1:
        milliseconds = int(delta.total_seconds() * 1000)
        return f"{milliseconds}ms"
    elif total_seconds < 60:
        return f"{total_seconds}s"
    else:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"


@login_required
def trace_list(request):
    """List traces for the current project (from session) or all user projects."""
    user_projects = get_user_projects(request.user)
    current_project_id = request.session.get("current_project_id")

    # Filter by current project if set, otherwise show all user projects
    if current_project_id:
        # Validate that the current project is still accessible to the user
        try:
            current_project = user_projects.get(id=current_project_id)
            traces = Trace.objects.filter(project=current_project).order_by("-started_at")
        except Project.DoesNotExist:
            # Current project is no longer accessible, clear it from session
            del request.session["current_project_id"]
            current_project = None
            traces = Trace.objects.filter(project__in=user_projects).order_by("-started_at")
    else:
        current_project = None
        traces = Trace.objects.filter(project__in=user_projects).order_by("-started_at")

    # Calculate durations for each trace
    traces_with_duration = []
    for trace in traces:
        duration = format_duration(trace.started_at, trace.ended_at)
        traces_with_duration.append(
            {
                "trace": trace,
                "duration": duration,
            }
        )

    context = {
        "traces_with_duration": traces_with_duration,
        "current_project": current_project,
        "user_projects": user_projects,
    }
    return render(request, "traces/list.html", context)


@login_required
def trace_list_clear_filter(request):
    """Clear the current project filter and show all traces."""
    if "current_project_id" in request.session:
        del request.session["current_project_id"]
    return redirect("traces:list")


@login_required
def trace_detail(request, trace_id):
    """View trace details and all associated spans."""
    trace = get_object_or_404(Trace, id=trace_id)

    # Check access - user must have access to the trace's project
    user_projects = get_user_projects(request.user)
    if trace.project not in user_projects:
        messages.error(request, "You do not have access to this trace.")
        return redirect("traces:list")

    # Get all spans for this trace, ordered by start_time
    spans = Span.objects.filter(trace=trace).order_by("start_time")

    # Calculate durations for trace and spans
    trace_duration = format_duration(trace.started_at, trace.ended_at)
    spans_with_duration = []
    for span in spans:
        span_duration = format_duration(span.start_time, span.end_time)

        # Format JSON fields for display
        finished_reasons_json = (
            json.dumps(span.finished_reasons, indent=2)
            if span.finished_reasons
            else None
        )
        system_instructions_json = (
            json.dumps(span.system_instructions, indent=2)
            if span.system_instructions
            else None
        )
        input_messages_json = (
            json.dumps(span.input_messages, indent=2) if span.input_messages else None
        )
        output_messages_json = (
            json.dumps(span.output_messages, indent=2) if span.output_messages else None
        )

        spans_with_duration.append(
            {
                "span": span,
                "duration": span_duration,
                "finished_reasons_json": finished_reasons_json,
                "system_instructions_json": system_instructions_json,
                "input_messages_json": input_messages_json,
                "output_messages_json": output_messages_json,
            }
        )

    # Get current project from session for context
    current_project_id = request.session.get("current_project_id")
    current_project = None
    if current_project_id:
        user_projects = get_user_projects(request.user)
        try:
            current_project = user_projects.get(id=current_project_id)
        except Project.DoesNotExist:
            pass

    context = {
        "trace": trace,
        "trace_duration": trace_duration,
        "spans_with_duration": spans_with_duration,
        "current_project": current_project,
    }
    return render(request, "traces/detail.html", context)
