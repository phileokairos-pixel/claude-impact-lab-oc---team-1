import os
import unittest
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.demo_hosting import DemoHosting

ENV={'CAREWARD_PUBLIC_DEMO':'1','RENDER_EXTERNAL_HOSTNAME':'demo.example.test','CAREWARD_DEMO_PASSWORD':'test-only-password-at-least-24-characters'}
class HostingTests(unittest.TestCase):
    def test_requires_host_and_password(self):
        with patch.dict(os.environ,{'CAREWARD_PUBLIC_DEMO':'1'},clear=True):
            with self.assertRaises(RuntimeError): DemoHosting.from_env()
    def test_host_auth_origin_and_upload_allowlist(self):
        with patch.dict(os.environ,ENV), TestClient(create_app(),base_url='https://demo.example.test') as c:
            self.assertEqual(c.get('/ready').status_code,200)
            for path in ['/', '/health','/api/referrals/missing','/vendor/pdf.mjs']:
                self.assertEqual(c.get(path).status_code,401)
            c.auth=('careward',ENV['CAREWARD_DEMO_PASSWORD'])
            self.assertEqual(c.get('/health').json()['deploymentMode'],'protected-demo')
            self.assertEqual(c.get('/vendor/pdf.mjs').status_code,200)
            self.assertEqual(c.get('/health',headers={'host':'attacker.test'}).status_code,403)
            self.assertEqual(c.post('/api/referrals',headers={'origin':'https://attacker.test'},files={'file':('test.pdf',b'%PDF-unknown')}).status_code,403)
            self.assertEqual(c.post('/api/referrals',files={'file':('test.pdf',b'%PDF-unknown')}).status_code,422)
            pdf=Path('frontend/fixtures/synthetic-training/Careward-Synthetic-Referral-Packet.pdf').read_bytes()
            self.assertEqual(c.post('/api/referrals',headers={'origin':'https://demo.example.test'},files={'file':('training.pdf',pdf)}).status_code,202)
