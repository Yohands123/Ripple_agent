import type { Metadata } from "next";
import { Archivo, Pixelify_Sans } from "next/font/google";
import "../styles/tokens.css";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  weight: "variable",
  axes: ["wdth"],
  variable: "--font-archivo",
  display: "swap",
});

const pixelify = Pixelify_Sans({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-pixelify",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ripple",
  description: "A resilience case study of Apple's publicly known supply chain, built from public data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${archivo.variable} ${pixelify.variable}`}>
      <body>{children}</body>
    </html>
  );
}
