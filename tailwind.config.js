/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: '#010714',
        panel: '#061633',
        elevated: '#0a2046',
        border: '#143666',
        accent: {
          DEFAULT: '#2563eb',
          hover: '#38bdf8',
          glow: '#60a5fa',
        },
        navy: {
          950: '#010714',
          900: '#030f28',
          850: '#06173a',
          800: '#081f4a',
          700: '#0d2d66',
          600: '#14418c',
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'Outfit', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        outfit: ['Outfit', 'sans-serif'],
        jakarta: ['Plus Jakarta Sans', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
        system: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        '4xl': '2.25rem',
      },
      boxShadow: {
        'glow-blue': '0 0 30px rgba(37, 99, 235, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
        'glow-cyan': '0 0 35px rgba(56, 189, 248, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
        'glass-pill': 'inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 10px 30px rgba(0, 0, 0, 0.35)',
      },
    },
  },
  plugins: [],
};
