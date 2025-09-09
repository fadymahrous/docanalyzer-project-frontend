from django import forms
from .models import UploadedFile,LebenslaufMetadata

class UploadedFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ['user', 'filetype', 'filelocation']  # exclude file_address_key
        widgets = {
            'user': forms.HiddenInput(),
        }
class lebenslaufMetadataForm(forms.ModelForm):
    class Meta:
        model = LebenslaufMetadata
        fields = '__all__'  # or specify fields as needed
        widgets = {
            'user': forms.HiddenInput(),
            'file_key': forms.HiddenInput(),
        }
