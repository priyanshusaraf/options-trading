"""Exact browser auth routes, registered at both existing API mounts."""
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError

from app.accounts import browser_auth as auth
from app.core.config import get_settings
from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix='/api/auth', tags=['browser-session'])
PUBLIC_ROUTES = frozenset({('POST', '/api/auth/login'), ('POST', '/api/auth/enroll')})
AUTH_ROUTES = PUBLIC_ROUTES | frozenset({('GET', '/api/auth/session'), *(
    ('POST', '/api/auth/' + name) for name in ('logout', 'logout-all', 'password', 'organization'))})


def clear_cookie(response):
    response.delete_cookie(auth.COOKIE, path='/', secure=True, httponly=True, samesite='lax')


def refusal(status: int):
    response = JSONResponse({'error': 'authentication unavailable' if status == 503 else 'authentication refused'},
                            status_code=status, headers={'Cache-Control': 'no-store'})
    if status == 401:
        clear_cookie(response)
    if status in {429, 503}:
        response.headers['Retry-After'] = '60'
    return response


async def read_body(request: Request, fields: set[str]) -> dict:
    if request.headers.getlist('content-type') != ['application/json']:
        raise auth.AuthRefusal(415)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > auth.MAX_BODY:
            raise auth.AuthRefusal(413)
        raw.extend(chunk)
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise auth.AuthRefusal(400) from None
    if not isinstance(value, dict) or set(value) != fields or any(not isinstance(v, str) for v in value.values()):
        raise auth.AuthRefusal(400)
    return value


def perform(action: str, data: dict, token: str | None, client: str):
    if action in {'login', 'enroll'}:
        email = auth.normalize_email(data['email'])
        auth.admit_attempt(email, client)
        if action == 'login':
            return auth.login(email, data['password'], token)
        return auth.enroll(email, data['password'], data['display_name'], data['invitation'], token)
    if action in {'password', 'logout-all'}:
        principal = auth.browser_principal(token)
        with SessionLocal() as session:
            email = session.get(User, principal.user_id).email_normalized
        auth.admit_attempt(email, client)
    return auth.mutate_session(token, action, **data)


async def dispatch(request: Request, action: str):
    if not auth.validate_configuration(get_settings()):
        return refusal(503)
    acquired = False
    try:
        auth.check_origin(request, mutation=action != 'session')
        token = auth.cookie_token(request)
        if action == 'session':
            if token is None:
                raise auth.AuthRefusal()
            value = await run_in_threadpool(auth.bootstrap, token)
            return JSONResponse(value, headers={'Cache-Control': 'no-store'})
        if action not in {'login', 'enroll'}:
            if token is None:
                raise auth.AuthRefusal()
            auth.check_csrf(request, token)
        fields = {'login': {'email', 'password'},
                  'enroll': {'email', 'password', 'display_name', 'invitation'},
                  'logout': set(), 'logout-all': {'password'},
                  'password': {'password', 'new_password'}, 'organization': {'organization_id'}}[action]
        acquired = auth.AUTH_SLOTS.acquire(blocking=False)
        if not acquired:
            raise auth.AuthRefusal(503)
        data = await asyncio.wait_for(read_body(request, fields), timeout=10)
        client = request.client.host if request.client else 'unknown'
        issued = await run_in_threadpool(perform, action, data, token, client)
        response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
        if issued:
            response.set_cookie(auth.COOKIE, issued.token, max_age=43200,
                                path='/', secure=True, httponly=True, samesite='lax')
        else:
            clear_cookie(response)
        return response
    except auth.AuthRefusal as exc:
        return refusal(exc.status)
    except TimeoutError:
        return refusal(408)
    except (SQLAlchemyError, MemoryError):
        # Never expose SQL parameters, verifier material or database errors.
        return refusal(503)
    finally:
        if acquired:
            auth.AUTH_SLOTS.release()


@router.post('/login')
async def login(request: Request):
    return await dispatch(request, 'login')


@router.post('/enroll')
async def enroll(request: Request):
    return await dispatch(request, 'enroll')


@router.get('/session')
async def session(request: Request):
    return await dispatch(request, 'session')


@router.post('/logout')
async def logout(request: Request):
    return await dispatch(request, 'logout')


@router.post('/logout-all')
async def logout_all(request: Request):
    return await dispatch(request, 'logout-all')


@router.post('/password')
async def password(request: Request):
    return await dispatch(request, 'password')


@router.post('/organization')
async def organization(request: Request):
    return await dispatch(request, 'organization')
