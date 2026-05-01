import pandas as pd
from modules.input.instruction_normalizer import normalize_instruction

def parse_excel_input(file_path_or_bytes) -> list:
    """
    Parses an Excel file containing campaign instructions.
    Returns a list of normalized instruction dictionaries.
    """
    df = pd.read_excel(file_path_or_bytes)
    instructions = []
    
    for _, row in df.iterrows():
        # Handle required_fields as comma-separated string
        req_fields = []
        if pd.notna(row.get('required_fields')):
            req_fields = [f.strip() for f in str(row['required_fields']).split(',')]
            
        data = {
            "campaign_name": row.get('campaign_name'),
            "platform": row.get('platform', 'google_maps'),
            "category": row.get('category'),
            "location": row.get('location'),
            "limit": row.get('limit', 100),
            "required_fields": req_fields
        }
        instructions.append(normalize_instruction(data))
        
    return instructions
