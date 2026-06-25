import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: 'Kitty',
    short_name: 'Kitty',
    description: 'Your personal AI companion',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#0f0f14',
    theme_color: '#0f0f14',
    categories: ['productivity', 'utilities'],
    icons: [
      {
        src: '/app-icons/kitty-192.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/app-icons/kitty-192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'maskable',
      },
      {
        src: '/app-icons/kitty-512.png',
        sizes: '512x512',
        type: 'image/png',
      },
      {
        src: '/app-icons/kitty-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
    ],
  }
}
