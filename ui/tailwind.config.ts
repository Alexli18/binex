import type { Config } from 'tailwindcss';
import tailwindcssAnimate from 'tailwindcss-animate';

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // ----------------------------------------------------------------
      // Custom color tokens (accessible via bg-brand-*, text-brand-*, etc.)
      // ----------------------------------------------------------------
      colors: {
        // CSS variable-based tokens (used by index.css @apply rules)
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // Amber accent palette
        brand: {
          50:  '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#e8a020',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          950: '#451a03',
        },
        // Surface palette — warm dark
        surface: {
          DEFAULT: '#0b0b0c',
          raised:  '#131315',
          overlay: '#1a1a1d',
        },
      },

      // ----------------------------------------------------------------
      // Typography
      // ----------------------------------------------------------------
      fontSize: {
        'heading-xl': ['1.875rem', { lineHeight: '2.25rem', fontWeight: '700' }],
        'heading-lg': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        'heading-md': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        'heading-sm': ['1.125rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        'body-lg': ['1rem', { lineHeight: '1.5rem' }],
        'body-md': ['0.875rem', { lineHeight: '1.25rem' }],
        'body-sm': ['0.75rem', { lineHeight: '1rem' }],
        'code-md': ['0.875rem', { lineHeight: '1.25rem' }],
        'code-sm': ['0.75rem', { lineHeight: '1rem' }],
      },

      fontFamily: {
        mono: [
          'JetBrains Mono',
          'Fira Code',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },

      // ----------------------------------------------------------------
      // Spacing extras
      // ----------------------------------------------------------------
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },

      // ----------------------------------------------------------------
      // Border radius
      // ----------------------------------------------------------------
      borderRadius: {
        lg: '0px',
        md: '0px',
        sm: '0px',
        'badge': '0px',
        'card': '0px',
        'modal': '0px',
      },

      // ----------------------------------------------------------------
      // Shadows (dark-optimized — subtle colored glows)
      // ----------------------------------------------------------------
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.4), 0 1px 2px -1px rgb(0 0 0 / 0.4)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.4)',
        'modal': '0 20px 25px -5px rgb(0 0 0 / 0.5), 0 8px 10px -6px rgb(0 0 0 / 0.5)',
        'glow-blue': '0 0 12px 2px rgb(59 130 246 / 0.25)',
        'glow-green': '0 0 12px 2px rgb(16 185 129 / 0.25)',
        'glow-red': '0 0 12px 2px rgb(239 68 68 / 0.25)',
      },

      // ----------------------------------------------------------------
      // Animations
      // ----------------------------------------------------------------
      keyframes: {
        'pulse-status': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
      },
      animation: {
        'pulse-status': 'pulse-status 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in-right': 'slide-in-right 0.2s ease-out',
      },

      // ----------------------------------------------------------------
      // Transitions
      // ----------------------------------------------------------------
      transitionDuration: {
        '250': '250ms',
      },
    },
  },
  plugins: [tailwindcssAnimate],
} satisfies Config;
