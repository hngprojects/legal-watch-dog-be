#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup

url = 'https://france-visas.gouv.fr/en/useful-information/fees'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f'Status: {response.status_code}')
    print(f'Content length: {len(response.text)} chars')
    print(f'Content type: {response.headers.get("content-type")}')
    print(f'\nFirst 2000 chars:\n{response.text[:2000]}')
    
    # Look for fee mentions
    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    fee_lines = [l for l in lines if any(word in l.lower() for word in ['fee', 'euro', '€', 'visa', 'cost'])]
    
    print(f'\n\nFound {len(fee_lines)} lines with fee-related keywords:')
    for line in fee_lines[:10]:
        print(f'  - {line[:100]}')
        
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
