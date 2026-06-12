/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: '#0f0f0f',
        panel: '#161616',
        elevated: '#1c1c1c',
        border: '#2a2a2a',
        accent: {
          DEFAULT: '#7c3aed',
          hover: '#8b5cf6',
        },
      },
      fontFamily: {
        system: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
