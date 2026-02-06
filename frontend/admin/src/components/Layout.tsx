import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LayoutDashboard, Users, Building, Key, FileText, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function Layout() {
    const { logout, user } = useAuth();
    const location = useLocation();

    const navigation = [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Organizations', href: '/organizations', icon: Building },
        { name: 'Tenants', href: '/tenants', icon: Users },
        { name: 'API Keys', href: '/api-keys', icon: Key },
        { name: 'Audit Log', href: '/audit-log', icon: FileText },
    ];

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <div className="flex w-64 flex-col bg-slate-900 text-white">
                <div className="flex h-16 items-center px-6 text-xl font-bold">
                    ParseFin Admin
                </div>
                <div className="flex flex-1 flex-col overflow-y-auto">
                    <nav className="flex-1 space-y-1 px-2 py-4">
                        {navigation.map((item) => {
                            const isActive = location.pathname.startsWith(item.href);
                            return (
                                <Link
                                    key={item.name}
                                    to={item.href}
                                    className={cn(
                                        isActive ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white',
                                        'group flex items-center rounded-md px-2 py-2 text-sm font-medium'
                                    )}
                                >
                                    <item.icon className="mr-3 h-6 w-6 flex-shrink-0" />
                                    {item.name}
                                </Link>
                            );
                        })}
                    </nav>
                </div>
                <div className="bg-slate-800 p-4">
                    <div className="mb-2 text-sm text-slate-400">{user?.email}</div>
                    <button
                        onClick={logout}
                        className="flex w-full items-center text-sm text-slate-300 hover:text-white"
                    >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign out
                    </button>
                </div>
            </div>

            {/* Main content */}
            <div className="flex flex-1 flex-col overflow-hidden">
                <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
