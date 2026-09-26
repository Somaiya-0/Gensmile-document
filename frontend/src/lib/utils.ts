import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Photos only, everywhere case photos are uploaded -- no video. */
export function isAllowedImageFile(file: File) {
  const allowedTypes = new Set([
    "image/heic",
    "image/heif",
    "image/jpeg",
    "image/jpg",
    "image/png",
  ])

  return allowedTypes.has(file.type)
}

type NativeFileSaver = {
  beginDownload: (filename: string, mimeType: string) => void
  appendChunk: (chunk: string) => void
  finishDownload: () => void
}

declare global {
  interface Window {
    AndroidFileSaver?: NativeFileSaver
    GenSmileDownloader?: NativeFileSaver
  }
}

// Android's addJavascriptInterface has a hard practical ceiling on string
// argument size -- a base64-encoded ZIP with a few attachments comfortably
// exceeds it, and the call fails silently partway through, leaving an
// empty/truncated file with no error on either side. Splitting into chunks
// well under that ceiling avoids it entirely; used for both platforms so
// there's one code path instead of two untested-at-scale ones.
const DOWNLOAD_CHUNK_SIZE = 500_000

/**
 * Triggers a file download for a Blob. A plain <a download> click on a
 * blob: URL silently does nothing inside the native iOS/Android apps --
 * neither WebView wrapper has any download-handling code, so the click is
 * just dropped. When a native bridge is present (added on each app's side
 * specifically for this), stream the file to it as base64 chunks instead;
 * otherwise fall back to the normal blob-URL/<a download> approach, which
 * already works fine in every real browser (desktop and mobile).
 */
export async function saveBlobAsFile(blob: Blob, filename: string) {
  const nativeSaver = window.AndroidFileSaver ?? window.GenSmileDownloader

  // Guards against a stale native app (an older build whose bridge only has
  // the pre-chunking downloadFile method) or a stale cached page -- without
  // this, calling a method the native side doesn't have throws and the
  // download just silently vanishes with no console trace either.
  if (nativeSaver && typeof nativeSaver.beginDownload !== "function") {
    console.error("saveBlobAsFile: native bridge present but missing beginDownload -- app/web version mismatch", nativeSaver)
  } else if (nativeSaver) {
    console.log(`saveBlobAsFile: streaming "${filename}" (${blob.size} bytes) to native bridge`)
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve((reader.result as string).split(",")[1] ?? "")
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(blob)
    })

    nativeSaver.beginDownload(filename, blob.type || "application/octet-stream")
    let chunkCount = 0
    for (let i = 0; i < base64.length; i += DOWNLOAD_CHUNK_SIZE) {
      nativeSaver.appendChunk(base64.slice(i, i + DOWNLOAD_CHUNK_SIZE))
      chunkCount++
    }
    nativeSaver.finishDownload()
    console.log(`saveBlobAsFile: sent ${chunkCount} chunk(s), base64 length ${base64.length}`)
    return
  }

  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
