import type { ParseResponse, SourceReference } from '../lib/types';
import { clsx } from 'clsx';

interface ExtractionPanelProps {
    data: ParseResponse | null;
    onSelectField: (source: SourceReference) => void;
}

export function ExtractionPanel({ data, onSelectField }: ExtractionPanelProps) {
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

    return (
        <div className="h-full flex flex-col bg-white overflow-hidden border-l border-gray-200">
            {/* Header */}
            <div className="p-4 border-b bg-gray-50">
                <h2 className="text-lg font-semibold text-gray-900">{metadata.broker_name}</h2>
                <div className="text-sm text-gray-600">
                    <span className="mr-4">Date: {metadata.report_date}</span>
                    <span>Account: {metadata.account_number || 'N/A'}</span>
                </div>
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
                                        <td
                                            onClick={() => handleSourceClick(h.source_map, 'symbol')}
                                            className={clsx("px-3 py-2 font-mono text-blue-600 cursor-pointer", h.source_map?.symbol && "hover:underline")}
                                        >
                                            {h.symbol}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(h.source_map, 'description')}
                                            className={clsx("px-3 py-2 cursor-pointer", h.source_map?.description && "hover:underline")}
                                        >
                                            {h.description}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(h.source_map, 'quantity')}
                                            className={clsx("px-3 py-2 text-right font-mono cursor-pointer", h.source_map?.quantity && "hover:underline")}
                                        >
                                            {h.quantity}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(h.source_map, 'market_value')}
                                            className={clsx("px-3 py-2 text-right font-mono cursor-pointer", h.source_map?.market_value && "hover:underline")}
                                        >
                                            {h.market_value}
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
                                        <td
                                            onClick={() => handleSourceClick(t.source_map, 'date')}
                                            className={clsx("px-3 py-2 whitespace-nowrap cursor-pointer", t.source_map?.date && "hover:underline")}
                                        >
                                            {t.date}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(t.source_map, 'type')}
                                            className={clsx("px-3 py-2 whitespace-nowrap cursor-pointer", t.source_map?.type && "hover:underline")}
                                        >
                                            {t.type}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(t.source_map, 'description')}
                                            className={clsx("px-3 py-2 max-w-xs truncate cursor-pointer", t.source_map?.description && "hover:underline")}
                                            title={t.description}
                                        >
                                            {t.description}
                                        </td>
                                        <td
                                            onClick={() => handleSourceClick(t.source_map, 'amount')}
                                            className={clsx("px-3 py-2 text-right font-mono cursor-pointer", t.source_map?.amount && "hover:underline")}
                                        >
                                            {t.amount}
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
