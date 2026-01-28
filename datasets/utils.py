from .models import Dataset
from traces.models import Trace


def create_dataset_from_traces(project, name, num_traces):
    """
    Create a dataset by randomly sampling traces from a project.
    
    Args:
        project: The Project instance to sample traces from
        name: Name for the dataset
        num_traces: Number of traces to randomly sample
        
    Returns:
        Dataset instance with associated traces
    """
    # Get available traces for the project
    available_traces = Trace.objects.filter(project=project)
    available_count = available_traces.count()
    
    # Determine how many traces to actually sample
    actual_num_traces = min(num_traces, available_count)
    
    # Randomly sample traces
    sampled_traces = available_traces.order_by('?')[:actual_num_traces]
    
    # Create the dataset
    dataset = Dataset.objects.create(name=name, project=project)
    
    # Associate traces via M2M
    dataset.traces.set(sampled_traces)
    
    return dataset

