from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from projects.decorators import require_project_access
from traces.models import Trace, Span
from traces.utils import extract_conversation_messages
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

    # Get first unannotated trace for annotation entry point
    first_unannotated_trace = dataset.get_first_unannotated_trace()

    context = {
        "dataset": dataset,
        "traces": traces,
        "trace_count": dataset.trace_count,
        "first_unannotated_trace": first_unannotated_trace,
        "unannotated_count": dataset.get_unannotated_count(),
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

    # Get annotated trace IDs (used for navigation and progress)
    annotated_trace_ids = set(
        Annotation.objects.filter(dataset=dataset).values_list("trace_id", flat=True)
    )

    # Find current trace index
    try:
        current_index = next(i for i, t in enumerate(all_traces) if t.uid == trace_uid)
    except StopIteration:
        messages.error(request, "Trace not found in dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get next/previous trace UIDs
    # Previous: go to previous trace (even if annotated, so users can review)
    prev_trace_uid = all_traces[current_index - 1].uid if current_index > 0 else None

    # Next: skip to next unannotated trace
    next_unannotated_trace = None
    for t in all_traces[current_index + 1 :]:
        if t.id not in annotated_trace_ids:
            next_unannotated_trace = t
            break

    next_trace_uid = next_unannotated_trace.uid if next_unannotated_trace else None

    # Get existing annotation if any
    annotation = None
    try:
        annotation = Annotation.objects.get(trace=trace, dataset=dataset)
    except Annotation.DoesNotExist:
        pass

    # Calculate progress
    total_traces = len(all_traces)
    annotated_count = len(annotated_trace_ids)
    unannotated_count = dataset.get_unannotated_count()

    # Calculate position among unannotated traces
    unannotated_traces = [t for t in all_traces if t.id not in annotated_trace_ids]
    try:
        current_unannotated_index = next(
            i for i, t in enumerate(unannotated_traces) if t.uid == trace_uid
        )
        current_unannotated_number = current_unannotated_index + 1
    except StopIteration:
        # Current trace is already annotated
        current_unannotated_number = None

    current_trace_number = current_index + 1

    if request.method == "POST":
        form = AnnotationForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data.get("notes", "").strip()

            # Get or create annotation with notes (even if empty, marks trace as reviewed)
            annotation, created = Annotation.objects.get_or_create(
                trace=trace, dataset=dataset, defaults={"notes": notes}
            )

            if not created:
                # Update existing annotation
                annotation.notes = notes
                annotation.save()

            if notes:
                messages.success(request, "Annotation saved successfully.")
            else:
                messages.success(request, "Trace marked as reviewed.")

            # Redirect to next trace or back to dataset detail
            if next_trace_uid:
                return redirect(
                    "datasets:annotate",
                    dataset_uid=dataset_uid,
                    trace_uid=next_trace_uid,
                )
            else:
                messages.info(
                    request, "You've finished annotating all traces in this dataset."
                )
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

    context = {
        "dataset": dataset,
        "trace": trace,
        "conversation_messages": conversation_messages,
        "form": form,
        "current_trace_number": current_trace_number,
        "total_traces": total_traces,
        "annotated_count": annotated_count,
        "unannotated_count": unannotated_count,
        "current_unannotated_number": current_unannotated_number,
        "prev_trace_uid": prev_trace_uid,
        "next_trace_uid": next_trace_uid,
        "current_project": request.current_project,
    }
    return render(request, "datasets/annotate.html", context)
