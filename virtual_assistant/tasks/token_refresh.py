"""
Background token refresh for calendar providers.
This module handles automatic refresh of OAuth tokens before they expire.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from virtual_assistant.utils.logger import logger
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.meetings.calendar_provider_factory import CalendarProviderFactory


async def refresh_tokens_for_account(account: CalendarAccount) -> bool:
    """
    Refresh tokens for a specific calendar account.
    
    Args:
        account: The calendar account to refresh tokens for
        
    Returns:
        bool: True if refresh was successful, False otherwise
        
    Raises:
        Exception: If the refresh operation fails
    """
    if not account:
        raise Exception("Account cannot be None")
        
    if not account.refresh_token:
        raise Exception(f"No refresh token available for {account.calendar_email}")
        
    # Get the appropriate provider for this account
    provider = CalendarProviderFactory.get_provider(account.provider)
    if not provider:
        raise Exception(f"No provider found for {account.provider}")
        
    # Attempt to refresh the token
    logger.info(f"Refreshing token for {account.calendar_email} ({account.provider})")
    await provider.refresh_token(account.calendar_email, account.app_login)
    
    logger.info(f"✅ Successfully refreshed token for {account.calendar_email}")
    return True


async def refresh_soon_expiring_tokens() -> Dict[str, int]:
    """
    Find accounts with tokens that will expire soon and refresh them.
    
    OAuth2 access tokens typically expire after 1 hour (O365, Google).
    We'll target accounts that were last refreshed more than 45 minutes ago.
    
    Returns:
        Dict with counts of success and failure
    """
    # Calculate the cutoff time - refresh tokens older than 45 minutes
    refresh_cutoff = datetime.now(timezone.utc) - timedelta(minutes=45)
    
    # Find accounts needing refresh
    accounts = CalendarAccount.get_accounts_by_last_sync(older_than=refresh_cutoff)
    
    if not accounts:
        logger.info("No accounts need token refresh at this time")
        return {"success": 0, "failed": 0}
    
    logger.info(f"Found {len(accounts)} accounts for token refresh")
    
    # Counters for result summary
    success_count = 0
    failed_count = 0
    
    # Process each account
    for account in accounts:
        # Skip accounts marked as needing reauth (these need user intervention)
        if account.needs_reauth:
            logger.info(f"Skipping {account.calendar_email} as it needs full reauth")
            continue
            
        # Skip accounts without refresh tokens
        if not account.refresh_token:
            logger.info(f"Skipping {account.calendar_email} as it has no refresh token")
            continue
            
        # Try to refresh the token
        try:
            await refresh_tokens_for_account(account)
            success_count += 1
        except Exception as e:
            logger.error(f"❌ Failed to refresh token for {account.calendar_email}: {str(e)}")
            
            # Mark account as needing reauth
            account.needs_reauth = True
            account.save()
            
            failed_count += 1
    
    # Log a meaningful summary
    logger.info(f"Token refresh summary: {success_count} successful, {failed_count} failed")
    
    return {
        "success": success_count,
        "failed": failed_count
    }


async def start_token_refresh_scheduler():
    """
    Start the background scheduler for token refresh.
    This runs the token refresh task every 30 minutes.
    """
    logger.info("Starting token refresh background scheduler")
    
    while True:
        try:
            # Run the token refresh task
            await refresh_soon_expiring_tokens()
            
        except Exception as e:
            logger.error(f"Error in token refresh scheduler: {str(e)}")
            
        # Wait for 30 minutes before next run
        await asyncio.sleep(30 * 60)  # 30 minutes in seconds 