from django import forms

class PDFUploadForm(forms.Form):
    file = forms.FileField(label='Upload your resume PDF')
