/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#111827',
        muted: '#4b5563',
        subtle: '#6b7280',
        canvas: '#f3f4f6',
        panel: '#ffffff',
        panel2: '#e5e7eb',
        line: '#d1d5db',
        lineStrong: '#9ca3af',
        positive: '#15803d',
        positiveSoft: '#e7f3ea',
        negative: '#dc2626',
        negativeSoft: '#f8e4e4',
        warning: '#d97706',
        warningSoft: '#f6ecd4',
        info: '#2563eb',
        infoSoft: '#e1e8f4',
        charcoal: '#111827',
      },
      boxShadow: {
        bento: '0 16px 40px rgba(17,24,39,0.08)',
        insetLine: 'inset 0 0 0 1px rgba(156,163,175,0.9)',
      },
      borderRadius: {
        bento: '8px',
      },
      fontFamily: {
        sans: [
          'Noto Sans SC',
          'Microsoft YaHei',
          'PingFang SC',
          'Hiragino Sans GB',
          'Source Han Sans SC',
          'Noto Sans CJK SC',
          'Noto Sans',
          'ui-sans-serif',
          'system-ui',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
