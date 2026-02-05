import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import type { BoundingBox } from '../lib/types';

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

interface PDFViewerProps {
    url: string | null;
    highlightBox?: BoundingBox | null;
    page?: number;
}

export function PDFViewer({ url, highlightBox, page = 1 }: PDFViewerProps) {
    const [numPages, setNumPages] = useState<number>(0);
    const [pageNumber, setPageNumber] = useState<number>(page);
    const [scale, setScale] = useState<number>(1.0);
    const [pageHeight, setPageHeight] = useState<number>(0);

    useEffect(() => {
        if (page) {
            setPageNumber(page);
        }
    }, [page]);

    function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
        setNumPages(numPages);
    }

    function onLoadSuccess(page: any) {
        setPageHeight(page.originalHeight);
    }

    return (
        <div className="flex flex-col h-full bg-gray-100 overflow-hidden relative">
            <div className="flex justify-between items-center p-2 bg-white border-b shadow-sm z-10">
                <div className="flex gap-2">
                    <button
                        onClick={() => setPageNumber(p => Math.max(1, p - 1))}
                        disabled={pageNumber <= 1}
                        className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
                    >
                        Prev
                    </button>
                    <span className="self-center text-sm font-medium">
                        Page {pageNumber} of {numPages}
                    </span>
                    <button
                        onClick={() => setPageNumber(p => Math.min(numPages, p + 1))}
                        disabled={pageNumber >= numPages}
                        className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
                    >
                        Next
                    </button>
                </div>
                <div className="flex gap-2 items-center">
                    <button onClick={() => setScale(s => Math.max(0.5, s - 0.1))} className="px-2 bg-gray-200 rounded">-</button>
                    <span className="text-sm">{Math.round(scale * 100)}%</span>
                    <button onClick={() => setScale(s => Math.min(2.5, s + 0.1))} className="px-2 bg-gray-200 rounded">+</button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-4 flex justify-center bg-gray-500/10">
                {url ? (
                    <div className="relative shadow-lg">
                        <Document
                            file={url}
                            onLoadSuccess={onDocumentLoadSuccess}
                            className="flex flex-col items-center"
                        >
                            <Page
                                pageNumber={pageNumber}
                                scale={scale}
                                renderTextLayer={true}
                                renderAnnotationLayer={true}
                                onLoadSuccess={onLoadSuccess}
                            />
                        </Document>

                        {/* Overlay Layer */}
                        {highlightBox && highlightBox.page === pageNumber && pageHeight > 0 && (
                            <div
                                className="absolute border-2 border-green-500 bg-green-500/20 pointer-events-none transition-all duration-300"
                                style={{
                                    left: `${highlightBox.x0 * scale}px`,
                                    top: `${(pageHeight - highlightBox.y1) * scale}px`, // y1 is top in PDF, so distance from top
                                    width: `${(highlightBox.x1 - highlightBox.x0) * scale}px`,
                                    height: `${(highlightBox.y1 - highlightBox.y0) * scale}px`,
                                }}
                            />
                        )}
                    </div>
                ) : (
                    <div className="flex items-center justify-center h-full text-gray-400">
                        No Document Loaded
                    </div>
                )}
            </div>
        </div>
    );
}
