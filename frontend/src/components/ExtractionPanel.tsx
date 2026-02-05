import { useState } from 'react';
import type { ParseResponse, SourceReference, Holding, Transaction } from '../lib/types';
import { verifyReport } from '../lib/api';
import { clsx } from 'clsx';
import { CheckCircle, Save } from 'lucide-react';

interface ExtractionPanelProps {
    data: ParseResponse | null;
    setData: React.Dispatch<React.SetStateAction<ParseResponse | null>>;
    docId: string | null;
    onSelectField: (source: SourceReference) => void;
    onSaveSuccess?: () => void;
    onSaveError?: (msg: string) => void;
}

export function ExtractionPanel({ data, setData, docId, onSelectField, onSaveSuccess, onSaveError }: ExtractionPanelProps) {
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    if (!data) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500 bg-gray-50">
                Upload a statement to see extracted data
            </div>
        );
    }

    const { portfolio_summary, holdings, transactions, metadata } = data;

    const handleSourceClick = (sourceMap: Record<string, SourceReference> | undefined, field: string) => {
        if (sourceMap && sourceMap[field]) {
            onSelectField(sourceMap[field]);
        }
    };

    const updateHolding = (index: number, field: keyof Holding, value: string) => {
        const newHoldings = [...holdings];
        newHoldings[index] = { ...newHoldings[index], [field]: value };
        setData({ ...data, holdings: newHoldings });
        setSaved(false);
    };

    const updateTransaction = (index: number, field: keyof Transaction, value: string) => {
        const newTransactions = [...transactions];
        newTransactions[index] = { ...newTransactions[index], [field]: value };
        setData({ ...data, transactions: newTransactions });
        setSaved(false);
    };

    const handleVerifyAndSave = async () => {
        if (!docId || !data) return;
        setSaving(true);
        try {
            await verifyReport(docId, data);
            setSaved(true);
            onSaveSuccess?.();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            onSaveError?.(message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="h-full flex flex-col bg-white overflow-hidden border-l border-gray-200">
            {/* Header */}
            <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900">{metadata.broker_name}</h2>
                    <div className="text-sm text-gray-600">
                        <span className="mr-4">Date: {metadata.report_date}</span>
                        <span>Account: {metadata.account_number || 'N/A'}</span>
                    </div>
                </div>
                {docId && (
                    <button
                        onClick={handleVerifyAndSave}
                        disabled={saving || saved}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                            saved
                                ? "bg-green-100 text-green-700 border border-green-200"
                                : "bg-blue-600 text-white hover:bg-blue-500"
                        )}
                    >
                        {saved ? <CheckCircle size={16} /> : <Save size={16} />}
                        {saving ? 'Saving...' : saved ? 'Verified' : 'Verify & Save'}
                    </button>
                )}
            </div>

            <div className="flex-1 overflow-auto p-4 space-y-6">

                {/* Portfolio Summary */}
                <section>
                    <h3 className="text-md font-bold text-gray-800 mb-2 border-b pb-1">Summary</h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="bg-slate-50 p-3 rounded border border-slate-100">
                            <span className="block text-gray-500 text-xs uppercase tracking-wider">Total Value</span>
                            <span className="text-xl font-bold text-slate-900">{portfolio_summary.currency} {portfolio_summary.total_value_gbp}</span>
                        </div>
                        <div className="bg-slate-50 p-3 rounded border border-slate-100">
                            <span className="block text-gray-500 text-xs uppercase tracking-wider">Investments</span>
                            <span className="text-md font-medium text-slate-800">{portfolio_summary.investments_value_gbp}</span>
                        </div>
                    </div>
                </section>

                {/* Holdings */}
                <section>
                    <h3 className="text-md font-bold text-gray-800 mb-2 border-b pb-1">Holdings ({holdings.length})</h3>
                    <div className="overflow-x-auto border rounded-sm">
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500">Symbol</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500">Description</th>
                                    <th className="px-3 py-2 text-right font-medium text-gray-500">Qty</th>
                                    <th className="px-3 py-2 text-right font-medium text-gray-500">Value</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 bg-white">
                                {holdings.map((h, i) => (
                                    <tr key={i} className="hover:bg-blue-50/50 transition-colors">
                                        <td className="px-3 py-2">
                                            <input
                                                type="text"
                                                value={h.symbol}
                                                onChange={(e) => updateHolding(i, 'symbol', e.target.value)}
                                                onClick={() => handleSourceClick(h.source_map, 'symbol')}
                                                className="w-full bg-transparent font-mono text-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                            />
                                        </td>
                                        <td className="px-3 py-2">
                                            <input
                                                type="text"
                                                value={h.description}
                                                onChange={(e) => updateHolding(i, 'description', e.target.value)}
                                                onClick={() => handleSourceClick(h.source_map, 'description')}
                                                className="w-full bg-transparent focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                            />
                                        </td>
                                        <td className="px-3 py-2 text-right">
                                            <input
                                                type="text"
                                                value={h.quantity}
                                                onChange={(e) => updateHolding(i, 'quantity', e.target.value)}
                                                onClick={() => handleSourceClick(h.source_map, 'quantity')}
                                                className="w-20 text-right bg-transparent font-mono focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                            />
                                        </td>
                                        <td className="px-3 py-2 text-right">
                                            <input
                                                type="text"
                                                value={h.market_value}
                                                onChange={(e) => updateHolding(i, 'market_value', e.target.value)}
                                                onClick={() => handleSourceClick(h.source_map, 'market_value')}
                                                className="w-24 text-right bg-transparent font-mono focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Transactions */}
                <section>
                    <h3 className="text-md font-bold text-gray-800 mb-2 border-b pb-1">Transactions ({transactions.length})</h3>
                    <div className="overflow-x-auto border rounded-sm">
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500">Date</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500">Type</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500">Description</th>
                                    <th className="px-3 py-2 text-right font-medium text-gray-500">Amount</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 bg-white">
                                {transactions.map((t, i) => (
                                    <tr key={i} className="hover:bg-blue-50/50 transition-colors">
                                        <td className="px-3 py-2 whitespace-nowrap">
                                            <input
                                                type="text"
                                                value={t.date}
                                                onChange={(e) => updateTransaction(i, 'date', e.target.value)}
                                                onClick={() => handleSourceClick(t.source_map, 'date')}
                                                className={clsx(
                                                    "w-24 bg-transparent focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1",
                                                    !t.date && "ring-1 ring-red-300"
                                                )}
                                            />
                                        </td>
                                        <td className="px-3 py-2 whitespace-nowrap">
                                            <input
                                                type="text"
                                                value={t.type}
                                                onChange={(e) => updateTransaction(i, 'type', e.target.value)}
                                                onClick={() => handleSourceClick(t.source_map, 'type')}
                                                className="w-20 bg-transparent focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                            />
                                        </td>
                                        <td className="px-3 py-2">
                                            <input
                                                type="text"
                                                value={t.description}
                                                onChange={(e) => updateTransaction(i, 'description', e.target.value)}
                                                onClick={() => handleSourceClick(t.source_map, 'description')}
                                                className="w-full bg-transparent focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1"
                                                title={t.description}
                                            />
                                        </td>
                                        <td className="px-3 py-2 text-right">
                                            <input
                                                type="text"
                                                value={t.amount}
                                                onChange={(e) => updateTransaction(i, 'amount', e.target.value)}
                                                onClick={() => handleSourceClick(t.source_map, 'amount')}
                                                className={clsx(
                                                    "w-24 text-right bg-transparent font-mono focus:outline-none focus:ring-1 focus:ring-blue-400 rounded px-1",
                                                    !t.amount && "ring-1 ring-red-300"
                                                )}
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        </div>
    );
}
