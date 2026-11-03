"""Standardize scan output into customer-readable result cards."""
STATUSES={'good','attention','problem','unknown'}
FALLBACK={'good':'Check complete','attention':'This check needs attention','problem':'A problem was found','unknown':'We could not read this information on this computer'}

def result_card(status, headline, explanation, action, technical_details=''):
    status=status if status in STATUSES else 'unknown'
    headline=str(headline or FALLBACK[status]).strip()
    explanation=str(explanation or 'No customer-facing explanation was available.').strip()
    action=str(action or 'Review the result with the customer.').strip()
    return {'status':status,'headline':headline,'explanation':explanation,'action':action,'details':str(technical_details or '')}
