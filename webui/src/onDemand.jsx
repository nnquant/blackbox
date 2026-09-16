import React, { useEffect, useRef, useState } from 'react';
import { apiGet } from './api';

export function useResource(path, { interval = 15000, enabled = true, accepts = null } = {}) {
  const [state, setState] = useState({ path: null, data: null, error: null });
  const [retry, setRetry] = useState(0);
  const acceptsRef = useRef(accepts);
  acceptsRef.current = accepts;
  useEffect(() => {
    if (!path || !enabled) return undefined;
    let stopped = false;
    let pending = false;
    let trailing = false;
    let timer;
    const load = async () => {
      if (stopped || document.hidden) return;
      if (pending) { trailing = true; return; }
      clearTimeout(timer);
      pending = true;
      try {
        const data = await apiGet(path);
        if (!stopped) setState(old => old.path === path && old.data === data && !old.error ? old : { path, data, error: null });
      } catch (error) {
        if (!stopped) setState(old => ({ path, data: old.path === path ? old.data : null, error: error.message }));
      } finally {
        pending = false;
        if (!stopped && !document.hidden) {
          timer = setTimeout(load, trailing ? 500 : interval);
          trailing = false;
        }
      }
    };
    const change = event => {
      if (acceptsRef.current && event.detail && !acceptsRef.current(event.detail)) return;
      if (pending) { trailing = true; return; }
      clearTimeout(timer); timer = setTimeout(load, 500);
    };
    const visibility = () => { clearTimeout(timer); if (!document.hidden) load(); };
    load();
    window.addEventListener('blackbox:data-change', change);
    document.addEventListener('visibilitychange', visibility);
    return () => { stopped = true; clearTimeout(timer); window.removeEventListener('blackbox:data-change', change); document.removeEventListener('visibilitychange', visibility); };
  }, [path, enabled, interval, retry]);
  return { data: state.path === path ? state.data : null, error: state.path === path ? state.error : null, reload: () => setRetry(v => v + 1) };
}

// Mount expensive panels only when they enter the viewport. Hidden tabs must not mount them.
export function OnDemand({ children, title = '内容', minHeight = 220 }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (visible) return undefined;
    if (!window.IntersectionObserver) { setVisible(true); return undefined; }
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, { rootMargin: '80px' });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [visible]);
  return <div ref={ref} style={{ minHeight: visible ? undefined : minHeight }}>{visible ? children : <div className="bento-panel p-4 text-sm text-muted">{title} · 滚动到此处加载</div>}</div>;
}

export function Resource({ path, children, minHeight = 220 }) {
  const { data, error, reload } = useResource(path);
  return <>{error ? <div className="p-3 text-sm text-negative">{error}<button className="secondary-button ml-2" onClick={reload}>重试</button></div> : null}{data ? children(data) : !error ? <div style={{minHeight}} className="p-4 text-sm text-muted">加载中…</div> : null}</>;
}

export function Pager({ page, total, limit, onChange }) {
  const pages = Math.max(1, Math.ceil((total || 0) / limit));
  return <div className="flex items-center justify-end gap-3 p-3 text-sm text-muted"><span>共 {total ?? '…'} 条 · 第 {page} / {pages} 页</span><button className="secondary-button" disabled={page <= 1} onClick={() => onChange(page - 1)}>上一页</button><button className="secondary-button" disabled={page >= pages} onClick={() => onChange(page + 1)}>下一页</button></div>;
}
