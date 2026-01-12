from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from projects.views import get_user_projects
from .models import Trace, Span


@login_required
def trace_list(request):
    """List all traces the user has access to (via their projects)."""
    user_projects = get_user_projects(request.user)
    traces = Trace.objects.filter(project__in=user_projects).order_by("-started_at")

    context = {
        "traces": traces,
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

    context = {
        "trace": trace,
        "spans": spans,
    }
    return render(request, "traces/detail.html", context)
