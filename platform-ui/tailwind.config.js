/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        panel: 'rgba(20, 25, 35, 0.6)',
        primary: '#3B82F6',
        secondary: '#10B981',
      },
      backdropBlur: {
        'glass': '12px',
      }
    },
  },
  plugins: [],
}