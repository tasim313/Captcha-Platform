"""
Models for target website configuration
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.mixins import TimestampMixin, AuditMixin


class CaptchaType(models.TextChoices):
    """Supported CAPTCHA types"""
    RECAPTCHA_V2 = 'recaptcha_v2', _('reCAPTCHA v2')
    RECAPTCHA_V3 = 'recaptcha_v3', _('reCAPTCHA v3')
    HCAPTCHA = 'hcaptcha', _('hCaptcha')
    IMAGE_CAPTCHA = 'image_captcha', _('Image CAPTCHA')
    TURNSTILE = 'turnstile', _('Cloudflare Turnstile')
    FUNCAPTCHA = 'funcaptcha', _('FunCaptcha')
    GEETEST = 'geetest', _('GeeTest')
    TEXT_CAPTCHA = 'text_captcha', _('Text CAPTCHA')


class WebsiteStatus(models.TextChoices):
    """Website status options"""
    ACTIVE = 'active', _('Active')
    INACTIVE = 'inactive', _('Inactive')
    BLOCKED = 'blocked', _('Blocked')
    MAINTENANCE = 'maintenance', _('Under Maintenance')


class TargetWebsite(TimestampMixin, AuditMixin):
    """
    Model representing a target website that requires CAPTCHA solving
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Website Name'),
        help_text=_('Friendly name for the target website')
    )
    
    url = models.URLField(
        max_length=500,
        verbose_name=_('URL'),
        help_text=_('Base URL of the target website')
    )
    
    captcha_type = models.CharField(
        max_length=20,
        choices=CaptchaType.choices,
        verbose_name=_('CAPTCHA Type'),
        help_text=_('Type of CAPTCHA used on this website')
    )
    
    site_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Site Key'),
        help_text=_('CAPTCHA site key (for reCAPTCHA, hCaptcha, etc.)')
    )
    
    page_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Page URL'),
        help_text=_('Specific page URL where CAPTCHA appears (if different from base URL)')
    )
    
    selector = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('CAPTCHA Selector'),
        help_text=_('CSS selector for CAPTCHA element on the page')
    )
    
    submit_selector = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Submit Button Selector'),
        help_text=_('CSS selector for the form submit button')
    )
    
    status = models.CharField(
        max_length=20,
        choices=WebsiteStatus.choices,
        default=WebsiteStatus.ACTIVE,
        verbose_name=_('Status'),
        db_index=True
    )
    
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ('easy', _('Easy')),
            ('medium', _('Medium')),
            ('hard', _('Hard')),
        ],
        default='medium',
        verbose_name=_('Difficulty'),
        help_text=_('Estimated solving difficulty')
    )
    
    avg_solve_time = models.FloatField(
        default=0,
        verbose_name=_('Avg Solve Time (s)'),
        help_text=_('Average time to solve CAPTCHA on this site')
    )
    
    success_rate = models.FloatField(
        default=0,
        verbose_name=_('Success Rate (%)'),
        help_text=_('Success rate for this website')
    )
    
    total_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Attempts')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this website')
    )
    
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Custom Headers'),
        help_text=_('Custom HTTP headers to send with requests')
    )
    
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Extra Data'),
        help_text=_('Additional configuration data as JSON')
    )
    
    class Meta:
        verbose_name = _('Target Website')
        verbose_name_plural = _('Target Websites')
        ordering = ['name']
        indexes = [
            models.Index(fields=['status', 'captcha_type']),
        ]
        unique_together = [['url', 'captcha_type']]
    
    def __str__(self):
        return f"{self.name} ({self.get_captcha_type_display()})"
    
    def update_stats(self, solve_time: float, success: bool):
        """Update website statistics after a solve attempt"""
        self.total_attempts += 1
        
        # Update average solve time (only for successful solves)
        if success and solve_time > 0:
            self.avg_solve_time = (
                (self.avg_solve_time * (self.total_attempts - 1) + solve_time) 
                / self.total_attempts
            )
        
        # Update success rate
        if success:
            self.success_rate = (self.success_rate * (self.total_attempts - 1) + 100) / self.total_attempts
        else:
            self.success_rate = (self.success_rate * (self.total_attempts - 1)) / self.total_attempts
        
        self.save(update_fields=['avg_solve_time', 'success_rate', 'total_attempts'])