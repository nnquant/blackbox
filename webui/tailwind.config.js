/** @type {import('tailwindcss').Config} */
// Colour tokens live in src/main.css as RGB triplets (--c-*) so the same utilities work in the
// dark (default) and light themes. `white` is remapped to the nested surface (surface2) on purpose.
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: token('ink'),
        muted: token('muted'),
        subtle: token('subtle'),
        canvas: token('canvas'),
        panel: token('panel'),
        panel2: token('panel2'),
        line: token('line'),
        lineStrong: token('lineStrong'),
        positive: token('positive'),
        positiveSoft: token('positiveSoft'),
        negative: token('negative'),
        negativeSoft: token('negativeSoft'),
        warning: token('warning'),
        warningSoft: token('warningSoft'),
        info: token('info'),
        infoSoft: token('infoSoft'),
        charcoal: token('accent'),
        accent: token('accent'),
        accentStrong: token('accentStrong'),
        accentInk: token('accentInk'),
        raised: token('raised'),
        surface2: token('surface2'),
        dim: token('dim'),
        white: token('surface2'),
      },
      boxShadow: {
        bento: 'none',
        insetLine: 'inset 0 0 0 1px rgb(var(--c-lineStrong) / 0.9)',
        lg: 'var(--shadow)',
        xl: 'var(--shadow)',
      },
      borderRadius: {
        sm: '2px',
        DEFAULT: '3px',
        md: '3px',
        lg: '6px',
        bento: '6px',
      },
      fontFamily: {
        sans: ['Noto Sans', 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'Source Han Sans SC', 'Noto Sans CJK SC', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['Noto Sans Mono', 'Cascadia Mono', 'SFMono-Regular', 'Consolas', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
