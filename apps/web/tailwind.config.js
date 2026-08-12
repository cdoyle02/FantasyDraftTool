/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#07120d',
        panel: '#0e1d16',
        line: '#213b2d',
        mint: '#66e3a4',
        lime: '#c6f56f',
        muted: '#8ca89a'
      },
      boxShadow: {
        glow: '0 0 35px rgba(102, 227, 164, .10)'
      }
    }
  },
  plugins: []
}
