/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#b3122a', dark: '#8c0f21', tint: '#f6e9eb' },
        ink: '#181a1d',
        navy: '#0f1a38'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        disp: ['"Inter Tight"', 'Inter', 'system-ui', 'sans-serif']
      }
    }
  },
  plugins: []
}
