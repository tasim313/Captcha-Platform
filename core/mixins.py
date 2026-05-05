"""
Reusable mixins for models, views, and services
"""
from django.db import models
from django.utils import timezone


class TimestampMixin(models.Model):
    """
    Abstract mixin that adds created_at and updated_at fields
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Abstract mixin for soft deletion
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Mark record as deleted instead of removing it"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class UUIDPrimaryKeyMixin(models.Model):
    """
    Abstract mixin that uses UUID as primary key
    """
    id = models.UUIDField(primary_key=True, editable=False)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        if not self.id:
            import uuid
            self.id = uuid.uuid4()
        super().save(*args, **kwargs)


class AuditMixin(models.Model):
    """
    Abstract mixin for audit tracking
    """
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    modified_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified'
    )
    
    class Meta:
        abstract = True