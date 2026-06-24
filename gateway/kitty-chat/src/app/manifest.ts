import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Kitty',
    short_name: 'Kitty',
    description: 'Your personal AI companion',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#0f0f14',
    theme_color: '#0f0f14',
    orientation: 'portrait',
    icons: [
      {
        src: '/mascots/kitty-mission.png',
        sizes: '1024x1024',
        type: 'image/png',
        purpose: 'maskable',
      },
      {
        src: '/kitty-mark.svg',
        sizes: '64x64',
        type: 'image/svg+xml',
        purpose: 'any',
      },
    ],
  }
}
