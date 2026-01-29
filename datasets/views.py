import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from projects.decorators import require_project_access
from traces.models import Trace, Span
from traces.utils import extract_conversation_messages
from .models import Dataset, Annotation, FailureMode
from .forms import DatasetCreateForm, AnnotationForm, FailureModeForm
from .utils import create_dataset_from_traces
from .llm_utils import categorize_annotations
from .decorators import validate_dataset_access, validate_failure_mode_access

logger = logging.getLogger(__name__)


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
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    # Get all traces for this dataset, ordered by started_at
    traces = dataset.get_traces_ordered()

    # Get first unannotated trace for annotation entry point
    first_unannotated_trace = dataset.get_first_unannotated_trace()
    # Get first trace for review mode (when all are annotated)
    first_trace = dataset.get_first_trace() if not first_unannotated_trace else None

    # Get annotations count for categorization
    annotations_count = (
        Annotation.objects.filter(dataset=dataset).exclude(notes="").count()
    )
    failure_modes_count = FailureMode.objects.filter(project=dataset.project).count()

    context = {
        "dataset": dataset,
        "traces": traces,
        "trace_count": dataset.trace_count,
        "first_unannotated_trace": first_unannotated_trace,
        "first_trace": first_trace,
        "unannotated_count": dataset.get_unannotated_count(),
        "annotations_count": annotations_count,
        "failure_modes_count": failure_modes_count,
        "current_project": request.current_project,
    }
    return render(request, "datasets/detail.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_POST
def dataset_delete(request, dataset_uid):
    """Delete a dataset (POST-only)."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    dataset_name = dataset.name
    dataset.delete()

    messages.success(request, f'Dataset "{dataset_name}" deleted successfully.')
    return redirect("datasets:list")


@login_required
@require_project_access(require_current_project=True)
@require_http_methods(["GET", "POST"])
def annotation_view(request, dataset_uid, trace_uid):
    """View for annotating a trace within a dataset."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    trace = get_object_or_404(Trace, uid=trace_uid)

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
        form = AnnotationForm(request.POST, project=dataset.project)
        if form.is_valid():
            notes = form.cleaned_data.get("notes", "")
            failure_modes = form.cleaned_data.get("failure_modes", [])

            # Save annotation (even if empty, marks trace as reviewed)
            annotation = Annotation.save_notes(trace, dataset, notes)

            # Update failure mode associations
            annotation.failure_modes.set(failure_modes)

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
        initial_failure_modes = None
        if annotation:
            initial_data["notes"] = annotation.notes
            initial_failure_modes = list(
                annotation.failure_modes.values_list("id", flat=True)
            )
        form = AnnotationForm(
            initial=initial_data,
            project=dataset.project,
            initial_failure_modes=initial_failure_modes,
        )

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


@login_required
@require_project_access(require_current_project=True)
@require_POST
def categorize_dataset(request, dataset_uid):
    """Generate failure mode categories from dataset annotations using LLM."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    # Get annotations with non-whitespace notes (same criteria as categorize_annotations)
    all_annotations = Annotation.objects.filter(dataset=dataset)
    annotations_with_content = [
        a for a in all_annotations if a.notes and a.notes.strip()
    ]

    if not annotations_with_content:
        messages.warning(
            request,
            "No annotations with notes found. Please add notes to your annotations first.",
        )
        return redirect("datasets:detail", dataset_uid=dataset_uid)

    try:
        # Call LLM to categorize annotations
        categories_data = categorize_annotations(annotations_with_content)

        if not categories_data:
            messages.warning(
                request,
                "No categories were generated from the annotations. Please try again.",
            )
            return redirect("datasets:detail", dataset_uid=dataset_uid)

        # Create failure modes and associate with annotations
        created_count = 0
        with transaction.atomic():
            for cat_data in categories_data:
                name = cat_data["name"]
                description = cat_data.get("description", "")

                # Get or create failure mode (unique per project)
                failure_mode, created = FailureMode.objects.get_or_create(
                    project=dataset.project,
                    name=name,
                    defaults={"description": description},
                )

                if created:
                    created_count += 1
                else:
                    # Update description if it was empty
                    if not failure_mode.description and description:
                        failure_mode.description = description
                        failure_mode.save()

        messages.success(
            request,
            f"Successfully generated {created_count} new failure mode categories. "
            f"Total categories: {len(categories_data)}. "
            f"You can now manually assign these categories to annotations.",
        )

    except ValueError as e:
        logger.error(f"Error categorizing dataset: {e}")
        messages.error(
            request,
            f"Failed to generate categories: {str(e)}. Please check your OpenAI API key and try again.",
        )
    except Exception as e:
        logger.error(f"Unexpected error categorizing dataset: {e}", exc_info=True)
        messages.error(
            request,
            "An unexpected error occurred while generating categories. Please try again.",
        )

    return redirect("datasets:detail", dataset_uid=dataset_uid)


@login_required
@require_project_access(require_current_project=True)
def category_list(request, dataset_uid):
    """List all failure modes for the dataset's project."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    # Get all failure modes for the project
    failure_modes = FailureMode.objects.filter(project=dataset.project).order_by("name")

    # Get annotation counts for each failure mode
    failure_modes_with_counts = []
    for fm in failure_modes:
        count = Annotation.objects.filter(dataset=dataset, failure_modes=fm).count()
        failure_modes_with_counts.append({"failure_mode": fm, "count": count})

    context = {
        "dataset": dataset,
        "failure_modes_with_counts": failure_modes_with_counts,
        "current_project": request.current_project,
    }
    return render(request, "datasets/categories.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_http_methods(["GET", "POST"])
def category_create(request, dataset_uid):
    """Create a new failure mode category."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    if request.method == "POST":
        form = FailureModeForm(request.POST, project=dataset.project)
        if form.is_valid():
            failure_mode = FailureMode.objects.create(
                project=dataset.project,
                name=form.cleaned_data["name"],
                description=form.cleaned_data.get("description", ""),
            )
            messages.success(
                request, f'Failure mode "{failure_mode.name}" created successfully.'
            )
            return redirect("datasets:categories", dataset_uid=dataset_uid)
    else:
        form = FailureModeForm(project=dataset.project)

    context = {
        "dataset": dataset,
        "form": form,
        "current_project": request.current_project,
    }
    return render(request, "datasets/category_form.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_http_methods(["GET", "POST"])
def category_edit(request, dataset_uid, category_uid):
    """Edit an existing failure mode category."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    failure_mode, error_response = validate_failure_mode_access(
        request, dataset, category_uid
    )
    if error_response:
        return error_response

    if request.method == "POST":
        form = FailureModeForm(
            request.POST, project=dataset.project, instance=failure_mode
        )
        if form.is_valid():
            failure_mode.name = form.cleaned_data["name"]
            failure_mode.description = form.cleaned_data.get("description", "")
            failure_mode.save()
            messages.success(
                request, f'Failure mode "{failure_mode.name}" updated successfully.'
            )
            return redirect("datasets:categories", dataset_uid=dataset_uid)
    else:
        form = FailureModeForm(project=dataset.project, instance=failure_mode)

    context = {
        "dataset": dataset,
        "failure_mode": failure_mode,
        "form": form,
        "current_project": request.current_project,
    }
    return render(request, "datasets/category_form.html", context)


@login_required
@require_project_access(require_current_project=True)
@require_POST
def category_delete(request, dataset_uid, category_uid):
    """Delete a failure mode category."""
    dataset, error_response = validate_dataset_access(request, dataset_uid)
    if error_response:
        return error_response

    failure_mode, error_response = validate_failure_mode_access(
        request, dataset, category_uid
    )
    if error_response:
        return error_response

    failure_mode_name = failure_mode.name
    failure_mode.delete()

    messages.success(
        request, f'Failure mode "{failure_mode_name}" deleted successfully.'
    )
    return redirect("datasets:categories", dataset_uid=dataset_uid)
