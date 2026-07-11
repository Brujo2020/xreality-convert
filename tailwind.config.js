/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: '#020b1c',
        panel: '#07152b',
        elevated: '#0b1d36',
        border: '#173659',
        accent: {
          DEFAULT: '#1689e8',
          hover: '#35a7ff',
        },
      },
      fontFamily: {
        system: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
