import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';
import { Activity, Zap, HardDrive } from 'lucide-react';

export default function Usage() {
    const { data: usage, isLoading: usageLoading } = useQuery({
        queryKey: ['usage'],
        queryFn: async () => (await api.get('/portal/usage')).data,
    });

    const { data: limits, isLoading: limitsLoading } = useQuery({
        queryKey: ['rate-limits'],
        queryFn: async () => (await api.get('/portal/rate-limits')).data,
    });

    const { data: history, isLoading: historyLoading } = useQuery({
        queryKey: ['usage-history'],
        queryFn: async () => (await api.get('/portal/usage/history')).data,
    });

    if (usageLoading || limitsLoading || historyLoading) {
        return <div>Loading usage data...</div>;
    }

    const stats = [
        { name: 'Jobs (Month)', value: usage?.jobs_this_month, limit: 'No Limit', icon: Activity, color: 'text-blue-500' },
        { name: 'API Calls (Month)', value: usage?.api_calls_this_month, limit: 'No Limit', icon: Zap, color: 'text-yellow-500' },
        { name: 'Storage', value: `${usage?.storage_used_mb} MB`, limit: `${limits?.storage_gb_limit || 10} GB`, icon: HardDrive, color: 'text-purple-500' },
    ];

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Usage & Limits</h1>

            {/* Current Usage */}
            <h2 className="text-lg font-medium text-gray-900">Current Usage (Month To Date)</h2>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {stats.map((stat) => (
                    <div key={stat.name} className="overflow-hidden rounded-lg bg-white shadow">
                        <div className="p-5">
                            <div className="flex items-center">
                                <div className="flex-shrink-0">
                                    <stat.icon className={`h-6 w-6 ${stat.color}`} aria-hidden="true" />
                                </div>
                                <div className="ml-5 w-0 flex-1">
                                    <dl>
                                        <dt className="truncate text-sm font-medium text-gray-500">{stat.name}</dt>
                                        <dd className="flex items-baseline">
                                            <div className="text-2xl font-semibold text-gray-900">{stat.value}</div>
                                            <div className="ml-2 flex items-baseline text-sm font-semibold text-gray-600">
                                                / {stat.limit}
                                            </div>
                                        </dd>
                                    </dl>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Rate Limits */}
            <h2 className="text-lg font-medium text-gray-900 mt-8">Rate Limits (Throttling)</h2>
            <div className="overflow-hidden bg-white shadow sm:rounded-lg">
                <div className="border-b border-gray-200 px-4 py-5 sm:px-6">
                    <h3 className="text-base font-semibold leading-6 text-gray-900">Configured Limits</h3>
                </div>
                <div className="px-4 py-5 sm:p-0">
                    <dl className="sm:divide-y sm:divide-gray-200">
                        <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                            <dt className="text-sm font-medium text-gray-500">Jobs Per Hour</dt>
                            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{limits?.jobs_per_hour}</dd>
                        </div>
                        <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                            <dt className="text-sm font-medium text-gray-500">API Calls Per Hour</dt>
                            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{limits?.api_calls_per_hour}</dd>
                        </div>
                        <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                            <dt className="text-sm font-medium text-gray-500">Concurrent Jobs</dt>
                            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{limits?.concurrent_jobs}</dd>
                        </div>
                    </dl>
                </div>
            </div>

            {/* Usage History */}
            <h2 className="text-lg font-medium text-gray-900 mt-8">Daily Usage History (Last 30 Days)</h2>
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
                <table className="min-w-full divide-y divide-gray-300">
                    <thead className="bg-gray-50">
                        <tr>
                            <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">Date</th>
                            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Jobs</th>
                            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">API Calls</th>
                            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Storage (MB)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {history?.map((record: any) => (
                            <tr key={record.date}>
                                <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                                    {new Date(record.date).toLocaleDateString()}
                                </td>
                                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{record.jobs_count}</td>
                                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{record.api_calls_count}</td>
                                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                                    {(record.storage_bytes / (1024 * 1024)).toFixed(2)}
                                </td>
                            </tr>
                        ))}
                        {!history?.length && (
                            <tr>
                                <td colSpan={4} className="py-4 text-center text-sm text-gray-500">No usage history available.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
