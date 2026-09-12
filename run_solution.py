import pandas as pd
import time
from step4_agent_engine import BuyOrWaitAgent

REQUIRED_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation"
]

def main():
    print("==================================================")
    print("   BUY OR WAIT? AGENT - CSV OUTPUT GENERATOR      ")
    print("==================================================")
    
    start_time = time.time()
    
    agent = BuyOrWaitAgent(base_dir=".")
    print("\n[INFO] Evaluating requests and generating 8-column financial recommendations...")
    
    recommendations = agent.process_all_requests()
    
    df = pd.DataFrame(recommendations)
    df = df[REQUIRED_COLUMNS]  # Enforce exact column order
    
    output_filename = "output.csv"
    df.to_csv(output_filename, index=False, encoding="utf-8")
    
    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] Processed {len(df)} requests in {elapsed:.2f} seconds.")
    print(f"[SUCCESS] CSV written to '{output_filename}'.")
    
    print("\n--- SAMPLE CSV ROW OUTPUT ---")
    print(df.head(2).to_string(index=False))

if __name__ == "__main__":
    main()