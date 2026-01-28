from dataclasses import dataclass
from .models import Dataset
from traces.models import Trace


@dataclass
class DatasetCreationResult:
    """Result object returned from dataset creation."""

    dataset: Dataset
    requested_count: int
    actual_count: int
    available_count: int

    @property
    def was_truncated(self):
        """Check if fewer traces were sampled than requested."""
        return self.actual_count < self.requested_count


def create_dataset_from_traces(project, name, num_traces):
    """
    Create a dataset by randomly sampling traces from a project.

    Args:
        project: The Project instance to sample traces from
        name: Name for the dataset
        num_traces: Number of traces to randomly sample

    Returns:
        DatasetCreationResult containing the dataset and metadata
    """
    # Get available traces for the project
    available_traces = Trace.objects.filter(project=project)
    available_count = available_traces.count()

    # Determine how many traces to actually sample
    actual_num_traces = min(num_traces, available_count)

    # Randomly sample traces
    sampled_traces = available_traces.order_by("?")[:actual_num_traces]

    # Create the dataset
    dataset = Dataset.objects.create(name=name, project=project)

    # Associate traces via M2M
    dataset.traces.set(sampled_traces)

    return DatasetCreationResult(
        dataset=dataset,
        requested_count=num_traces,
        actual_count=actual_num_traces,
        available_count=available_count,
    )
