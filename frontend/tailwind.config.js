/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0b0e14',
          900: '#0b0e14',
          800: '#10141c',
          700: '#161b25',
          600: '#1d2330',
        },
        border: {
          DEFAULT: '#222a37',
          subtle: '#1a212c',
        },
        brand: {
          DEFAULT: '#3b82f6',
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
        },
        profit: '#22c55e',
        loss: '#ef4444',
        muted: '#7e8aa0',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
