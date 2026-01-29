from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from .models import Dataset, FailureMode


def validate_dataset_access(request, dataset_uid, error_redirect="datasets:list"):
    """
    Validate that user has access to a dataset and it belongs to current project.

    Args:
        request: Django request object (must have user_projects and current_project set)
        dataset_uid: UUID of the dataset to validate
        error_redirect: URL name to redirect to on error (default: "datasets:list")

    Returns:
        tuple: (dataset, None) if access is valid, (None, HttpResponse) if invalid
    """
    dataset = get_object_or_404(Dataset, uid=dataset_uid)

    # Check access - user must have access to the dataset's project
    if dataset.project not in request.user_projects:
        messages.error(request, "You do not have access to this dataset.")
        return None, redirect("projects:list")

    # Ensure the dataset belongs to the current project
    if not dataset.belongs_to_project(request.current_project):
        messages.error(request, "This dataset does not belong to the current project.")
        return None, redirect(error_redirect)

    return dataset, None


def validate_failure_mode_access(
    request, dataset, failure_mode_uid, error_redirect="datasets:categories"
):
    """
    Validate that user has access to a failure mode and it belongs to the dataset's project.

    Args:
        request: Django request object
        dataset: Dataset object (already validated)
        failure_mode_uid: UUID of the failure mode to validate
        error_redirect: URL name to redirect to on error (default: "datasets:categories")

    Returns:
        tuple: (failure_mode, None) if access is valid, (None, HttpResponse) if invalid
    """
    failure_mode = get_object_or_404(FailureMode, uid=failure_mode_uid)

    # Ensure failure mode belongs to the project
    if not failure_mode.belongs_to_project(dataset.project):
        messages.error(request, "This failure mode does not belong to this project.")
        return None, redirect(error_redirect, dataset_uid=dataset.uid)

    return failure_mode, None
