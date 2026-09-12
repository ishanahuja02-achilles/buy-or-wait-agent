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
    Complete Buy or Wait AI Financial Decision Agent.
    Converts amounts back to requested currency and structures the required challenge schema.
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
        
        # Safe extraction for currency column variant
        if 'currency' in request_row:
            req_curr = str(request_row['currency'])
        elif 'requested_currency' in request_row:
            req_curr = str(request_row['requested_currency'])
        else:
            req_curr = home_curr
        
        # Determine exchange rate factor from Step 1 processing or lookup table
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
        
        # Temporarily adapt request row for home currency calculations
        req_home_row = request_row.copy()
        req_home_row['requested_amount'] = req_amount_home
        
        # 1. Base Metrics Calculation
        safe_today_home, earliest_date = self.simulator.calculate_base_metrics(u_id, req_date, req_amount_home)
        safe_today_orig = round(safe_today_home / rate_to_home, 2)
        
        # 2. Candidate Generation & Selection
        candidates = self.generator.generate_candidate_plans(req_home_row)
        best_plan = self.generator.select_best_plan(u_id, candidates)
        
        rec_type = best_plan['recommendation_type']
        
        # 3. Format Payment Schedule back to original requested currency
        schedule_formatted = []
        for p_date, p_amt_home in best_plan.get('schedule', []):
            p_amt_orig = round(p_amt_home / rate_to_home, 2)
            schedule_formatted.append({
                "date": p_date,
                "amount": p_amt_orig,
                "currency": req_curr
            })
            
        # 4. Generate Natural Language Rationale
        if rec_type == 'BUY_NOW':
            reasoning = f"Sufficient liquidity headroom. Full payment of {req_curr} {req_amount_orig:,.2f} maintains required safety buffer."
        elif rec_type == 'INSTALLMENTS':
            m = best_plan.get('installment_months', 1)
            reasoning = f"Full payment upfront risks safety balance buffer. Recommended split into {m} monthly installments."
        elif rec_type == 'WAIT':
            d_days = best_plan.get('delay_days', 0)
            reasoning = f"Immediate purchase violates minimum safety balance. Delaying payment by {d_days} days to {earliest_date} ensures full safety."
        elif rec_type == 'BUY_WITH_ADJUSTMENTS':
            reasoning = "Purchase is safe today provided specified non-essential spending categories are paused or reduced."
        else:
            reasoning = f"Insufficient projected cash flow over 90-day horizon to safely cover {req_curr} {req_amount_orig:,.2f}."

        # 5. Assemble Challenge Response Schema
        return {
            "request_id": req_id,
            "user_id": u_id,
            "recommendation": rec_type,
            "amount_safe_to_pay_today": safe_today_orig,
            "earliest_date_for_full_payment": earliest_date if earliest_date else "N/A",
            "payment_schedule": schedule_formatted,
            "spending_adjustments": best_plan.get('spending_changes', []),
            "reasoning": reasoning
        }

    def process_all_requests(self) -> List[Dict[str, Any]]:
        results = []
        for _, req in self.data['requests'].iterrows():
            evaluated = self.evaluate_request(req)
            results.append(evaluated)
        return results