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
    # Get first trace for review mode (when all are annotated)
    first_trace = dataset.get_first_trace() if not first_unannotated_trace else None

    context = {
        "dataset": dataset,
        "traces": traces,
        "trace_count": dataset.trace_count,
        "first_unannotated_trace": first_unannotated_trace,
        "first_trace": first_trace,
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
    if not dataset.contains_trace(trace):
        messages.error(request, "This trace does not belong to the dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get navigation information
    navigation = dataset.get_annotation_navigation(trace)
    if navigation is None:
        messages.error(request, "Trace not found in dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get progress information
    progress = dataset.get_annotation_progress(trace)
    if progress is None:
        messages.error(request, "Trace not found in dataset.")
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    # Get existing annotation if any
    annotation = Annotation.get_for_trace_dataset(trace, dataset)

    if request.method == "POST":
        form = AnnotationForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data.get("notes", "")

            # Save annotation (even if empty, marks trace as reviewed)
            Annotation.save_notes(trace, dataset, notes)

            # Redirect to next trace or back to dataset detail
            if navigation["next_trace_uid"]:
                return redirect(
                    "datasets:annotate",
                    dataset_uid=dataset_uid,
                    trace_uid=navigation["next_trace_uid"],
                )
            else:
                if navigation["all_annotated"]:
                    messages.info(request, "You've finished reviewing all traces.")
                else:
                    messages.info(
                        request,
                        "You've finished annotating all traces in this dataset.",
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
        "current_project": request.current_project,
        **progress,  # Unpack progress dict
        **navigation,  # Unpack navigation dict
    }
    return render(request, "datasets/annotate.html", context)
