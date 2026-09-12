import pandas as pd
from step1_ingest_data import load_and_preprocess_dataset
from step2_simulator import CashFlowSimulator
from step3_candidate_generator import CandidatePlanGenerator

def test_step3_pipeline():
    print("==========================================")
    print("      STARTING STEP 3 VERIFICATION        ")
    print("==========================================")
    
    data = load_and_preprocess_dataset(base_dir=".")
    simulator = CashFlowSimulator(data['profiles'], data['events'])
    generator = CandidatePlanGenerator(simulator)
    
    requests_df = data['requests']
    plans = []
    
    for _, req in requests_df.iterrows():
        candidates = generator.generate_candidate_plans(req)
        best_plan = generator.select_best_plan(req['user_id'], candidates)
        best_plan['request_id'] = req['request_id']
        plans.append(best_plan)
        
    results_df = pd.DataFrame(plans)
    print("\n--- RECOMMENDATION TYPES BREAKDOWN ---")
    print(results_df['recommendation_type'].value_counts())
    
    print("\n[SUCCESS] Candidate Generator executed cleanly.")

if __name__ == "__main__":
    test_step3_pipeline()