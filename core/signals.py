"""
Signal handlers for core application
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """Handle user creation events"""
    if created:
        from activity_logs.services import log_audit_event
        log_audit_event(
            action='user_created',
            model_name='User',
            object_id=instance.id,
            details={'username': instance.username},
            user=instance
        )


@receiver(pre_delete, sender=User)
def user_deletion_handler(sender, instance, **kwargs):
    """Handle user deletion events"""
    from activity_logs.services import log_audit_event
    log_audit_event(
        action='user_deleted',
        model_name='User',
        object_id=instance.id,
        details={'username': instance.username},
        user=instance
    )