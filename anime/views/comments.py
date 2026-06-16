import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models import Anime, Comment
from ..forms import CommentForm
from ..templatetags.time_tags import natural_time

logger = logging.getLogger(__name__)

@login_required
@require_POST
def add_comment(request, pk):
    anime = get_object_or_404(Anime, pk=pk)
    form = CommentForm(request.POST)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.user = request.user
        comment.anime = anime
        
        parent_id = request.POST.get('parent_id')
        if parent_id:
            try:
                comment.parent = Comment.objects.get(id=parent_id)
            except Comment.DoesNotExist:
                pass
        
        comment.save()
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'parent_id': str(comment.parent_id) if comment.parent_id else '',
            'user': comment.user.username,
            'text': comment.text,
            'created_at': natural_time(comment.created_at),
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid form'})

@login_required
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)
        comment.dislikes.remove(request.user)
    return JsonResponse({'likes': comment.likes.count(), 'dislikes': comment.dislikes.count()})

@login_required
def dislike_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user in comment.dislikes.all():
        comment.dislikes.remove(request.user)
    else:
        if request.user in comment.likes.all():
            comment.likes.remove(request.user)
        comment.dislikes.add(request.user)
    return JsonResponse({'likes': comment.likes.count(), 'dislikes': comment.dislikes.count()})
