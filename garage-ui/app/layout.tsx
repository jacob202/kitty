import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { DensityProvider } from './components/DensityContext'
import { ToastProvider } from './components/Toast'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const jbMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Kitty Dashboard',
  description: 'Kitty - Personal AI Gateway',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jbMono.variable}`}>
      <body className="font-sans antialiased text-[var(--text-main)] bg-[var(--bg-color)] selection:bg-[var(--accent-color)] selection:text-white">
        <ToastProvider>
          <DensityProvider>
            {children}
          </DensityProvider>
        </ToastProvider>
      </body>
    </html>
  )
}
