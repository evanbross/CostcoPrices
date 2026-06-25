// ai: claude-sonnet-4-6 | 2026-06-19
import { useCallback, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { AlertCircle, CheckCircle, FileText, ImagePlus, Loader2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadReceiptImage } from '../api/client'
import type { OcrResponse, ParsedLine } from '../types'

interface Piece {
  id: number
  objectUrl: string | null  // null for PDFs (can't be shown as <img>)
  isPdf: boolean
  filename: string
  status: 'uploading' | 'done' | 'error'
  lines: ParsedLine[]
  ocr: OcrResponse | null
}

interface Props {
  onParsed: (result: OcrResponse) => void
}

let _nextId = 0

export default function ReceiptUploadZone({ onParsed }: Props) {
  const [pieces, setPieces] = useState<Piece[]>([])

  const processFile = useCallback(async (file: File) => {
    const id = _nextId++
    const isPdf = file.type === 'application/pdf'
    const objectUrl = isPdf ? null : URL.createObjectURL(file)
    setPieces((prev) => [
      ...prev,
      { id, objectUrl, isPdf, filename: file.name, status: 'uploading', lines: [], ocr: null },
    ])

    try {
      const result = await uploadReceiptImage(file)
      setPieces((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, status: 'done', lines: result.lines, ocr: result } : p,
        ),
      )
    } catch {
      setPieces((prev) => prev.map((p) => (p.id === id ? { ...p, status: 'error' } : p)))
      toast.error('Failed to parse file — try a clearer image or PDF.')
    }
  }, [])

  // Clipboard paste support (images only — PDFs can't be pasted)
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const imageItem = Array.from(e.clipboardData?.items ?? []).find((i) =>
        i.type.startsWith('image/'),
      )
      if (!imageItem) return
      const file = imageItem.getAsFile()
      if (file) {
        e.preventDefault()
        processFile(file)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [processFile])

  const onDrop = useCallback(
    (accepted: File[]) => accepted.forEach(processFile),
    [processFile],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.webp'],
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  })

  function removePiece(id: number) {
    setPieces((prev) => {
      const p = prev.find((x) => x.id === id)
      if (p?.objectUrl) URL.revokeObjectURL(p.objectUrl)
      return prev.filter((x) => x.id !== id)
    })
  }

  function handleReview() {
    const done = pieces.filter((p) => p.status === 'done' && p.ocr)
    if (done.length === 0) return
    const merged: OcrResponse = {
      lines: done.flatMap((p) => p.lines),
      raw_text: done.map((p) => p.ocr?.raw_text ?? '').filter(Boolean).join('\n') || null,
      barcode: done.map((p) => p.ocr?.barcode).find((b) => b != null) ?? null,
      detected_date: done.map((p) => p.ocr?.detected_date).find((d) => d != null) ?? null,
      detected_store: done.map((p) => p.ocr?.detected_store).find((s) => s != null) ?? null,
    }
    onParsed(merged)
  }

  const doneCount = pieces.filter((p) => p.status === 'done').length
  const uploadingCount = pieces.filter((p) => p.status === 'uploading').length

  return (
    <div className="space-y-3">
      {/* Drop / click / paste zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-colors ${
          isDragActive
            ? 'border-costco-red bg-red-50'
            : 'border-costco-border-gray hover:border-costco-red hover:bg-red-50/30'
        }`}
      >
        <input {...getInputProps()} />
        <ImagePlus className="w-10 h-10 text-costco-red" />
        <div className="text-center">
          <p className="text-sm font-semibold text-gray-700">
            {isDragActive ? 'Drop files here' : 'Drag & drop receipt screenshots or PDFs'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            click to browse ·{' '}
            <kbd className="font-mono bg-gray-100 border border-gray-300 rounded px-1 py-0.5">
              Ctrl+V
            </kbd>{' '}
            to paste · JPEG, PNG, WebP, or PDF · add multiple if the receipt spans several pages
          </p>
        </div>
      </div>

      {/* Thumbnails */}
      {pieces.length > 0 && (
        <>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
            {pieces.map((piece) => (
              <div
                key={piece.id}
                className="relative rounded-lg border border-costco-border-gray overflow-hidden bg-gray-50 aspect-[3/4]"
              >
                {piece.isPdf ? (
                  /* PDF placeholder — browsers can't render PDFs in <img> */
                  <div className="w-full h-full flex flex-col items-center justify-center gap-1 text-gray-400 px-2">
                    <FileText className="w-8 h-8" />
                    <span className="text-[10px] text-center break-all leading-tight">
                      {piece.filename}
                    </span>
                  </div>
                ) : (
                  <img
                    src={piece.objectUrl!}
                    alt="Receipt piece"
                    className="w-full h-full object-cover"
                  />
                )}

                {/* Status overlay */}
                <div className="absolute inset-0 bg-black/25 flex items-center justify-center">
                  {piece.status === 'uploading' && (
                    <Loader2 className="w-6 h-6 text-white animate-spin" />
                  )}
                  {piece.status === 'done' && (
                    <CheckCircle className="w-6 h-6 text-green-300" />
                  )}
                  {piece.status === 'error' && (
                    <AlertCircle className="w-6 h-6 text-red-400" />
                  )}
                </div>

                {/* Line count badge */}
                {piece.status === 'done' && (
                  <div className="absolute bottom-1 left-1 text-[10px] bg-black/60 text-white rounded px-1.5 py-0.5 leading-tight">
                    {piece.lines.length} lines
                  </div>
                )}

                {/* Remove button */}
                <button
                  className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/50 text-white flex items-center justify-center hover:bg-costco-red transition-colors"
                  onClick={(e) => { e.stopPropagation(); removePiece(piece.id) }}
                  title="Remove"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>

          {/* Status + Review button */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {doneCount} piece{doneCount !== 1 ? 's' : ''} parsed
              {uploadingCount > 0 && (
                <span className="text-gray-400"> · {uploadingCount} still processing…</span>
              )}
            </p>
            <button
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleReview}
              disabled={doneCount === 0 || uploadingCount > 0}
            >
              Review receipt →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
