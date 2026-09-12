import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List
from step1_ingest_data import load_and_preprocess_dataset
from step2_simulator import CashFlowSimulator
from step3_candidate_generator import CandidatePlanGenerator

class BuyOrWaitAgent:
    """
    Buy or Wait AI Financial Decision Agent.
    Reconstructs financial positions, reserves pending debits, ignores unrealized/unconfirmed credits,
    and outputs exactly the 8 required CSV columns.
    """
    
    def __init__(self, base_dir: str = "."):
        self.data = load_and_preprocess_dataset(base_dir=base_dir)
        self.simulator = CashFlowSimulator(self.data['profiles'], self.data['events'])
        self.generator = CandidatePlanGenerator(self.simulator)
        
    def evaluate_request(self, request_row: pd.Series) -> Dict[str, Any]:
        req_id = str(request_row['request_id'])
        u_id = str(request_row['user_id'])
        req_date = str(request_row['request_date'])
        req_amount_orig = float(request_row['requested_amount'])
        
        profile = self.simulator.get_user_profile(u_id)
        home_curr = str(profile.get('home_currency', 'USD'))
        
        # Safely determine currency & exchange rates
        req_curr = str(request_row.get('currency', request_row.get('requested_currency', home_curr)))
        rate_to_home = float(request_row.get('exchange_rate_to_home', 1.0))
        if rate_to_home <= 0:
            rate_to_home = 1.0

        if req_curr != home_curr and 'exchange_rate_to_home' not in request_row:
            rates_df = self.data.get('rates', pd.DataFrame())
            if not rates_df.empty:
                date_col = 'rate_date' if 'rate_date' in rates_df.columns else ('date' if 'date' in rates_df.columns else None)
                if date_col:
                    rate_match = rates_df[
                        (rates_df[date_col] == req_date) & 
                        (rates_df['from_currency'] == req_curr) & 
                        (rates_df['to_currency'] == home_curr)
                    ]
                    if not rate_match.empty:
                        rate_to_home = float(rate_match.iloc[0]['rate'])

        req_amount_home = req_amount_orig * rate_to_home
        
        req_home_row = request_row.copy()
        req_home_row['requested_amount'] = req_amount_home
        
        # 1. Simulator liquidity & reserve buffer evaluation
        safe_today_home, earliest_date = self.simulator.calculate_base_metrics(u_id, req_date, req_amount_home)
        safe_today_orig = round(safe_today_home / rate_to_home, 2)
        
        # 2. Candidate strategy selection
        candidates = self.generator.generate_candidate_plans(req_home_row)
        best_plan = self.generator.select_best_plan(u_id, candidates)
        
        internal_rec = best_plan['recommendation_type']
        
        # 3. Map to exact required 5 decisions & affordability status schema
        if internal_rec == 'BUY_NOW':
            affordability_status = "affordable_now"
            recommended_payment_method = "full_payment"
        elif internal_rec == 'INSTALLMENTS':
            affordability_status = "affordable_with_plan"
            recommended_payment_method = "installments"
        elif internal_rec == 'BUY_WITH_ADJUSTMENTS':
            if safe_today_orig > 0:
                affordability_status = "affordable_with_plan"
                recommended_payment_method = "partial_payment"
            else:
                affordability_status = "affordable_with_plan"
                recommended_payment_method = "installments"
        elif internal_rec == 'WAIT':
            affordability_status = "affordable_later"
            recommended_payment_method = "wait"
        else: # CANNOT_AFFORD
            affordability_status = "not_affordable"
            recommended_payment_method = "not_recommended"
            
        # 4. Format payment_plan string (e.g., "YYYY-MM-DD:AMOUNT|YYYY-MM-DD:AMOUNT")
        schedule_list = best_plan.get('schedule', [])
        if schedule_list:
            plan_tokens = []
            for p_date, p_amt_home in schedule_list:
                p_amt_orig = round(p_amt_home / rate_to_home, 2)
                plan_tokens.append(f"{p_date}:{int(p_amt_orig) if p_amt_orig.is_integer() else p_amt_orig}")
            payment_plan = "|".join(plan_tokens)
        else:
            payment_plan = "none"

        # 5. Format spending_changes_needed
        adjustments = best_plan.get('spending_changes', [])
        if adjustments:
            spending_changes_needed = "|".join([f"{adj.get('category')}:{adj.get('reduction_pct', 0)}%" for adj in adjustments])
        else:
            spending_changes_needed = "none"

        # 6. Generate precise financial explanation
        if recommended_payment_method == "full_payment":
            decision_explanation = f"Full payment of {req_curr} {req_amount_orig:,.2f} is safe today while preserving user's minimum required balance and accounting for pending debits."
        elif recommended_payment_method == "partial_payment":
            decision_explanation = f"Full payment exceeds current liquid headroom after reserving pending debits. A partial payment of {req_curr} {safe_today_orig:,.2f} is safe today, with remaining balance scheduled later."
        elif recommended_payment_method == "installments":
            m = best_plan.get('installment_months', 1)
            decision_explanation = f"Lump sum upfront payment reduces projected balance below safety limits. Splitting into {m} installments maintains required minimum balance."
        elif recommended_payment_method == "wait":
            decision_explanation = f"Immediate purchase violates safety reserves. Delaying payment to {earliest_date} allows pending confirmed salary settlement to cover the request safely."
        else:
            decision_explanation = f"Insufficient projected net cash flow over 90-day horizon to safely cover {req_curr} {req_amount_orig:,.2f} without breaching minimum safety balance."

        # Return exact 8-column dictionary mapping
        return {
            "request_id": req_id,
            "amount_safe_to_pay": safe_today_orig,
            "affordability_status": affordability_status,
            "recommended_payment_method": recommended_payment_method,
            "payment_plan": payment_plan,
            "earliest_date_for_full_payment": earliest_date if earliest_date else "N/A",
            "spending_changes_needed": spending_changes_needed,
            "decision_explanation": decision_explanation
        }

    def process_all_requests(self) -> List[Dict[str, Any]]:
        results = []
        for _, req in self.data['requests'].iterrows():
            evaluated = self.evaluate_request(req)
            results.append(evaluated)
        return results