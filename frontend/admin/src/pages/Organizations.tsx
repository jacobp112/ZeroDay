import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/api/client';
import { Plus, Trash2 } from 'lucide-react';

export default function Organizations() {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [name, setName] = useState('');
    const [slug, setSlug] = useState('');

    const { data: orgs, isLoading } = useQuery({
        queryKey: ['organizations'],
        queryFn: async () => (await api.get('/admin/organizations')).data,
    });

    const createMutation = useMutation({
        mutationFn: (newOrg: any) => api.post('/admin/organizations', newOrg),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['organizations'] });
            setIsOpen(false);
            setName('');
            setSlug('');
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => api.delete(`/admin/organizations/${id}?reason=AdminDeletion`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['organizations'] });
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        createMutation.mutate({ name, slug });
    };

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">Organizations</h1>
                <button
                    onClick={() => setIsOpen(true)}
                    className="flex items-center rounded-md bg-black px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
                >
                    <Plus className="mr-2 h-4 w-4" />
                    New Organization
                </button>
            </div>

            <div className="overflow-hidden rounded-lg bg-white shadow">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Slug</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                            <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                        {orgs?.map((org: any) => (
                            <tr key={org.organization_id}>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <div className="font-medium text-gray-900">{org.name}</div>
                                    <div className="text-xs text-gray-500">{org.organization_id}</div>
                                </td>
                                <td className="whitespace-nowrap px-6 py-4">{org.slug}</td>
                                <td className="whitespace-nowrap px-6 py-4">
                                    <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${org.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                        {org.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td className="whitespace-nowrap px-6 py-4 text-right">
                                    <button
                                        onClick={() => {
                                            if (confirm('Delete organization?')) deleteMutation.mutate(org.organization_id);
                                        }}
                                        className="text-red-600 hover:text-red-900"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="w-full max-w-md rounded-lg bg-white p-6">
                        <h2 className="mb-4 text-lg font-bold">New Organization</h2>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Name</label>
                                <input
                                    type="text"
                                    required
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Slug</label>
                                <input
                                    type="text"
                                    required
                                    className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
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
                                    className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
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
