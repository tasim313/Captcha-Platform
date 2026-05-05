"""
Business logic services for CAPTCHA accounts
"""
import logging
from typing import Optional, List, Dict, Any
from django.utils import timezone

from .models import CaptchaAccount, AccountAuditLog

logger = logging.getLogger(__name__)


class AccountService:
    """
    Service class for CAPTCHA account operations
    """
    
    def update_balance(self, account: CaptchaAccount) -> float:
        """
        Fetch and update account balance from the service API
        
        Args:
            account: CaptchaAccount instance
            
        Returns:
            Updated balance as float
            
        Raises:
            Exception: If balance check fails
        """
        if account.service == '2captcha':
            return self._check_2captcha_balance(account)
        elif account.service == 'anticaptcha':
            return self._check_anticaptcha_balance(account)
        else:
            raise ValueError(f"Unsupported service: {account.service}")
    
    def _check_2captcha_balance(self, account: CaptchaAccount) -> float:
        """Check balance for 2Captcha account"""
        import httpx
        
        url = f"https://2captcha.com/res.php?key={account.api_key}&action=getbalance"
        
        response = httpx.get(url, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}")
        
        result = response.text.strip()
        
        if result.startswith('ERROR_'):
            error_map = {
                'ERROR_KEY_DOES_NOT_EXIST': 'Invalid API key',
                'ERROR_ZERO_BALANCE': 'Account has zero balance',
                'ERROR_INVALID_ACTION': 'Invalid action',
            }
            error_msg = error_map.get(result, result)
            raise Exception(error_msg)
        
        try:
            balance = float(result)
        except ValueError:
            raise Exception(f"Invalid balance response: {result}")
        
        # Update account
        old_balance = account.balance
        account.balance = balance
        account.balance_last_checked = timezone.now()
        account.save(update_fields=['balance', 'balance_last_checked'])
        
        # Log balance check
        self._log_balance_check(account, old_balance, balance)
        
        logger.info(f"Balance checked for {account.name}: ${balance:.2f}")
        return balance
    
    def _check_anticaptcha_balance(self, account: CaptchaAccount) -> float:
        """Check balance for Anti-Captcha account"""
        import httpx
        
        url = "https://api.anti-captcha.com/getBalance"
        payload = {"clientKey": account.api_key}
        
        response = httpx.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}")
        
        data = response.json()
        
        if data.get('errorId') != 0:
            raise Exception(data.get('errorDescription', 'Unknown error'))
        
        balance = float(data.get('balance', 0))
        
        # Update account
        old_balance = account.balance
        account.balance = balance
        account.balance_last_checked = timezone.now()
        account.save(update_fields=['balance', 'balance_last_checked'])
        
        # Log balance check
        self._log_balance_check(account, old_balance, balance)
        
        logger.info(f"Balance checked for {account.name}: ${balance:.2f}")
        return balance
    
    def _log_balance_check(self, account: CaptchaAccount, old_balance: float, new_balance: float):
        """Log balance check event"""
        AccountAuditLog.objects.create(
            account=account,
            action='balance_checked',
            old_values={'balance': float(old_balance)},
            new_values={'balance': float(new_balance)},
            details=f"Balance changed from ${old_balance:.2f} to ${new_balance:.2f}"
        )
    
    def get_default_account(self) -> Optional[CaptchaAccount]:
        """Get the default account for solving"""
        return CaptchaAccount.objects.filter(
            is_default=True,
            status='active',
            balance__gt=0
        ).first()
    
    def get_best_account(self, captcha_type: str = None) -> Optional[CaptchaAccount]:
        """
        Get the best available account based on:
        1. Default account if set and available
        2. Account with highest balance
        3. Account with highest success rate for the CAPTCHA type
        """
        # Try default first
        default = self.get_default_account()
        if default:
            return default
        
        # Get accounts ordered by balance
        accounts = CaptchaAccount.objects.filter(
            status='active',
            balance__gt=0
        ).order_by('-balance')
        
        if accounts.exists():
            return accounts.first()
        
        return None
    
    def check_all_balances(self) -> Dict[str, Any]:
        """Check balances for all active accounts"""
        accounts = CaptchaAccount.objects.filter(status='active')
        results = []
        errors = []
        
        for account in accounts:
            try:
                balance = self.update_balance(account)
                results.append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'balance': balance,
                    'success': True,
                })
            except Exception as e:
                errors.append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'error': str(e),
                    'success': False,
                })
                # Mark account as error if balance check fails
                account.status = 'error'
                account.save(update_fields=['status'])
        
        return {
            'results': results,
            'errors': errors,
            'total': len(accounts),
            'successful': len(results),
            'failed': len(errors),
        }


def log_account_change(
    account: CaptchaAccount,
    action: str,
    old_values: Dict = None,
    new_values: Dict = None,
    user=None,
    ip_address: str = None
):
    """
    Log an account change event to the audit log
    
    Args:
        account: The CaptchaAccount instance
        action: The action type (created, updated, etc.)
        old_values: Dictionary of old values (with sensitive data masked)
        new_values: Dictionary of new values (with sensitive data masked)
        user: The user who made the change
        ip_address: IP address of the requester
    """
    AccountAuditLog.objects.create(
        account=account,
        action=action,
        old_values=old_values,
        new_values=new_values,
        changed_by=user,
        ip_address=ip_address,
        details=f"Account {action}"
    )