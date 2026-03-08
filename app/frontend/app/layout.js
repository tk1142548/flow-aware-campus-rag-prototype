import './globals.css';

export const metadata = {
  title: '流程感知校园办事 RAG 原型',
  description: 'JNU flow-aware campus RAG prototype',
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
