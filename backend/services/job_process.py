"""Production verification subprocess; the parent enforces a hard time limit."""
import json
import sys

from backend.services.verification import VerificationService

if __name__ == '__main__':
    job = json.load(sys.stdin)
    service = VerificationService()
    try:
        if job['operation'] == 'verify':
            result = service.verify(**job['arguments'])
        else:
            result = service.retest(**job['arguments'])
        print(json.dumps({'result': result}))
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({'error_type': type(exc).__name__}))
        sys.exit(1)
