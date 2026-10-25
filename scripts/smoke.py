"""Authenticated deployed smoke check; credentials are read from environment."""
import os
import sys

import httpx

if __name__ == '__main__':
    with httpx.Client(base_url=os.environ['SPECGUARD_SMOKE_URL'].rstrip('/'), timeout=10,
                      headers={'X-SpecGuard-Client': 'web'}) as client:
        login = client.post('/auth/login', json={'username': os.environ['SPECGUARD_SMOKE_USER'],
                                                 'password': os.environ['SPECGUARD_SMOKE_PASSWORD']})
        login.raise_for_status()
        client.headers['X-CSRF-Token'] = login.json()['csrf']
        for path in ['/ready', '/capabilities', '/projects']:
            client.get(path).raise_for_status()
        client.post('/auth/logout').raise_for_status()
    print('Authenticated readiness, worker availability and account access passed')
    sys.exit(0)
