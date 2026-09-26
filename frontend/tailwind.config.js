// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      keyframes: {
        scrollDown: {
          '0%': { transform: 'translateY(0%)' },
          '100%': { transform: 'translateY(-50%)' },
        },
        scrollUp: {
          '0%': { transform: 'translateY(-50%)' },
          '100%': { transform: 'translateY(0%)' },
        },
      },
      animation: {
        'scroll-down': 'scrollDown 25s linear infinite',
        'scroll-up': 'scrollUp 30s linear infinite',
        'scroll-down-slow': 'scrollDown 35s linear infinite',
      },
    },
  },
}