from django import forms
from .models import Comment  # Убедитесь, что модель Comment импортирована

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text', 'parent')
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ваш комментарий...'
            })
        }