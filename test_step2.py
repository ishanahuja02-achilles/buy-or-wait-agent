from step1_ingest_data import load_and_preprocess_dataset
from step2_simulator import CashFlowSimulator

def test_step2_pipeline():
    print("==========================================")
    print("      STARTING STEP 2 VERIFICATION        ")
    print("==========================================")
    
    data = load_and_preprocess_dataset(base_dir=".")
    simulator = CashFlowSimulator(data['profiles'], data['events'])
    
    # Test simulation on first 3 user purchase requests
    requests_df = data['requests']
    for idx, req in requests_df.head(3).iterrows():
        r_id = req['request_id']
        u_id = req['user_id']
        r_date = req['request_date']
        req_amt = float(req['requested_amount'])
        
        safe_amt, earliest_date = simulator.calculate_base_metrics(u_id, r_date, req_amt)
        
        print(f"\n[Request: {r_id}] User: {u_id}")
        print(f" - Request Date:               {r_date}")
        print(f" - Requested Amount:           {req_amt}")
        print(f" - Safe Amount Today:          {safe_amt}")
        print(f" - Earliest Full Payment Date: {earliest_date}")

if __name__ == "__main__":
    test_step2_pipeline()