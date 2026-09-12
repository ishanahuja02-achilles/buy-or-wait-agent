import json
import time
from step4_agent_engine import BuyOrWaitAgent

def main():
    print("==================================================")
    print("   HACKERRANK ORCHESTRATE: BUY OR WAIT? AGENT     ")
    print("==================================================")
    
    start_time = time.time()
    
    # Initialize Agent and run full pipeline
    agent = BuyOrWaitAgent(base_dir=".")
    print("\n[INFO] Agent initialized. Processing all evaluation requests...")
    
    recommendations = agent.process_all_requests()
    
    output_filename = "final_recommendations.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(recommendations, f, indent=2)
        
    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] Processed {len(recommendations)} requests in {elapsed:.2f} seconds.")
    print(f"[SUCCESS] Results written to '{output_filename}'.")
    
    # Quick sample display
    if recommendations:
        print("\n--- SAMPLE DECISION OUTPUT ---")
        print(json.dumps(recommendations[0], indent=2))

if __name__ == "__main__":
    main()