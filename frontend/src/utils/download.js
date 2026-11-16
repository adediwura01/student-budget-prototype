export function downloadFile(blob, filename) {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  try {
    link.href = url
    link.download = filename
    document.body.append(link)
    link.click()
  } finally {
    link.remove()
    // Give the browser time to consume the URL before releasing the download.
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
