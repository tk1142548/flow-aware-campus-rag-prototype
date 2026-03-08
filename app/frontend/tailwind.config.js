module.exports = {
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      boxShadow: {
        panel: '0 18px 40px rgba(25, 39, 33, 0.08)',
      },
      colors: {
        canvas: '#f3efe7',
        ink: '#18241f',
        moss: '#125a43',
        clay: '#a6622c',
        danger: '#b53b2e',
        amber: '#a66e15',
      },
      fontFamily: {
        display: ['Georgia', 'serif'],
        body: ['Segoe UI', 'PingFang SC', 'sans-serif'],
      },
      backgroundImage: {
        grid: 'linear-gradient(rgba(24,36,31,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(24,36,31,0.05) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
};
