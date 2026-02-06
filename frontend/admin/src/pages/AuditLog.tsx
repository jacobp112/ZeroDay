import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';

export default function AuditLog() {
    const { data: logs, isLoading } = useQuery({
        queryKey: ['audit-log'],
        queryFn: async () => (await api.get('/admin/audit-log')).data,
    });

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Audit Log</h1>

            <div className="overflow-hidden rounded-lg bg-white shadow">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Timestamp</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Action</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">User</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Resource</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Reason</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">IP</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {logs?.map((log: any) => (
                            <tr key={log.id}>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                                    {new Date(log.timestamp).toLocaleString()}
                                </td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">{log.action}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{log.admin_user_id}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{log.resource_id}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{log.reason}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{log.ip_address}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
