import type { Metadata } from 'next'
import './globals.css'
import { DensityProvider } from './components/DensityContext'

export const metadata: Metadata = {
  title: 'Orange Lab',
  description: 'AgentCompany Garage Dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <DensityProvider>
          {children}
        </DensityProvider>
      </body>
    </html>
  )
}
