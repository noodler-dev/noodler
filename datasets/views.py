from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from projects.decorators import require_project_access
from .models import Dataset
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
        name = request.POST.get("name", "").strip()
        num_traces_str = request.POST.get("num_traces", "").strip()

        if not name:
            messages.error(request, "Dataset name is required.")
            return render(
                request,
                "datasets/new.html",
                {
                    "current_project": request.current_project,
                    "available_count": available_count,
                },
            )

        if not num_traces_str:
            messages.error(request, "Number of traces is required.")
            return render(
                request,
                "datasets/new.html",
                {
                    "current_project": request.current_project,
                    "available_count": available_count,
                },
            )

        try:
            num_traces = int(num_traces_str)
            if num_traces <= 0:
                raise ValueError("Number must be positive")
        except ValueError:
            messages.error(request, "Number of traces must be a positive integer.")
            return render(
                request,
                "datasets/new.html",
                {
                    "current_project": request.current_project,
                    "available_count": available_count,
                },
            )

        if available_count == 0:
            messages.error(
                request,
                "No traces available in this project. Please add traces before creating a dataset.",
            )
            return render(
                request,
                "datasets/new.html",
                {
                    "current_project": request.current_project,
                    "available_count": available_count,
                },
            )

        # Create the dataset
        result = create_dataset_from_traces(request.current_project, name, num_traces)

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

    context = {
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
