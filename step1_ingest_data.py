import os
import re
import pandas as pd
import numpy as np
from PIL import Image
import pytesseract

def extract_amount_from_image(image_path: str) -> float:
    """Extracts numeric transaction amount from receipt image using fast Tesseract OCR."""
    if not os.path.exists(image_path):
        return 0.0
    
    try:
        # Perform instant CPU OCR
        text = pytesseract.image_to_string(Image.open(image_path))
        
        # Extract currency and float amounts
        matches = re.findall(r'[\$\€\£\₹]?\s*(\d+(?:\.\d{1,2})?)', text)
        clean_floats = []
        for match in matches:
            try:
                val = float(match)
                if val > 0:
                    clean_floats.append(val)
            except ValueError:
                continue
                
        return max(clean_floats) if clean_floats else 0.0
    except Exception as e:
        print(f"[Warning] Fast OCR failed for {image_path}: {e}")
        return 0.0

def apply_message_overrides(events_df: pd.DataFrame, messages_df: pd.DataFrame) -> pd.DataFrame:
    """Scans chat messages to flag cancelled/refunded events."""
    events_df['is_cancelled'] = False
    
    if messages_df.empty:
        return events_df

    for _, msg in messages_df.iterrows():
        related_id = msg.get('related_event_id')
        msg_text = str(msg.get('message_text', '')).lower()
        
        if pd.notna(related_id) and str(related_id).strip() != '':
            if any(k in msg_text for k in ['cancel', 'refunded', 'void', 'returned', 'never mind']):
                events_df.loc[events_df['event_id'] == related_id, 'is_cancelled'] = True
                
    return events_df

def convert_to_home_currency(events_df: pd.DataFrame, profiles_df: pd.DataFrame, rates_df: pd.DataFrame) -> pd.DataFrame:
    """Converts foreign transaction amounts to user home currency using exchange rates."""
    user_home_curr = profiles_df.set_index('user_id')['home_currency'].to_dict()
    events_df['home_currency'] = events_df['user_id'].map(user_home_curr)
    
    # Handle both 'rate_date' and 'date' column names safely
    date_col = 'rate_date' if 'rate_date' in rates_df.columns else 'date'
    
    rates_dict = rates_df.set_index([date_col, 'from_currency', 'to_currency'])['rate'].to_dict()
    
    converted_amounts = []
    for _, row in events_df.iterrows():
        amt = row.get('amount', 0.0)
        amt = 0.0 if pd.isna(amt) else float(amt)
        
        from_curr = row.get('currency')
        to_curr = row.get('home_currency')
        e_date = str(row.get('event_date'))
        
        if from_curr == to_curr or pd.isna(from_curr) or pd.isna(to_curr):
            converted_amounts.append(round(amt, 2))
        else:
            rate = rates_dict.get((e_date, from_curr, to_curr), 1.0)
            converted_amounts.append(round(amt * float(rate), 2))
            
    events_df['amount_home_curr'] = converted_amounts
    return events_df

def load_and_preprocess_dataset(base_dir: str = ".") -> dict:
    """Main data loader and preprocessor for Step 1."""
    data_path = os.path.join(base_dir, "dataset") if os.path.exists(os.path.join(base_dir, "dataset")) else base_dir
    
    requests_df = pd.read_csv(os.path.join(data_path, "requests.csv"))
    profiles_df = pd.read_csv(os.path.join(data_path, "financial_profiles.csv"))
    events_df = pd.read_csv(os.path.join(data_path, "financial_events.csv"))
    rates_df = pd.read_csv(os.path.join(data_path, "exchange_rates.csv"))
    messages_df = pd.read_csv(os.path.join(data_path, "messages.csv")) if os.path.exists(os.path.join(data_path, "messages.csv")) else pd.DataFrame()
    images_df = pd.read_csv(os.path.join(data_path, "images.csv")) if os.path.exists(os.path.join(data_path, "images.csv")) else pd.DataFrame()

    # Fill missing event amounts using OCR
    for idx, row in events_df.iterrows():
        if pd.isna(row['amount']) or str(row['amount']).strip() == '':
            e_id = row['event_id']
            if not images_df.empty:
                img_match = images_df[images_df['related_event_id'] == e_id]
                if not img_match.empty:
                    img_id = img_match.iloc[0]['image_id']
                    img_file = os.path.join(data_path, "media", "images", f"{img_id}.png")
                    extracted = extract_amount_from_image(img_file)
                    events_df.at[idx, 'amount'] = extracted

    events_df = apply_message_overrides(events_df, messages_df)
    events_df = convert_to_home_currency(events_df, profiles_df, rates_df)
    
    return {
        'requests': requests_df,
        'profiles': profiles_df,
        'events': events_df,
        'rates': rates_df,
        'messages': messages_df,
        'images': images_df
    }