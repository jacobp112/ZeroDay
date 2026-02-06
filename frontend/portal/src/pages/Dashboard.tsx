import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { HardDrive, Activity, Key, FileText } from 'lucide-react';

export default function Dashboard() {
    const { user } = useAuth();

    const { data: usage } = useQuery({
        queryKey: ['usage'],
        queryFn: async () => (await api.get('/portal/usage')).data,
    });

    const cards = [
        { name: 'Jobs This Month', value: usage?.jobs_this_month || 0, icon: Activity, color: 'text-blue-500' },
        { name: 'API Calls', value: usage?.api_calls_this_month || 0, icon: FileText, color: 'text-green-500' },
        { name: 'Storage Used', value: `${usage?.storage_used_mb || 0} MB`, icon: HardDrive, color: 'text-purple-500' },
        { name: 'Active Keys', value: usage?.active_keys || 0, icon: Key, color: 'text-yellow-500' },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">Dashboard</h1>
                <div className="text-sm text-gray-500">Tenant ID: {user?.tenant_id}</div>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {cards.map((card) => (
                    <div key={card.name} className="overflow-hidden rounded-lg bg-white shadow">
                        <div className="p-5">
                            <div className="flex items-center">
                                <div className="flex-shrink-0">
                                    <card.icon className={`h-6 w-6 ${card.color}`} aria-hidden="true" />
                                </div>
                                <div className="ml-5 w-0 flex-1">
                                    <dl>
                                        <dt className="truncate text-sm font-medium text-gray-500">{card.name}</dt>
                                        <dd>
                                            <div className="text-lg font-medium text-gray-900">{card.value}</div>
                                        </dd>
                                    </dl>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Quick Actions or Recent Jobs */}
            <div className="rounded-lg bg-white shadow">
                <div className="border-b border-gray-200 px-4 py-5 sm:px-6">
                    <h3 className="text-base font-semibold leading-6 text-gray-900">Recent Jobs (Placeholder)</h3>
                </div>
                <div className="p-6 text-center text-gray-500">
                    No recent jobs found.
                </div>
            </div>
        </div>
    );
}
