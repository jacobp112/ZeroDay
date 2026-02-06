import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

export default function Login() {
    const [accessKey, setAccessKey] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const res = await api.post('/portal/auth/login', {
                access_key_id: accessKey,
                secret_key: secretKey
            });

            login(res.data.access_token);
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-100">
            <div className="w-full max-w-md space-y-8 rounded-lg bg-white p-8 shadow-md">
                <div>
                    <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900">
                        Customer Portal
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Sign in with your API Key credentials
                    </p>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="space-y-4 rounded-md shadow-sm">
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Access Key ID</label>
                            <input
                                type="text"
                                required
                                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                value={accessKey}
                                onChange={(e) => setAccessKey(e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Secret Key</label>
                            <input
                                type="password"
                                required
                                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                value={secretKey}
                                onChange={(e) => setSecretKey(e.target.value)}
                            />
                        </div>
                    </div>

                    {error && <div className="text-sm text-red-500">{error}</div>}

                    <div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="group relative flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
                        >
                            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Sign in
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
