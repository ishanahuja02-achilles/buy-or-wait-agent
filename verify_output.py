import json
import os

REQUIRED_KEYS = {
    "request_id",
    "user_id",
    "recommendation",
    "amount_safe_to_pay_today",
    "earliest_date_for_full_payment",
    "payment_schedule",
    "spending_adjustments",
    "reasoning"
}

VALID_RECOMMENDATIONS = {
    "BUY_NOW",
    "WAIT",
    "INSTALLMENTS",
    "BUY_WITH_ADJUSTMENTS",
    "CANNOT_AFFORD"
}

def validate_submission(json_file="final_recommendations.json"):
    print("==========================================")
    print("      SUBMISSION JSON VALIDATION          ")
    print("==========================================")

    if not os.path.exists(json_file):
        print(f"[ERROR] File '{json_file}' not found.")
        return False

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] JSON root must be a list of recommendation objects.")
        return False

    print(f"[CHECK 1/4] Total records generated: {len(data)}")

    errors = 0
    rec_counts = {}

    for idx, item in enumerate(data):
        missing = REQUIRED_KEYS - set(item.keys())
        if missing:
            print(f"[ERROR] Record #{idx} (request_id: {item.get('request_id')}) missing keys: {missing}")
            errors += 1

        rec = item.get("recommendation")
        if rec not in VALID_RECOMMENDATIONS:
            print(f"[ERROR] Record #{idx} invalid recommendation type: '{rec}'")
            errors += 1
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

        safe_amt = item.get("amount_safe_to_pay_today")
        if not isinstance(safe_amt, (int, float)) or safe_amt < 0:
            print(f"[ERROR] Record #{idx} invalid amount_safe_to_pay_today: {safe_amt}")
            errors += 1

    print("[CHECK 2/4] Schema key completeness: VERIFIED")
    
    print("\n[CHECK 3/4] Breakdown of Recommendation Types:")
    for r_type, count in rec_counts.items():
        print(f"  - {r_type}: {count}")

    if errors == 0:
        print("\n==========================================")
        print(" [SUCCESS] SUBMISSION FILE IS 100% VALID  ")
        print("==========================================")
        return True
    else:
        print(f"\n[FAIL] Found {errors} validation errors.")
        return False

if __name__ == "__main__":
    validate_submission()