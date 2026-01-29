import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from projects.decorators import require_project_access
from traces.models import Trace, Span
from traces.utils import format_duration, extract_conversation_messages
from .models import Dataset, Annotation
from .forms import DatasetCreateForm, AnnotationForm
from .utils import create_dataset_from_traces


@login_required
@require_project_access(require_current_project=True)
def dataset_list(request):
    """List all datasets for the current project."""
    datasets = Dataset.objects.filter(project=request.current_project)

    # Add trace count to each dataset
    datasets_with_counts = [
        {"dataset": dataset, "trace_count": dataset.trace_count} for dataset in datasets
    ]

    context = {
        "datasets_with_counts": datasets_with_counts,
        "current_project": request.current_project,
    }
    return render(request, "datasets/list.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_http_methods(["GET", "POST"])
def dataset_create(request):
    """Create a new dataset by randomly sampling traces."""
    # Get available trace count for the project
    available_count = request.current_project.get_available_trace_count()

    if request.method == "POST":
        form = DatasetCreateForm(request.POST, available_count=available_count)
        if form.is_valid():
            name = form.cleaned_data["name"]
            num_traces = form.cleaned_data["num_traces"]

            # Create the dataset
            result = create_dataset_from_traces(
                request.current_project, name, num_traces
            )

            if result.was_truncated:
                messages.warning(
                    request,
                    f"Dataset created with {result.actual_count} traces (requested {result.requested_count}, but only {result.available_count} available).",
                )
            else:
                messages.success(
                    request,
                    f'Dataset "{result.dataset.name}" created successfully with {result.actual_count} traces.',
                )

            return redirect("datasets:detail", dataset_uid=result.dataset.uid)
    else:
        form = DatasetCreateForm(available_count=available_count)

    context = {
        "form": form,
        "current_project": request.current_project,
        "available_count": available_count,
    }
    return render(request, "datasets/new.html", context)


@login_required
@require_project_access(require_current_project=True)
def dataset_detail(request, dataset_uid):
    """View dataset details and all associated traces."""
    dataset = get_object_or_404(Dataset, uid=dataset_uid)

    # Check access - user must have access to the dataset's project
    if dataset.project not in request.user_projects:
        messages.error(request, "You do not have access to this dataset.")
        return redirect("projects:list")

    # Ensure the dataset belongs to the current project
    if not dataset.belongs_to_project(request.current_project):
        messages.error(request, "This dataset does not belong to the current project.")
        return redirect("datasets:list")

    # Get all traces for this dataset, ordered by started_at
    traces = dataset.get_traces_ordered()

    context = {
        "dataset": dataset,
        "traces": traces,
        "trace_count": dataset.trace_count,
        "current_project": request.current_project,
    }
    return render(request, "datasets/detail.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_POST
def dataset_delete(request, dataset_uid):
    """Delete a dataset (POST-only)."""
    dataset = get_object_or_404(Dataset, uid=dataset_uid)

    # Check access
    if dataset.project not in request.user_projects:
        messages.error(request, "You do not have access to this dataset.")
        return redirect("projects:list")

    # Ensure the dataset belongs to the current project
    if not dataset.belongs_to_project(request.current_project):
        messages.error(request, "This dataset does not belong to the current project.")
        return redirect("datasets:list")

    dataset_name = dataset.name
    dataset.delete()

    messages.success(request, f'Dataset "{dataset_name}" deleted successfully.')
    return redirect("datasets:list")


@login_required
@require_project_access(require_current_project=True)
@require_http_methods(["GET", "POST"])
def annotation_view(request, dataset_uid, trace_uid):
    """View for annotating a trace within a dataset."""
    dataset = get_object_or_404(Dataset, uid=dataset_uid)
    trace = get_object_or_404(Trace, uid=trace_uid)

    # Check access - user must have access to the dataset's project
    if dataset.project not in request.user_projects:
        messages.error(request, "You do not have access to this dataset.")
        return redirect("projects:list")

    # Ensure the dataset belongs to the current project
    if not dataset.belongs_to_project(request.current_project):
        messages.error(request, "This dataset does not belong to the current project.")
        return redirect("datasets:list")

    # Verify trace belongs to dataset
    if not dataset.traces.filter(uid=trace_uid).exists():
        messages.error(request, "This trace does not belong to the dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get all traces in dataset (ordered)
    all_traces = list(dataset.get_traces_ordered())
    
    # Find current trace index
    try:
        current_index = next(i for i, t in enumerate(all_traces) if t.uid == trace_uid)
    except StopIteration:
        messages.error(request, "Trace not found in dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get next/previous trace UIDs
    prev_trace_uid = all_traces[current_index - 1].uid if current_index > 0 else None
    next_trace_uid = all_traces[current_index + 1].uid if current_index < len(all_traces) - 1 else None

    # Get existing annotation if any
    annotation = None
    try:
        annotation = Annotation.objects.get(trace=trace, dataset=dataset)
    except Annotation.DoesNotExist:
        pass

    # Calculate progress
    total_traces = len(all_traces)
    annotated_count = Annotation.objects.filter(dataset=dataset).count()
    current_trace_number = current_index + 1

    if request.method == "POST":
        form = AnnotationForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data["notes"]
            
            # Get or create annotation
            annotation, created = Annotation.objects.get_or_create(
                trace=trace,
                dataset=dataset,
                defaults={"notes": notes}
            )
            
            if not created:
                # Update existing annotation
                annotation.notes = notes
                annotation.save()
            
            messages.success(request, "Annotation saved successfully.")
            
            # Redirect to next trace or back to dataset detail
            if next_trace_uid:
                return redirect("datasets:annotate", dataset_uid=dataset_uid, trace_uid=next_trace_uid)
            else:
                messages.info(request, "You've finished annotating all traces in this dataset.")
                return redirect("datasets:detail", dataset_uid=dataset_uid)
    else:
        # GET request - populate form with existing annotation if available
        initial_data = {}
        if annotation:
            initial_data["notes"] = annotation.notes
        form = AnnotationForm(initial=initial_data)

    # Get all spans for this trace, ordered by start_time
    spans = Span.objects.filter(trace=trace).order_by("start_time")

    # Extract conversation messages
    conversation_messages = extract_conversation_messages(spans)

    # Calculate durations for trace and spans
    trace_duration = format_duration(trace.started_at, trace.ended_at)

    # Calculate total tokens across all spans
    total_input_tokens = sum(span.input_tokens or 0 for span in spans)
    total_output_tokens = sum(span.output_tokens or 0 for span in spans)
    total_tokens = total_input_tokens + total_output_tokens

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
        "dataset": dataset,
        "trace": trace,
        "trace_duration": trace_duration,
        "spans_with_duration": spans_with_duration,
        "conversation_messages": conversation_messages,
        "total_tokens": total_tokens,
        "form": form,
        "current_trace_number": current_trace_number,
        "total_traces": total_traces,
        "annotated_count": annotated_count,
        "prev_trace_uid": prev_trace_uid,
        "next_trace_uid": next_trace_uid,
        "current_project": request.current_project,
    }
    return render(request, "datasets/annotate.html", context)
