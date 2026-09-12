import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

class CashFlowSimulator:
    """
    Deterministic 90-Day Cash Flow Simulator & Safety Checker.
    Enforces minimum balance safety constraints and projects daily cash positions.
    """
    
    def __init__(self, profiles_df: pd.DataFrame, events_df: pd.DataFrame):
        self.profiles = profiles_df.set_index('user_id')
        self.events = events_df.copy()
        self.events['event_date'] = pd.to_datetime(self.events['event_date'])
        
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Returns user financial profile settings."""
        if user_id in self.profiles.index:
            return self.profiles.loc[user_id].to_dict()
        raise ValueError(f"User profile for {user_id} not found.")

    def _get_starting_balance(self, profile: Dict[str, Any]) -> float:
        """Helper to extract starting balance safely across schema variations."""
        for col in ['current_available_balance','current_balance', 'available_balance', 'starting_balance', 'balance']:
            if col in profile and pd.notna(profile[col]):
                return float(profile[col])
        raise KeyError(f"No balance column found in profile keys: {list(profile.keys())}")

    def build_daily_ledger(
        self, 
        user_id: str, 
        start_date: str, 
        days: int = 90,
        spending_changes: Optional[List[str]] = None
    ) -> pd.DataFrame:
        profile = self.get_user_profile(user_id)
        current_balance = self._get_starting_balance(profile)
        
        start_dt = pd.to_datetime(start_date)
        date_range = [start_dt + timedelta(days=i) for i in range(days)]
        
        user_events = self.events[
            (self.events['user_id'] == user_id) & 
            (~self.events['is_cancelled'])
        ].copy()
        
        stopped_events = set()
        reduced_events = {}
        if spending_changes:
            for change in spending_changes:
                parts = change.split(':')
                if parts[0] == 'stop' and len(parts) >= 2:
                    stopped_events.add(parts[1])
                elif parts[0] == 'reduce_to' and len(parts) >= 3:
                    reduced_events[parts[1]] = float(parts[2])

        daily_cashflows = {dt: 0.0 for dt in date_range}
        
        for _, event in user_events.iterrows():
            event_id = str(event['event_id'])
            if event_id in stopped_events:
                continue
                
            e_date = event['event_date']
            status = str(event.get('status', '')).lower()
            e_type = str(event.get('event_type', '')).lower()
            
            if status in ['pending_credit', 'failed', 'cancelled', 'unrealized']:
                continue
                
            amt = float(event['amount_home_curr'])
            if event_id in reduced_events:
                amt = reduced_events[event_id]
                
            is_expense = e_type in ['expense', 'debit', 'bill', 'recurring_expense', 'transfer_out']
            net_change = -amt if is_expense else amt
            
            is_recurring = str(event.get('is_recurring', '')).lower() in ['true', '1', 'yes']
            
            if is_recurring:
                curr_e_date = e_date
                while curr_e_date <= date_range[-1]:
                    if curr_e_date >= start_dt and curr_e_date in daily_cashflows:
                        daily_cashflows[curr_e_date] += net_change
                    curr_e_date += timedelta(days=30)
            else:
                if start_dt <= e_date <= date_range[-1] and e_date in daily_cashflows:
                    daily_cashflows[e_date] += net_change
                    
        ledger_data = []
        running_bal = current_balance
        
        for dt in date_range:
            running_bal += daily_cashflows[dt]
            ledger_data.append({
                'date': dt.strftime('%Y-%m-%d'),
                'daily_change': daily_cashflows[dt],
                'forecast_balance': round(running_bal, 2)
            })
            
        return pd.DataFrame(ledger_data)

    def is_plan_safe(
        self, 
        user_id: str, 
        start_date: str, 
        payment_schedule: List[Tuple[str, float]],
        spending_changes: Optional[List[str]] = None
    ) -> bool:
        profile = self.get_user_profile(user_id)
        min_balance = float(profile['minimum_balance_to_keep'])
        
        ledger_df = self.build_daily_ledger(user_id, start_date, days=90, spending_changes=spending_changes)
        ledger_dict = ledger_df.set_index('date')['forecast_balance'].to_dict()
        
        plan_payments = {}
        for p_date, p_amt in payment_schedule:
            plan_payments[p_date] = plan_payments.get(p_date, 0.0) + p_amt
            
        running_deduction = 0.0
        for dt_str in list(ledger_dict.keys()):
            if dt_str in plan_payments:
                running_deduction += plan_payments[dt_str]
            
            effective_balance = ledger_dict[dt_str] - running_deduction
            if effective_balance < min_balance:
                return False
                
        return True

    def calculate_base_metrics(
        self, 
        user_id: str, 
        request_date: str, 
        requested_amount: float
    ) -> Tuple[float, Optional[str]]:
        profile = self.get_user_profile(user_id)
        min_balance = float(profile['minimum_balance_to_keep'])
        
        ledger_df = self.build_daily_ledger(user_id, request_date, days=90)
        min_projected_bal = ledger_df['forecast_balance'].min()
        
        lowest_headroom_90d = min_projected_bal - min_balance
        amount_safe_today = max(0.0, min(requested_amount, lowest_headroom_90d))
        amount_safe_today = round(amount_safe_today, 2)
        
        earliest_full_date = None
        for idx, row in ledger_df.iterrows():
            d_str = row['date']
            if self.is_plan_safe(user_id, request_date, [(d_str, requested_amount)]):
                earliest_full_date = d_str
                break
                
        return amount_safe_today, earliest_full_date