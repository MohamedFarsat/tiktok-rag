import type { Metadata } from "next";
import { Fraunces, Work_Sans } from "next/font/google";
import "../styles/globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display"
});

const workSans = Work_Sans({
  subsets: ["latin"],
  variable: "--font-body"
});

export const metadata: Metadata = {
  title: "Social Media Policy Assistant",
  description: "Cross-platform policy insights with grounded citations."
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${workSans.variable} bg-canvas text-ink`}>
        {children}
      </body>
    </html>
  );
}
