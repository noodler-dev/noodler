import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from projects.decorators import require_project_access
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
@require_project_access(require_current_project=True)
def trace_list(request):
    """List traces for the current project (from session). Requires a project to be selected."""
    # Filter traces by current project only
    traces = Trace.objects.filter(project=request.current_project).order_by("-started_at")

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
        "current_project": request.current_project,
        "user_projects": request.user_projects,
    }
    return render(request, "traces/list.html", context)


@login_required
@require_project_access(require_current_project=True)
def trace_detail(request, trace_id):
    """View trace details and all associated spans."""
    trace = get_object_or_404(Trace, id=trace_id)

    # Check access - user must have access to the trace's project
    if trace.project not in request.user_projects:
        messages.error(request, "You do not have access to this trace.")
        return redirect("projects:list")

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

    context = {
        "trace": trace,
        "trace_duration": trace_duration,
        "spans_with_duration": spans_with_duration,
        "current_project": request.current_project,
    }
    return render(request, "traces/detail.html", context)
