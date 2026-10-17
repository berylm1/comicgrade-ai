/** Tailwind theme for the ComicGrade AI "comic pop" dark-mode look. */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./App.tsx', './src/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#0a0a12', // app background
          900: '#12121f', // card background
          800: '#1c1c2e', // elevated surfaces
        },
        pop: {
          yellow: '#ffd21f', // Ben-Day explosion accent
          red: '#ff3b3b', // hero red
          blue: '#2f6bff', // cape blue
          cyan: '#35e0d2', // halftone glow
          magenta: '#ff2fb9',
        },
        grade: {
          high: '#3ddc84', // 9.5+
          mid: '#ffd21f', // 7.0-9.4
          low: '#ff6b3b', // < 7.0
        },
      },
      fontFamily: {
        slab: ['System'], // swap in a comic slab font asset later
      },
    },
  },
  plugins: [],
};