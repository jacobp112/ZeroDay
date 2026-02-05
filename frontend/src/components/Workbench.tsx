import { useState, useCallback, useEffect } from 'react';
import { uploadStatement, getDocumentUrl, getDocumentReport } from '../lib/api';
import type { ParseResponse, SourceReference, BoundingBox } from '../lib/types';
import { PDFViewer } from './PDFViewer';
import { ExtractionPanel } from './ExtractionPanel';
import { Upload, AlertCircle } from 'lucide-react';

export function Workbench() {
    const [data, setData] = useState<ParseResponse | null>(null);
    const [docUrl, setDocUrl] = useState<string | null>(null);
    const [docId, setDocId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // PDF Interaction State
    const [highlightBox, setHighlightBox] = useState<BoundingBox | null>(null);
    const [activePage, setActivePage] = useState<number>(1);

    // Autoload handling - Load from persisted report if doc_id is present
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const urlDocId = params.get('doc_id');
        if (urlDocId) {
            setDocId(urlDocId);
            setLoading(true);

            // Fetch report (NOT re-parsing)
            Promise.all([
                getDocumentReport(urlDocId),
                fetch(`http://localhost:8000/v1/documents/${urlDocId}/content`).then(r => r.ok ? r.blob() : Promise.reject('PDF not found'))
            ])
                .then(([report, blob]) => {
                    setData(report);
                    setDocUrl(URL.createObjectURL(blob));
                })
                .catch(err => {
                    console.error("Autoload failed", err);
                    setError(String(err.message || err));
                })
                .finally(() => setLoading(false));
        }
    }, []);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setError(null);
        setData(null);
        setDocUrl(null);

        try {
            const response = await uploadStatement(file);
            setData(response);
            console.log("Parsed Data:", response);

            if (response.metadata.document_id) {
                setDocUrl(getDocumentUrl(response.metadata.document_id));
            } else {
                // Fallback: Create blob URL if backend doesn't serve it yet (though plan says it does)
                // Or if we want to preview local file before successful parse?
                // Ideally we use backend served URL to ensure consistency.
                // For MVP, if doc_id missing, use local object URL:
                setDocUrl(URL.createObjectURL(file));
            }
        } catch (err: any) {
            console.error(err);
            setError(err.message || "Failed to upload and parse statement");
        } finally {
            setLoading(false);
        }
    };

    const handleSelectField = useCallback((source: SourceReference) => {
        if (source && source.bboxes && source.bboxes.length > 0) {
            // Focus on the first bbox for now
            // Ideally we handle multiple bboxes (union or multi-highlight)
            // PDFViewer currently supports single highlightBox
            const box = source.bboxes[0];
            setHighlightBox(box);
            setActivePage(box.page);
        }
    }, []);

    return (
        <div className="flex h-screen w-screen flex-col overflow-hidden bg-gray-100 text-gray-900">
            {/* Top Bar */}
            <header className="flex items-center justify-between border-b bg-white px-4 py-2 shadow-sm z-20 h-14">
                <div className="flex items-center gap-2">
                    <span className="text-xl font-bold tracking-tight text-blue-600">Reconciliation<span className="font-normal text-gray-600">Workbench</span></span>
                </div>

                <div className="flex items-center gap-4">
                    {error && (
                        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-1 rounded-full border border-red-200">
                            <AlertCircle size={14} />
                            {error}
                        </div>
                    )}

                    <label className={`flex items-center gap-2 rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-500 cursor-pointer transition-colors ${loading ? 'opacity-70 pointer-events-none' : ''}`}>
                        <Upload size={16} />
                        {loading ? 'Processing...' : 'Upload Statement'}
                        <input
                            type="file"
                            accept="application/pdf"
                            onChange={handleFileUpload}
                            className="hidden"
                            disabled={loading}
                        />
                    </label>
                </div>
            </header>

            {/* Main Split Layout */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Panel: PDF Viewer */}
                <div className="w-1/2 border-r border-gray-200 h-full relative">
                    <PDFViewer
                        url={docUrl}
                        highlightBox={highlightBox}
                        page={activePage}
                    />
                </div>

                {/* Right Panel: Extraction Results */}
                <div className="w-1/2 h-full bg-white relative">
                    <ExtractionPanel
                        data={data}
                        setData={setData}
                        docId={docId}
                        onSelectField={handleSelectField}
                        onSaveSuccess={() => setError(null)}
                        onSaveError={(msg) => setError(msg)}
                    />
                </div>
            </div>
        </div>
    );
}
