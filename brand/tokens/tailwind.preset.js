/** Preset Tailwind pi*VMA — uso: presets: [require('./tokens/tailwind.preset.js')] */
module.exports = {
  theme: {
    extend: {
      colors: {
        pivma: {
          green: '#014e2a',
          lime: '#a3ed40',
          blue: '#0167f7',
          'blue-deep': '#025ecc',
          yellow: '#d9ae21',
          red: '#db3016',
          paper: '#efefef',
        },
        gray: { logo: '#b2b2b2', 2: '#9d9d9c', 3: '#878787', 4: '#706f6f' },
        success: '#014e2a',
        warning: '#d9ae21',
        danger: '#db3016',
        info: '#0167f7',
      },
      fontFamily: {
        heading: ['Barlow', 'Segoe UI', 'system-ui', 'sans-serif'],
        body: ['Lexend', 'Segoe UI', 'system-ui', 'sans-serif'],
        sans: ['Lexend', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
      borderRadius: { xs: '4px', sm: '8px', md: '12px', lg: '20px' },
      boxShadow: {
        sm: '0 1px 2px rgb(1 78 42 / .12)',
        md: '0 4px 12px rgb(1 78 42 / .16)',
      },
    },
  },
};
