from django import forms


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
