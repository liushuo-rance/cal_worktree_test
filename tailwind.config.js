/**
 * Tailwind CSS Configuration: The Digital Jurist
 * Extends default Tailwind with design system tokens
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    './src/web/templates/**/*.html',
    './src/web/static/js/**/*.js',
  ],
  theme: {
    extend: {
      // ========================================
      // COLORS (from design tokens)
      // ========================================
      colors: {
        // Primary - Deep Navy
        primary: {
          DEFAULT: '#000666',
          container: '#1a237e',
          fixed: '#e0e0ff',
          'fixed-dim': '#bdc2ff',
        },
        'on-primary': {
          DEFAULT: '#ffffff',
          container: '#8690ee',
          fixed: '#000767',
          'fixed-variant': '#343d96',
        },
        'inverse-primary': '#bdc2ff',

        // Secondary - Success Green
        secondary: {
          DEFAULT: '#1b6d24',
          container: '#a0f399',
          fixed: '#a3f69c',
          'fixed-dim': '#88d982',
        },
        'on-secondary': {
          DEFAULT: '#ffffff',
          container: '#217128',
          fixed: '#002204',
          'fixed-variant': '#005312',
        },

        // Tertiary - Warning Orange
        tertiary: {
          DEFAULT: '#321100',
          container: '#532100',
          fixed: '#ffdbca',
          'fixed-dim': '#ffb68f',
        },
        'on-tertiary': {
          DEFAULT: '#ffffff',
          container: '#f57009',
          fixed: '#331200',
          'fixed-variant': '#773200',
        },

        // Error - Danger Red
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        'on-error': {
          DEFAULT: '#ffffff',
          container: '#93000a',
        },

        // Surface - Paper Tones
        background: '#fbf8ff',
        'on-background': '#1a1b23',
        surface: {
          DEFAULT: '#fbf8ff',
          variant: '#e2e1ed',
          dim: '#dad9e4',
          bright: '#fbf8ff',
          tint: '#4c56af',
        },
        'on-surface': {
          DEFAULT: '#1a1b23',
          variant: '#454652',
        },
        'inverse-surface': '#2f3038',
        'inverse-on-surface': '#f1f0fb',

        // Container Hierarchy
        'surface-container': {
          lowest: '#ffffff',
          'low': '#f3f2fe',
          DEFAULT: '#eeedf8',
          high: '#e8e7f2',
          highest: '#e2e1ed',
        },

        // Outline
        outline: {
          DEFAULT: '#767683',
          variant: '#c6c5d4',
        },
      },

      // ========================================
      // TYPOGRAPHY
      // ========================================
      fontFamily: {
        headline: ['Manrope', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        body: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        label: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['SF Mono', 'Monaco', 'Inconsolata', 'monospace'],
      },

      fontSize: {
        'display-lg': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '800' }],
        'display-md': ['2.5rem', { lineHeight: '1.15', letterSpacing: '-0.02em', fontWeight: '700' }],
        'display-sm': ['2rem', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-lg': ['2rem', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-md': ['1.5rem', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-sm': ['1.25rem', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        'title-lg': ['1.125rem', { lineHeight: '1.4', fontWeight: '600' }],
        'title-md': ['1rem', { lineHeight: '1.5', fontWeight: '600' }],
        'title-sm': ['0.875rem', { lineHeight: '1.5', fontWeight: '500' }],
        'body-lg': ['1rem', { lineHeight: '1.6' }],
        'body-md': ['0.875rem', { lineHeight: '1.6' }],
        'body-sm': ['0.8125rem', { lineHeight: '1.5' }],
        'label-lg': ['0.875rem', { lineHeight: '1.4', fontWeight: '500' }],
        'label-md': ['0.75rem', { lineHeight: '1.4', fontWeight: '500' }],
        'label-sm': ['0.6875rem', { lineHeight: '1.4', fontWeight: '500', letterSpacing: '0.025em' }],
      },

      // ========================================
      // SPACING
      // ========================================
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '30': '7.5rem',
      },

      // ========================================
      // BORDER RADIUS
      // ========================================
      borderRadius: {
        'xs': '0.125rem',
        'sm': '0.25rem',
        'md': '0.5rem',
        'lg': '0.75rem',
        'xl': '1rem',
      },

      // ========================================
      // SHADOWS
      // ========================================
      boxShadow: {
        'ambient': '0 0 48px rgba(26, 27, 35, 0.06)',
        'ambient-lg': '0 0 64px rgba(26, 27, 35, 0.08)',
        'ambient-dark': '0 0 48px rgba(0, 0, 0, 0.4)',
        'sidebar': '4px 0 24px rgba(0, 6, 102, 0.15)',
        'glass': '0 8px 32px rgba(0, 6, 102, 0.08)',
      },

      // ========================================
      // TRANSITIONS
      // ========================================
      transitionDuration: {
        '400': '400ms',
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },

      // ========================================
      // Z-INDEX
      // ========================================
      zIndex: {
        'dropdown': '100',
        'sticky': '200',
        'fixed': '300',
        'modal-backdrop': '400',
        'modal': '500',
        'popover': '600',
        'tooltip': '700',
        'toast': '800',
      },

      // ========================================
      // BACKDROP BLUR
      // ========================================
      backdropBlur: {
        '24': '24px',
      },

      // ========================================
      // WIDTH
      // ========================================
      width: {
        'sidebar': '16rem',
        'sidebar-collapsed': '4rem',
      },

      // ========================================
      // HEIGHT
      // ========================================
      height: {
        'header': '4rem',
      },

      // ========================================
      // MAX WIDTH
      // ========================================
      maxWidth: {
        'content': '80rem',
      },
    },
  },
  plugins: [
    // Custom plugin for additional utilities
    function({ addUtilities }) {
      addUtilities({
        // Tabular numbers for data alignment
        '.tabular-nums': {
          'font-variant-numeric': 'tabular-nums',
        },
        // Glassmorphism
        '.glass': {
          'background': 'rgba(243, 242, 254, 0.8)',
          'backdrop-filter': 'blur(24px)',
          '-webkit-backdrop-filter': 'blur(24px)',
        },
        '.glass-dark': {
          'background': 'rgba(26, 27, 35, 0.8)',
          'backdrop-filter': 'blur(24px)',
          '-webkit-backdrop-filter': 'blur(24px)',
        },
        // Sidebar gradient
        '.bg-sidebar-gradient': {
          'background': 'linear-gradient(180deg, #000666 0%, #1a237e 100%)',
        },
        // Line clamp utilities
        '.line-clamp-2': {
          'display': '-webkit-box',
          '-webkit-line-clamp': '2',
          '-webkit-box-orient': 'vertical',
          'overflow': 'hidden',
        },
        '.line-clamp-3': {
          'display': '-webkit-box',
          '-webkit-line-clamp': '3',
          '-webkit-box-orient': 'vertical',
          'overflow': 'hidden',
        },
      });
    },
  ],
};
