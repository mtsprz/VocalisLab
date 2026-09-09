/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./index.tsx",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        premium: {
          dark: '#0b0f19',
          card: '#161d30',
          border: '#242f4c'
        }
      }
    }
  },
  plugins: [],
}
