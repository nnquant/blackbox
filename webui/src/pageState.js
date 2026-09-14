import { useEffect, useRef, useState } from 'react';

const storageKey = (scope) => `blackbox.page:${scope}`;

export function savedPageQuery(scope) {
  try { return window.sessionStorage.getItem(storageKey(scope)) || ''; } catch { return ''; }
}

// URL is authoritative for shared links; session state restores navigation within this tab.
export function usePageQuery(scope, key, initial) {
  const read = () => {
    const query = window.location.pathname === scope ? window.location.search : savedPageQuery(scope);
    try {
      const raw = new URLSearchParams(query).get(key);
      const value = raw === null ? initial : JSON.parse(raw);
      if (value === null || typeof value !== typeof initial || Array.isArray(value) !== Array.isArray(initial)) return initial;
      return value;
    } catch { return initial; }
  };
  const [value, setValue] = useState(read);
  const stateScope = useRef(`${scope}:${key}`);
  if (stateScope.current !== `${scope}:${key}`) {
    stateScope.current = `${scope}:${key}`;
    setValue(read());
  }
  useEffect(() => {
    const restore = () => { if (window.location.pathname === scope) setValue(read()); };
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
  }, [scope, key]);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (window.location.pathname !== scope) return;
      const params = new URLSearchParams(window.location.search);
      if (JSON.stringify(value) === JSON.stringify(initial)) params.delete(key);
      else params.set(key, JSON.stringify(value));
      const query = params.size ? `?${params}` : '';
      try { window.sessionStorage.setItem(storageKey(scope), query); } catch { /* private storage */ }
      window.history.replaceState(window.history.state, '', `${scope}${query}${window.location.hash}`);
    });
    return () => cancelAnimationFrame(frame);
  }, [scope, key, value]);
  return [value, setValue];
}
