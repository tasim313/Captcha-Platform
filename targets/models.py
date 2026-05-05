"""
Target website models for CAPTCHA solving jobs.
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class TargetWebsite(models.Model):
    """
    Target website configuration for CAPTCHA solving.
    """
    
    class CaptchaType(models.TextChoices):
        RECAPTCHA_V2 = 'recaptcha_v2', _('reCAPTCHA v2')
        RECAPTCHA_V3 = 'recaptcha_v3', _('reCAPTCHA v3')
        RECAPTCHA_ENTERPRISE = 'recaptcha_enterprise', _('reCAPTCHA Enterprise')
        HCAPTCHA = 'hcaptcha', _('hCaptcha')
        TURNSTILE = 'turnstile', _('Cloudflare Turnstile')
        FUNCAPTCHA = 'funcaptcha', _('FunCaptcha')
        IMAGE = 'image', _('Image CAPTCHA')
        GEETEST = 'geetest', _('GeeTest')
        TEXT = 'text', _('Text CAPTCHA')
    
    # Identification
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Website Name'),
        help_text=_('Internal name for this target')
    )
    url = models.URLField(
        verbose_name=_('Website URL'),
        help_text=_('Base URL of the target website')
    )
    
    # CAPTCHA Configuration
    captcha_type = models.CharField(
        max_length=30,
        choices=CaptchaType.choices,
        verbose_name=_('CAPTCHA Type')
    )
    site_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Site Key'),
        help_text=_('CAPTCHA site key (for reCAPTCHA, hCaptcha, etc.)')
    )
    captcha_selector = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('CAPTCHA Selector'),
        help_text=_('CSS selector for CAPTCHA iframe/element')
    )
    submit_selector = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Submit Button Selector'),
        help_text=_('CSS selector for submit button after solving')
    )
    
    # Advanced Configuration
    is_invisible = models.BooleanField(
        default=False,
        verbose_name=_('Invisible CAPTCHA'),
        help_text=_('Set if CAPTCHA is invisible type')
    )
    enterprise_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Enterprise Payload'),
        help_text=_('Additional payload for enterprise CAPTCHAs')
    )
    action = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Action (reCAPTCHA v3)'),
        help_text=_('Action name for reCAPTCHA v3')
    )
    min_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Minimum Score (reCAPTCHA v3)'),
        help_text=_('Minimum score threshold (0.0 - 1.0)')
    )
    
    # Browser Settings
    custom_user_agent = models.TextField(
        blank=True,
        verbose_name=_('Custom User Agent'),
        help_text=_('Custom user agent string (optional)')
    )
    extra_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Extra Headers'),
        help_text=_('Additional HTTP headers to send')
    )
    wait_selectors = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Wait Selectors'),
        help_text=_('CSS selectors to wait for before solving')
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        db_index=True
    )
    
    # Audit
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_target_websites',
        verbose_name=_('Created By')
    )
    
    class Meta:
        verbose_name = _('Target Website')
        verbose_name_plural = _('Target Websites')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['captcha_type', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    models.Q(captcha_type__in=['recaptcha_v2', 'recaptcha_v3', 'recaptcha_enterprise', 'hcaptcha', 'turnstile', 'funcaptcha']) &
                    ~models.Q(site_key='')
                ) | models.Q(captcha_type__in=['image', 'text', 'geetest']),
                name='site_key_required_for_token_captchas',
                violation_error_message=_('Site key is required for token-based CAPTCHAs')
            ),
            models.CheckConstraint(
                check=models.Q(min_score__isnull=True) | models.Q(min_score__gte=0, min_score__lte=1),
                name='min_score_range_check',
                violation_error_message=_('Minimum score must be between 0.0 and 1.0')
            ),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_captcha_type_display()})"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)
    
    @property
    def requires_site_key(self) -> bool:
        """Check if this CAPTCHA type requires a site key."""
        return self.captcha_type in [
            self.CaptchaType.RECAPTCHA_V2,
            self.CaptchaType.RECAPTCHA_V3,
            self.CaptchaType.RECAPTCHA_ENTERPRISE,
            self.CaptchaType.HCAPTCHA,
            self.CaptchaType.TURNSTILE,
            self.CaptchaType.FUNCAPTCHA,
        ]


class ProxyConfiguration(models.Model):
    """
    Proxy configuration for use in jobs.
    """
    
    class ProxyType(models.TextChoices):
        HTTP = 'http', _('HTTP')
        HTTPS = 'https', _('HTTPS')
        SOCKS4 = 'socks4', _('SOCKS4')
        SOCKS5 = 'socks5', _('SOCKS5')
    
    class RotationStrategy(models.TextChoices):
        SEQUENTIAL = 'sequential', _('Sequential')
        RANDOM = 'random', _('Random')
        LEAST_USED = 'least_used', _('Least Used')
    # Identification
    name = models.CharField(
        max_length=255,
        verbose_name=_('Configuration Name')
    )
    
    # Single Proxy Settings
    proxy_type = models.CharField(
        max_length=10,
        choices=ProxyType.choices,
        default=ProxyType.HTTP,
        verbose_name=_('Proxy Type')
    )
    host = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Host'),
        help_text=_('Proxy host (leave blank if using proxy list)')
    )
    port = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Port'),
        help_text=_('Proxy port')
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Username')
    )
    password = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Password')
    )
    
    # Proxy List (for rotation)
    proxy_list = models.TextField(
        blank=True,
        verbose_name=_('Proxy List'),
        help_text=_('One proxy per line: host:port or user:pass@host:port')
    )
    rotation_strategy = models.CharField(
        max_length=20,
        choices=RotationStrategy.choices,
        default=RotationStrategy.RANDOM,
        verbose_name=_('Rotation Strategy')
    )
    
    # Settings
    timeout = models.PositiveIntegerField(
        default=30,
        verbose_name=_('Timeout (seconds)')
    )
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Max Retries per Proxy')
    )
    fail_threshold = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Fail Threshold'),
        help_text=_('Disable proxy after this many failures')
    )
    cooldown_seconds = models.PositiveIntegerField(
        default=300,
        verbose_name=_('Cooldown (seconds)'),
        help_text=_('Cooldown period after reaching fail threshold')
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    
    class Meta:
        verbose_name = _('Proxy Configuration')
        verbose_name_plural = _('Proxy Configurations')
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return self.name
    
    def get_proxy_url(self, index: int = 0) -> str:
        """Get a proxy URL from the configuration."""
        if self.proxy_list:
            proxies = [p.strip() for p in self.proxy_list.split('\n') if p.strip()]
            if proxies:
                proxy = proxies[index % len(proxies)]
                if '@' not in proxy and self.username:
                    proxy = f"{self.username}:{self.password}@{proxy}"
                return f"{self.proxy_type}://{proxy}"
        
        if self.host and self.port:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"{self.proxy_type}://{auth}{self.host}:{self.port}"
        
        return ''
    
    def get_all_proxy_urls(self) -> list[str]:
        """Get all proxy URLs from this configuration."""
        urls = []
        
        if self.proxy_list:
            for line in self.proxy_list.split('\n'):
                line = line.strip()
                if line:
                    if '@' not in line and self.username:
                        line = f"{self.username}:{self.password}@{line}"
                    urls.append(f"{self.proxy_type}://{line}")
        elif self.host and self.port:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            urls.append(f"{self.proxy_type}://{auth}{self.host}:{self.port}")
        
        return urls