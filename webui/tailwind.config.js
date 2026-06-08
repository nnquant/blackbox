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
        positive: '#16a34a',
        positiveSoft: '#dcfce7',
        negative: '#ef233c',
        negativeSoft: '#fee2e2',
        warning: '#f97316',
        warningSoft: '#fef3c7',
        info: '#0f70ff',
        infoSoft: '#dbeafe',
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
