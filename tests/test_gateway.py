import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

_temp = tempfile.TemporaryDirectory()
os.environ['DATA_DIR'] = _temp.name
os.environ['PARALLEL_TOKEN'] = 'test-only-token-that-is-at-least-24-characters'
from fastapi.testclient import TestClient
from backend.app import app


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer '+os.environ['PARALLEL_TOKEN']}

    def test_requires_token(self):
        self.assertEqual(self.client.get('/api/health').status_code,401)

    def test_missing_model_is_explicit(self):
        with patch('backend.app.translator',side_effect=RuntimeError('model missing')):
            response = self.client.post('/api/translate',json={'text':'hello'},headers=self.headers)
            self.assertEqual(response.status_code,503)
            self.assertIn('model missing',response.json()['detail'])

    def test_upload_validation(self):
        response = self.client.post('/api/games',files={'file':('test.iso',b'example')},data={'profile':'{}'},headers=self.headers)
        self.assertEqual(response.status_code,422)
        profile = {'schema_version':1,'id':'test','title':'Test','game_version':'1','adapter':'test'}
        response = self.client.post('/api/games',files={'file':('../../test.iso',b'example')},data={'profile':json.dumps(profile)},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['launch_supported'])
        self.assertNotIn('/',response.json()['id'])

    def test_bad_image(self):
        response = self.client.post('/api/ocr',files={'file':('bad.png',b'not an image')},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_ocr_pipeline(self):
        image = Image.new('RGB',(100,100),'white')
        buf = io.BytesIO()
        image.save(buf,format='PNG')
        async def fake_translate(text):
            return 'مرحبا'
        with patch('backend.app.read_text',return_value='Hello'), patch('backend.app.translate',side_effect=fake_translate):
            response = self.client.post('/api/ocr',files={'file':('screen.png',buf.getvalue())},headers=self.headers)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['english'],'Hello')
            self.assertEqual(response.json()['arabic'],'مرحبا')
            self.assertIn('elapsed_ms',response.json())

    def test_crop_region_and_validation(self):
        image = Image.new('RGB',(200,100),'white')
        buf = io.BytesIO()
        image.save(buf,format='PNG')
        seen=[]
        def recognize(img):
            seen.append(img.size)
            return ''
        with patch('backend.app.read_text',side_effect=recognize):
            response = self.client.post('/api/ocr?region=bottom',files={'file':('screen.png',buf.getvalue())},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(seen,[(200,45)])
        response = self.client.post('/api/ocr?region=bogus',files={'file':('screen.png',buf.getvalue())},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_non_object_profile_is_rejected(self):
        response = self.client.post('/api/games',files={'file':('test.iso',b'example')},data={'profile':'[]'},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_readiness_is_truthful(self):
        with patch('backend.app.translator',side_effect=RuntimeError('missing')), patch('backend.app.ocr_ready',return_value=False):
            response = self.client.get('/api/health',headers=self.headers)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertFalse(data['translation_ready'])
        self.assertFalse(data['ocr_ready'])
        self.assertFalse(data['iso_launch'])
        self.assertFalse(data['stream_tested'])
        self.assertEqual(data['commercial_game_adapters'],[])

    def test_chunked_body_limit_cannot_trust_content_length(self):
        with patch('backend.app.MAX_ISO',1):
            response = self.client.post('/api/games',files={'file':('test.iso',b'x'*(1024*1024+1000))},data={'profile':'{}'},headers={**self.headers,'Content-Length':'10'})
            self.assertEqual(response.status_code,413)

    def test_room_positions(self):
        with self.client.websocket_connect('/ws/testroom') as first, self.client.websocket_connect('/ws/testroom') as second:
            for client in (first,second):
                client.send_json({'type':'auth','token':os.environ['PARALLEL_TOKEN']})
                self.assertEqual(client.receive_json()['type'],'ready')
            first.send_json({'type':'position','x':100,'y':200,'z':0})
            first.receive_json()
            message = second.receive_json()
            self.assertEqual(list(message['players'].values())[0]['x'],100)

    def test_stream_requires_display(self):
        with patch.dict(os.environ,{'DISPLAY_SOURCE':''}):
            response = self.client.post('/api/offer',json={'type':'offer','sdp':'test'},headers=self.headers)
            self.assertEqual(response.status_code,503)


if __name__ == '__main__':
    unittest.main()
