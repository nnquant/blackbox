/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#202326',
        muted: '#60666c',
        subtle: '#858a8f',
        canvas: '#f6f6f2',
        panel: '#fbfbf8',
        panel2: '#edeeea',
        line: '#e1e2dd',
        lineStrong: '#cfd1cc',
        positive: '#15803d',
        positiveSoft: '#e7f3ea',
        negative: '#dc2626',
        negativeSoft: '#f8e4e4',
        warning: '#d97706',
        warningSoft: '#f6ecd4',
        info: '#2563eb',
        infoSoft: '#e1e8f4',
        charcoal: '#1c1f22',
      },
      boxShadow: {
        bento: '0 16px 40px rgba(28,31,34,0.08)',
        insetLine: 'inset 0 0 0 1px rgba(207,209,204,0.9)',
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
