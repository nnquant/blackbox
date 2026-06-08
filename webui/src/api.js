import { t } from './i18n';

const API_BASE = import.meta.env.VITE_BLACKBOX_API_BASE || '';
const STATIC_TOKEN = import.meta.env.VITE_BLACKBOX_TOKEN || '';
const TOKEN_STORAGE_KEY = 'blackbox.apiToken';

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  return unwrap(response);
}

export async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body || {}),
  });
  return unwrap(response);
}

export async function apiPatch(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body || {}),
  });
  return unwrap(response);
}

export async function apiUpload(path, file, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  });
  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(),
    body: file,
  });
  return unwrap(response);
}

export function getApiToken() {
  return STATIC_TOKEN || window.localStorage.getItem(TOKEN_STORAGE_KEY) || '';
}

export function setApiToken(token) {
  if (STATIC_TOKEN) return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function websocketUrl(path) {
  const base = API_BASE || window.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = getApiToken();
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

export function artifactContentUrl(artifactId) {
  const base = API_BASE || window.location.origin;
  const url = new URL(`/api/v1/artifacts/${artifactId}/content`, base);
  const token = getApiToken();
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

function authHeaders() {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function unwrap(response) {
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      const error = new Error(t('API returned a non-JSON response. Start the FastAPI server or set VITE_BLACKBOX_API_BASE.'));
      error.code = 'INVALID_JSON_RESPONSE';
      error.status = response.status;
      throw error;
    }
  }
  if (!payload) {
    const error = new Error(t('API returned an empty response. Start the FastAPI server or set VITE_BLACKBOX_API_BASE.'));
    error.code = 'EMPTY_RESPONSE';
    error.status = response.status;
    throw error;
  }
  if (!response.ok || !payload.ok) {
    const message = payload?.error?.message || t('API request failed');
    const error = new Error(message);
    error.code = payload?.error?.code;
    error.status = response.status;
    throw error;
  }
  return payload.data;
}

export function metricValue(run, namespace, key) {
  const value = run?.summary_json?.[namespace]?.[key];
  return value === undefined || value === null ? null : value;
}

export function formatMetric(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '--';
  if (typeof value === 'number') return value.toFixed(digits);
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : String(value);
}
