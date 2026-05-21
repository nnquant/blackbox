---
version: alpha
name: Quant Ash
description: A dual light/dark, grayscale-first, low-saturation design system for
  financial research, portfolio analytics, and quantitative trading interfaces.
colors:
  primary: '#1C1F22'
  secondary: '#666C72'
  tertiary: '#4B625E'
  neutral: '#ECEDEA'
  light-bg: '#F6F6F2'
  light-surface: '#EDEEEA'
  light-surface-raised: '#F2F2EF'
  light-surface-muted: '#E3E4E0'
  light-border: '#CFD1CC'
  light-border-strong: '#B8BBB5'
  light-text: '#202326'
  light-text-muted: '#60666C'
  light-text-subtle: '#858A8F'
  dark-bg: '#15171A'
  dark-surface: '#1D2023'
  dark-surface-raised: '#25282B'
  dark-surface-muted: '#2D3033'
  dark-border: '#383C40'
  dark-border-strong: '#4B5055'
  dark-text: '#E5E6E1'
  dark-text-muted: '#B0B4B6'
  dark-text-subtle: '#82888D'
  positive: '#5F7A68'
  positive-soft-light: '#DDE7DF'
  positive-soft-dark: '#26342D'
  negative: '#8A5B56'
  negative-soft-light: '#E9DAD7'
  negative-soft-dark: '#3A2827'
  warning: '#8B744E'
  warning-soft-light: '#EAE2D0'
  warning-soft-dark: '#3A3326'
  info: '#637486'
  info-soft-light: '#DCE3EA'
  info-soft-dark: '#26313C'
  focus-light: '#303438'
  focus-dark: '#C9CBC6'
  grid-light: '#D9DBD5'
  grid-dark: '#34383C'
  overlay-light: '#202326CC'
  overlay-dark: '#0E1012CC'
  shadow-light: '#1C1F221F'
  shadow-dark: '#090A0B66'
  surface: '#f9faf7'
  surface-dim: '#d9dad7'
  surface-bright: '#f9faf7'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f1'
  surface-container: '#edeeeb'
  surface-container-high: '#e7e8e5'
  surface-container-highest: '#e2e3e0'
  on-surface: '#1a1c1b'
  on-surface-variant: '#44474a'
  inverse-surface: '#2e312f'
  inverse-on-surface: '#f0f1ee'
  outline: '#75777a'
  outline-variant: '#c5c6ca'
  surface-tint: '#5c5f62'
  on-primary: '#ffffff'
  primary-container: '#1c1f22'
  on-primary-container: '#84868a'
  inverse-primary: '#c5c6ca'
  on-secondary: '#ffffff'
  secondary-container: '#dde3ea'
  on-secondary-container: '#5f656b'
  on-tertiary: '#ffffff'
  tertiary-container: '#0b221f'
  on-tertiary-container: '#738b86'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e2e6'
  primary-fixed-dim: '#c5c6ca'
  on-primary-fixed: '#191c1f'
  on-primary-fixed-variant: '#44474a'
  secondary-fixed: '#dde3ea'
  secondary-fixed-dim: '#c1c7ce'
  on-secondary-fixed: '#161c21'
  on-secondary-fixed-variant: '#41474d'
  tertiary-fixed: '#cee8e2'
  tertiary-fixed-dim: '#b3ccc7'
  on-tertiary-fixed: '#081f1c'
  on-tertiary-fixed-variant: '#344b47'
  background: '#f9faf7'
  on-background: '#1a1c1b'
  surface-variant: '#e2e3e0'
typography:
  display:
    fontFamily: Noto Sans
    fontSize: 3rem
    fontWeight: 600
    lineHeight: '1.05'
    letterSpacing: -0.04em
    fontFeature: '"kern" 1'
  h1:
    fontFamily: Noto Sans
    fontSize: 2.25rem
    fontWeight: 600
    lineHeight: '1.15'
    letterSpacing: -0.035em
    fontFeature: '"kern" 1'
  h2:
    fontFamily: Noto Sans
    fontSize: 1.5rem
    fontWeight: 600
    lineHeight: '1.25'
    letterSpacing: -0.025em
    fontFeature: '"kern" 1'
  h3:
    fontFamily: Noto Sans
    fontSize: 1.125rem
    fontWeight: 600
    lineHeight: '1.35'
    letterSpacing: -0.015em
    fontFeature: '"kern" 1'
  body-lg:
    fontFamily: Noto Sans
    fontSize: 1rem
    fontWeight: 400
    lineHeight: '1.6'
    letterSpacing: -0.005em
  body-md:
    fontFamily: Noto Sans
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: '1.55'
    letterSpacing: 0em
  body-sm:
    fontFamily: Noto Sans
    fontSize: 0.75rem
    fontWeight: 400
    lineHeight: '1.45'
    letterSpacing: 0.005em
  label:
    fontFamily: Noto Sans
    fontSize: 0.75rem
    fontWeight: 600
    lineHeight: '1.2'
    letterSpacing: 0.04em
  label-caps:
    fontFamily: Noto Sans
    fontSize: 0.6875rem
    fontWeight: 600
    lineHeight: '1.2'
    letterSpacing: 0.08em
  metric-lg:
    fontFamily: Noto Sans
    fontSize: 2rem
    fontWeight: 600
    lineHeight: '1.1'
    letterSpacing: -0.035em
    fontFeature: '"tnum" 1, "kern" 1'
  metric-md:
    fontFamily: Noto Sans
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: '1.2'
    letterSpacing: -0.02em
    fontFeature: '"tnum" 1, "kern" 1'
  table-cell:
    fontFamily: Noto Sans
    fontSize: 0.8125rem
    fontWeight: 400
    lineHeight: '1.35'
    letterSpacing: 0em
    fontFeature: '"tnum" 1, "kern" 1'
rounded:
  none: 0px
  xs: 2px
  sm: 4px
  md: 6px
  lg: 10px
  xl: 14px
  full: 999px
  DEFAULT: 0.25rem
spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  xxxl: 48px
components:
  app-background-light:
    backgroundColor: '{colors.light-bg}'
    textColor: '{colors.light-text}'
    typography: '{typography.body-md}'
  app-background-dark:
    backgroundColor: '{colors.dark-bg}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-md}'
  topbar-light:
    backgroundColor: '{colors.light-surface-raised}'
    textColor: '{colors.light-text}'
    typography: '{typography.label}'
    height: 48px
    padding: '{spacing.md}'
  topbar-dark:
    backgroundColor: '{colors.dark-surface-raised}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label}'
    height: 48px
    padding: '{spacing.md}'
  sidebar-light:
    backgroundColor: '{colors.light-surface}'
    textColor: '{colors.light-text}'
    typography: '{typography.body-sm}'
    width: 260px
    padding: '{spacing.lg}'
  sidebar-dark:
    backgroundColor: '{colors.dark-surface}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-sm}'
    width: 260px
    padding: '{spacing.lg}'
  workspace-light:
    backgroundColor: '{colors.light-bg}'
    textColor: '{colors.light-text}'
    typography: '{typography.body-md}'
    padding: '{spacing.xl}'
  workspace-dark:
    backgroundColor: '{colors.dark-bg}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-md}'
    padding: '{spacing.xl}'
  card-light:
    backgroundColor: '{colors.light-surface-raised}'
    textColor: '{colors.light-text}'
    typography: '{typography.body-md}'
    rounded: '{rounded.lg}'
    padding: '{spacing.lg}'
  card-dark:
    backgroundColor: '{colors.dark-surface-raised}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-md}'
    rounded: '{rounded.lg}'
    padding: '{spacing.lg}'
  card-muted-light:
    backgroundColor: '{colors.light-surface-muted}'
    textColor: '{colors.light-text-muted}'
    typography: '{typography.body-sm}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  card-muted-dark:
    backgroundColor: '{colors.dark-surface-muted}'
    textColor: '{colors.dark-text-muted}'
    typography: '{typography.body-sm}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  button-primary-light:
    backgroundColor: '{colors.primary}'
    textColor: '{colors.light-surface-raised}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  button-primary-dark:
    backgroundColor: '{colors.dark-text}'
    textColor: '{colors.dark-bg}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  button-secondary-light:
    backgroundColor: '{colors.light-surface-muted}'
    textColor: '{colors.light-text}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  button-secondary-dark:
    backgroundColor: '{colors.dark-surface-muted}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  button-accent-light:
    backgroundColor: '{colors.tertiary}'
    textColor: '{colors.light-surface-raised}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  button-accent-dark:
    backgroundColor: '{colors.tertiary}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  input-light:
    backgroundColor: '{colors.light-surface-raised}'
    textColor: '{colors.light-text}'
    typography: '{typography.body-md}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  input-dark:
    backgroundColor: '{colors.dark-surface-raised}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-md}'
    rounded: '{rounded.sm}'
    padding: '{spacing.md}'
    height: 40px
  table-header-light:
    backgroundColor: '{colors.light-surface-muted}'
    textColor: '{colors.light-text-muted}'
    typography: '{typography.label-caps}'
    padding: '{spacing.sm}'
    height: 36px
  table-header-dark:
    backgroundColor: '{colors.dark-surface-muted}'
    textColor: '{colors.dark-text-muted}'
    typography: '{typography.label-caps}'
    padding: '{spacing.sm}'
    height: 36px
  table-row-light:
    backgroundColor: '{colors.light-surface-raised}'
    textColor: '{colors.light-text}'
    typography: '{typography.table-cell}'
    padding: '{spacing.sm}'
    height: 36px
  table-row-dark:
    backgroundColor: '{colors.dark-surface-raised}'
    textColor: '{colors.dark-text}'
    typography: '{typography.table-cell}'
    padding: '{spacing.sm}'
    height: 36px
  metric-card-light:
    backgroundColor: '{colors.light-surface-raised}'
    textColor: '{colors.light-text}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.lg}'
    padding: '{spacing.lg}'
  metric-card-dark:
    backgroundColor: '{colors.dark-surface-raised}'
    textColor: '{colors.dark-text}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.lg}'
    padding: '{spacing.lg}'
  metric-positive-light:
    backgroundColor: '{colors.positive-soft-light}'
    textColor: '{colors.positive}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  metric-positive-dark:
    backgroundColor: '{colors.positive-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  metric-negative-light:
    backgroundColor: '{colors.negative-soft-light}'
    textColor: '{colors.negative}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  metric-negative-dark:
    backgroundColor: '{colors.negative-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.metric-md}'
    rounded: '{rounded.md}'
    padding: '{spacing.md}'
  badge-positive-light:
    backgroundColor: '{colors.positive-soft-light}'
    textColor: '{colors.positive}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-positive-dark:
    backgroundColor: '{colors.positive-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-negative-light:
    backgroundColor: '{colors.negative-soft-light}'
    textColor: '{colors.negative}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-negative-dark:
    backgroundColor: '{colors.negative-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-warning-light:
    backgroundColor: '{colors.warning-soft-light}'
    textColor: '{colors.warning}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-warning-dark:
    backgroundColor: '{colors.warning-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-info-light:
    backgroundColor: '{colors.info-soft-light}'
    textColor: '{colors.info}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  badge-info-dark:
    backgroundColor: '{colors.info-soft-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.label-caps}'
    rounded: '{rounded.full}'
    padding: '{spacing.sm}'
  chart-grid-light:
    backgroundColor: '{colors.grid-light}'
    textColor: '{colors.light-text-subtle}'
    typography: '{typography.body-sm}'
  chart-grid-dark:
    backgroundColor: '{colors.grid-dark}'
    textColor: '{colors.dark-text-subtle}'
    typography: '{typography.body-sm}'
  modal-overlay-light:
    backgroundColor: '{colors.overlay-light}'
    textColor: '{colors.light-surface-raised}'
    typography: '{typography.body-md}'
  modal-overlay-dark:
    backgroundColor: '{colors.overlay-dark}'
    textColor: '{colors.dark-text}'
    typography: '{typography.body-md}'
---

"