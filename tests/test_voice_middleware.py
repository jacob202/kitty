from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gateway.voice_middleware import VoiceGateMiddleware


def test_filtered_json_response_recomputes_content_length():
    app = FastAPI()
    app.add_middleware(VoiceGateMiddleware)

    @app.get('/completion')
    def completion():
        return JSONResponse(
            {
                'choices': [
                    {'message': {'role': 'assistant', 'content': 'Certainly! Two causes.'}}
                ]
            }
        )

    response = TestClient(app).get('/completion')

    assert response.status_code == 200
    assert response.json()['choices'][0]['message']['content'] == 'Two causes.'
    assert int(response.headers['content-length']) == len(response.content)
