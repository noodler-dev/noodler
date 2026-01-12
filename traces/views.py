from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from projects.views import get_user_projects
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
    """List all traces the user has access to (via their projects)."""
    user_projects = get_user_projects(request.user)
    traces = Trace.objects.filter(project__in=user_projects).order_by("-started_at")

    # Calculate durations for each trace
    traces_with_duration = []
    for trace in traces:
        duration = format_duration(trace.started_at, trace.ended_at)
        traces_with_duration.append({
            "trace": trace,
            "duration": duration,
        })

    context = {
        "traces_with_duration": traces_with_duration,
    }
    return render(request, "traces/list.html", context)


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
        spans_with_duration.append({
            "span": span,
            "duration": span_duration,
        })

    context = {
        "trace": trace,
        "trace_duration": trace_duration,
        "spans_with_duration": spans_with_duration,
    }
    return render(request, "traces/detail.html", context)
