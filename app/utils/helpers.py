import re
from typing import Optional  # Add this import

def extract_target_code(href: str) -> Optional[str]:  # Change to Optional[str]
    """
    Try to extract the target currency ISO code from a URL.
    Expected URL format: /Some-Currency-XYZ-currency-table.html
    Returns the code (e.g., "XYZ") in uppercase or None if it cannot be determined.
    """
    match = re.search(r"-([A-Z]{2,4})-currency-table\.html", href, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None
