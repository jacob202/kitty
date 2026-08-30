const MAX_FILE_SIZE = 25 * 1024 * 1024 // 25 MB

const ALLOWED_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/svg+xml',
  'application/pdf',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'application/xml',
  'text/html',
  'text/css',
  'text/javascript',
  'application/javascript',
  'application/typescript',
])

const ALLOWED_EXTENSIONS = new Set([
  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
  '.pdf', '.txt', '.md', '.csv', '.json', '.xml',
  '.html', '.css', '.js', '.ts', '.tsx', '.jsx',
  '.py', '.rs', '.go', '.java', '.rb', '.sh',
  '.yaml', '.yml', '.toml', '.ini', '.cfg',
  '.log', '.sql', '.diff', '.patch',
])

export interface AttachmentError {
  file: string
  reason: string
}

export function validateAttachment(file: File): AttachmentError | null {
  if (file.size > MAX_FILE_SIZE) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1)
    return { file: file.name, reason: `${sizeMB} MB exceeds the 25 MB limit` }
  }

  const ext = ('.' + file.name.split('.').pop()?.toLowerCase()).replace('..', '.')
  const typeAllowed = ALLOWED_TYPES.has(file.type) || ALLOWED_EXTENSIONS.has(ext)

  if (!typeAllowed && file.type && !file.type.startsWith('text/')) {
    return { file: file.name, reason: `${file.type || ext} is not an allowed file type` }
  }

  return null
}

export function validateAttachments(files: FileList): {
  valid: File[]
  errors: AttachmentError[]
} {
  const valid: File[] = []
  const errors: AttachmentError[] = []

  for (const file of Array.from(files)) {
    const error = validateAttachment(file)
    if (error) {
      errors.push(error)
    } else {
      valid.push(file)
    }
  }

  return { valid, errors }
}
