from django import forms


class Upload1cFileForm(forms.Form):
    uploaded_file = forms.FileField(label='Файл')
    comment = forms.CharField(
        label='Комментарий',
        widget=forms.Textarea(
            attrs={
                'cols': 100,
                'rows': 2,
                'class': 'form-control form-control-sm',
                'placeholder': 'Комментарий',
            }
        ),
        required=False
    )
