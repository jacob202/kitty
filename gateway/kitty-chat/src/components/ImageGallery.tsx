'use client'

import { useState, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { RowsPhotoAlbum, type Photo } from 'react-photo-album'
import 'react-photo-album/rows.css'
import Lightbox from 'yet-another-react-lightbox'
import 'yet-another-react-lightbox/styles.css'
import type { ImageEntry } from '@/lib/gateway'

interface Props {
  images: ImageEntry[]
  compact?: boolean
}

function toPhoto(img: ImageEntry): Photo {
  return {
    src: `/proxy/image/view/${img.filename}`,
    width: 512,
    height: 512,
    alt: img.prompt,
    title: img.prompt,
  }
}

export function ImageGallery({ images, compact = false }: Props) {
  const [lightboxIndex, setLightboxIndex] = useState(-1)

  const photos = images.map(toPhoto)

  const handleClick = useCallback(({ index }: { index: number }) => {
    setLightboxIndex(index)
  }, [])

  if (images.length === 0) {
    return <p style={emptyStyle}>no images yet</p>
  }

  return (
    <>
      <RowsPhotoAlbum
        photos={photos}
        targetRowHeight={compact ? 120 : 180}
        rowConstraints={{ maxPhotos: compact ? 2 : 4 }}
        spacing={4}
        onClick={handleClick}
        componentsProps={{
          image: { loading: 'lazy' },
          button: { style: buttonOverride },
        }}
      />
      <Lightbox
        open={lightboxIndex >= 0}
        close={() => setLightboxIndex(-1)}
        index={lightboxIndex}
        slides={photos.map((p) => ({
          src: p.src,
          alt: p.alt,
          title: p.title,
        }))}
        styles={{
          container: { backgroundColor: 'rgba(0,0,0,0.92)' },
        }}
        controller={{ closeOnBackdropClick: true }}
      />
    </>
  )
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const buttonOverride: CSSProperties = {
  borderRadius: 6,
  overflow: 'hidden',
  border: '1px solid var(--line)',
  cursor: 'pointer',
}
