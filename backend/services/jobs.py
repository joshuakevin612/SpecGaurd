"""Supervise model preparation, worker calls and report persistence as one job."""
import json
import logging
import subprocess
import sys

from fastapi import HTTPException

from backend.database.db import get_db_connection


def bounded_operation(operation, **arguments):
    try:
        result = subprocess.run([sys.executable, '-m', 'backend.services.job_process'],
                                input=json.dumps({'operation': operation, 'arguments': arguments}),
                                capture_output=True, text=True, timeout=150)
        if result.returncode or len(result.stdout) > 20000:
            logging.getLogger('uvicorn.error').error('verification_job_failed project_id=%s exit=%s',
                                                     arguments['project_id'], result.returncode)
            raise ValueError('Job failed')
        return json.loads(result.stdout)['result']
    except (subprocess.TimeoutExpired, ValueError, KeyError, OSError):
        with get_db_connection() as conn:
            conn.execute('UPDATE runs SET status=\'failed\',error=? WHERE project_id=? AND status=\'running\'',
                         ('Run stopped or exceeded its time budget; previous evidence is not current.',
                          arguments['project_id']))
        raise HTTPException(502, 'Verification stopped or exceeded its budget. Inspect the report before retrying.') from None
