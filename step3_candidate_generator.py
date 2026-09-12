import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from step2_simulator import CashFlowSimulator

class CandidatePlanGenerator:
    """
    Generates and evaluates candidate financial plans:
    1. Pay in full today (if safe)
    2. Wait for earliest date full payment is safe
    3. Installment schedules (2 to max_installment_months)
    4. Optional spending adjustments (stop/reduce non-essential categories)
    """

    def __init__(self, simulator: CashFlowSimulator):
        self.simulator = simulator

    def generate_candidate_plans(self, request_row: pd.Series) -> List[Dict[str, Any]]:
        req_id = request_row['request_id']
        user_id = request_row['user_id']
        req_date = str(request_row['request_date'])
        req_amount = float(request_row['requested_amount'])
        
        profile = self.simulator.get_user_profile(user_id)
        
        # Safely parse max_installment_months handling NaN values
        raw_max = profile.get('max_installment_months', 6)
        max_months = int(raw_max) if pd.notna(raw_max) and str(raw_max).strip() != '' else 6
        
        candidates = []
        
        # 1. Option: Pay Full Today
        if self.simulator.is_plan_safe(user_id, req_date, [(req_date, req_amount)]):
            candidates.append({
                'plan_id': 'pay_full_today',
                'recommendation_type': 'BUY_NOW',
                'delay_days': 0,
                'schedule': [(req_date, req_amount)],
                'spending_changes': [],
                'installment_months': 1
            })

        # 2. Option: Wait for Earliest Safe Date
        safe_today, earliest_full_date = self.simulator.calculate_base_metrics(user_id, req_date, req_amount)
        if earliest_full_date and earliest_full_date != req_date:
            delay = (pd.to_datetime(earliest_full_date) - pd.to_datetime(req_date)).days
            candidates.append({
                'plan_id': f'delay_{delay}_days',
                'recommendation_type': 'WAIT',
                'delay_days': delay,
                'schedule': [(earliest_full_date, req_amount)],
                'spending_changes': [],
                'installment_months': 1
            })

        # 3. Option: Equal Monthly Installments (2 to max_months)
        for m in range(2, max_months + 1):
            monthly_amt = round(req_amount / m, 2)
            inst_schedule = []
            dt = pd.to_datetime(req_date)
            for i in range(m):
                inst_dt = (dt + timedelta(days=30 * i)).strftime('%Y-%m-%d')
                inst_schedule.append((inst_dt, monthly_amt))
                
            if self.simulator.is_plan_safe(user_id, req_date, inst_schedule):
                candidates.append({
                    'plan_id': f'installment_{m}_months',
                    'recommendation_type': 'INSTALLMENTS',
                    'delay_days': 0,
                    'schedule': inst_schedule,
                    'spending_changes': [],
                    'installment_months': m
                })

        # 4. Fallback: Optional Spending Adjustment Plans
        if not candidates:
            user_events = self.simulator.events[
                (self.simulator.events['user_id'] == user_id) & 
                (~self.simulator.events['is_cancelled'])
            ]
            
            stop_candidates = []
            raw_stop = profile.get('expense_categories_user_is_willing_to_stop', '')
            stop_categories = str(raw_stop).lower().split(';') if pd.notna(raw_stop) else []
            
            for _, ev in user_events.iterrows():
                ev_cat = str(ev.get('category', '')).lower()
                if any(c in ev_cat for c in stop_categories if c.strip()):
                    stop_candidates.append(f"stop:{ev['event_id']}")

            if stop_candidates and self.simulator.is_plan_safe(user_id, req_date, [(req_date, req_amount)], spending_changes=stop_candidates):
                candidates.append({
                    'plan_id': 'pay_with_spending_cuts',
                    'recommendation_type': 'BUY_WITH_ADJUSTMENTS',
                    'delay_days': 0,
                    'schedule': [(req_date, req_amount)],
                    'spending_changes': stop_candidates,
                    'installment_months': 1
                })

        return candidates

        # 2. Option: Wait for Earliest Safe Date
        safe_today, earliest_full_date = self.simulator.calculate_base_metrics(user_id, req_date, req_amount)
        if earliest_full_date and earliest_full_date != req_date:
            delay = (pd.to_datetime(earliest_full_date) - pd.to_datetime(req_date)).days
            candidates.append({
                'plan_id': f'delay_{delay}_days',
                'recommendation_type': 'WAIT',
                'delay_days': delay,
                'schedule': [(earliest_full_date, req_amount)],
                'spending_changes': [],
                'installment_months': 1
            })

        # 3. Option: Equal Monthly Installments (2 to max_months)
        for m in range(2, max_months + 1):
            monthly_amt = round(req_amount / m, 2)
            inst_schedule = []
            dt = pd.to_datetime(req_date)
            for i in range(m):
                inst_dt = (dt + timedelta(days=30 * i)).strftime('%Y-%m-%d')
                inst_schedule.append((inst_dt, monthly_amt))
                
            if self.simulator.is_plan_safe(user_id, req_date, inst_schedule):
                candidates.append({
                    'plan_id': f'installment_{m}_months',
                    'recommendation_type': 'INSTALLMENTS',
                    'delay_days': 0,
                    'schedule': inst_schedule,
                    'spending_changes': [],
                    'installment_months': m
                })

        # 4. Fallback: Optional Spending Adjustment Plans
        if not candidates:
            # Candidate with stop/reduce spending changes
            user_events = self.simulator.events[
                (self.simulator.events['user_id'] == user_id) & 
                (~self.simulator.events['is_cancelled'])
            ]
            
            stop_candidates = []
            stop_categories = str(profile.get('expense_categories_user_is_willing_to_stop', '')).lower().split(';')
            
            for _, ev in user_events.iterrows():
                ev_cat = str(ev.get('category', '')).lower()
                if any(c in ev_cat for c in stop_categories if c.strip()):
                    stop_candidates.append(f"stop:{ev['event_id']}")

            if stop_candidates and self.simulator.is_plan_safe(user_id, req_date, [(req_date, req_amount)], spending_changes=stop_candidates):
                candidates.append({
                    'plan_id': 'pay_with_spending_cuts',
                    'recommendation_type': 'BUY_WITH_ADJUSTMENTS',
                    'delay_days': 0,
                    'schedule': [(req_date, req_amount)],
                    'spending_changes': stop_candidates,
                    'installment_months': 1
                })

        return candidates

    def select_best_plan(self, user_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tie-breaker ranking: Prioritizes minimal delay, fewer installments, and fewer spending changes."""
        if not candidates:
            return {
                'recommendation_type': 'CANNOT_AFFORD',
                'delay_days': 90,
                'schedule': [],
                'spending_changes': [],
                'reasoning': 'Insufficient headroom within 90-day forecast.'
            }

        def plan_rank_key(plan):
            return (
                plan['delay_days'],                      # 1. Prefer shortest delay
                len(plan['spending_changes']),            # 2. Prefer fewer spending cuts
                plan['installment_months']                # 3. Prefer fewer installment periods
            )

        sorted_plans = sorted(candidates, key=plan_rank_key)
        return sorted_plans[0]