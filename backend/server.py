from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, io, csv, logging, uuid, shutil, re
from urllib.parse import parse_qs, urlparse

def _env_flag(name: str, default: str = '1') -> bool:
    val = os.environ.get(name, default)
    return str(val).strip().lower() not in {'0', 'false', 'no', 'off', ''}

USE_MOCK_DB = _env_flag('USE_MOCK_DB', '1')
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from .auth import (
        LoginIn, ChangePasswordIn, TokenOut,
        issue_token, verify_pw, hash_pw,
        ensure_default_admin, require_admin,
    )
except ImportError:  # pragma: no cover - support running as a script from backend/
    from auth import (
        LoginIn, ChangePasswordIn, TokenOut,
        issue_token, verify_pw, hash_pw,
        ensure_default_admin, require_admin,
    )

ROOT_DIR = Path(__file__).parent
UPLOAD_DIR = ROOT_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'njeduhub')

def create_db_client():
    if USE_MOCK_DB:
        try:
            import mongomock_motor
            logger = logging.getLogger('njeduhub')
            logger.info('Using mock MongoDB client for local development')
            return mongomock_motor.AsyncMongoMockClient(mongo_url)
        except Exception:
            pass
    return AsyncIOMotorClient(mongo_url)

client = create_db_client()
db = client[db_name]

app = FastAPI(title='NJ Edu-Hub API')
api = APIRouter(prefix='/api')

logger = logging.getLogger('njeduhub')
logging.basicConfig(level=logging.INFO)

# ---------- Helpers ----------
def now_iso() -> str:
    return datetime.utcnow().isoformat()

def strip_id(doc: dict) -> dict:
    if not doc: return doc
    doc.pop('_id', None)
    doc.pop('password_hash', None)
    return doc

# ---------- Models ----------
LeadStatus = Literal['new', 'contacted', 'enrolled', 'lost']

class IDModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=now_iso)

class Course(IDModel):
    slug: str
    title: str
    duration: str
    audience: str
    price: str
    short: str
    image: str
    highlights: List[str] = []
    subjects: List[str] = []
    detail: str = ''
    is_active: bool = True

class Faculty(IDModel):
    name: str
    subject: str
    exp: str
    img: str
    credentials: str = ''
    bio: str = ''

class Blog(IDModel):
    slug: str
    title: str
    excerpt: str
    author: str
    category: str
    cover: str
    body: str
    date: str = ''

class Testimonial(IDModel):
    name: str
    rank: str
    img: str
    text: str

class Topper(IDModel):
    name: str
    rank: str
    score: str
    img: str
    year: int = 2026

class ResultRecord(IDModel):
    year: int
    name: str
    rank: str
    exam: str
    college: str

class GalleryItem(IDModel):
    url: str
    caption: str = ''

class NewsItem(IDModel):
    title: str
    date: str
    img: str
    desc: str

class Banner(IDModel):
    title: str
    subtitle: str = ''
    image: str
    cta: str = 'Learn More'
    link: str = '/'
    order: int = 0
    is_active: bool = True

class Counter(IDModel):
    value: int = 0
    prefix: str = ''
    suffix: str = ''
    label: str = ''

class FAQ(IDModel):
    question: str
    answer: str

class ProgramStrip(IDModel):
    code: str
    title: str
    sub: str = ''
    desc: str = ''
    href: str = '/courses'

class WhyUsItem(IDModel):
    icon: str = 'Sparkles'
    title: str
    desc: str = ''

class Centre(IDModel):
    name: str
    city: str = ''
    address: str = ''

class SEOConfig(IDModel):
    page: str
    title: str = ''
    description: str = ''
    keywords: str = ''
    og_image: str = ''

class SiteSetting(IDModel):
    key: str
    value: str = ''
    group: str = 'site'

class HomePageSection(IDModel):
    section: str = 'homepage'
    title: str = ''
    subtitle: str = ''
    description: str = ''
    image: str = ''
    status: str = 'active'

class Video(IDModel):
    title: str
    video_url: str
    embed_url: str = ''
    thumbnail_url: str = ''
    description: str = ''
    category: str = 'Campus Tour'
    display_order: int = 0
    is_published: bool = True
    is_featured: bool = False
    show_on_homepage: bool = True
    updated_at: str = Field(default_factory=now_iso)

class Exam(IDModel):
    exam_name: str
    description: str = ''
    academic_level: str = ''
    class_level: str = ''
    subject: str = ''
    exam_type: str = ''
    academic_year: str = ''
    exam_date: str = ''
    start_time: str = ''
    end_time: str = ''
    duration: str = ''
    registration_deadline: str = ''
    timezone: str = 'Asia/Kolkata'
    general_instructions: str = ''
    exam_specific_instructions: str = ''
    required_materials: str = ''
    rules_and_restrictions: str = ''
    additional_notes: str = ''
    classplus_url: str = ''
    registration_url: str = ''
    result_url: str = ''
    action_button_label: str = 'Register Now'
    is_published: bool = True
    access_enabled: bool = True
    display_order: int = 0
    is_featured: bool = False
    status: str = 'Scheduled'
    updated_at: str = Field(default_factory=now_iso)

class LectureSubject(IDModel):
    name: str
    slug: str = ''
    description: str = ''
    thumbnail: str = ''
    is_published: bool = True
    display_order: int = 0
    updated_at: str = Field(default_factory=now_iso)

class Lecture(IDModel):
    subject_id: str
    subject_name: str = ''
    title: str
    lecture_topic: str = ''
    chapter_or_unit: str = ''
    description: str = ''
    instructor_name: str = ''
    lecture_date: str = ''
    thumbnail_url: str = ''
    video_url: str = ''
    duration: str = ''
    language: str = 'English'
    is_published: bool = True
    display_order: int = 0
    updated_at: str = Field(default_factory=now_iso)


def _generate_embed_url(video_url: str) -> str:
    if not video_url or not isinstance(video_url, str):
        raise ValueError('Video URL is required.')
    video_url = video_url.strip()
    if not video_url.startswith(('http://', 'https://')):
        raise ValueError('Only HTTP/HTTPS video URLs are allowed.')

    parsed = urlparse(video_url)
    host = (parsed.netloc or '').lower()

    if 'youtube.com' in host or 'youtu.be' in host or 'm.youtube.com' in host:
        video_id = None
        if 'youtu.be' in host:
            video_id = parsed.path.strip('/').split('/')[0]
        else:
            qs = parse_qs(parsed.query)
            video_id = qs.get('v', [None])[0]
            if not video_id and parsed.path.startswith('/shorts/'):
                video_id = parsed.path.strip('/').split('/')[-1]
            if not video_id and parsed.path.startswith('/embed/'):
                video_id = parsed.path.strip('/').split('/')[-1]
        if not video_id or len(video_id) < 6:
            raise ValueError('Invalid YouTube video URL.')
        return f'https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1'

    if 'vimeo.com' in host:
        match = re.search(r'/video/(\d+)', parsed.path)
        if not match:
            raise ValueError('Invalid Vimeo video URL.')
        video_id = match.group(1)
        return f'https://player.vimeo.com/video/{video_id}?title=0&byline=0&portrait=0'

    raise ValueError('Unsupported video hosting provider. Use YouTube or Vimeo URLs only.')


def _extract_video_id(video_url: str) -> Optional[str]:
    if not video_url:
        return None
    parsed = urlparse(video_url)
    host = (parsed.netloc or '').lower()
    if 'youtube.com' in host or 'm.youtube.com' in host:
        qs = parse_qs(parsed.query)
        vid = qs.get('v', [None])[0]
        if vid:
            return vid
        if parsed.path.startswith('/shorts/'):
            return parsed.path.strip('/').split('/')[-1]
        if parsed.path.startswith('/embed/'):
            return parsed.path.strip('/').split('/')[-1]
    if 'youtu.be' in host:
        return parsed.path.strip('/').split('/')[0]
    if 'vimeo.com' in host:
        match = re.search(r'/video/(\d+)', parsed.path)
        if match:
            return match.group(1)
    return None


def _generate_thumbnail_url(video_url: str) -> str:
    media_id = _extract_video_id(video_url)
    if not media_id:
        return ''
    if 'youtube.com' in (urlparse(video_url).netloc or '').lower() or 'youtu.be' in (urlparse(video_url).netloc or '').lower():
        return f'https://img.youtube.com/vi/{media_id}/hqdefault.jpg'
    if 'vimeo.com' in (urlparse(video_url).netloc or '').lower():
        return f'https://vumbnail.com/{media_id}.jpg'
    return ''


def _normalize_media_thumbnail(value: str, fallback_video_url: str = '') -> str:
    raw = (value or '').strip()
    if raw:
        fallback = _generate_thumbnail_url(raw)
        return fallback or raw
    if fallback_video_url:
        return _generate_thumbnail_url(fallback_video_url) or fallback_video_url
    return ''


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def normalize_video_payload(data: dict) -> dict:
    payload = dict(data)
    payload['title'] = (payload.get('title') or '').strip()
    if not payload['title']:
        raise ValueError('Video title is required.')

    video_url = (payload.get('video_url') or '').strip()
    if not video_url:
        raise ValueError('Video URL is required.')
    payload['video_url'] = video_url

    try:
        payload['embed_url'] = _generate_embed_url(video_url)
    except ValueError as exc:
        raise exc

    thumbnail = (payload.get('thumbnail_url') or '').strip()
    if not thumbnail:
        thumbnail = _generate_thumbnail_url(video_url)
    if thumbnail and not thumbnail.startswith(('http://', 'https://')):
        raise ValueError('Thumbnail URL must use http or https.')
    payload['thumbnail_url'] = thumbnail

    payload['category'] = (payload.get('category') or 'Campus Tour').strip() or 'Campus Tour'
    payload['description'] = (payload.get('description') or '').strip()
    payload['display_order'] = int(payload.get('display_order', 0) or 0)
    payload['is_published'] = _coerce_bool(payload.get('is_published', True))
    payload['is_featured'] = _coerce_bool(payload.get('is_featured', False))
    payload['show_on_homepage'] = _coerce_bool(payload.get('show_on_homepage', True))
    payload['updated_at'] = now_iso()
    if not payload.get('created_at'):
        payload['created_at'] = now_iso()
    return payload


def _is_valid_https_url(value: str) -> bool:
    if not value:
        return False
    candidate = value.strip()
    if not candidate.startswith('https://'):
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(candidate)
        return bool(parsed.scheme == 'https' and parsed.netloc)
    except Exception:
        return False


def _normalize_time_value(value: str) -> str:
    raw = (str(value or '00:00')).strip()
    if not raw:
        return '00:00'
    match = re.fullmatch(r'(?i)(\d{1,2}):(\d{2})\s*(AM|PM)?', raw)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = (match.group(3) or '').upper()
        if meridiem == 'AM' and hour == 12:
            hour = 0
        elif meridiem == 'PM' and hour < 12:
            hour += 12
        return f'{hour:02d}:{minute:02d}'
    return raw


def _maybe_parse_dt(date_value: str, time_value: str = '00:00', tz_name: str = 'Asia/Kolkata') -> Optional[datetime]:
    if not date_value:
        return None

    candidate = str(date_value).strip()
    time_part = _normalize_time_value(time_value)
    tzinfo = ZoneInfo(tz_name) if tz_name else None

    if 'T' in candidate:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.replace(tzinfo=tzinfo) if tzinfo and dt.tzinfo is None else dt
        except ValueError:
            pass

    if ' ' in candidate and ':' in candidate.split()[-1]:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.replace(tzinfo=tzinfo) if tzinfo and dt.tzinfo is None else dt
        except ValueError:
            pass

    for date_fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            date_dt = datetime.strptime(candidate, date_fmt)
            combined = datetime.strptime(f"{date_dt.strftime('%Y-%m-%d')} {time_part}", '%Y-%m-%d %H:%M')
            return combined.replace(tzinfo=tzinfo) if tzinfo else combined
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(f'{candidate}T{time_part}')
        return dt.replace(tzinfo=tzinfo) if tzinfo and dt.tzinfo is None else dt
    except ValueError:
        return None


def compute_exam_status(exam: dict, now_override: Optional[datetime] = None) -> str:
    if not exam:
        return 'Scheduled'

    raw_status = str(exam.get('status') or '').strip().lower()
    if raw_status == 'cancelled':
        return 'Cancelled'

    exam_date = str(exam.get('exam_date') or '')
    start_time = str(exam.get('start_time') or '00:00')
    end_time = str(exam.get('end_time') or '00:00')
    timezone_name = (str(exam.get('timezone') or 'Asia/Kolkata')).strip() or 'Asia/Kolkata'
    tz = ZoneInfo(timezone_name)
    now = now_override if now_override is not None else datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    start_dt = _maybe_parse_dt(exam_date, start_time, timezone_name)
    end_dt = _maybe_parse_dt(exam_date, end_time, timezone_name)

    if start_dt and end_dt:
        if now < start_dt:
            registration_deadline = exam.get('registration_deadline')
            if registration_deadline:
                deadline_value = str(registration_deadline).strip()
                deadline_dt = _maybe_parse_dt(
                    deadline_value.split('T')[0] if 'T' in deadline_value else deadline_value,
                    deadline_value.split('T')[1][:5] if 'T' in deadline_value and ':' in deadline_value.split('T')[1][:5] else '23:59',
                    timezone_name,
                )
                if deadline_dt and now <= deadline_dt:
                    return 'Registration Open'
            return 'Scheduled'
        if start_dt <= now < end_dt:
            return 'Live'
        if now >= end_dt:
            return 'Completed'

    if raw_status:
        return raw_status.title()
    return 'Scheduled'


def normalize_exam_payload(data: dict) -> dict:
    payload = dict(data)
    payload['exam_name'] = (payload.get('exam_name') or '').strip()
    if not payload['exam_name']:
        raise ValueError('Exam name is required.')
    payload['description'] = (payload.get('description') or '').strip()
    payload['academic_level'] = (payload.get('academic_level') or '').strip()
    payload['class_level'] = (payload.get('class_level') or '').strip()
    payload['subject'] = (payload.get('subject') or '').strip()
    payload['exam_type'] = (payload.get('exam_type') or '').strip()
    payload['academic_year'] = (payload.get('academic_year') or '').strip()
    payload['exam_date'] = (payload.get('exam_date') or '').strip()
    payload['start_time'] = (payload.get('start_time') or '').strip() or '09:00'
    payload['end_time'] = (payload.get('end_time') or '').strip() or '10:00'
    payload['duration'] = (payload.get('duration') or '').strip() or '60 mins'
    payload['registration_deadline'] = (payload.get('registration_deadline') or '').strip()
    payload['timezone'] = (payload.get('timezone') or 'Asia/Kolkata').strip() or 'Asia/Kolkata'
    payload['general_instructions'] = (payload.get('general_instructions') or '').strip()
    payload['exam_specific_instructions'] = (payload.get('exam_specific_instructions') or '').strip()
    payload['required_materials'] = (payload.get('required_materials') or '').strip()
    payload['rules_and_restrictions'] = (payload.get('rules_and_restrictions') or '').strip()
    payload['additional_notes'] = (payload.get('additional_notes') or '').strip()
    classplus_url = (payload.get('classplus_url') or '').strip()
    if classplus_url and not _is_valid_https_url(classplus_url):
        raise ValueError('Classplus URL must be a valid HTTPS URL.')
    payload['classplus_url'] = classplus_url
    registration_url = (payload.get('registration_url') or '').strip()
    if registration_url and not _is_valid_https_url(registration_url):
        raise ValueError('Registration URL must be a valid HTTPS URL.')
    payload['registration_url'] = registration_url
    result_url = (payload.get('result_url') or '').strip()
    if result_url and not _is_valid_https_url(result_url):
        raise ValueError('Result URL must be a valid HTTPS URL.')
    payload['result_url'] = result_url
    payload['action_button_label'] = (payload.get('action_button_label') or 'Register Now').strip() or 'Register Now'
    payload['is_published'] = _coerce_bool(payload.get('is_published', True))
    payload['access_enabled'] = _coerce_bool(payload.get('access_enabled', True))
    payload['display_order'] = int(payload.get('display_order', 0) or 0)
    payload['is_featured'] = _coerce_bool(payload.get('is_featured', False))
    payload['status'] = (payload.get('status') or 'Scheduled').strip() or 'Scheduled'
    payload['updated_at'] = now_iso()
    if not payload.get('created_at'):
        payload['created_at'] = now_iso()
    payload['computed_status'] = compute_exam_status(payload)
    return payload


def normalize_lecture_subject_payload(data: dict) -> dict:
    payload = dict(data)
    payload['name'] = (payload.get('name') or '').strip()
    if not payload['name']:
        raise ValueError('Subject name is required.')
    payload['slug'] = (payload.get('slug') or payload['name']).strip().lower().replace(' ', '-')
    payload['description'] = (payload.get('description') or '').strip()
    payload['thumbnail'] = _normalize_media_thumbnail(payload.get('thumbnail') or '', '')
    if payload['thumbnail'] and not payload['thumbnail'].startswith(('http://', 'https://')):
        raise ValueError('Thumbnail URL must use http or https.')
    payload['is_published'] = _coerce_bool(payload.get('is_published', True))
    payload['display_order'] = int(payload.get('display_order', 0) or 0)
    payload['updated_at'] = now_iso()
    if not payload.get('created_at'):
        payload['created_at'] = now_iso()
    return payload


def normalize_lecture_payload(data: dict) -> dict:
    payload = dict(data)
    payload['subject_id'] = (payload.get('subject_id') or '').strip()
    if not payload['subject_id']:
        raise ValueError('A valid subject is required.')
    payload['subject_name'] = (payload.get('subject_name') or '').strip()
    payload['title'] = (payload.get('title') or '').strip()
    if not payload['title']:
        raise ValueError('Lecture title is required.')
    payload['lecture_topic'] = (payload.get('lecture_topic') or '').strip()
    payload['chapter_or_unit'] = (payload.get('chapter_or_unit') or '').strip()
    payload['description'] = (payload.get('description') or '').strip()
    payload['instructor_name'] = (payload.get('instructor_name') or '').strip()
    payload['lecture_date'] = (payload.get('lecture_date') or '').strip()
    payload['thumbnail_url'] = _normalize_media_thumbnail(payload.get('thumbnail_url') or '', payload.get('video_url') or '')
    if payload['thumbnail_url'] and not payload['thumbnail_url'].startswith(('http://', 'https://')):
        raise ValueError('Thumbnail URL must use http or https.')
    payload['video_url'] = (payload.get('video_url') or '').strip()
    if payload['video_url'] and not _is_valid_https_url(payload['video_url']):
        raise ValueError('Lecture URL must be a valid HTTPS URL.')
    payload['duration'] = (payload.get('duration') or '').strip()
    payload['language'] = (payload.get('language') or 'English').strip() or 'English'
    payload['is_published'] = _coerce_bool(payload.get('is_published', True))
    payload['display_order'] = int(payload.get('display_order', 0) or 0)
    payload['updated_at'] = now_iso()
    if not payload.get('created_at'):
        payload['created_at'] = now_iso()
    return payload

# Lead models
class Inquiry(IDModel):
    name: str
    phone: str
    email: str
    city: str = ''
    course: str = ''
    message: str = ''
    status: LeadStatus = 'new'

class Admission(IDModel):
    name: str
    dob: str = ''
    gender: str = ''
    email: str
    phone: str
    father: str = ''
    mother: str = ''
    city: str = ''
    school: str = ''
    stream: str = ''
    percent: str = ''
    course: str = ''
    mode: str = ''
    message: str = ''
    status: LeadStatus = 'new'

class Scholarship(IDModel):
    name: str
    email: str
    phone: str
    standard: str = ''
    city: str = ''
    status: LeadStatus = 'new'

class CareerApp(IDModel):
    name: str
    email: str
    phone: str
    role: str = ''
    message: str = ''
    status: LeadStatus = 'new'

class StatusUpdate(BaseModel):
    status: LeadStatus

# ---------- Health ----------
@api.get('/')
async def root():
    return {'message': 'Backend is working fine.'}

# ---------- AUTH endpoints ----------
@api.post('/admin/login', response_model=TokenOut)
async def admin_login(body: LoginIn):
    admin = await db.admins.find_one({'username': body.username})
    if not admin or not verify_pw(body.password, admin.get('password_hash', '')):
        raise HTTPException(status_code=401, detail='Invalid username or password')
    return TokenOut(token=issue_token(body.username), username=body.username)

@api.get('/admin/me')
async def admin_me(user: str = Depends(require_admin)):
    return {'username': user}

@api.post('/admin/change-password')
async def admin_change_password(body: ChangePasswordIn, user: str = Depends(require_admin)):
    admin = await db.admins.find_one({'username': user})
    if not admin or not verify_pw(body.current_password, admin.get('password_hash', '')):
        raise HTTPException(status_code=400, detail='Current password is incorrect')
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail='New password must be at least 6 characters')
    await db.admins.update_one({'username': user}, {'$set': {'password_hash': hash_pw(body.new_password)}})
    return {'ok': True}

# ---------- File Upload ----------
@api.post('/upload')
async def upload_image(file: UploadFile = File(...), _: str = Depends(require_admin)):
    """Accept an image upload and return a public URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f'Unsupported file type: {file.content_type}. Allowed: jpg, png, gif, webp, svg')
    # Read and check size
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail='File too large (max 10MB)')
    # Generate unique filename, preserve extension
    ext = (file.filename or '').rsplit('.', 1)[-1].lower() if '.' in (file.filename or '') else 'jpg'
    if len(ext) > 8 or not ext.isalnum():
        ext = 'jpg'
    fname = f'{uuid.uuid4().hex}.{ext}'
    fpath = UPLOAD_DIR / fname
    with open(fpath, 'wb') as f:
        f.write(contents)
    return {'url': f'/api/uploads/{fname}', 'filename': fname, 'size': len(contents)}

# ---------- Generic CRUD factory ----------
def build_crud(path: str, collection: str, model):
    """Public GET (list), admin POST / PUT / DELETE."""

    @api.get(f'/{path}')
    async def list_items():
        docs = await db[collection].find().sort('created_at', -1).to_list(1000)
        return [strip_id(d) for d in docs]

    @api.post(f'/{path}')
    async def create_item(item: model, _: str = Depends(require_admin)):
        d = item.dict()
        await db[collection].insert_one(d.copy())
        return d

    @api.put(f'/{path}/' + '{item_id}')
    async def update_item(item_id: str, item: model, _: str = Depends(require_admin)):
        d = item.dict(); d['id'] = item_id
        await db[collection].update_one({'id': item_id}, {'$set': d}, upsert=True)
        return d

    @api.delete(f'/{path}/' + '{item_id}')
    async def delete_item(item_id: str, _: str = Depends(require_admin)):
        await db[collection].delete_one({'id': item_id})
        return {'ok': True}

build_crud('courses', 'courses', Course)
build_crud('faculty', 'faculty', Faculty)
build_crud('blogs', 'blogs', Blog)
build_crud('testimonials', 'testimonials', Testimonial)
build_crud('toppers', 'toppers', Topper)
build_crud('results', 'results', ResultRecord)
build_crud('gallery', 'gallery', GalleryItem)
build_crud('news', 'news', NewsItem)
build_crud('banners', 'banners', Banner)
build_crud('counters', 'counters', Counter)
build_crud('faqs', 'faqs', FAQ)
build_crud('programs-strip', 'programs-strip', ProgramStrip)
build_crud('why-us', 'why-us', WhyUsItem)
build_crud('centres', 'centres', Centre)
build_crud('seo-manager', 'seo-manager', SEOConfig)
build_crud('site-settings', 'site-settings', SiteSetting)
build_crud('homepage-editor', 'homepage-editor', HomePageSection)


def serialize_exam_record(doc: dict) -> dict:
    item = dict(doc)
    item['status'] = compute_exam_status(item)
    return strip_id(item)


@api.get('/exams')
async def list_public_exams(
    subject: Optional[str] = None,
    class_filter: Optional[str] = None,
    exam_type: Optional[str] = None,
    view: Optional[str] = None,
):
    query = {'is_published': True}
    if subject:
        query['subject'] = {'$regex': subject, '$options': 'i'}
    if class_filter:
        query['class_level'] = {'$regex': class_filter, '$options': 'i'}
    if exam_type:
        query['exam_type'] = {'$regex': exam_type, '$options': 'i'}
    docs = await db.exams.find(query).sort('display_order', 1).sort('exam_date', 1).to_list(1000)
    items = [serialize_exam_record(d) for d in docs]
    if view == 'upcoming':
        items = [i for i in items if i.get('status') in {'Scheduled', 'Registration Open', 'Live'}]
    elif view == 'completed':
        items = [i for i in items if i.get('status') == 'Completed']
    return items


@api.get('/admin/exams')
async def list_admin_exams(
    subject: Optional[str] = None,
    class_filter: Optional[str] = None,
    exam_type: Optional[str] = None,
    _: str = Depends(require_admin),
):
    query = {}
    if subject:
        query['subject'] = {'$regex': subject, '$options': 'i'}
    if class_filter:
        query['class_level'] = {'$regex': class_filter, '$options': 'i'}
    if exam_type:
        query['exam_type'] = {'$regex': exam_type, '$options': 'i'}
    docs = await db.exams.find(query).sort('display_order', 1).sort('exam_date', 1).to_list(1000)
    return [serialize_exam_record(d) for d in docs]


@api.get('/exams/{exam_id}')
async def get_exam(exam_id: str):
    doc = await db.exams.find_one({'id': exam_id, 'is_published': True})
    if not doc:
        raise HTTPException(status_code=404, detail='Exam not found')
    return serialize_exam_record(doc)


@api.post('/admin/exams')
async def create_exam(item: Exam, _: str = Depends(require_admin)):
    payload = normalize_exam_payload(item.dict())
    payload['id'] = str(uuid.uuid4())
    await db.exams.insert_one(payload)
    return serialize_exam_record(payload)


@api.put('/admin/exams/{exam_id}')
async def update_exam(exam_id: str, item: Exam, _: str = Depends(require_admin)):
    payload = normalize_exam_payload(item.dict())
    payload['id'] = exam_id
    result = await db.exams.update_one({'id': exam_id}, {'$set': payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Exam not found')
    updated = await db.exams.find_one({'id': exam_id})
    return serialize_exam_record(updated)


@api.delete('/admin/exams/{exam_id}')
async def delete_exam(exam_id: str, _: str = Depends(require_admin)):
    result = await db.exams.delete_one({'id': exam_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail='Exam not found')
    return {'ok': True}


@api.get('/lecture-subjects')
async def list_public_lecture_subjects():
    docs = await db.lecture_subjects.find({'is_published': True}).sort('display_order', 1).sort('created_at', -1).to_list(1000)
    return [strip_id(d) for d in docs]


@api.get('/admin/lecture-subjects')
async def list_admin_lecture_subjects(_: str = Depends(require_admin)):
    docs = await db.lecture_subjects.find({}).sort('display_order', 1).sort('created_at', -1).to_list(1000)
    return [strip_id(d) for d in docs]


@api.get('/lecture-subjects/{subject_id}')
async def get_lecture_subject(subject_id: str):
    doc = await db.lecture_subjects.find_one({'id': subject_id, 'is_published': True})
    if not doc:
        raise HTTPException(status_code=404, detail='Subject not found')
    return strip_id(doc)


@api.post('/admin/lecture-subjects')
async def create_lecture_subject(item: LectureSubject, _: str = Depends(require_admin)):
    payload = normalize_lecture_subject_payload(item.dict())
    payload['id'] = str(uuid.uuid4())
    await db.lecture_subjects.insert_one(payload)
    return strip_id(payload)


@api.put('/admin/lecture-subjects/{subject_id}')
async def update_lecture_subject(subject_id: str, item: LectureSubject, _: str = Depends(require_admin)):
    payload = normalize_lecture_subject_payload(item.dict())
    payload['id'] = subject_id
    result = await db.lecture_subjects.update_one({'id': subject_id}, {'$set': payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Subject not found')
    updated = await db.lecture_subjects.find_one({'id': subject_id})
    return strip_id(updated)


@api.delete('/admin/lecture-subjects/{subject_id}')
async def delete_lecture_subject(subject_id: str, _: str = Depends(require_admin)):
    if await db.lectures.count_documents({'subject_id': subject_id}):
        raise HTTPException(status_code=400, detail='Delete or reassign lectures before removing this subject.')
    result = await db.lecture_subjects.delete_one({'id': subject_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail='Subject not found')
    return {'ok': True}


@api.get('/lectures')
async def list_public_lectures(subject_id: Optional[str] = None):
    query = {'is_published': True}
    if subject_id:
        query['subject_id'] = subject_id
    docs = await db.lectures.find(query).sort('display_order', 1).sort('created_at', -1).to_list(2000)
    return [strip_id(d) for d in docs]


@api.get('/admin/lectures')
async def list_admin_lectures(subject_id: Optional[str] = None, _: str = Depends(require_admin)):
    query = {}
    if subject_id:
        query['subject_id'] = subject_id
    docs = await db.lectures.find(query).sort('display_order', 1).sort('created_at', -1).to_list(2000)
    return [strip_id(d) for d in docs]


@api.get('/lectures/{lecture_id}')
async def get_lecture(lecture_id: str):
    doc = await db.lectures.find_one({'id': lecture_id, 'is_published': True})
    if not doc:
        raise HTTPException(status_code=404, detail='Lecture not found')
    return strip_id(doc)


@api.post('/admin/lectures')
async def create_lecture(item: Lecture, _: str = Depends(require_admin)):
    if not await db.lecture_subjects.find_one({'id': item.subject_id}):
        raise HTTPException(status_code=400, detail='Subject not found.')
    payload = normalize_lecture_payload(item.dict())
    payload['id'] = str(uuid.uuid4())
    await db.lectures.insert_one(payload)
    return strip_id(payload)


@api.put('/admin/lectures/{lecture_id}')
async def update_lecture(lecture_id: str, item: Lecture, _: str = Depends(require_admin)):
    if not await db.lecture_subjects.find_one({'id': item.subject_id}):
        raise HTTPException(status_code=400, detail='Subject not found.')
    payload = normalize_lecture_payload(item.dict())
    payload['id'] = lecture_id
    result = await db.lectures.update_one({'id': lecture_id}, {'$set': payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Lecture not found')
    updated = await db.lectures.find_one({'id': lecture_id})
    return strip_id(updated)


@api.delete('/admin/lectures/{lecture_id}')
async def delete_lecture(lecture_id: str, _: str = Depends(require_admin)):
    result = await db.lectures.delete_one({'id': lecture_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail='Lecture not found')
    return {'ok': True}


@api.get('/videos')
async def list_public_videos(category: Optional[str] = None, published: Optional[bool] = None, homepage: Optional[bool] = None):
    query = {'is_published': True}
    if category:
        query['category'] = category
    if homepage is not None:
        query['show_on_homepage'] = homepage
    if published is not None:
        query['is_published'] = published
    docs = await db.videos.find(query).sort('display_order', 1).sort('created_at', -1).to_list(1000)
    return [strip_id(d) for d in docs]

@api.get('/admin/videos')
async def list_admin_videos(category: Optional[str] = None, published: Optional[bool] = None, _: str = Depends(require_admin)):
    query = {}
    if category:
        query['category'] = category
    if published is not None:
        query['is_published'] = published
    docs = await db.videos.find(query).sort('display_order', 1).sort('created_at', -1).to_list(1000)
    return [strip_id(d) for d in docs]

@api.post('/admin/videos')
async def create_video(item: Video, _: str = Depends(require_admin)):
    payload = normalize_video_payload(item.dict())
    payload['id'] = str(uuid.uuid4())
    await db.videos.insert_one(payload)
    return payload

@api.get('/admin/videos/{video_id}')
async def get_video(video_id: str, _: str = Depends(require_admin)):
    doc = await db.videos.find_one({'id': video_id})
    if not doc:
        raise HTTPException(status_code=404, detail='Video not found')
    return strip_id(doc)

@api.put('/admin/videos/{video_id}')
async def update_video(video_id: str, item: Video, _: str = Depends(require_admin)):
    payload = normalize_video_payload(item.dict())
    payload['id'] = video_id
    payload['updated_at'] = now_iso()
    result = await db.videos.update_one({'id': video_id}, {'$set': payload}, upsert=True)
    if result.matched_count == 0 and result.upserted_id is None:
        raise HTTPException(status_code=404, detail='Video not found')
    updated = await db.videos.find_one({'id': video_id})
    return strip_id(updated)

@api.delete('/admin/videos/{video_id}')
async def delete_video(video_id: str, _: str = Depends(require_admin)):
    result = await db.videos.delete_one({'id': video_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail='Video not found')
    return {'ok': True}

@api.patch('/admin/videos/{video_id}/status')
async def patch_video_status(video_id: str, body: dict, _: str = Depends(require_admin)):
    if 'is_published' not in body and 'show_on_homepage' not in body:
        raise HTTPException(status_code=400, detail='Missing status update fields.')
    updates = {}
    if 'is_published' in body:
        updates['is_published'] = bool(body['is_published'])
    if 'show_on_homepage' in body:
        updates['show_on_homepage'] = bool(body['show_on_homepage'])
    updates['updated_at'] = now_iso()
    result = await db.videos.update_one({'id': video_id}, {'$set': updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Video not found')
    updated = await db.videos.find_one({'id': video_id})
    return strip_id(updated)

# ---------- Single fetch by slug ----------
@api.get('/courses/slug/{slug}')
async def course_by_slug(slug: str):
    d = await db.courses.find_one({'slug': slug})
    if not d: raise HTTPException(404, 'Not found')
    return strip_id(d)

@api.get('/blogs/slug/{slug}')
async def blog_by_slug(slug: str):
    d = await db.blogs.find_one({'slug': slug})
    if not d: raise HTTPException(404, 'Not found')
    return strip_id(d)

# ---------- Lead endpoints (public POST, admin GET/PATCH/DELETE/CSV) ----------
def build_leads(path: str, coll: str, model):
    @api.post(f'/{path}', name=f'create_{path}')
    async def create(item: model):
        d = item.dict()
        await db[coll].insert_one(d.copy())
        return d

    @api.get(f'/{path}', name=f'list_{path}')
    async def lst(status: Optional[str] = None, _: str = Depends(require_admin)):
        q = {} if not status else {'status': status}
        docs = await db[coll].find(q).sort('created_at', -1).to_list(2000)
        return [strip_id(d) for d in docs]

    @api.patch(f'/{path}/' + '{item_id}', name=f'update_{path}')
    async def upd(item_id: str, body: StatusUpdate, _: str = Depends(require_admin)):
        await db[coll].update_one({'id': item_id}, {'$set': {'status': body.status}})
        d = await db[coll].find_one({'id': item_id})
        if not d: raise HTTPException(404, 'Not found')
        return strip_id(d)

    @api.put(f'/{path}/' + '{item_id}', name=f'full_update_{path}')
    async def full_upd(item_id: str, item: model, _: str = Depends(require_admin)):
        """Admin can edit any field on a lead."""
        d = item.dict(); d['id'] = item_id
        await db[coll].update_one({'id': item_id}, {'$set': d}, upsert=True)
        return d

    @api.delete(f'/{path}/' + '{item_id}', name=f'delete_{path}')
    async def dele(item_id: str, _: str = Depends(require_admin)):
        await db[coll].delete_one({'id': item_id})
        return {'ok': True}

    @api.get(f'/{path}/export.csv', name=f'export_{path}')
    async def export(token: Optional[str] = None):
        # Allow CSV download via ?token=<jwt> since browsers can't easily set
        # Authorization headers on plain anchor downloads.
        from auth import decode_token
        if not token or not decode_token(token):
            raise HTTPException(status_code=401, detail='Invalid or missing token')
        docs = await db[coll].find().sort('created_at', -1).to_list(5000)
        if not docs:
            return StreamingResponse(io.StringIO('No data'), media_type='text/csv')
        fields = [k for k in docs[0].keys() if k not in ('_id', 'password_hash')]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        for d in docs:
            d.pop('_id', None); d.pop('password_hash', None)
            w.writerow({k: d.get(k, '') for k in fields})
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename={path}.csv'})

build_leads('inquiries',   'inquiries',   Inquiry)
build_leads('admissions',  'admissions',  Admission)
build_leads('scholarship', 'scholarship', Scholarship)
build_leads('careers',     'careers',     CareerApp)

# ---------- Dashboard (admin) ----------
@api.get('/dashboard/stats')
async def dashboard(_: str = Depends(require_admin)):
    out = {}
    for c in ['inquiries','admissions','scholarship','careers']:
        out[c] = await db[c].count_documents({})
        out[f'{c}_new'] = await db[c].count_documents({'status': 'new'})
    out['courses'] = await db.courses.count_documents({})
    out['faculty'] = await db.faculty.count_documents({})
    out['blogs'] = await db.blogs.count_documents({})
    out['testimonials'] = await db.testimonials.count_documents({})
    out['toppers'] = await db.toppers.count_documents({})
    out['gallery'] = await db.gallery.count_documents({})
    out['news'] = await db.news.count_documents({})
    out['results'] = await db.results.count_documents({})
    out['banners'] = await db.banners.count_documents({})
    out['exams'] = await db.exams.count_documents({})
    out['lecture_subjects'] = await db.lecture_subjects.count_documents({})
    out['lectures'] = await db.lectures.count_documents({})
    return out

# ---------- Seed (admin) ----------
@api.post('/seed')
async def seed(_: str = Depends(require_admin)):
    try:
        from .seed_data import seed_db  # type: ignore
    except ImportError:  # pragma: no cover - support running as a script from backend/
        from seed_data import seed_db  # type: ignore
    return await seed_db(db)

# Public seed-once endpoint for first-run bootstrapping (idempotent)
@api.post('/seed-public')
async def seed_public():
    try:
        from .seed_data import seed_db  # type: ignore
    except ImportError:  # pragma: no cover - support running as a script from backend/
        from seed_data import seed_db  # type: ignore
    return await seed_db(db)

# ---------- App lifecycle ----------
@app.on_event('startup')
async def on_start():
    global client, db
    try:
        await ensure_default_admin(db)
    except Exception:
        if not USE_MOCK_DB:
            raise
        import mongomock_motor
        client = mongomock_motor.AsyncMongoMockClient(mongo_url)
        db = client[db_name]
        await ensure_default_admin(db)

    try:
        from .seed_data import seed_db  # type: ignore
    except ImportError:  # pragma: no cover - support running as a script from backend/
        from seed_data import seed_db  # type: ignore
    await seed_db(db)
    logger.info('Default admin ensured (admin / admin@123) and seed data initialized')

@app.on_event('shutdown')
async def shutdown_db_client():
    client.close()

# Include router
app.include_router(api)

# Mount static files for uploaded images (must be after router include so /api/uploads/* resolves)
app.mount('/api/uploads', StaticFiles(directory=str(UPLOAD_DIR)), name='uploads')

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)
