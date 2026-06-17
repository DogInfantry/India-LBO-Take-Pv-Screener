import "./globals.css";
export const metadata = { title: "India LBO Take-Private Screener" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body className="min-h-screen antialiased">{children}</body></html>
  );
}
