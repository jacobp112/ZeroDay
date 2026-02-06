import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/api/client';
import { Plus } from 'lucide-react';

export default function Tenants() {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [name, setName] = useState('');
    const [slug, setSlug] = useState('');
    const [orgId, setOrgId] = useState('');

    const { data: tenants, isLoading } = useQuery({
        queryKey: ['tenants'],
        queryFn: async () => (await api.get('/admin/tenants')).data,
    });

    const { data: orgs } = useQuery({
        queryKey: ['organizations'],
        queryFn: async () => (await api.get('/admin/organizations')).data,
    });

    const createMutation = useMutation({
        mutationFn: (newTenant: any) => api.post('/admin/tenants', newTenant),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tenants'] });
            setIsOpen(false);
            setName('');
            setSlug('');
            setOrgId('');
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        createMutation.mutate({ name, slug, organization_id: orgId });
    };

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">Tenants</h1>
                <button
                    onClick={() => setIsOpen(true)}
                    className="flex items-center rounded-md bg-black px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
                >
                    <Plus className="mr-2 h-4 w-4" />
                    New Tenant
                </button>
            </div>

            <div className="overflow-hidden rounded-lg bg-white shadow">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Org ID</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {tenants?.map((tenant: any) => (
                            <tr key={tenant.tenant_id}>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <div className="font-medium text-gray-900">{tenant.name}</div>
                                    <div className="text-xs text-gray-500">{tenant.slug}</div>
                                </td>
                                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{tenant.organization_id}</td>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${tenant.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                        {tenant.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="w-full max-w-md rounded-lg bg-white p-6">
                        <h2 className="mb-4 text-lg font-bold">New Tenant</h2>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Organization</label>
                                <select
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                                    value={orgId}
                                    onChange={(e) => setOrgId(e.target.value)}
                                    required
                                >
                                    <option value="">Select Organization</option>
                                    {orgs?.map((org: any) => (
                                        <option key={org.organization_id} value={org.organization_id}>{org.name}</option>
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
                                <label className="block text-sm font-medium text-gray-700">Slug</label>
                                <input
                                    type="text"
                                    required
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                                    value={slug}
                                    onChange={(e) => setSlug(e.target.value)}
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
