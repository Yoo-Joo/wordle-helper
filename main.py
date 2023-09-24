from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi import FastAPI, HTTPException, Response, Depends
from uuid import UUID
import requests
import uvicorn
import uuid
import re

from schema.word import BasicVerifier, Word, SessionData

app = FastAPI()

backend = InMemoryBackend[UUID, SessionData]()
verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session")
)
cookie_params = CookieParameters()
cookie = SessionCookie(
    cookie_name="cookie",
    identifier="general_verifier",
    auto_error=True,
    secret_key="DONOTUSE",
    cookie_params=cookie_params,
)

@app.get('/start_game')
async def start_game(response: Response):
    local_uuid = uuid.uuid4()
    all_words = requests.get('https://gist.githubusercontent.com/dracos/dd0668f281e685bad51479e5acaadb93/raw/6bfa15d263d6d5b63840a8e5b64e04b382fdb079/valid-wordle-words.txt').text.split('\n')
    del all_words[-1]

    game = SessionData(
        user_uuid = local_uuid,
        words = all_words
    )
    await backend.create(local_uuid, game)
    cookie.attach_to_response(response, local_uuid)

    return {
        "details": "Game created !"
    }

@app.post('/wordle', dependencies=[Depends(cookie)])
async def find(input: Word, response: Response, session_data: SessionData = Depends(verifier), session_id: UUID = Depends(cookie)):
    pattern = r"^[ynp]{5}$"
    local_words = session_data.words

    if not re.match(pattern, input.positions):
        return {
            "details": "invalid positions format"
        }
    
    for index, (i, j) in enumerate(zip(input.word, input.positions)):
        if j.lower() == 'y':
            local_words = [k for k in local_words if k[index] == i]
        elif j.lower() == 'n':
            local_words = [k for k in local_words if i not in k]
        elif j.lower() == 'p':
            local_words = [k for k in local_words if i in k and i != k[index]]
        else:
            return {
                "details": "Invalid position !"
            }
    
    data_session_dict = session_data.dict()
    data_session_dict["words"] = local_words

    await backend.update(session_id, SessionData(**data_session_dict))
    cookie.attach_to_response(response, session_id)

    return {
        "count": len(local_words),
        "words": local_words
    }

@app.get('/game_details', dependencies=[Depends(cookie)])
async def game_details(session_data: SessionData = Depends(verifier)):
    return {
        "uuid": session_data.user_uuid,
        "count": len(session_data.words),
        "words": session_data.words
    }

@app.get('/end_game', dependencies=[Depends(cookie)])
async def end_game(response: Response, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    cookie.delete_from_response(response)

    return {
        "details": "Game deleted !"
    }


if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)
