from django import forms
from .models import FailureMode


class DatasetCreateForm(forms.Form):
    """Form for creating a new dataset."""

    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Enter a name for your dataset.",
    )
    num_traces = forms.IntegerField(
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        help_text="Number of traces to randomly sample.",
    )

    def __init__(self, *args, available_count=None, **kwargs):
        """Initialize form with available trace count for validation."""
        super().__init__(*args, **kwargs)
        self.available_count = available_count
        if available_count is not None and available_count > 0:
            self.fields["num_traces"].widget.attrs["max"] = str(available_count)

    def clean_num_traces(self):
        """Validate that num_traces doesn't exceed available traces."""
        num_traces = self.cleaned_data.get("num_traces")
        if num_traces is None:
            return num_traces

        if self.available_count is not None:
            if self.available_count == 0:
                raise forms.ValidationError(
                    "No traces available in this project. Please add traces before creating a dataset."
                )
            if num_traces > self.available_count:
                raise forms.ValidationError(
                    f"Requested {num_traces} traces, but only {self.available_count} available."
                )

        return num_traces


class FailureModeForm(forms.Form):
    """Form for creating or editing a failure mode category."""

    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Enter a name for this failure mode category.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": "4",
                "placeholder": "Optional description of this failure mode...",
            }
        ),
    )

    def __init__(self, *args, project=None, instance=None, **kwargs):
        """Initialize form with project for validation."""
        super().__init__(*args, **kwargs)
        self.project = project
        self.instance = instance
        if instance:
            self.fields["name"].initial = instance.name
            self.fields["description"].initial = instance.description

    def clean_name(self):
        """Validate that name is unique within project."""
        name = self.cleaned_data.get("name")
        if not name:
            return name

        if self.project:
            # Check for existing failure mode with same name in project
            existing = FailureMode.objects.filter(
                project=self.project, name=name
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing.exists():
                raise forms.ValidationError(
                    f'A failure mode with the name "{name}" already exists in this project.'
                )

        return name


class AnnotationForm(forms.Form):
    """Form for annotating a trace."""

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": "8",
                "placeholder": "Enter your notes about what needs improvement, fixing, or avoiding...",
            }
        ),
    )
    failure_modes = forms.ModelMultipleChoiceField(
        queryset=FailureMode.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        help_text="Select failure mode categories for this annotation.",
    )

    def __init__(self, *args, project=None, initial_failure_modes=None, **kwargs):
        """Initialize form with project-specific failure modes."""
        super().__init__(*args, **kwargs)
        if project:
            self.fields["failure_modes"].queryset = FailureMode.objects.filter(
                project=project
            ).order_by("name")
        if initial_failure_modes:
            self.fields["failure_modes"].initial = initial_failure_modes
