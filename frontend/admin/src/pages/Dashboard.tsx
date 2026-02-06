import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';
import { Activity, Users, Building, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';

export default function Dashboard() {
    const { data: health } = useQuery({
        queryKey: ['health'],
        queryFn: async () => (await api.get('/admin/health/details')).data,
        refetchInterval: 30000,
    });

    const { data: auditLogs } = useQuery({
        queryKey: ['audit-log-recent'],
        queryFn: async () => (await api.get('/admin/audit-log?limit=5')).data,
    });

    const cards = [
        { name: 'System Status', value: health?.status || 'Loading...', icon: Activity, color: health?.status === 'ok' ? 'text-green-600' : 'text-red-500' },
        { name: 'Total Organizations', value: 'View', icon: Building, href: '/organizations', color: 'text-blue-500' },
        { name: 'Total Tenants', value: 'View', icon: Users, href: '/tenants', color: 'text-purple-500' },
    ];

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Dashboard</h1>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {cards.map((card) => (
                    <div key={card.name} className="overflow-hidden rounded-lg bg-white shadow">
                        <div className="p-5">
                            <div className="flex items-center">
                                <div className="flex-shrink-0">
                                    <card.icon className={cn("h-6 w-6", card.color)} aria-hidden="true" />
                                </div>
                                <div className="ml-5 w-0 flex-1">
                                    <dl>
                                        <dt className="truncate text-sm font-medium text-gray-500">{card.name}</dt>
                                        <dd>
                                            <div className="text-lg font-medium text-gray-900">
                                                {card.href ? (
                                                    <Link to={card.href} className="hover:underline">{card.value}</Link>
                                                ) : (
                                                    card.value
                                                )}
                                            </div>
                                        </dd>
                                    </dl>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="rounded-lg bg-white shadow">
                    <div className="border-b border-gray-200 px-4 py-5 sm:px-6">
                        <h3 className="text-base font-semibold leading-6 text-gray-900">Recent Activity</h3>
                    </div>
                    <ul role="list" className="divide-y divide-gray-200">
                        {auditLogs?.map((log: any) => (
                            <li key={log.id} className="px-4 py-4 sm:px-6">
                                <div className="flex items-center justify-between">
                                    <p className="truncate text-sm font-medium text-indigo-600">{log.action}</p>
                                    <div className="ml-2 flex flex-shrink-0">
                                        <p className="inline-flex rounded-full bg-green-100 px-2 text-xs font-semibold leading-5 text-green-800">
                                            {log.admin_user_id}
                                        </p>
                                    </div>
                                </div>
                                <div className="mt-2 sm:flex sm:justify-between">
                                    <div className="sm:flex">
                                        <p className="flex items-center text-sm text-gray-500">
                                            {log.reason}
                                        </p>
                                    </div>
                                    <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                                        <p>{new Date(log.timestamp).toLocaleString()}</p>
                                    </div>
                                </div>
                            </li>
                        ))}
                        {!auditLogs && (
                            <li className="px-4 py-4 text-center text-gray-500">Loading...</li>
                        )}
                    </ul>
                </div>
            </div>
        </div>
    );
}
