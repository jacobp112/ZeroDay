import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/api/client';
import { Plus, Trash2, Key, Copy } from 'lucide-react';

export default function Keys() {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [name, setName] = useState('');
    const [newKey, setNewKey] = useState<{ api_key: string, secret_key: string, access_key_id: string } | null>(null);

    const { data: keys, isLoading } = useQuery({
        queryKey: ['keys'],
        queryFn: async () => (await api.get('/portal/keys')).data,
    });

    const createMutation = useMutation({
        mutationFn: (data: any) => api.post('/portal/keys', data),
        onSuccess: (res) => {
            queryClient.invalidateQueries({ queryKey: ['keys'] });
            // Construct full key for display: ak_ACCESS_SECRET (no, format is usually handled by client lib or just Access+Secret)
            // Middleware expects: ak_{access_key_id}_{secret}
            // My python code generated access_key_id and secret separately.
            // And middleware expects: api_key.split("_", 2) -> "ak", access, secret.
            // So the Full Key string is `ak_${res.data.access_key_id}_${res.data.secret_key}`.
            const fullKey = `ak_${res.data.access_key_id}_${res.data.secret_key}`;
            setNewKey({ ...res.data, api_key: fullKey });

            setIsOpen(false);
            setName('');
        },
    });

    const revokeMutation = useMutation({
        mutationFn: (id: string) => api.delete(`/portal/keys/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['keys'] });
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        createMutation.mutate({ name });
    };

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">API Keys</h1>
                <button
                    onClick={() => setIsOpen(true)}
                    className="flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
                >
                    <Plus className="mr-2 h-4 w-4" />
                    Generate New Key
                </button>
            </div>

            {newKey && (
                <div className="rounded-md bg-green-50 p-4 border border-green-200">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <Key className="h-5 w-5 text-green-400" aria-hidden="true" />
                        </div>
                        <div className="ml-3 w-full">
                            <h3 className="text-sm font-medium text-green-800">Key Generated Successfully</h3>
                            <div className="mt-2 text-sm text-green-700">
                                <p>Copy this key now. You will not be able to see it again!</p>
                                <div className="mt-2 flex items-center space-x-2">
                                    <code className="block flex-1 rounded bg-black p-3 text-white break-all">{newKey.api_key}</code>
                                    <button
                                        onClick={() => navigator.clipboard.writeText(newKey.api_key)}
                                        className="p-2 text-gray-500 hover:text-gray-900"
                                        title="Copy"
                                    >
                                        <Copy className="h-5 w-5" />
                                    </button>
                                </div>
                            </div>
                            <div className="mt-4">
                                <button
                                    type="button"
                                    onClick={() => setNewKey(null)}
                                    className="rounded-md bg-green-100 px-2 py-1.5 text-sm font-medium text-green-800 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-offset-2 focus:ring-offset-green-50"
                                >
                                    I have saved it
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
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Created</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                            <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {keys?.map((key: any) => (
                            <tr key={key.key_id}>
                                <td className="whitespace-nowrap px-6 py-4 font-medium text-gray-900">{key.name}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-gray-500 font-mono text-xs">{key.access_key_id}</td>
                                <td className="whitespace-nowrap px-6 py-4 text-gray-500 text-sm">{new Date(key.created_at).toLocaleDateString()}</td>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${key.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                        {key.is_active ? 'Active' : 'Revoked'}
                                    </span>
                                </td>
                                <td className="whitespace-nowrap px-6 py-4 text-right">
                                    {key.is_active && (
                                        <button
                                            onClick={() => {
                                                if (confirm('Revoke this key? APIs using it will stop working immediately.')) revokeMutation.mutate(key.key_id);
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
                        <h2 className="mb-4 text-lg font-bold">Generate New API Key</h2>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Description / Name</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="e.g. Production App, Test Script"
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
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
                                    className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
                                >
                                    Generate
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
