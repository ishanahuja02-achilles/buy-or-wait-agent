import os
import pandas as pd
from step1_ingest_data import load_and_preprocess_dataset

def test_step1_pipeline():
    print("==========================================")
    print("      STARTING STEP 1 VERIFICATION        ")
    print("==========================================")
    
    # Load and preprocess dataset
    data = load_and_preprocess_dataset(base_dir=".")
    
    events_df = data['events']
    profiles_df = data['profiles']
    requests_df = data['requests']
    
    print("\n--- 1. DATASET INGESTION SUMMARY ---")
    print(f"Total Requests Loaded: {len(requests_df)}")
    print(f"Total User Profiles:  {len(profiles_df)}")
    print(f"Total Events Loaded:   {len(events_df)}")
    
    print("\n--- 2. PROCESSED EVENTS SAMPLE ---")
    print(events_df[['event_id', 'user_id', 'amount', 'currency', 'amount_home_curr', 'is_cancelled']].head(10))
    
    output_path = "step1_processed_preview.csv"
    events_df.to_csv(output_path, index=False)
    print(f"\n[SUCCESS] Pipeline executed successfully! Results saved to '{output_path}'.")

if __name__ == "__main__":
    test_step1_pipeline()