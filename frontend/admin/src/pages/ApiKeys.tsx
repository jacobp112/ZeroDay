import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/api/client';
import { Plus, Trash2, Key } from 'lucide-react';

export default function ApiKeys() {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [name, setName] = useState('');
    const [reason, setReason] = useState('');
    const [tenantId, setTenantId] = useState('');
    const [newKey, setNewKey] = useState<{ api_key: string, note: string } | null>(null);

    const { data: keys, isLoading } = useQuery({
        queryKey: ['api-keys'],
        queryFn: async () => (await api.get('/admin/api-keys')).data,
    });

    const { data: tenants } = useQuery({
        queryKey: ['tenants'],
        queryFn: async () => (await api.get('/admin/tenants')).data,
    });

    const createMutation = useMutation({
        mutationFn: (data: any) => api.post(`/admin/tenants/${data.tenantId}/api-keys`, { name: data.name, reason: data.reason }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
            setNewKey(data.data); // Capture secret
            setIsOpen(false);
            setName('');
            setReason('');
            setTenantId('');
        },
    });

    const revokeMutation = useMutation({
        mutationFn: (id: string) => api.delete(`/admin/api-keys/${id}?reason=AdminRevoke`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        createMutation.mutate({ name, reason, tenantId });
    };

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">API Keys</h1>
                <button
                    onClick={() => setIsOpen(true)}
                    className="flex items-center rounded-md bg-black px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
                >
                    <Plus className="mr-2 h-4 w-4" />
                    New Key
                </button>
            </div>

            {newKey && (
                <div className="rounded-md bg-green-50 p-4">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <Key className="h-5 w-5 text-green-400" aria-hidden="true" />
                        </div>
                        <div className="ml-3">
                            <h3 className="text-sm font-medium text-green-800">Key Created Successfully</h3>
                            <div className="mt-2 text-sm text-green-700">
                                <p>Save this key now. It will not be shown again.</p>
                                <code className="mt-2 block rounded bg-black p-2 text-white">{newKey.api_key}</code>
                            </div>
                            <div className="mt-4">
                                <button
                                    type="button"
                                    onClick={() => setNewKey(null)}
                                    className="rounded-md bg-green-100 px-2 py-1.5 text-sm font-medium text-green-800 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-offset-2 focus:ring-offset-green-50"
                                >
                                    Dismiss
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="overflow-hidden rounded-lg bg-white shadow">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Access ID</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Tenant</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                            <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {keys?.map((key: any) => (
                            <tr key={key.key_id}>
                                <td className="whitespace-nowrap px-6 py-4 font-medium text-gray-900">{key.name}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-gray-500">{key.access_key_id}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-gray-500">{key.tenant_id}</td>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${key.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                        {key.is_active ? 'Active' : 'Revoked'}
                                    </span>
                                </td>
                                <td className="whitespace-nowrap px-6 py-4 text-right">
                                    {key.is_active && (
                                        <button
                                            onClick={() => {
                                                if (confirm('Revoke API Key?')) revokeMutation.mutate(key.key_id);
                                            }}
                                            className="text-red-600 hover:text-red-900"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="w-full max-w-md rounded-lg bg-white p-6">
                        <h2 className="mb-4 text-lg font-bold">New API Key</h2>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Tenant</label>
                                <select
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                                    value={tenantId}
                                    onChange={(e) => setTenantId(e.target.value)}
                                    required
                                >
                                    <option value="">Select Tenant</option>
                                    {tenants?.map((t: any) => (
                                        <option key={t.tenant_id} value={t.tenant_id}>{t.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Name</label>
                                <input
                                    type="text"
                                    required
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Reason</label>
                                <input
                                    type="text"
                                    required
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                />
                            </div>
                            <div className="flex justify-end space-x-2">
                                <button
                                    type="button"
                                    onClick={() => setIsOpen(false)}
                                    className="rounded-md border bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={createMutation.isPending}
                                    className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
                                >
                                    Create
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
