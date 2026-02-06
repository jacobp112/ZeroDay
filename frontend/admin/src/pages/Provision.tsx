import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function Provision() {
    const [orgName, setOrgName] = useState('');
    const [email, setEmail] = useState('');
    const [slug, setSlug] = useState('');
    const [requestId, setRequestId] = useState<string | null>(null);
    const [result, setResult] = useState<any>(null);

    // Auto-generate slug
    useEffect(() => {
        if (!slug && orgName) {
            setSlug(
                orgName
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/(^-|-$)/g, '')
            );
        }
    }, [orgName]);

    // Mutation to start provisioning
    const { mutate: provision, isPending, error } = useMutation({
        mutationFn: async () => {
            const res = await api.post('/admin/provisioning', {
                org_name: orgName,
                admin_email: email,
                org_slug: slug
            });
            return res.data;
        },
        onSuccess: (data) => {
            setRequestId(data.request_id);
        }
    });

    // Validating/Polling Logic
    const { data: statusData, error: pollError } = useQuery({
        queryKey: ['provisioning-status', requestId],
        queryFn: async () => {
            const res = await api.get(`/admin/provisioning/${requestId}`);
            return res.data;
        },
        enabled: !!requestId && !result,
        refetchInterval: (query) => {
            const data = query.state.data;
            if (data && (data.status === 'COMPLETED' || data.status === 'FAILED')) {
                return false;
            }
            return 1000;
        }
    });

    useEffect(() => {
        if (statusData) {
            if (statusData.status === 'COMPLETED') {
                setResult(statusData);
            } else if (statusData.status === 'FAILED') {
                // handled by UI
            }
        }
    }, [statusData]);

    const resetForm = () => {
        setOrgName('');
        setEmail('');
        setSlug('');
        setRequestId(null);
        setResult(null);
    };

    return (
        <div className="max-w-3xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
            <h1 className="text-2xl font-bold mb-6">Provision New Tenant</h1>

            {!requestId && !result && (
                <div className="bg-white shadow sm:rounded-lg p-6">
                    <form onSubmit={(e) => { e.preventDefault(); provision(); }} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Organization Name</label>
                            <input
                                type="text"
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                                value={orgName}
                                onChange={(e) => setOrgName(e.target.value)}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700">Organization Slug</label>
                            <input
                                type="text"
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                                value={slug}
                                onChange={(e) => setSlug(e.target.value)}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700">Admin Email</label>
                            <input
                                type="email"
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>

                        {error && (
                            <div className="rounded-md bg-red-50 p-4">
                                <div className="flex">
                                    <AlertCircle className="h-5 w-5 text-red-400" />
                                    <div className="ml-3 text-sm text-red-700">{error.message}</div>
                                </div>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={isPending}
                            className="inline-flex justify-center rounded-md border border-transparent bg-indigo-600 py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
                        >
                            {isPending ? 'Starting...' : 'Provision Tenant'}
                        </button>
                    </form>
                </div>
            )}

            {requestId && !result && statusData?.status !== 'FAILED' && (
                <div className="bg-white shadow sm:rounded-lg p-12 text-center">
                    <Loader2 className="h-12 w-12 text-indigo-600 mx-auto animate-spin mb-4" />
                    <h3 className="text-lg font-medium">Provisioning in Progress...</h3>
                    <p className="text-gray-500 mt-2">Steps: {statusData?.current_step || 'Initializing'}</p>
                </div>
            )}

            {requestId && statusData?.status === 'FAILED' && (
                <div className="bg-white shadow sm:rounded-lg p-6">
                    <div className="rounded-md bg-red-50 p-4 mb-4">
                        <div className="flex">
                            <AlertCircle className="h-5 w-5 text-red-400" />
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-red-800">Provisioning Failed</h3>
                                <div className="mt-2 text-sm text-red-700">{statusData.error_message}</div>
                            </div>
                        </div>
                    </div>
                    <button onClick={resetForm} className="text-indigo-600 hover:text-indigo-500 font-medium">Try Again</button>
                </div>
            )}

            {result && (
                <div className="bg-white shadow sm:rounded-lg p-6">
                    <div className="rounded-md bg-green-50 p-4 mb-6">
                        <div className="flex">
                            <CheckCircle2 className="h-5 w-5 text-green-400" />
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-green-800">Provisioning Successful</h3>
                            </div>
                        </div>
                    </div>

                    <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
                        <dl className="sm:divide-y sm:divide-gray-200">
                            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
                                <dt className="text-sm font-medium text-gray-500">Organization ID</dt>
                                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{result.result_data.organization_id}</dd>
                            </div>
                            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
                                <dt className="text-sm font-medium text-gray-500">Default Access Key ID</dt>
                                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 font-mono">{result.result_data.access_key_id}</dd>
                            </div>
                            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
                                <dt className="text-sm font-medium text-gray-500">Secret Key</dt>
                                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                                    <span className="text-amber-600 font-medium">Sent via email to {email}</span>
                                    <p className="text-xs text-gray-400 mt-1">(Stored in Pending Notifications if email failed)</p>
                                </dd>
                            </div>
                        </dl>
                    </div>

                    <div className="mt-6">
                        <button onClick={resetForm} className="inline-flex justify-center rounded-md border border-gray-300 bg-white py-2 px-4 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none">
                            Provision Another
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
