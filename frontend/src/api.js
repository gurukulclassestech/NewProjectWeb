import axios from 'axios';
import { STORAGE_KEY } from './auth/AuthContext';

const API = (process.env.REACT_APP_API_URL || '/api').replace(/\/$/, '');

const http = axios.create({ baseURL: API, timeout: 20000 });

// Attach Bearer token automatically when available.
http.interceptors.request.use((config) => {
  try {
    const auth = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (auth?.token) config.headers.Authorization = `Bearer ${auth.token}`;
  } catch {}
  return config;
});

// On 401, wipe local auth so next render redirects to login.
http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem(STORAGE_KEY);
      // Only redirect if we're inside admin
      if (window.location.pathname.startsWith('/admin-x9k2')) {
        window.location.replace('/admin-x9k2/login');
      }
    }
    return Promise.reject(err);
  }
);

const getToken = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')?.token; } catch { return null; }
};

export const api = {
  // Public content
  courses:       () => http.get('/courses').then(r => r.data),
  courseBySlug:  (slug) => http.get(`/courses/slug/${slug}`).then(r => r.data),
  faculty:       () => http.get('/faculty').then(r => r.data),
  blogs:         () => http.get('/blogs').then(r => r.data),
  blogBySlug:    (slug) => http.get(`/blogs/slug/${slug}`).then(r => r.data),
  testimonials:  () => http.get('/testimonials').then(r => r.data),
  toppers:       () => http.get('/toppers').then(r => r.data),
  results:       () => http.get('/results').then(r => r.data),
  gallery:       () => http.get('/gallery').then(r => r.data),
  videos:        (params = {}) => http.get('/videos', { params }).then(r => r.data),
  news:          () => http.get('/news').then(r => r.data),
  banners:       () => http.get('/banners').then(r => r.data),

  // Lead submissions (public)
  submitInquiry:    (data) => http.post('/inquiries', data).then(r => r.data),
  submitAdmission:  (data) => http.post('/admissions', data).then(r => r.data),
  submitScholarship:(data) => http.post('/scholarship', data).then(r => r.data),
  submitCareer:     (data) => http.post('/careers', data).then(r => r.data),

  // Admin
  stats:         () => http.get('/dashboard/stats').then(r => r.data),
  list:          (path, params={}) => http.get(`/${path}`, { params }).then(r => r.data),
  create:        (path, data) => http.post(`/${path}`, data).then(r => r.data),
  update:        (path, id, data) => http.put(`/${path}/${id}`, data).then(r => r.data),
  patchStatus:   (path, id, status) => http.patch(`/${path}/${id}`, { status }).then(r => r.data),
  remove:        (path, id) => http.delete(`/${path}/${id}`).then(r => r.data),
  csvUrl:        (path) => `${API}/${path}/export.csv?token=${encodeURIComponent(getToken() || '')}`,
};

export default api;
